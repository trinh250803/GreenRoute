"""Independent re-calculation of an optimisation run, straight from the handover formulas.

Nothing here imports app code: distances, times, fuel, CO₂ and costs are recomputed from
the raw orders/vehicles stored in the run plus the fuel config, then compared with what the
API (and therefore the UI) reports.

    python scripts/verify_formulas.py                      # local server, latest run
    python scripts/verify_formulas.py https://greenroute-ai-mewj.onrender.com
    python scripts/verify_formulas.py <url> --new-run      # run a fresh optimisation first

Formulas checked (Phụ lục 1 §3, Phụ lục 2 §1–2, mục 6):
  km              = Σ haversine(chặng) × detour_factor, kho → điểm giao … → kho
  nhiên liệu (L)  = km × tiêu hao (L/100km) / 100        | điện (kWh) tương tự
  EF pha ethanol  = (1 − x)·EF_xăng + x·EF_ethanol
  CO₂ trực tiếp   = L × EF  (xe điện: 0; gián tiếp lưới = kWh × EF_lưới, báo riêng)
  chi phí NL      = L (kWh) × giá
  chi phí vận hành= km × cost_per_km + chi phí cố định
  tổng chi phí    = vận hành + năng lượng;  CO₂/km = CO₂ / km;  /đơn = ÷ số đơn đã giao
  % thay đổi      = (tối ưu − baseline) / baseline × 100
"""
import json
import math
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- reference formulas
def haversine_km(lat1, lng1, lat2, lng2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lng2 - lng1) * p / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def emission_factor(code, cfg, vehicle):
    """kg CO₂ per L/kWh, or None when the config gives no trustworthy factor."""
    if vehicle.get("emission_factor_value") not in (None, ""):
        return float(vehicle["emission_factor_value"])
    fuel, base = cfg["fuels"][code], cfg["base_factors"]
    if fuel.get("factor_key"):
        return base[fuel["factor_key"]]["value"]
    if fuel["status"] == "unverified":
        return None
    x = fuel["ethanol_share_volume"]
    return (1 - x) * base["gasoline"]["value"] + x * base["ethanol"]["value"]


def hhmm(minutes):
    return f"{int(minutes // 60):02d}:{int(round(minutes % 60)):02d}"


