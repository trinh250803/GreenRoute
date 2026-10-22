import time

import pytest
from fastapi.testclient import TestClient

ADMIN_PW = "Admin@12345"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("DB_PATH", str(tmp_path_factory.mktemp("db") / "db.json"))
    mp.setenv("ADMIN_USERNAME", "admin")
    mp.setenv("ADMIN_PASSWORD", ADMIN_PW)
    from app.main import app
    with TestClient(app) as c:  # runs lifespan → bootstrap admin
        yield c
    mp.undo()


def login(client, username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f'Bearer {r.json()["token"]}'}


def make_user(client, admin, username, role, vehicle_id=None):
    r = client.post("/api/admin/users", headers=admin, json={"username": username, "role": role, "password": "TempPass1!", "vehicle_id": vehicle_id})
    assert r.status_code == 201, r.text
    h = login(client, username, "TempPass1!")
    # Forced password change on first login.
    assert client.get("/api/auth/me", headers=h).json()["must_change_password"]
    assert client.get("/api/depot", headers=h).status_code == 403
    assert client.post("/api/auth/change-password", headers=h, json={"old_password": "TempPass1!", "new_password": "NewPass123!"}).status_code == 204
    return login(client, username, "NewPass123!")


@pytest.fixture(scope="module")
def admin(client):
    h = login(client, "admin", ADMIN_PW)
    assert client.post("/api/sample/load?dataset=small", headers=h).json()["orders"]["imported"] == 42
    return h


def test_requires_login(client):
    assert client.get("/api/orders").status_code == 401
    assert client.post("/api/optimization/run", json={}).status_code == 401
    assert client.get("/api/health").status_code == 200


def test_wrong_password_and_lockout(client):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "ghost", "password": "x"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "ghost", "password": "x"}).status_code == 429


def test_role_permissions(client, admin):
    fleet = make_user(client, admin, "fleet1", "fleet_manager")
    ops = make_user(client, admin, "ops1", "ops_manager")
    assert client.post("/api/vehicles", headers=fleet, json={"vehicle_id": "NEW-1", "vehicle_type": "van", "capacity_weight_kg": 500,
                                                             "cost_per_km": 3000, "fuel_blend_code": "E5", "consumption_rate": 9}).status_code == 201
    assert client.post("/api/orders", headers=fleet, json={"order_id": "Z1", "latitude": 10.7, "longitude": 106.7}).status_code == 403
    assert client.post("/api/optimization/run", headers=ops, json={}).status_code == 403
    assert client.get("/api/orders", headers=ops).status_code == 200
    assert client.get("/api/admin/users", headers=ops).status_code == 403
    assert client.delete("/api/vehicles/NEW-1", headers=fleet).status_code == 204


def test_end_to_end_with_driver(client, admin):
    dispatcher = make_user(client, admin, "dispatch1", "dispatcher")
    run = client.post("/api/optimization/run", headers=dispatcher, json={"time_limit_s": 2}).json()
    assert run["optimized"]["totals"]["orders_unassigned"] == 2
    assert run["created_by"] == "dispatch1"

    vid = run["optimized"]["routes"][0]["vehicle_id"]
    other_vid = run["optimized"]["routes"][1]["vehicle_id"]
    driver = make_user(client, admin, "driver1", "driver", vid)
    # Driver sees nothing before publishing and cannot read staff data.
    assert client.get("/api/driver/route", headers=driver).json()["route"] is None
    assert client.get("/api/orders", headers=driver).status_code == 403
    assert client.get("/api/optimization", headers=driver).status_code == 403

    pub = client.post(f'/api/optimization/{run["id"]}/publish', headers=dispatcher).json()
    assert other_vid in pub["vehicles_without_driver"]

    route = client.get("/api/driver/route", headers=driver).json()["route"]
    assert route["vehicle_id"] == vid
    first, second = route["stops"][0]["order_id"], route["stops"][1]["order_id"]
    s0 = route["stops"][0]
    near = {"latitude": s0["latitude"] + 0.0005, "longitude": s0["longitude"], "accuracy_m": 20}  # ~55 m away
    ok = client.post(f"/api/driver/stops/{first}", headers=driver, json={"status": "delivered", "local_time": "09:15", "location": near})
    assert ok.status_code == 200 and ok.json()["status"] == "delivered"
    assert ok.json()["location_check"] == "ok" and 40 <= ok.json()["distance_to_stop_m"] <= 70
    assert client.post(f"/api/driver/stops/{second}", headers=driver, json={"status": "failed"}).status_code == 400
    far = {"latitude": 21.0285, "longitude": 105.8542, "accuracy_m": 15}  # Hà Nội, far from the HCMC stop
    bad = client.post(f"/api/driver/stops/{second}", headers=driver, json={"status": "failed", "reason": "customer_absent", "location": far})
    assert bad.status_code == 200 and bad.json()["location_check"] == "far"
    third = route["stops"][2]["order_id"]
    miss = client.post(f"/api/driver/stops/{third}", headers=driver, json={"status": "delivered", "location_error": "Tài xế không cho phép định vị"})
    assert miss.json()["location_check"] == "missing"
    # Cannot touch another vehicle's stop.
    foreign = run["optimized"]["routes"][1]["stops"][0]["order_id"]
    assert client.post(f"/api/driver/stops/{foreign}", headers=driver, json={"status": "delivered"}).status_code == 403

    board = client.get("/api/dispatch", headers=dispatcher).json()
    assert board["counts"]["delivered"] == 2 and board["counts"]["failed"] == 1

    x = client.get(f'/api/reports/{run["id"]}?format=xlsx', headers=admin)
    assert x.status_code == 200 and x.content[:2] == b"PK"
    rep = client.get(f'/api/reports/{run["id"]}', headers=admin).json()
    assert {d["status"] for d in rep["deliveries"]} >= {"delivered", "failed"}

    audit = client.get("/api/admin/audit", headers=admin).json()
    assert {"publish_plan", "delivery_outcome", "run_optimization"} <= {a["action"] for a in audit}


