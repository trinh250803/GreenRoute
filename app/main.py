"""GreenRoute AI — FastAPI backend (mục 8, 9)."""
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import analytics, auth, dispatch, geocode, seed, store, tracking
from .admin_config import update_config
from .auth import ROLES, STAFF, AuthError, audit, require
from .compare import compare_totals, run_fuel_scenario
from .distance import build_distance_matrix
from .emissions import load_fuel_config, num
from .io_files import parse_csv, parse_upload, to_csv, to_xlsx
from .solver import baseline, solve
from .validation import fmt_time, validate_orders, validate_vehicles

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("greenroute")

# Role groups (GAPS.md §1)
ANY_STAFF = require(*STAFF)
ORDERS_WRITE = require("admin", "dispatcher")
FLEET_WRITE = require("admin", "fleet_manager")
PLANNER = require("admin", "dispatcher")
ADMIN = require("admin")
DRIVER = require("driver")


@asynccontextmanager
async def lifespan(_: FastAPI):
    auth.bootstrap_admin()
    seed.seed_from_env()
    yield


app = FastAPI(title="GreenRoute AI API", version="0.3.0", lifespan=lifespan,
              description="Tối ưu giao hàng chặng cuối đa phương tiện — FastAPI + Google OR-Tools. "
                          "Mọi API (trừ /api/auth/login, /api/health) cần header `Authorization: Bearer <token>`.")

ApiError = AuthError


@app.exception_handler(AuthError)
async def api_error(_: Request, e: AuthError):
    return JSONResponse({"error": e.message}, status_code=e.status)


@app.exception_handler(Exception)
async def unhandled(request: Request, e: Exception):
    # Log without request bodies to avoid leaking customer data.
    log.exception("[%s %s] %s", request.method, request.url.path, e)
    return JSONResponse({"error": "Lỗi máy chủ"}, status_code=500)


async def body_json(request: Request):
    raw = await request.body()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError(400, "JSON không hợp lệ (cần mã hóa UTF-8)")


async def rows_from_request(request: Request) -> list[dict]:
    """Multipart 'file' (CSV/XLSX) or JSON {rows: [...]}."""
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        form = await request.form()
        f = form.get("file")
        if f is None:
            raise ApiError(400, "Thiếu file")
        data = await f.read()
        if len(data) > 5 * 1024 * 1024:
            raise ApiError(413, "File quá lớn (tối đa 5MB)")
        try:
            return parse_upload(f.filename, data)
        except ValueError as e:
            raise ApiError(400, str(e))
    return (await body_json(request)).get("rows") or []


def order_row(o):
    return {**o, "delivery_window_start": fmt_time(o["tw_start"]), "delivery_window_end": fmt_time(o["tw_end"])}


def vehicle_row(v):
    return {**v, "start_time": fmt_time(v["start_time"]), "end_time": fmt_time(v["end_time"])}


def result_response(out: dict, ok_status: int = 200) -> JSONResponse:
    return JSONResponse(out, status_code=422 if out["errors"] else ok_status)


def log_action(user: dict, action: str, detail=None):
    with store.lock:
        db = store.load()
        audit(db, user["username"], action, detail)
        store.save(db)


# ---------- Auth ----------
@app.post("/api/auth/login")
async def login(request: Request):
    b = await body_json(request)
    return auth.login(str(b.get("username") or "").strip(), b.get("password") or "")


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, user=Depends(auth.current_user)):
    auth.logout(request.state.session)


@app.get("/api/auth/me")
def me(user=Depends(auth.current_user)):
    return auth.public_user(user)


@app.post("/api/auth/change-password")
async def change_password(request: Request, user=Depends(auth.current_user)):
    b = await body_json(request)
    return auth.change_password(user, b.get("old_password"), b.get("new_password"))


# ---------- Admin: users, config, audit ----------
@app.get("/api/admin/users")
def list_users(user=Depends(ADMIN)):
    return [auth.public_user(u) for u in store.load().get("users", [])]


@app.post("/api/admin/users", status_code=201)
async def create_user(request: Request, user=Depends(ADMIN)):
    return auth.create_user(user, await body_json(request))


