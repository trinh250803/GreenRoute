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
    assert client.post("/api/sample/load", headers=h).json()["orders"]["imported"] == 42
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
