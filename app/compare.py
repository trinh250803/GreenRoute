"""Baseline vs optimised comparison and fuel scenarios (Phụ lục 1 §1, §4)."""
from .emissions import check_compatibility, compute_trip, rnd
from .solver import solve, summarize

METRICS = ["distance_km", "duration_min", "total_cost_vnd", "energy_cost_vnd", "co2_direct_kg",
           "co2_grid_indirect_kg", "co2_per_km", "vehicles_used", "orders_unassigned"]


def pct_change(base, val):
    if base is None or val is None:
        return None
    if base == 0:
        return 0 if val == 0 else None
    return rnd((val - base) / base * 100, 2)


def compare_totals(reference: dict, candidate: dict) -> dict:
    """Side-by-side metrics with % change. Regressions are reported too (mục 6.3)."""
    rows = [{"metric": m, "reference": reference.get(m), "candidate": candidate.get(m),
             "change_pct": pct_change(reference.get(m), candidate.get(m))} for m in METRICS]
    return {"rows": rows,
            "improved": [r["metric"] for r in rows if r["change_pct"] is not None and r["change_pct"] < 0],
            "worse": [r["metric"] for r in rows if r["change_pct"] is not None and r["change_pct"] > 0]}


def apply_overrides(vehicles: list[dict], overrides: dict, cfg: dict):
    errors, out = [], []
    for v in vehicles:
        o = overrides.get(v["vehicle_id"])
        if not o:
            out.append(v)
            continue
        nv = {**v, **o}
        new_fuel = o.get("fuel_blend_code")
        if new_fuel and new_fuel != v["fuel_blend_code"]:
            c = check_compatibility(v["vehicle_type"], new_fuel, cfg, bool(o.get("confirm_simulation_fuel")))
            if not c["ok"]:
                errors.append({"vehicle_id": v["vehicle_id"], "error": c["reason"], "needs_confirmation": bool(c.get("needs_confirmation"))})
            # Switching energy kind without new consumption would silently reuse a rate in the wrong unit.
            old_kind = cfg["fuels"].get(v["fuel_blend_code"], {}).get("kind")
            if o.get("consumption_rate") is None and cfg["fuels"].get(new_fuel, {}).get("kind") != old_kind:
                errors.append({"vehicle_id": v["vehicle_id"], "error": "Đổi loại năng lượng cần nhập mức tiêu hao mới (đơn vị khác)"})
        out.append(nv)
    return out, errors


def run_fuel_scenario(base_result, vehicles, orders, matrix, cfg, overrides, mode, weights=None, time_limit_s=5) -> dict:
    """mode 'same_route' keeps routes (isolates fuel effect); 'reoptimize' re-runs OR-Tools."""
    nv, errors = apply_overrides(vehicles, overrides or {}, cfg)
    if errors:
        return {"ok": False, "errors": errors}
    if mode == "reoptimize":
        result = solve(orders, nv, matrix, cfg, weights, time_limit_s)
    else:
        by_id = {v["vehicle_id"]: v for v in nv}
        routes = [{**r, **compute_trip(r["distance_km"], by_id[r["vehicle_id"]], cfg),
                   "fuel_blend_code": by_id[r["vehicle_id"]]["fuel_blend_code"]} for r in base_result["routes"]]
        result = {"routes": routes, "unassigned": base_result["unassigned"],
                  "totals": summarize(routes, base_result["totals"]["orders_total"], len(base_result["unassigned"])),
                  "meta": {**base_result["meta"], "scenario_mode": "same_route"}}
    reopt = mode == "reoptimize"
    return {
        "ok": True, "mode": "reoptimize" if reopt else "same_route",
        "basis_note": "Kết quả dựa trên tuyến đã tối ưu lại riêng cho kịch bản này." if reopt
        else "Kết quả dựa trên CÙNG tuyến đường — chỉ khác nhiên liệu/cấu hình năng lượng.",
        "result": result, "comparison": compare_totals(base_result["totals"], result["totals"]),
    }