@app.put("/api/admin/users/{username}")
async def update_user(username: str, request: Request, user=Depends(ADMIN)):
    return auth.update_user(user, username, await body_json(request))


@app.get("/api/admin/roles")
def roles(user=Depends(ADMIN)):
    return ROLES


@app.get("/api/admin/config/history")
def config_history(user=Depends(ADMIN)):
    return store.load().get("config_history", [])


@app.put("/api/admin/config")
async def put_config(request: Request, user=Depends(ADMIN)):
    b = await body_json(request)
    return update_config(user, b.get("changes") or {}, b.get("reason") or "")


@app.get("/api/admin/audit")
def audit_log(limit: int = 200, user=Depends(ADMIN)):
    return store.load().get("audit", [])[: max(1, min(limit, 2000))]


# ---------- Config / depot ----------
@app.get("/api/config")
def get_config(user=Depends(auth.current_user)):
    return load_fuel_config()


ENV_BANNER = os.environ.get("APP_ENV_BANNER", "Môi trường nghiên cứu, chưa áp dụng chính thức")  # set to "" in production


@app.get("/api/health")
def health():
    return {"ok": True, "routing": "osrm" if os.environ.get("OSRM_URL") else "haversine_estimate", "solver": "ortools",
            "env_banner": ENV_BANNER}


@app.middleware("http")
async def no_stale_web_app(request: Request, call_next):
    # HTML/JS/CSS change with every deploy: make browsers revalidate instead of running old code.
    resp = await call_next(request)
    if not request.url.path.startswith("/api/") and request.url.path.endswith(("/", ".html", ".js", ".css")):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/api/geocode/search")
def geocode_search(q: str = "", user=Depends(ORDERS_WRITE)):
    depot = store.load().get("depot") or {}
    return geocode.search(q, depot.get("latitude"), depot.get("longitude"))


@app.get("/api/geocode/reverse")
def geocode_reverse(lat: float, lng: float, user=Depends(ORDERS_WRITE)):
    return geocode.reverse(lat, lng)


@app.get("/api/depot")
def get_depot(user=Depends(ANY_STAFF)):
    return store.load()["depot"]


@app.put("/api/depot")
async def put_depot(request: Request, user=Depends(ORDERS_WRITE)):
    b = await body_json(request)
    lat, lng = num(b.get("latitude")), num(b.get("longitude"))
    if lat is None or lng is None:
        raise ApiError(400, "Tọa độ kho không hợp lệ")
    with store.lock:
        db = store.load()
        db["depot"] = {"name": b.get("name") or "Kho", "latitude": lat, "longitude": lng}
        audit(db, user["username"], "update_depot", db["depot"])
        store.save(db)
    return db["depot"]


# ---------- Orders (F-02) ----------
def upsert_orders(rows: list[dict], mode: str, user: dict | None = None) -> dict:
    with store.lock:
        db = store.load()
        existing = [order_row(o) for o in db["orders"]] if mode == "append" else []
        rep = validate_orders(existing + rows)
        for e in rep["errors"] + rep["warnings"]:
            e["line"] -= len(existing)  # line numbers relative to the submitted rows
        if not rep["errors"]:
            db["orders"] = rep["valid"]
            if user:
                audit(db, user["username"], "orders_" + mode, {"rows": len(rows), "total": len(db["orders"])})
            store.save(db)
        return {"imported": 0 if rep["errors"] else len(rows), "total": len(db["orders"]), "errors": rep["errors"], "warnings": rep["warnings"]}


@app.get("/api/orders")
def list_orders(user=Depends(require("admin", "dispatcher", "ops_manager"))):
    return store.load()["orders"]


@app.post("/api/orders/import")
async def import_orders(request: Request, mode: str = "replace", user=Depends(ORDERS_WRITE)):
    return result_response(upsert_orders(await rows_from_request(request), "append" if mode == "append" else "replace", user))


@app.post("/api/orders")
async def create_order(request: Request, user=Depends(ORDERS_WRITE)):
    return result_response(upsert_orders([await body_json(request)], "append", user), 201)


