"""Handover formulas re-derived independently (scripts/verify_formulas.py) and compared with the API."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from verify_formulas import check_run  # noqa: E402

ADMIN_PW = "Admin@12345"
GAS, ETH = 2.31, 1.51


def ef(x):
    return (1 - x) * GAS + x * ETH


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("DB_PATH", str(tmp_path_factory.mktemp("db") / "db.json"))
    mp.setenv("ADMIN_USERNAME", "admin")
    mp.setenv("ADMIN_PASSWORD", ADMIN_PW)
    from app.main import app
    with TestClient(app) as c:
        h = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW}).json()["token"]}
        c.post("/api/sample/load?dataset=hcm", headers=h)
        run = c.post("/api/optimization/run", headers=h, json={"time_limit_s": 3}).json()
        yield c, h, run, c.get("/api/config", headers=h).json()
    mp.undo()


def scenario(ctx, overrides):
    c, h, run, _ = ctx
    return c.post(f'/api/optimization/{run["id"]}/fuel-scenario', headers=h, json={"overrides": overrides, "mode": "same_route"})


def test_every_number_matches_independent_recalculation(ctx):
    _, _, run, cfg = ctx
    failed = check_run(run, cfg).failed
    assert not failed, "\n".join(f"{g} · {c}: {d}" for g, c, _, d in failed[:20])


def test_blend_factor_formula_in_config():
    assert ef(0.05) == pytest.approx(2.27)
    assert ef(0.10) == pytest.approx(2.23)


def first_route(run, fuel):
    return next(r for r in run["optimized"]["routes"] if r["fuel_blend_code"] == fuel)


def test_same_route_fuel_switch_changes_only_fuel_terms(ctx):
    _, _, run, cfg = ctx
    r = first_route(run, "E5")
    body = scenario(ctx, {r["vehicle_id"]: {"fuel_blend_code": "E10"}}).json()
    s = next(x for x in body["result"]["routes"] if x["vehicle_id"] == r["vehicle_id"])
    assert s["distance_km"] == r["distance_km"] and s["energy_amount"] == r["energy_amount"]
    assert s["co2_direct_kg"] == pytest.approx(r["energy_amount"] * ef(0.10), abs=1e-3)
    assert s["energy_cost_vnd"] == pytest.approx(r["energy_amount"] * cfg["fuels"]["E10"]["price_vnd"], abs=1)
    assert s["co2_biogenic_kg"] == pytest.approx(r["energy_amount"] * 0.10 * ETH, abs=1e-3)
    # Reusing the E5 consumption for E10 is flagged, not silently assumed (Phụ lục 2 §2).
    assert any("dùng lại mức tiêu hao" in w for w in body["result"]["totals"]["warnings"])


def test_new_consumption_and_price_flow_through(ctx):
    _, _, run, _ = ctx
    r = first_route(run, "E5")
    body = scenario(ctx, {r["vehicle_id"]: {"fuel_blend_code": "E10", "consumption_rate": 3.0, "fuel_price": 30000}}).json()
    s = next(x for x in body["result"]["routes"] if x["vehicle_id"] == r["vehicle_id"])
    litres = r["distance_km"] * 3.0 / 100
    assert s["energy_amount"] == pytest.approx(litres, abs=1e-3)
    assert s["energy_cost_vnd"] == pytest.approx(litres * 30000, abs=1)
    assert s["co2_direct_kg"] == pytest.approx(litres * ef(0.10), abs=1e-3)
    assert not any("dùng lại mức tiêu hao" in w for w in body["result"]["totals"]["warnings"])


def test_missing_price_gives_no_cost_instead_of_a_guess(ctx):
    _, _, run, _ = ctx
    r = first_route(run, "E5")
    body = scenario(ctx, {r["vehicle_id"]: {"fuel_blend_code": "E20", "consumption_rate": 2.4, "confirm_simulation_fuel": True}}).json()
    s = next(x for x in body["result"]["routes"] if x["vehicle_id"] == r["vehicle_id"])
    assert s["energy_cost_vnd"] is None and body["result"]["totals"]["total_cost_vnd"] is None
    assert s["co2_direct_kg"] == pytest.approx(r["distance_km"] * 2.4 / 100 * ef(0.20), abs=1e-3)
    warnings = " ".join(body["result"]["totals"]["warnings"])
    assert "chưa có giá" in warnings and "chỉ dùng mô phỏng" in warnings


def test_simulation_fuel_needs_confirmation(ctx):
    r = first_route(ctx[2], "E5")
    res = scenario(ctx, {r["vehicle_id"]: {"fuel_blend_code": "E20", "consumption_rate": 2.4}})
    assert res.status_code == 422 and res.json()["errors"][0]["needs_confirmation"]


def test_incompatible_fuel_is_rejected(ctx):
    r = first_route(ctx[2], "E5")
    res = scenario(ctx, {r["vehicle_id"]: {"fuel_blend_code": "electricity"}})  # xe máy xăng không chạy điện
    assert res.status_code == 422
    assert any("tiêu hao mới" in e["error"] for e in res.json()["errors"])  # và L/100km không dùng được cho kWh
