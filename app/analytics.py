"""Dashboard analytics and order/vehicle detail views, computed from the plan in focus
(the published plan if any, otherwise the latest optimisation run)."""
import re
from collections import Counter, defaultdict

from .dispatch import FAIL_REASONS, drivers_by_vehicle
from .emissions import rnd
from .validation import fmt_time

_DISTRICT = re.compile(r",\s*([^,(]+?)\s*(?:\(|$)")


def district_of(address: str) -> str:
    m = _DISTRICT.search(address or "")
    return m.group(1).strip() if m else "Khác"


def focus_run(db: dict) -> dict | None:
    pid = (db.get("dispatch") or {}).get("run_id")
    return next((r for r in db["runs"] if r["id"] == pid), None) or (db["runs"][0] if db["runs"] else None)


def window_bucket(tw_start) -> str:
    if tw_start is None:
        return "Cả ngày"
    h = tw_start / 60
    return "Sáng (<11h)" if h < 11 else "Trưa (11–14h)" if h < 14 else "Chiều (14–17h)" if h < 17 else "Tối (≥17h)"


def analytics(db: dict) -> dict | None:
    run = focus_run(db)
    if not run:
        return None
    opt, orders = run["optimized"], {o["order_id"]: o for o in run["input"]["orders"]}
    deliveries = run.get("deliveries", {})
    unassigned = {u["order_id"] for u in opt["unassigned"]}
    t = opt["totals"]

    by_vehicle = []
    for r in opt["routes"]:
        ds = [deliveries.get(s["order_id"], {}).get("status", "pending") for s in r["stops"]]
        by_vehicle.append({
            "vehicle_id": r["vehicle_id"], "vehicle_type": r["vehicle_type"], "fuel": r["fuel_blend_code"],
            "stops": len(r["stops"]), "distance_km": r["distance_km"], "duration_min": r["duration_min"],
            "operating_cost_vnd": r["operating_cost_vnd"], "energy_cost_vnd": r["energy_cost_vnd"],
            "co2_fossil_kg": r["co2_fossil_kg"], "co2_biogenic_kg": r["co2_biogenic_kg"], "co2_grid_indirect_kg": r["co2_grid_indirect_kg"],
            "utilization_pct": r["utilization_weight_pct"], "peak_legs": r.get("peak_legs", 0),
            "peak_delay_min": r.get("peak_delay_min", 0), "late_risk": r.get("late_risk", 0),
            "delivered": ds.count("delivered"), "failed": ds.count("failed"),
        })

    by_fuel = defaultdict(lambda: {"vehicles": 0, "distance_km": 0.0, "co2_fossil_kg": 0.0, "co2_biogenic_kg": 0.0,
                                   "co2_grid_indirect_kg": 0.0, "energy_cost_vnd": 0})
    for v in by_vehicle:
        f = by_fuel[v["fuel"]]
        f["vehicles"] += 1
        f["distance_km"] += v["distance_km"]
        f["co2_fossil_kg"] += v["co2_fossil_kg"] or 0
        f["co2_biogenic_kg"] += v["co2_biogenic_kg"] or 0
        f["co2_grid_indirect_kg"] += v["co2_grid_indirect_kg"] or 0
        f["energy_cost_vnd"] += v["energy_cost_vnd"] or 0

    by_district = defaultdict(lambda: {"orders": 0, "weight_kg": 0.0, "unassigned": 0, "delivered": 0, "failed": 0})
    by_window = Counter()
    for oid, o in orders.items():
        d = by_district[district_of(o["address"])]
        d["orders"] += 1
        d["weight_kg"] += o["weight_kg"]
        d["unassigned"] += oid in unassigned
        st = deliveries.get(oid, {}).get("status")
        d["delivered"] += st == "delivered"
        d["failed"] += st == "failed"
        by_window[window_bucket(o["tw_start"])] += 1

    arrivals = Counter()
    peak_arrivals = Counter()
    for r in opt["routes"]:
        for s in r["stops"]:
            h = int(s["arrival"][:2])
            arrivals[h] += 1
            peak_arrivals[h] += bool(s.get("peak"))

    recs = [x for x in deliveries.values() if x.get("status") in ("delivered", "failed")]
    timed = [x for x in recs if x.get("on_time") is not None]
    fail_reasons = Counter(x.get("reason") for x in recs if x["status"] == "failed")
    loc = Counter(x.get("location_check") or "missing" for x in recs)

    weights = [o["weight_kg"] for o in orders.values()]
    return {
        "run": {"id": run["id"], "created_at": run["created_at"], "published": bool(run.get("published_at")), "published_at": run.get("published_at")},
        "totals": t,
        "efficiency": {
            "km_per_order": rnd(t["distance_km"] / t["orders_assigned"], 2) if t["orders_assigned"] else None,
            "stops_per_vehicle": rnd(t["orders_assigned"] / t["vehicles_used"], 1) if t["vehicles_used"] else None,
            "avg_utilization_pct": rnd(sum(v["utilization_pct"] for v in by_vehicle) / len(by_vehicle), 1) if by_vehicle else None,
            "fleet_used_pct": rnd(t["vehicles_used"] / max(1, sum(1 for v in run["input"]["vehicles"] if v["available"])) * 100, 1),
            "avg_parcel_kg": rnd(sum(weights) / len(weights), 2) if weights else None,
            "ev_share_km_pct": rnd(sum(v["distance_km"] for v in by_vehicle if v["fuel"] == "electricity") / t["distance_km"] * 100, 1) if t["distance_km"] else None,
        },
        "comparison": run["comparison"],
        "by_vehicle": by_vehicle,
        "by_fuel": [{"fuel": k, **{kk: rnd(vv, 3) if isinstance(vv, float) else vv for kk, vv in v.items()}} for k, v in sorted(by_fuel.items())],
        "by_district": sorted(({"district": k, **{kk: rnd(vv, 1) if isinstance(vv, float) else vv for kk, vv in v.items()}} for k, v in by_district.items()), key=lambda x: -x["orders"]),
        "by_window": [{"bucket": b, "orders": by_window.get(b, 0)} for b in ("Cả ngày", "Sáng (<11h)", "Trưa (11–14h)", "Chiều (14–17h)", "Tối (≥17h)")],
        "arrivals_by_hour": [{"hour": h, "stops": arrivals.get(h, 0), "peak": peak_arrivals.get(h, 0)} for h in range(6, 21)],
        "deliveries": {
            "done": len(recs), "delivered": sum(1 for x in recs if x["status"] == "delivered"), "failed": len(recs) - sum(1 for x in recs if x["status"] == "delivered"),
            "on_time_pct": rnd(sum(1 for x in timed if x["on_time"]) / len(timed) * 100, 1) if timed else None,
            "fail_reasons": [{"reason": FAIL_REASONS.get(k, k), "count": c} for k, c in fail_reasons.most_common()],
            "location_check": dict(loc),
        },
        "traffic": {"peak_legs": t.get("peak_legs", 0), "peak_delay_min": t.get("peak_delay_min", 0), "late_risk": t.get("late_risk", 0)},
        "unassigned": opt["unassigned"],
    }