def close(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


class Checker:
    def __init__(self):
        self.rows = []  # (group, check, ok, detail)

    def add(self, group, check, ok, detail=""):
        self.rows.append((group, check, bool(ok), detail))

    @property
    def failed(self):
        return [r for r in self.rows if not r[2]]


def recompute_route(route, run, cfg):
    """Everything the handover formulas say about one vehicle's route."""
    orders = {o["order_id"]: o for o in run["input"]["orders"]}
    v = next(x for x in run["input"]["vehicles"] if x["vehicle_id"] == route["vehicle_id"])
    depot, k = run["depot"], cfg["routing"]["detour_factor"]
    pts = [(depot["latitude"], depot["longitude"])] + [(orders[s["order_id"]]["latitude"], orders[s["order_id"]]["longitude"]) for s in route["stops"]]
    pts.append(pts[0])
    legs = [haversine_km(*pts[i], *pts[i + 1]) * k for i in range(len(pts) - 1)]
    km = sum(legs)

    # Time: depart at shift start, drive at the vehicle's speed, wait if early, serve.
    t, arrivals = v["start_time"], []
    for s, leg in zip(route["stops"], legs):
        o = orders[s["order_id"]]
        t += leg / v["speed_kmh"] * 60
        if o["tw_start"] is not None and t < o["tw_start"]:
            t = o["tw_start"]
        arrivals.append(t)
        t += o["service_time_min"]
    t += legs[-1] / v["speed_kmh"] * 60

    fuel = cfg["fuels"][v["fuel_blend_code"]]
    rate = v.get("consumption_rate")
    amount = None if rate is None else km * rate / 100
    price = v.get("fuel_price") if v.get("fuel_price") is not None else fuel.get("price_vnd")
    ef = emission_factor(v["fuel_blend_code"], cfg, v)
    electric = fuel["kind"] == "electric"
    co2 = grid = None
    if amount is not None and ef is not None:
        co2, grid = (0.0, amount * ef) if electric else (amount * ef, 0.0)
    return {
        "vehicle": v, "legs": legs, "km": km, "arrivals": arrivals, "end": t, "duration": t - v["start_time"],
        "weight": sum(orders[s["order_id"]]["weight_kg"] for s in route["stops"]),
        "volume": sum(orders[s["order_id"]]["volume_m3"] for s in route["stops"]),
        "rate": rate, "amount": amount, "unit": "kWh" if electric else "L", "price": price, "ef": ef,
        "energy_cost": None if amount is None or price is None else amount * price,
        "co2": co2, "grid": grid, "operating": km * v["cost_per_km"] + v["fixed_cost_vnd"],
    }


def check_plan(c, name, plan, run, cfg):
    all_ids = [o["order_id"] for o in run["input"]["orders"]]
    orders = {o["order_id"]: o for o in run["input"]["orders"]}
    served = [s["order_id"] for r in plan["routes"] for s in r["stops"]]
    dropped = [u["order_id"] for u in plan["unassigned"]]
    c.add(name, "Mỗi đơn được giao đúng 1 lần, không trùng", len(served) == len(set(served)), f"{len(served)} điểm dừng")
    c.add(name, "Đơn đã giao + đơn chưa phân công = tổng đơn (không bỏ sót âm thầm)",
          sorted(served + dropped) == sorted(all_ids), f"{len(served)} + {len(dropped)} = {len(all_ids)}")
    c.add(name, "Mọi đơn chưa phân công đều có lý do", all(u.get("message") for u in plan["unassigned"]))

    sums = {"km": 0.0, "duration": 0.0, "energy": 0.0, "operating": 0.0, "co2": 0.0, "grid": 0.0}
    missing_energy = missing_co2 = False
    for r in plan["routes"]:
        x, vid, v = recompute_route(r, run, cfg), r["vehicle_id"], None
        v = x["vehicle"]
        g = f"{name} · {vid}"
        c.add(g, "Quãng đường (km) = Σ chặng × hệ số đường vòng", close(r["distance_km"], x["km"], 0.002), f'app {r["distance_km"]} / tính lại {x["km"]:.3f}')
        c.add(g, "Từng chặng (leg_km)", all(close(s["leg_km"], l, 0.002) for s, l in zip(r["stops"], x["legs"])))
        c.add(g, "Tải trọng ≤ sức chứa", x["weight"] <= v["capacity_weight_kg"] + 1e-9, f'{x["weight"]:.2f} / {v["capacity_weight_kg"]} kg')
        if v.get("capacity_volume_m3") is not None:
            c.add(g, "Thể tích ≤ sức chứa", x["volume"] <= v["capacity_volume_m3"] + 1e-9, f'{x["volume"]:.3f} / {v["capacity_volume_m3"]} m³')
        late = [s["order_id"] for s, t in zip(r["stops"], x["arrivals"])
                if orders[s["order_id"]]["tw_end"] is not None and t > orders[s["order_id"]]["tw_end"] + 1]
        c.add(g, "Đến trong khung giờ giao", not late, f"trễ: {', '.join(late)}" if late else "")
        c.add(g, "Giờ đến hiển thị khớp tính lại (±1 phút)",
              all(abs(int(s["arrival"][:2]) * 60 + int(s["arrival"][3:]) - t) <= 1.01 for s, t in zip(r["stops"], x["arrivals"])))
        c.add(g, "Về kho trong ca làm việc", x["end"] <= v["end_time"] + 1, f'về {hhmm(x["end"])}, hết ca {hhmm(v["end_time"])}')
        c.add(g, "Thời gian tuyến (phút)", close(r["duration_min"], x["duration"], 1.0), f'app {r["duration_min"]} / tính lại {x["duration"]:.1f}')
        c.add(g, f'Năng lượng ({x["unit"]}) = km × tiêu hao / 100', close(r["energy_amount"], x["amount"], 1e-3),
              f'app {r["energy_amount"]} / tính lại {x["amount"] if x["amount"] is None else round(x["amount"], 4)}')
        c.add(g, "Chi phí năng lượng = lượng × giá", close(r["energy_cost_vnd"], x["energy_cost"], 1.0),
              f'app {r["energy_cost_vnd"]} / tính lại {x["energy_cost"] if x["energy_cost"] is None else round(x["energy_cost"])}')
        c.add(g, "CO₂ trực tiếp = lượng × EF (xe điện = 0)", close(r["co2_direct_kg"], x["co2"], 1e-3),
              f'app {r["co2_direct_kg"]} / tính lại {x["co2"] if x["co2"] is None else round(x["co2"], 4)}')
        c.add(g, "CO₂ gián tiếp lưới điện (báo riêng)", close(r["co2_grid_indirect_kg"], x["grid"], 1e-3))
        if r.get("co2_fossil_kg") is not None and r["co2_direct_kg"]:
            c.add(g, "CO₂ hóa thạch + sinh học = CO₂ trực tiếp", close(r["co2_fossil_kg"] + r["co2_biogenic_kg"], r["co2_direct_kg"], 1e-3))
        c.add(g, "Chi phí vận hành = km × cost_per_km + cố định", close(r["operating_cost_vnd"], x["operating"], 1.0),
              f'app {r["operating_cost_vnd"]} / tính lại {round(x["operating"])}')
        sums["km"] += x["km"]; sums["duration"] += x["duration"]; sums["operating"] += x["operating"]
        if x["energy_cost"] is None:
            missing_energy = True
        else:
            sums["energy"] += x["energy_cost"]
        if x["co2"] is None:
            missing_co2 = True
        else:
            sums["co2"] += x["co2"]; sums["grid"] += x["grid"]

    t, assigned = plan["totals"], len(served)
    total_cost = None if missing_energy else sums["operating"] + sums["energy"]
    co2 = None if missing_co2 else sums["co2"]
    g = f"{name} · TỔNG"
    c.add(g, "Tổng km", close(t["distance_km"], sums["km"], 0.01), f'app {t["distance_km"]} / tính lại {sums["km"]:.2f}')
    c.add(g, "Số xe dùng", t["vehicles_used"] == len(plan["routes"]))
    c.add(g, "Số đơn giao / chưa giao", t["orders_assigned"] == assigned and t["orders_unassigned"] == len(plan["unassigned"]))
    c.add(g, "Chi phí năng lượng", close(t["energy_cost_vnd"], None if missing_energy else sums["energy"], len(plan["routes"]) + 1))
    c.add(g, "Tổng chi phí = vận hành + năng lượng", close(t["total_cost_vnd"], total_cost, len(plan["routes"]) * 2 + 1),
          f'app {t["total_cost_vnd"]} / tính lại {total_cost if total_cost is None else round(total_cost)}')
    c.add(g, "Tổng CO₂ trực tiếp", close(t["co2_direct_kg"], co2, 0.005), f'app {t["co2_direct_kg"]} / tính lại {co2 if co2 is None else round(co2, 3)}')
    c.add(g, "CO₂ gián tiếp lưới điện", close(t["co2_grid_indirect_kg"], None if missing_co2 else sums["grid"], 0.005))
    c.add(g, "CO₂/km = CO₂ ÷ km", close(t["co2_per_km"], None if co2 is None else co2 / sums["km"], 1e-3))
    c.add(g, "CO₂/đơn = CO₂ ÷ số đơn đã giao", close(t["co2_per_order"], None if co2 is None or not assigned else co2 / assigned, 1e-3))
    c.add(g, "Chi phí/đơn = tổng chi phí ÷ số đơn đã giao",
          close(t["cost_per_order_vnd"], None if total_cost is None or not assigned else total_cost / assigned, 1.0))


def check_comparison(c, comparison, ref, cand, label):
    for row in comparison["rows"]:
        a, b = ref.get(row["metric"]), cand.get(row["metric"])
        exp = None if a is None or b is None or a == 0 else (b - a) / a * 100
        if a == 0 and b == 0:
            exp = 0
        c.add(label, f'% thay đổi {row["metric"]} = (mới − gốc) / gốc × 100', close(row["change_pct"], exp, 0.01),
              f'{a} → {b}: app {row["change_pct"]}% / tính lại {exp if exp is None else round(exp, 2)}%')


def check_run(run, cfg):
    c = Checker()
    check_plan(c, "Tối ưu", run["optimized"], run, cfg)
    check_plan(c, "Baseline", run["baseline"], run, cfg)
    check_comparison(c, run["comparison"], run["baseline"]["totals"], run["optimized"]["totals"], "So sánh baseline → tối ưu")
    return c


def worked_example(run, cfg):
    """One vehicle, every step, so a tester can redo it with a calculator."""
    r = next((r for r in run["optimized"]["routes"] if cfg["fuels"][r["fuel_blend_code"]]["kind"] == "liquid"), run["optimized"]["routes"][0])
    x = recompute_route(r, run, cfg)
    v, f = x["vehicle"], cfg["fuels"][r["fuel_blend_code"]]
    lines = [f'Xe {v["vehicle_id"]} ({v["vehicle_type"]}, {r["fuel_blend_code"]}), {len(r["stops"])} điểm giao']
    lines.append(f'  km = Σ chặng × {cfg["routing"]["detour_factor"]} = {x["km"]:.3f} km   (app: {r["distance_km"]})')
    if f["kind"] == "liquid" and not f.get("factor_key") and x["ef"] is not None:
        b = cfg["base_factors"]; xs = f["ethanol_share_volume"]
        lines.append(f'  EF = (1 − {xs})×{b["gasoline"]["value"]} + {xs}×{b["ethanol"]["value"]} = {x["ef"]:.4f} kg CO₂/L')
    else:
        lines.append(f'  EF = {x["ef"]} kg CO₂/{x["unit"]}')
    if x["amount"] is not None:
        lines.append(f'  Nhiên liệu = {x["km"]:.3f} × {x["rate"]} / 100 = {x["amount"]:.4f} {x["unit"]}   (app: {r["energy_amount"]})')
        if x["co2"] is not None:
            lines.append(f'  CO₂ = {x["amount"]:.4f} × {x["ef"]:.4f} = {x["co2"]:.4f} kg   (app: {r["co2_direct_kg"]})')
        if x["price"] is not None:
            lines.append(f'  Chi phí NL = {x["amount"]:.4f} × {x["price"]:,} = {x["energy_cost"]:,.0f} ₫   (app: {r["energy_cost_vnd"]:,})')
    lines.append(f'  Vận hành = {x["km"]:.3f} × {v["cost_per_km"]:,} + {v["fixed_cost_vnd"]:,} = {x["operating"]:,.0f} ₫   (app: {r["operating_cost_vnd"]:,})')
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI against a server
def _call(base, method, path, token=None, body=None):
    req = urllib.request.Request(base + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=120) as res:
        return json.load(res)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    base = (args[0] if args else "http://127.0.0.1:8000").rstrip("/")
    pw = dict(re.findall(r"^\|[^|]*\| `([^`]+)` \| `([^`]+)` \|", (ROOT / "TEST_ACCOUNTS.md").read_text(encoding="utf-8"), re.M))
    token = _call(base, "POST", "/api/auth/login", body={"username": "dieuphoi01", "password": pw["dieuphoi01"]})["token"]
    runs = _call(base, "GET", "/api/optimization", token)
    if "--new-run" in sys.argv or not runs:
        run = _call(base, "POST", "/api/optimization/run", token, {"time_limit_s": 5, "label": "verify_formulas"})
    else:
        run = _call(base, "GET", f'/api/optimization/{runs[0]["id"]}', token)
    cfg = _call(base, "GET", "/api/config", token)
    c = check_run(run, cfg)
    print(f'Run {run["id"]} — {run["created_at"]} — {len(run["input"]["orders"])} đơn, {len(run["input"]["vehicles"])} xe')
    print(worked_example(run, cfg), "\n")
    for group, check, ok, detail in c.rows:
        if not ok or "TỔNG" in group or group.startswith("So sánh"):
            print(f'{"PASS" if ok else "FAIL"}  {group:28} {check:55} {detail}')
    print(f"\n{len(c.rows) - len(c.failed)}/{len(c.rows)} kiểm tra đạt")
    sys.exit(1 if c.failed else 0)


if __name__ == "__main__":
    main()