def test_admin_config_versioning(client, admin):
    before = client.get("/api/config", headers=admin).json()
    assert client.put("/api/admin/config", headers=admin, json={"changes": {"fuels.E5.price_vnd": 22000}, "reason": ""}).status_code == 400
    assert client.put("/api/admin/config", headers=admin, json={"changes": {"fuels.E5.label": "x"}, "reason": "thử sửa nhãn"}).status_code == 400
    r = client.put("/api/admin/config", headers=admin, json={"changes": {"fuels.E5.price_vnd": 22000, "base_factors.gasoline.value": 2.29},
                                                             "reason": "Cập nhật giá theo công bố tuần 43"})
    assert r.status_code == 200
    after = client.get("/api/config", headers=admin).json()
    assert after["fuels"]["E5"]["price_vnd"] == 22000 and after["version"] != before["version"]
    hist = client.get("/api/admin/config/history", headers=admin).json()
    assert hist[0]["changes"][0]["old"] == before["fuels"]["E5"]["price_vnd"]


def test_cannot_lock_out_last_admin(client, admin):
    assert client.put("/api/admin/users/admin", headers=admin, json={"active": False}).status_code == 400


def test_invalid_import_writes_nothing(client, admin):
    before = len(client.get("/api/orders", headers=admin).json())
    assert client.post("/api/orders", headers=admin, json={"order_id": "DH001", "address": "x"}).status_code == 422
    assert len(client.get("/api/orders", headers=admin).json()) == before


def test_live_tracking(client, admin):
    drv = make_user(client, admin, "driver_track", "driver", "TRUCK-01")
    ping = {"latitude": 10.78, "longitude": 106.70, "accuracy_m": 12, "ts": 0}
    # No tracking without the driver's explicit consent.
    assert client.post("/api/driver/location", headers=drv, json=ping).status_code == 409
    assert client.post("/api/driver/sharing", headers=drv, json={"on": True}).json()["sharing"] is True
    t0 = time.time() * 1000 - 300_000
    pts = [{"latitude": 10.78 + i * 0.001, "longitude": 106.70, "accuracy_m": 10, "ts": t0 + i * 30_000} for i in range(5)]
    assert client.post("/api/driver/location", headers=drv, json={"points": pts}).json()["stored"] == 5
    assert client.post("/api/driver/location", headers=drv, json={"latitude": 999, "longitude": 0}).status_code == 400
    board = client.get("/api/tracking", headers=admin).json()
    truck = next(v for v in board["vehicles"] if v["vehicle_id"] == "TRUCK-01")
    assert truck["sharing"] and truck["last"]["lat"] == 10.784 and not truck["stale"]
    assert len(truck["trail"]) == 5 and truck["trail_km"] > 0.3
    assert client.get("/api/tracking", headers=drv).status_code == 403
    client.post("/api/driver/sharing", headers=drv, json={"on": False})
    assert client.post("/api/driver/location", headers=drv, json=ping).status_code == 409
    assert client.get("/api/driver/route", headers=drv).json()["tracking"]["sharing"] is False


def test_non_utf8_body_is_400(client, admin):
    r = client.put("/api/depot", headers={**admin, "Content-Type": "application/json"},
                   content='{"name":"Kho Bạch Đằng","latitude":10.8,"longitude":106.7}'.encode("cp1258", errors="replace"))
    assert r.status_code == 400


def test_analytics_details_and_assistant(client, admin, monkeypatch):
    run = client.post("/api/optimization/run", headers=admin, json={"time_limit_s": 1}).json()
    a = client.get("/api/analytics", headers=admin).json()
    assert a["run"]["id"] and a["by_vehicle"] and a["by_district"] and len(a["arrivals_by_hour"]) == 15
    assert {"peak_legs", "late_risk"} <= set(a["traffic"])
    stop = run["optimized"]["routes"][0]["stops"][0]["order_id"]
    od = client.get(f"/api/orders/{stop}/detail", headers=admin).json()
    assert od["assignment"]["sequence"] >= 1 and od["order"]["order_id"] == stop
    assert client.get("/api/orders/DH041/detail", headers=admin).json()["unassigned"]["code"] == "EXCEEDS_CAPACITY"
    assert client.get("/api/orders/NOPE/detail", headers=admin).status_code == 404
    vd = client.get(f'/api/vehicles/{run["optimized"]["routes"][0]["vehicle_id"]}/detail', headers=admin).json()
    assert vd["route"]["stops"]
    # Without a key the assistant reports "not configured" instead of crashing.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert client.get("/api/assistant/status", headers=admin).json()["configured"] is False
    assert client.post("/api/assistant/ask", headers=admin, json={"question": "Xe nào chạy xa nhất?"}).status_code == 503


def test_assistant_context_has_no_customer_pii(client, admin):
    from app import store
    from app.assistant import plan_context
    ctx = plan_context(store.load())
    assert "0120" not in ctx and "(synthetic)" not in ctx and "customer_name" not in ctx