@app.put("/api/orders/{order_id}")
async def update_order(order_id: str, request: Request, user=Depends(ORDERS_WRITE)):
    b = await body_json(request)
    db = store.load()
    if not any(o["order_id"] == order_id for o in db["orders"]):
        raise ApiError(404, "Không tìm thấy đơn")
    rows = [{**order_row(o), **b, "order_id": o["order_id"]} if o["order_id"] == order_id else order_row(o) for o in db["orders"]]
    return result_response(upsert_orders(rows, "replace", user))


@app.delete("/api/orders/{order_id}", status_code=204)
def delete_order(order_id: str, user=Depends(ORDERS_WRITE)):
    with store.lock:
        db = store.load()
        db["orders"] = [o for o in db["orders"] if o["order_id"] != order_id]
        audit(db, user["username"], "delete_order", {"order_id": order_id})
        store.save(db)


@app.delete("/api/orders", status_code=204)
def clear_orders(user=Depends(ORDERS_WRITE)):
    with store.lock:
        db = store.load()
        audit(db, user["username"], "clear_orders", {"count": len(db["orders"])})
        db["orders"] = []
        store.save(db)


# ---------- Vehicles (F-03) ----------
def upsert_vehicles(rows: list[dict], mode: str, user: dict | None = None) -> dict:
    with store.lock:
        db = store.load()
        existing = [vehicle_row(v) for v in db["vehicles"]] if mode == "append" else []
        rep = validate_vehicles(existing + rows, load_fuel_config())
        for e in rep["errors"] + rep["warnings"]:
            e["line"] -= len(existing)
        if not rep["errors"]:
            db["vehicles"] = rep["valid"]
            if user:
                audit(db, user["username"], "vehicles_" + mode, {"rows": len(rows), "total": len(db["vehicles"])})
            store.save(db)
        return {"imported": 0 if rep["errors"] else len(rows), "total": len(db["vehicles"]), "errors": rep["errors"], "warnings": rep["warnings"]}


@app.get("/api/vehicles")
def list_vehicles(user=Depends(ANY_STAFF)):
    db = store.load()
    drivers = dispatch.drivers_by_vehicle(db)
    return [{**v, "driver": drivers[v["vehicle_id"]]["username"] if v["vehicle_id"] in drivers else None} for v in db["vehicles"]]


@app.post("/api/vehicles/import")
async def import_vehicles(request: Request, mode: str = "replace", user=Depends(FLEET_WRITE)):
    return result_response(upsert_vehicles(await rows_from_request(request), "append" if mode == "append" else "replace", user))


@app.post("/api/vehicles")
async def create_vehicles(request: Request, user=Depends(FLEET_WRITE)):
    b = await body_json(request)
    return result_response(upsert_vehicles(b if isinstance(b, list) else [b], "append", user), 201)


@app.put("/api/vehicles/{vehicle_id}")
async def update_vehicle(vehicle_id: str, request: Request, user=Depends(FLEET_WRITE)):
    b = await body_json(request)
    db = store.load()
    if not any(v["vehicle_id"] == vehicle_id for v in db["vehicles"]):
        raise ApiError(404, "Không tìm thấy xe")
    rows = [{**vehicle_row(v), **b, "vehicle_id": v["vehicle_id"]} if v["vehicle_id"] == vehicle_id else vehicle_row(v) for v in db["vehicles"]]
    return result_response(upsert_vehicles(rows, "replace", user))


@app.delete("/api/vehicles/{vehicle_id}", status_code=204)
def delete_vehicle(vehicle_id: str, user=Depends(FLEET_WRITE)):
    with store.lock:
        db = store.load()
        db["vehicles"] = [v for v in db["vehicles"] if v["vehicle_id"] != vehicle_id]
        audit(db, user["username"], "delete_vehicle", {"vehicle_id": vehicle_id})
        store.save(db)


# ---------- Sample data (synthetic, labelled) ----------
SAMPLE_DATASETS = {"small": "sample", "hcm": "sample_hcm"}


@app.get("/api/sample/datasets")
def sample_datasets(user=Depends(ADMIN)):
    return {"small": "Nhỏ — 42 đơn quanh Quận 1, 8 xe (dùng cho test tự động)",
            "hcm": "TP.HCM — 150 đơn ở 14 quận, 12 xe, có tên khách & SĐT giả lập"}


