"""Publishing routes to drivers and recording delivery outcomes (mục 1 đầu ra; 5.1 delivery_status; 7.3).

Outcomes recorded here are the real-world labels (on-time / late / failed, actual times)
that the ML stage needs later.
"""
from . import store
from .auth import AuthError, audit, now_iso
from .distance import haversine_km
from .emissions import load_fuel_config, num
from .validation import parse_time


def location_check(stop: dict, data: dict) -> dict:
    """Compare the phone's GPS fix at reporting time with the stop's coordinates.
    'ok' within max(threshold, GPS accuracy); 'far' beyond it; 'missing' when the phone sent no fix."""
    loc = data.get("location") or {}
    lat, lng, acc = num(loc.get("latitude")), num(loc.get("longitude")), num(loc.get("accuracy_m"))
    threshold = load_fuel_config().get("delivery_check", {}).get("max_distance_m", 300)
    if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return {"location": None, "location_check": "missing", "location_error": str(data.get("location_error") or "Không có định vị")[:200],
                "distance_to_stop_m": None, "location_threshold_m": threshold}
    dist = haversine_km({"latitude": lat, "longitude": lng}, stop) * 1000
    allowed = max(threshold, acc or 0)
    return {"location": {"latitude": lat, "longitude": lng, "accuracy_m": None if acc is None else round(acc)},
            "location_check": "ok" if dist <= allowed else "far", "location_error": None,
            "distance_to_stop_m": round(dist), "location_threshold_m": threshold}

FAIL_REASONS = {
    "customer_absent": "Khách vắng nhà / không liên lạc được",
    "wrong_address": "Sai địa chỉ / không tìm thấy",
    "refused": "Khách từ chối nhận",
    "damaged": "Hàng hư hỏng",
    "access_restricted": "Không tiếp cận được (cấm đường, khu hạn chế)",
    "out_of_time": "Hết thời gian ca",
    "other": "Lý do khác",
}


def _run(db, run_id):
    run = next((r for r in db["runs"] if r["id"] == run_id), None)
    if not run:
        raise AuthError(404, "Không tìm thấy lần tối ưu")
    return run


def drivers_by_vehicle(db) -> dict:
    return {u["vehicle_id"]: u for u in db.get("users", []) if u["role"] == "driver" and u["active"] and u.get("vehicle_id")}


def publish(actor: dict, run_id: str) -> dict:
    with store.lock:
        db = store.load()
        run = _run(db, run_id)
        if not run["optimized"]["routes"]:
            raise AuthError(400, "Phương án không có tuyến nào để phát hành")
        drivers = drivers_by_vehicle(db)
        missing = [r["vehicle_id"] for r in run["optimized"]["routes"] if r["vehicle_id"] not in drivers]
        previous = (db.get("dispatch") or {}).get("run_id")
        db["dispatch"] = {"run_id": run_id, "published_at": now_iso(), "published_by": actor["username"]}
        run.setdefault("deliveries", {})
        run["published_at"] = db["dispatch"]["published_at"]
        audit(db, actor["username"], "publish_plan", {"run_id": run_id, "replaced": previous, "vehicles_without_driver": missing})
        store.save(db)
    return {**db["dispatch"], "vehicles_without_driver": missing, "replaced_run_id": previous}


def status_board(db: dict) -> dict | None:
    d = db.get("dispatch")
    if not d:
        return None
    run = next((r for r in db["runs"] if r["id"] == d["run_id"]), None)
    if not run:
        return None
    drivers = drivers_by_vehicle(db)
    deliveries = run.get("deliveries", {})
    routes, counts = [], {"pending": 0, "delivered": 0, "failed": 0}
    for r in run["optimized"]["routes"]:
        stops = []
        for s in r["stops"]:
            st = deliveries.get(s["order_id"], {"status": "pending"})
            counts[st["status"]] += 1
            stops.append({**s, **st})
        drv = drivers.get(r["vehicle_id"])
        routes.append({"vehicle_id": r["vehicle_id"], "driver": drv and {"username": drv["username"], "full_name": drv["full_name"]}, "stops": stops})
    return {**d, "routes": routes, "counts": counts, "fail_reasons": FAIL_REASONS}


def driver_route(user: dict) -> dict:
    db = store.load()
    if not user.get("vehicle_id"):
        return {"route": None, "message": "Tài khoản chưa được gán xe — liên hệ quản trị viên"}
    board = status_board(db)
    if not board:
        return {"route": None, "message": "Chưa có tuyến được phát hành"}
    run = _run(db, board["run_id"])
    route = next((r for r in run["optimized"]["routes"] if r["vehicle_id"] == user["vehicle_id"]), None)
    if not route:
        return {"route": None, "message": f'Xe {user["vehicle_id"]} không có tuyến trong kế hoạch đang phát hành'}
    orders = {o["order_id"]: o for o in run["input"]["orders"]}
    deliveries = run.get("deliveries", {})
    stops = [{**s, "address": orders[s["order_id"]]["address"], "weight_kg": orders[s["order_id"]]["weight_kg"],
              "service_time_min": orders[s["order_id"]]["service_time_min"],
              **deliveries.get(s["order_id"], {"status": "pending"})} for s in route["stops"]]
    return {"route": {"run_id": run["id"], "published_at": board["published_at"], "vehicle_id": route["vehicle_id"],
                      "start": route["start"], "end": route["end"], "distance_km": route["distance_km"], "depot": run["depot"], "stops": stops},
            "fail_reasons": FAIL_REASONS}


def record_outcome(user: dict, order_id: str, data: dict) -> dict:
    status = data.get("status")
    if status not in ("delivered", "failed", "pending"):
        raise AuthError(400, "Trạng thái phải là delivered, failed hoặc pending (hoàn tác)")
    reason = data.get("reason")
    if status == "failed" and reason not in FAIL_REASONS:
        raise AuthError(400, "Giao thất bại phải chọn lý do")
    with store.lock:
        db = store.load()
        d = db.get("dispatch")
        if not d:
            raise AuthError(409, "Chưa có tuyến được phát hành")
        run = _run(db, d["run_id"])
        route = next((r for r in run["optimized"]["routes"] if r["vehicle_id"] == user.get("vehicle_id")), None)
        stop = route and next((s for s in route["stops"] if s["order_id"] == order_id), None)
        if not stop:
            raise AuthError(403, "Đơn này không thuộc tuyến của bạn")
        deliveries = run.setdefault("deliveries", {})
        if status == "pending":
            deliveries.pop(order_id, None)
            rec = {"status": "pending"}
        else:
            at = now_iso()
            order = next(o for o in run["input"]["orders"] if o["order_id"] == order_id)
            local = parse_time(data.get("local_time")) if data.get("local_time") else None
            rec = {"status": status, "reason": reason if status == "failed" else None, "reason_label": FAIL_REASONS.get(reason) if status == "failed" else None,
                   "note": (data.get("note") or "")[:500], "recorded_at": at, "recorded_by": user["username"],
                   "planned_arrival": stop["arrival"], "actual_time": data.get("local_time") or None,
                   "on_time": None if local is None or order["tw_end"] is None else local <= order["tw_end"],
                   **location_check(stop, data)}
            deliveries[order_id] = rec
        audit(db, user["username"], "delivery_outcome", {"run_id": run["id"], "order_id": order_id, "status": status, "reason": reason,
                                                         "location_check": rec.get("location_check"), "distance_to_stop_m": rec.get("distance_to_stop_m")})
        store.save(db)
    return rec
