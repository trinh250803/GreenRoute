"""Heterogeneous-fleet CVRPTW solved with Google OR-Tools (mục 6).

Node 0 = depot, order i = node i+1. Hard constraints: weight and volume capacity,
delivery time windows, vehicle shift, availability. Orders that cannot be served are
dropped through disjunctions and always reported with a reason (never silently).

Objective per used vehicle (VND; weights need business approval — mục 6.2):
  km × (cost_per_km + energy_cost_per_km + co2_vnd_per_kg × co2_per_km)
  + fixed_cost + time_vnd_per_min × route duration
"""
import math
import time

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .emissions import compute_trip, num, resolve_factor, rnd
from .validation import fmt_time

DEFAULT_WEIGHTS = {"co2_vnd_per_kg": 0.0, "time_vnd_per_min": 0.0}
COST_SCALE = 100            # OR-Tools needs integers: costs in 1/100 VND
HORIZON_S = 24 * 3600
INF_ARC = 10**12
DROP_PENALTY = 10**11       # far above any route cost, so orders are dropped only when infeasible

STATUS = {0: "NOT_SOLVED", 1: "SUCCESS", 2: "PARTIAL_SUCCESS_LOCAL_OPTIMUM_NOT_REACHED", 3: "FAIL",
          4: "FAIL_TIMEOUT", 5: "INVALID", 6: "INFEASIBLE", 7: "OPTIMAL"}


def prepare_vehicles(vehicles: list[dict], cfg: dict, weights: dict) -> list[dict]:
    out = []
    for v in vehicles:
        if not v["available"]:
            continue
        fuel = cfg["fuels"].get(v["fuel_blend_code"])
        rate = num(v.get("consumption_rate")) or 0.0
        price = num(v.get("fuel_price"))
        if price is None:
            price = fuel["price_vnd"] if fuel else 0.0
        f = resolve_factor(v["fuel_blend_code"], cfg, v)
        co2_per_km = 0.0 if fuel and fuel["kind"] == "electric" else rate / 100 * (f["value"] or 0.0)
        per_km = v["cost_per_km"] + rate / 100 * price + weights["co2_vnd_per_kg"] * co2_per_km
        out.append({**v, "_per_km": per_km})
    return out


class Problem:
    """Shared, integer-second model of the instance so OR-Tools and the checker agree exactly."""

    def __init__(self, orders, matrix, weights):
        self.orders, self.matrix, self.weights = orders, matrix, weights
        self.service_s = [0] + [int(round(o["service_time_min"] * 60)) for o in orders]
        self._travel = {}

    def travel_s(self, speed_kmh: float) -> list[list[int]]:
        if speed_kmh not in self._travel:
            self._travel[speed_kmh] = [[int(round(d / speed_kmh * 3600)) if math.isfinite(d) else HORIZON_S * 10 for d in row]
                                       for row in self.matrix]
        return self._travel[speed_kmh]

    def evaluate(self, v: dict, seq: list[int]):
        """Simulate a route (depart at shift start, wait if early). None if infeasible."""
        orders = self.orders
        w = sum(orders[i]["weight_kg"] for i in seq)
        vol = sum(orders[i]["volume_m3"] for i in seq)
        # Integer grams / cm³, identical to the OR-Tools dimensions.
        if sum(int(round(orders[i]["weight_kg"] * 1000)) for i in seq) > int(v["capacity_weight_kg"] * 1000):
            return None
        if v.get("capacity_volume_m3") is not None and \
                sum(int(round(orders[i]["volume_m3"] * 1_000_000)) for i in seq) > int(v["capacity_volume_m3"] * 1_000_000):
            return None
        tt = self.travel_s(v["speed_kmh"])
        t = int(v["start_time"] * 60)
        prev, km, stops = 0, 0.0, []
        for i in seq:
            d = self.matrix[prev][i + 1]
            if not math.isfinite(d):
                return None
            km += d
            t += tt[prev][i + 1]
            o = orders[i]
            wait = 0
            if o["tw_start"] is not None and t < o["tw_start"] * 60:
                wait = int(o["tw_start"] * 60) - t
                t += wait
            if o["tw_end"] is not None and t > o["tw_end"] * 60:
                return None
            stops.append((i, d, t, wait))
            t += self.service_s[i + 1]
            prev = i + 1
        back = self.matrix[prev][0]
        if not math.isfinite(back):
            return None
        km += back
        t += tt[prev][0]
        if t > v["end_time"] * 60:
            return None
        duration_min = (t - v["start_time"] * 60) / 60
        cost = km * v["_per_km"] + v["fixed_cost_vnd"] + self.weights["time_vnd_per_min"] * duration_min if seq else 0.0
        return {"km": km, "cost": cost, "end_min": t / 60, "duration_min": duration_min, "weight": w, "volume": vol, "stops": stops}


