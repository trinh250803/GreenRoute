import json
from pathlib import Path

import pytest

from app.compare import run_fuel_scenario
from app.distance import haversine_matrix
from app.emissions import check_compatibility, compute_trip, load_fuel_config, resolve_factor
from app.io_files import parse_csv
from app.solver import baseline, solve
from app.validation import validate_orders, validate_vehicles

CFG = load_fuel_config()
SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"


@pytest.fixture(scope="module")
def problem():
    depot = json.loads((SAMPLE / "depot.json").read_text(encoding="utf-8"))
    orders = validate_orders(parse_csv((SAMPLE / "orders.csv").read_text(encoding="utf-8")))["valid"]
    vehicles = validate_vehicles(parse_csv((SAMPLE / "vehicles.csv").read_text(encoding="utf-8")), CFG)["valid"]
    matrix = haversine_matrix([depot, *orders], CFG)["matrix"]
    return {"orders": orders, "vehicles": vehicles, "matrix": matrix}


@pytest.fixture(scope="module")
def optimized(problem):
    return solve(problem["orders"], problem["vehicles"], problem["matrix"], CFG, time_limit_s=3)


def test_fuel_formulas():
    t = compute_trip(100, {"vehicle_id": "X", "fuel_blend_code": "diesel", "consumption_rate": 10, "fuel_price": 20000}, CFG)
    assert t["energy_amount"] == 10
    assert t["energy_cost_vnd"] == 200000
    assert t["co2_direct_kg"] == pytest.approx(26.8)


def test_electric_tailpipe_zero_grid_separate():
    t = compute_trip(100, {"vehicle_id": "E", "fuel_blend_code": "electricity", "consumption_rate": 3}, CFG)
    assert t["energy_amount"] == 3
    assert t["co2_direct_kg"] == 0
    assert t["co2_grid_indirect_kg"] == pytest.approx(3 * 0.6592)


def test_ethanol_blend_split_fossil_biogenic():
    assert resolve_factor("E10", CFG)["value"] == pytest.approx(0.9 * 2.31 + 0.1 * 1.51)
    t = compute_trip(100, {"vehicle_id": "M", "fuel_blend_code": "E10", "consumption_rate": 2}, CFG)
    assert t["co2_fossil_kg"] == pytest.approx(2 * 0.9 * 2.31, abs=1e-3)
    assert t["co2_biogenic_kg"] == pytest.approx(2 * 0.1 * 1.51, abs=1e-3)


def test_inputs_change_results():
    v = {"vehicle_id": "X", "fuel_blend_code": "E5", "consumption_rate": 2, "fuel_price": 20000}
    a = compute_trip(50, v, CFG)
    b = compute_trip(50, {**v, "consumption_rate": 4, "fuel_price": 10000, "emission_factor_value": 3}, CFG)
    assert b["energy_amount"] == a["energy_amount"] * 2
    assert b["energy_cost_vnd"] == a["energy_cost_vnd"]
    assert b["co2_direct_kg"] == pytest.approx(6)


def test_missing_data_not_fabricated():
    no_rate = compute_trip(10, {"vehicle_id": "X", "fuel_blend_code": "E5"}, CFG)
    assert no_rate["co2_direct_kg"] is None and no_rate["warnings"]
    e100 = compute_trip(10, {"vehicle_id": "X", "fuel_blend_code": "E100", "consumption_rate": 3}, CFG)
    assert e100["co2_direct_kg"] is None
    assert any("hệ số" in w for w in e100["warnings"])


def test_compatibility():
    assert not check_compatibility("motorbike_electric", "diesel", CFG)["ok"]
    assert check_compatibility("motorbike_petrol", "E20", CFG)["needs_confirmation"]
    assert check_compatibility("motorbike_petrol", "E20", CFG, True)["ok"]
    assert check_compatibility("small_truck", "diesel", CFG)["ok"]


def test_order_validation():
    r = validate_orders([
        {"order_id": "A", "latitude": 10, "longitude": 106, "weight_kg": 1},
        {"order_id": "A", "latitude": 10, "longitude": 106},
        {"order_id": "B", "address": "12 Lê Lợi"},
        {"order_id": "C", "latitude": 10, "longitude": 106, "delivery_window_start": "10:00", "delivery_window_end": "09:00"},
        {"order_id": "D", "latitude": 10, "longitude": 106, "weight_kg": -3},
    ])
    assert len(r["valid"]) == 1
    assert len(r["errors"]) == 4
    assert "chưa định vị" in r["errors"][1]["errors"][0]


def test_solver_constraints(problem, optimized):
    orders = {o["order_id"]: o for o in problem["orders"]}
    vehicles = {v["vehicle_id"]: v for v in problem["vehicles"]}
    served = [s["order_id"] for r in optimized["routes"] for s in r["stops"]]
    assert len(set(served)) == len(served), "no order served twice"
    assert len(served) + len(optimized["unassigned"]) == len(orders), "nothing dropped silently"
    for r in optimized["routes"]:
        v = vehicles[r["vehicle_id"]]
        assert v["available"]
        assert r["load_weight_kg"] <= v["capacity_weight_kg"] + 1e-9
        if v["capacity_volume_m3"] is not None:
            assert r["load_volume_m3"] <= v["capacity_volume_m3"] + 1e-9
        for s in r["stops"]:
            o = orders[s["order_id"]]
            h, m = map(int, s["arrival"].split(":"))
            if o["tw_end"] is not None:
                assert h * 60 + m <= o["tw_end"] + 1, f'{s["order_id"]} late'
    reasons = {u["order_id"]: u["code"] for u in optimized["unassigned"]}
    assert reasons["DH041"] == "EXCEEDS_CAPACITY"
    assert reasons["DH042"] == "TIME_WINDOW_INFEASIBLE"
    assert optimized["meta"]["algorithm"].startswith("Google OR-Tools")


def test_optimized_not_worse_than_baseline(problem, optimized):
    base = baseline(problem["orders"], problem["vehicles"], problem["matrix"], CFG)
    assert optimized["totals"]["orders_assigned"] >= base["totals"]["orders_assigned"]
    if optimized["totals"]["orders_assigned"] == base["totals"]["orders_assigned"]:
        assert optimized["totals"]["total_cost_vnd"] <= base["totals"]["total_cost_vnd"]


def test_same_route_fuel_scenario(problem, optimized):
    route = optimized["routes"][0]
    vid = route["vehicle_id"]
    sc = run_fuel_scenario(optimized, problem["vehicles"], problem["orders"], None, CFG, {vid: {"consumption_rate": 50}}, "same_route")
    assert sc["ok"]
    assert sc["result"]["totals"]["distance_km"] == optimized["totals"]["distance_km"]
    assert sc["result"]["routes"][0]["energy_amount"] > route["energy_amount"]
    incompatible = "diesel" if CFG["fuels"][route["fuel_blend_code"]]["kind"] == "electric" else "electricity"
    bad = run_fuel_scenario(optimized, problem["vehicles"], problem["orders"], None, CFG, {vid: {"fuel_blend_code": incompatible}}, "same_route")
    assert not bad["ok"]