def _audit_for(db, key, value, limit=30):
    return [a for a in db.get("audit", []) if isinstance(a.get("detail"), dict) and a["detail"].get(key) == value][:limit]


def order_detail(db: dict, order_id: str) -> dict | None:
    run = focus_run(db)
    order = next((o for o in db["orders"] if o["order_id"] == order_id), None)
    if order is None and run:
        order = next((o for o in run["input"]["orders"] if o["order_id"] == order_id), None)
    if order is None:
        return None
    assignment, unassigned = None, None
    if run:
        for r in run["optimized"]["routes"]:
            for i, s in enumerate(r["stops"]):
                if s["order_id"] == order_id:
                    drv = drivers_by_vehicle(db).get(r["vehicle_id"])
                    assignment = {"vehicle_id": r["vehicle_id"], "vehicle_type": r["vehicle_type"], "fuel": r["fuel_blend_code"],
                                  "sequence": i + 1, "of": len(r["stops"]), **{k: s.get(k) for k in ("arrival", "wait_min", "leg_km", "window", "peak", "peak_delay_min", "est_arrival_peak", "late_risk")},
                                  "driver": drv and {"username": drv["username"], "full_name": drv["full_name"]}}
        unassigned = next((u for u in run["optimized"]["unassigned"] if u["order_id"] == order_id), None)
    return {
        "order": {**order, "window": f'{fmt_time(order["tw_start"])}–{fmt_time(order["tw_end"])}' if order["tw_start"] is not None or order["tw_end"] is not None else "",
                  "district": district_of(order["address"])},
        "run": run and {"id": run["id"], "created_at": run["created_at"], "published_at": run.get("published_at")},
        "assignment": assignment, "unassigned": unassigned,
        "delivery": (run or {}).get("deliveries", {}).get(order_id),
        "history": _audit_for(db, "order_id", order_id),
    }


def vehicle_detail(db: dict, vehicle_id: str) -> dict | None:
    v = next((x for x in db["vehicles"] if x["vehicle_id"] == vehicle_id), None)
    if v is None:
        return None
    run = focus_run(db)
    route = next((r for r in run["optimized"]["routes"] if r["vehicle_id"] == vehicle_id), None) if run else None
    deliveries = (run or {}).get("deliveries", {})
    drv = drivers_by_vehicle(db).get(vehicle_id)
    tr = db.get("tracking", {}).get(vehicle_id, {})
    return {
        "vehicle": {**v, "start": fmt_time(v["start_time"]), "end": fmt_time(v["end_time"])},
        "driver": drv and {"username": drv["username"], "full_name": drv["full_name"], "last_login_at": drv.get("last_login_at")},
        "route": route and {**{k: route.get(k) for k in ("distance_km", "duration_min", "start", "end", "load_weight_kg", "utilization_weight_pct",
                                                        "operating_cost_vnd", "energy_cost_vnd", "energy_amount", "energy_unit", "co2_fossil_kg",
                                                        "co2_biogenic_kg", "co2_grid_indirect_kg", "factor", "peak_legs", "peak_delay_min", "late_risk")},
                            "stops": [{**s, **{k: deliveries.get(s["order_id"], {}).get(k) for k in ("status", "location_check")}} for s in route["stops"]]},
        "tracking": {"sharing": bool(tr.get("sharing")), "last": tr.get("last"), "points": len(tr.get("points", []))},
        "history": _audit_for(db, "vehicle_id", vehicle_id),
    }