def solve(orders, vehicles, matrix, cfg, weights=None, time_limit_s: float = 5) -> dict:
    W = {**DEFAULT_WEIGHTS, **(weights or {})}
    W = {k: float(num(v) or 0) for k, v in W.items()}
    t0 = time.perf_counter()
    vs = prepare_vehicles(vehicles, cfg, W)
    prob = Problem(orders, matrix, W)
    n = len(orders)
    routes = [[] for _ in vs]
    status = "NO_VEHICLE"

    if vs and n:
        manager = pywrapcp.RoutingIndexManager(n + 1, len(vs), 0)
        routing = pywrapcp.RoutingModel(manager)
        node = manager.IndexToNode

        # Arc cost per vehicle (heterogeneous fleet), shared across vehicles with identical per-km cost.
        cost_cb = {}
        for vi, v in enumerate(vs):
            key = round(v["_per_km"], 6)
            if key not in cost_cb:
                cm = [[int(round(d * v["_per_km"] * COST_SCALE)) if math.isfinite(d) else INF_ARC for d in row] for row in matrix]
                cost_cb[key] = routing.RegisterTransitCallback(lambda a, b, cm=cm: cm[node(a)][node(b)])
            routing.SetArcCostEvaluatorOfVehicle(cost_cb[key], vi)
            routing.SetFixedCostOfVehicle(int(round(v["fixed_cost_vnd"] * COST_SCALE)), vi)

        # Capacity: weight in grams, volume in cm³ (integers).
        wd = [0] + [int(round(o["weight_kg"] * 1000)) for o in orders]
        vd = [0] + [int(round(o["volume_m3"] * 1_000_000)) for o in orders]
        w_cb = routing.RegisterUnaryTransitCallback(lambda a: wd[node(a)])
        v_cb = routing.RegisterUnaryTransitCallback(lambda a: vd[node(a)])
        routing.AddDimensionWithVehicleCapacity(w_cb, 0, [int(v["capacity_weight_kg"] * 1000) for v in vs], True, "Weight")
        routing.AddDimensionWithVehicleCapacity(
            v_cb, 0, [int(v["capacity_volume_m3"] * 1_000_000) if v.get("capacity_volume_m3") is not None else 10**15 for v in vs],
            True, "Volume")

        # Time: service at origin + travel at the vehicle's speed; slack = waiting.
        time_cbs = {}
        for v in vs:
            if v["speed_kmh"] not in time_cbs:
                tt = prob.travel_s(v["speed_kmh"])
                time_cbs[v["speed_kmh"]] = routing.RegisterTransitCallback(
                    lambda a, b, tt=tt: prob.service_s[node(a)] + tt[node(a)][node(b)])
        routing.AddDimensionWithVehicleTransits([time_cbs[v["speed_kmh"]] for v in vs], HORIZON_S, HORIZON_S, False, "Time")
        td = routing.GetDimensionOrDie("Time")
        for i, o in enumerate(orders):
            lo = int(o["tw_start"] * 60) if o["tw_start"] is not None else 0
            hi = int(o["tw_end"] * 60) if o["tw_end"] is not None else HORIZON_S
            td.CumulVar(manager.NodeToIndex(i + 1)).SetRange(lo, hi)
            # Priority orders are costlier to drop.
            routing.AddDisjunction([manager.NodeToIndex(i + 1)], DROP_PENALTY * (1 + int(o["priority"])))
        span_coef = int(round(W["time_vnd_per_min"] * COST_SCALE / 60))
        for vi, v in enumerate(vs):
            st, et = int(v["start_time"] * 60), int(v["end_time"] * 60)
            td.CumulVar(routing.Start(vi)).SetRange(st, st)
            td.CumulVar(routing.End(vi)).SetRange(st, et)
            if span_coef:
                td.SetSpanCostCoefficientForVehicle(span_coef, vi)

        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        params.time_limit.FromMilliseconds(int(max(time_limit_s, 0.5) * 1000))

        solution = routing.SolveWithParameters(params)
        status = STATUS.get(routing.status(), str(routing.status()))
        if solution:
            for vi in range(len(vs)):
                idx = solution.Value(routing.NextVar(routing.Start(vi)))
                while not routing.IsEnd(idx):
                    routes[vi].append(node(idx) - 1)
                    idx = solution.Value(routing.NextVar(idx))

    # Independent re-check of every route with the shared model.
    for vi, seq in enumerate(routes):
        if seq and prob.evaluate(vs[vi], seq) is None:
            raise RuntimeError(f"OR-Tools trả về tuyến không hợp lệ cho xe {vs[vi]['vehicle_id']}")

    served = {i for seq in routes for i in seq}
    pending = [i for i in range(n) if i not in served]
    objective = sum(prob.evaluate(vs[vi], seq)["cost"] for vi, seq in enumerate(routes))
    return build_result(routes, vs, prob, cfg, pending, vehicles, {
        "algorithm": "Google OR-Tools RoutingModel: PARALLEL_CHEAPEST_INSERTION + GUIDED_LOCAL_SEARCH",
        "time_ms": round((time.perf_counter() - t0) * 1000), "status": status,
        "time_limit_s": time_limit_s, "weights": W, "objective_vnd": round(objective),
    })