@app.post("/api/sample/load")
def load_sample(dataset: str = "hcm", user=Depends(ADMIN)):
    if dataset not in SAMPLE_DATASETS:
        raise ApiError(400, f"Bộ dữ liệu không hợp lệ ({', '.join(SAMPLE_DATASETS)})")
    d = ROOT / "data" / SAMPLE_DATASETS[dataset]
    with store.lock:
        db = store.load()
        db["depot"] = json.loads((d / "depot.json").read_text(encoding="utf-8"))
        audit(db, user["username"], "load_sample", {"dataset": dataset})
        store.save(db)
    o = upsert_orders(parse_csv((d / "orders.csv").read_text(encoding="utf-8")), "replace")
    v = upsert_vehicles(parse_csv((d / "vehicles.csv").read_text(encoding="utf-8")), "replace")
    return {"orders": o, "vehicles": v, "dataset": dataset, "label": "Dữ liệu minh họa (synthetic)"}


# ---------- Optimization (F-05, F-06, F-07) ----------
def clamp_limit(v, default=5.0) -> float:
    n = num(v)
    return min(max(n if n else default, 1.0), 60.0)


@app.post("/api/optimization/run")
async def run_optimization(request: Request, user=Depends(PLANNER)):
    b = await body_json(request)
    db = store.load()
    if not db["depot"]:
        raise ApiError(400, "Chưa cấu hình kho xuất phát")
    if not db["orders"]:
        raise ApiError(400, "Chưa có đơn hàng")
    ids = b.get("vehicle_ids")
    vehicles = [v for v in db["vehicles"] if v["vehicle_id"] in ids] if ids else db["vehicles"]
    if not any(v["available"] for v in vehicles):
        raise ApiError(400, "Không có xe sẵn sàng")
    cfg = load_fuel_config()
    defaults = cfg.get("default_weights", {})
    weights = {"co2_vnd_per_kg": defaults.get("co2_vnd_per_kg", 0), "time_vnd_per_min": defaults.get("time_vnd_per_min", 0), **(b.get("weights") or {})}
    dm = build_distance_matrix([db["depot"], *db["orders"]], cfg)
    optimized = await run_in_threadpool(solve, db["orders"], vehicles, dm["matrix"], cfg, weights,
                                        clamp_limit(b.get("time_limit_s"), defaults.get("time_limit_s", 5)))
    base = baseline(db["orders"], vehicles, dm["matrix"], cfg)
    run = {
        "id": str(uuid.uuid4()), "label": b.get("label") or "", "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user["username"],
        "depot": db["depot"], "input": {"orders": db["orders"], "vehicles": vehicles},
        "assumptions": {
            "emission_scope": cfg["emission_scope"], "scope_note": cfg["scope_note"], "fuel_config_version": cfg["version"],
            "illustrative": cfg["illustrative"], "illustrative_note": cfg["illustrative_note"],
            "routing_source": dm["source"], "routing_note": dm["note"], "routing_fallback": dm.get("fallback_reason"),
            "solver": optimized["meta"]["algorithm"],
            "cost_model": "Chi phí = km × cost_per_km (vận hành, ngoài năng lượng) + chi phí cố định/xe + năng lượng (lượng tiêu thụ × giá)"
                          f" + tài xế ({(cfg.get('costs') or {}).get('driver_vnd_per_hour', 0)} VND/giờ × thời gian tuyến)",
        },
        "optimized": optimized, "baseline": base, "comparison": compare_totals(base["totals"], optimized["totals"]), "scenarios": [],
    }
    with store.lock:
        db = store.load()
        db["runs"] = [run, *db["runs"]][:20]
        audit(db, user["username"], "run_optimization", {"run_id": run["id"], "orders": len(run["input"]["orders"]), "config_version": cfg["version"]})
        store.save(db)
    return run


@app.get("/api/optimization")
def list_runs(user=Depends(ANY_STAFF)):
    active = (store.load().get("dispatch") or {}).get("run_id")
    return [{"id": r["id"], "label": r["label"], "created_at": r["created_at"], "created_by": r.get("created_by"),
             "published": r["id"] == active, "totals": r["optimized"]["totals"]} for r in store.load()["runs"]]


def find_run(db, run_id):
    run = next((r for r in db["runs"] if r["id"] == run_id), None)
    if not run:
        raise ApiError(404, "Không tìm thấy lần tối ưu")
    return run


@app.get("/api/optimization/{run_id}")
def get_run(run_id: str, user=Depends(ANY_STAFF)):
    return find_run(store.load(), run_id)


@app.post("/api/optimization/{run_id}/fuel-scenario")
async def fuel_scenario(run_id: str, request: Request, user=Depends(ANY_STAFF)):
    b = await body_json(request)
    run = find_run(store.load(), run_id)
    mode = b.get("mode") or "same_route"
    cfg = load_fuel_config()
    matrix = build_distance_matrix([run["depot"], *run["input"]["orders"]], cfg)["matrix"] if mode == "reoptimize" else None
    out = await run_in_threadpool(run_fuel_scenario, run["optimized"], run["input"]["vehicles"], run["input"]["orders"], matrix, cfg,
                                  b.get("overrides") or {}, mode, run["optimized"]["meta"].get("weights"), clamp_limit(b.get("time_limit_s")))
    if not out["ok"]:
        return JSONResponse(out, status_code=422)
    with store.lock:
        db = store.load()
        run = find_run(db, run_id)
        scenario = {"id": str(uuid.uuid4()), "name": b.get("name") or f'Kịch bản {len(run["scenarios"]) + 1}', "created_by": user["username"],
                    "overrides": b.get("overrides") or {}, **out}
        run["scenarios"].append(scenario)
        audit(db, user["username"], "fuel_scenario", {"run_id": run_id, "mode": out["mode"]})
        store.save(db)
    return scenario


# ---------- Dispatch: publish to drivers, delivery tracking ----------
@app.post("/api/optimization/{run_id}/publish")
def publish(run_id: str, user=Depends(PLANNER)):
    return dispatch.publish(user, run_id)


@app.get("/api/dispatch")
def dispatch_board(user=Depends(ANY_STAFF)):
    return dispatch.status_board(store.load())


@app.get("/api/driver/route")
def driver_route(user=Depends(DRIVER)):
    return {**dispatch.driver_route(user), "tracking": tracking.driver_state(user)}


@app.post("/api/driver/sharing")
async def driver_sharing(request: Request, user=Depends(DRIVER)):
    return tracking.set_sharing(user, bool((await body_json(request)).get("on")))


@app.post("/api/driver/location")
async def driver_location(request: Request, user=Depends(DRIVER)):
    return tracking.record_points(user, await body_json(request))


@app.get("/api/tracking")
def tracking_board(user=Depends(ANY_STAFF)):
    return tracking.board(store.load())


@app.post("/api/driver/stops/{order_id}")
async def driver_outcome(order_id: str, request: Request, user=Depends(DRIVER)):
    return dispatch.record_outcome(user, order_id, await body_json(request))


# ---------- Analytics, details ----------
@app.get("/api/analytics")
def get_analytics(user=Depends(ANY_STAFF)):
    return analytics.analytics(store.load())


@app.get("/api/orders/{order_id}/detail")
def get_order_detail(order_id: str, user=Depends(require("admin", "dispatcher", "ops_manager"))):
    d = analytics.order_detail(store.load(), order_id)
    if d is None:
        raise ApiError(404, "Không tìm thấy đơn")
    return d


@app.get("/api/vehicles/{vehicle_id}/detail")
def get_vehicle_detail(vehicle_id: str, user=Depends(ANY_STAFF)):
    d = analytics.vehicle_detail(store.load(), vehicle_id)
    if d is None:
        raise ApiError(404, "Không tìm thấy xe")
    return d