def unassigned_reason(o: dict, oi: int, vehicles: list[dict], prob: Problem) -> dict:
    avail = [v for v in vehicles if v["available"]]
    if not avail:
        return {"code": "NO_VEHICLE", "message": "Không có xe sẵn sàng"}
    if not any(o["weight_kg"] <= v["capacity_weight_kg"] and (v.get("capacity_volume_m3") is None or o["volume_m3"] <= v["capacity_volume_m3"]) for v in avail):
        return {"code": "EXCEEDS_CAPACITY", "message": f'Đơn {o["weight_kg"]:g} kg / {o["volume_m3"]:g} m³ vượt sức chứa mọi xe'}
    if not any(prob.evaluate({**v, "_per_km": 0, "fixed_cost_vnd": 0}, [oi]) for v in avail):
        return {"code": "TIME_WINDOW_INFEASIBLE", "message": "Không xe nào đến kịp khung giờ / quay về kho trong ca, kể cả khi giao riêng"}
    return {"code": "FLEET_CAPACITY_EXHAUSTED", "message": "Đội xe hết tải trọng/thời gian — cần thêm xe hoặc nới khung giờ"}


def build_result(routes, vs, prob: Problem, cfg, pending, vehicles, meta) -> dict:
    orders = prob.orders
    out_routes = []
    for vi, seq in enumerate(routes):
        if not seq:
            continue
        v = vs[vi]
        ev = prob.evaluate(v, seq)
        stops = []
        for i, leg_km, t_s, wait_s in ev["stops"]:
            o = orders[i]
            has_tw = o["tw_start"] is not None or o["tw_end"] is not None
            stops.append({"order_id": o["order_id"], "latitude": o["latitude"], "longitude": o["longitude"], "leg_km": rnd(leg_km, 3),
                          "arrival": fmt_time(t_s / 60), "wait_min": rnd(wait_s / 60, 1),
                          "window": f'{fmt_time(o["tw_start"])}–{fmt_time(o["tw_end"])}' if has_tw else ""})
        trip = compute_trip(ev["km"], v, cfg)
        out_routes.append({
            "vehicle_id": v["vehicle_id"], "vehicle_type": v["vehicle_type"], "fuel_blend_code": v["fuel_blend_code"],
            "stops": stops, "duration_min": rnd(ev["duration_min"], 1),
            "start": fmt_time(v["start_time"]), "end": fmt_time(ev["end_min"]),
            "load_weight_kg": rnd(ev["weight"], 2), "capacity_weight_kg": v["capacity_weight_kg"],
            "load_volume_m3": rnd(ev["volume"], 3), "capacity_volume_m3": v.get("capacity_volume_m3"),
            "utilization_weight_pct": rnd(ev["weight"] / v["capacity_weight_kg"] * 100, 1),
            "operating_cost_vnd": round(ev["km"] * v["cost_per_km"] + v["fixed_cost_vnd"]),
            **trip, "distance_km": rnd(ev["km"], 3),
        })
    unassigned = [{"order_id": orders[i]["order_id"], **unassigned_reason(orders[i], i, vehicles, prob)} for i in pending]
    return {"routes": out_routes, "unassigned": unassigned, "totals": summarize(out_routes, len(orders), len(unassigned)), "meta": meta}