# ---------- Prediction (F-08): honest fallback until a model is trained and evaluated ----------
@app.post("/api/predictions/travel-time")
async def predict_travel_time(request: Request, user=Depends(ANY_STAFF)):
    b = await body_json(request)
    d = num(b.get("distance_km"))
    if d is None or d < 0:
        raise ApiError(400, "distance_km không hợp lệ")
    speed = load_fuel_config()["vehicle_types"].get(b.get("vehicle_type"), {}).get("speed_kmh", 22)
    return {"travel_time_min": round(d / speed * 60, 1), "model_status": "not_trained", "method": f"fallback: distance / {speed} km/h",
            "note": "Chưa có mô hình ML được huấn luyện & đánh giá trên dữ liệu thật (G4). Đây là ước tính heuristic."}


# ---------- Reports (F-09) ----------
def report_rows(run: dict) -> dict:
    def route_rows(result, plan):
        return [{
            "plan": plan, "vehicle_id": r["vehicle_id"], "vehicle_type": r["vehicle_type"], "fuel": r["fuel_blend_code"], "stops": len(r["stops"]),
            "sequence": " > ".join(s["order_id"] for s in r["stops"]), "distance_km": r["distance_km"], "duration_min": r["duration_min"],
            "load_kg": r["load_weight_kg"], "operating_cost_vnd": r["operating_cost_vnd"], "energy": r["energy_amount"], "energy_unit": r["energy_unit"],
            "energy_cost_vnd": r["energy_cost_vnd"], "driver_cost_vnd": r.get("driver_cost_vnd", 0),
            "price_used": r.get("price_used"), "price_source_used": r.get("price_source_used"), "co2_fossil_kg": r.get("co2_fossil_kg"), "co2_biogenic_kg": r.get("co2_biogenic_kg"),
            "co2_grid_indirect_kg": r["co2_grid_indirect_kg"], "co2_tailpipe_total_kg": r["co2_direct_kg"],
            "factor_value": (r["factor"] or {}).get("value"), "factor_unit": (r["factor"] or {}).get("unit"),
            "factor_source": (r["factor"] or {}).get("source"), "factor_year": (r["factor"] or {}).get("year"),
        } for r in result["routes"]]

    deliveries = run.get("deliveries", {})
    return {
        "summary": [{"metric": r["metric"], "baseline": r["reference"], "optimized": r["candidate"], "change_pct": r["change_pct"]} for r in run["comparison"]["rows"]],
        "routes": route_rows(run["baseline"], "baseline") + route_rows(run["optimized"], "optimized")
        + [row for s in run["scenarios"] for row in route_rows(s["result"], f'scenario:{s["name"]} ({s["mode"]})')],
        "unassigned": [{"plan": "baseline", **u} for u in run["baseline"]["unassigned"]] + [{"plan": "optimized", **u} for u in run["optimized"]["unassigned"]],
        "scenarios": [{"scenario": s["name"], "mode": s["mode"], "metric": r["metric"], "reference": r["reference"], "scenario_value": r["candidate"], "change_pct": r["change_pct"]}
                      for s in run["scenarios"] for r in s["comparison"]["rows"]],
        "deliveries": [{"vehicle_id": r["vehicle_id"], "order_id": s["order_id"], "planned_arrival": s["arrival"], "window": s["window"],
                        **{k: deliveries.get(s["order_id"], {}).get(k) for k in ("status", "reason_label", "actual_time", "on_time", "location_check", "distance_to_stop_m", "location_error", "note", "recorded_by", "recorded_at")}}
                       for r in run["optimized"]["routes"] for s in r["stops"]] if run.get("published_at") else [],
        "assumptions": [{"key": k, "value": str(v)} for k, v in run["assumptions"].items()],
    }


@app.get("/api/reports/{run_id}")
def get_report(run_id: str, format: str = "json", user=Depends(ANY_STAFF)):
    run = find_run(store.load(), run_id)
    rows = report_rows(run)
    fname = f'greenroute-{run["created_at"][:10]}-{run["id"][:8]}'
    if format == "xlsx":
        return Response(to_xlsx(rows), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{fname}.xlsx"'})
    if format == "csv":
        return Response(to_csv(rows["routes"]), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{fname}-routes.csv"'})
    return rows


app.mount("/", StaticFiles(directory=ROOT / "public", html=True), name="web")