def _sum(routes, key):
    total = 0.0
    for r in routes:
        if r.get(key) is None:
            return None
        total += r[key]
    return total


def summarize(routes: list[dict], n_orders: int, n_unassigned: int) -> dict:
    km, co2 = _sum(routes, "distance_km"), _sum(routes, "co2_direct_kg")
    energy, op = _sum(routes, "energy_cost_vnd"), _sum(routes, "operating_cost_vnd")
    assigned = n_orders - n_unassigned
    warnings = list(dict.fromkeys(w for r in routes for w in r["warnings"]))
    return {
        "orders_total": n_orders, "orders_assigned": assigned, "orders_unassigned": n_unassigned,
        "assignment_rate_pct": rnd(assigned / n_orders * 100, 1) if n_orders else 0,
        "vehicles_used": len(routes),
        "distance_km": rnd(km, 2), "duration_min": rnd(_sum(routes, "duration_min"), 1),
        "operating_cost_vnd": None if op is None else round(op),
        "energy_cost_vnd": None if energy is None else round(energy),
        "total_cost_vnd": None if energy is None else round(op + energy),
        "co2_direct_kg": rnd(co2, 3), "co2_fossil_kg": rnd(_sum(routes, "co2_fossil_kg"), 3),
        "co2_biogenic_kg": rnd(_sum(routes, "co2_biogenic_kg"), 3),
        "co2_grid_indirect_kg": rnd(_sum(routes, "co2_grid_indirect_kg"), 3),
        "co2_per_km": rnd(co2 / km, 4) if co2 is not None and km else None,
        "co2_per_order": rnd(co2 / assigned, 4) if co2 is not None and assigned else None,
        "cost_per_order_vnd": round((op + energy) / assigned) if energy is not None and assigned else None,
        "warnings": warnings,
    }


def baseline(orders, vehicles, matrix, cfg) -> dict:
    """Baseline (mục 6.3), defined explicitly — "first fit in input order": take orders in
    input sequence and append each to the first vehicle (in fleet list order) that can still
    take it at the end of its route. No reordering. Same orders, fleet, matrix and constraints
    as the optimiser."""
    t0 = time.perf_counter()
    vs = prepare_vehicles(vehicles, cfg, DEFAULT_WEIGHTS)
    prob = Problem(orders, matrix, DEFAULT_WEIGHTS)
    routes = [[] for _ in vs]
    pending = []
    for oi in range(len(orders)):
        for k in range(len(vs)):
            if prob.evaluate(vs[k], routes[k] + [oi]):
                routes[k].append(oi)
                break
        else:
            pending.append(oi)
    return build_result(routes, vs, prob, cfg, pending, vehicles, {
        "algorithm": "baseline: thứ tự đơn gốc, xếp vào xe đầu tiên còn chỗ (first-fit)",
        "time_ms": round((time.perf_counter() - t0) * 1000), "status": "BASELINE",
    })
