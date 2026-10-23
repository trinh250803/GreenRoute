"""Live driver location sharing (F-10, brought forward for testing).

Location is shared only while the driver has switched sharing on ("Bắt đầu ca") and the
driver page is open — a browser cannot track in the background. Points older than 24 h
are dropped.
"""
import math
import time

from . import store
from .auth import AuthError, audit, now_iso
from .dispatch import drivers_by_vehicle, status_board
from .distance import haversine_km
from .emissions import load_fuel_config, num

MAX_POINTS = 3000
RETAIN_S = 24 * 3600
TRAIL_POINTS = 400


def settings() -> dict:
    t = load_fuel_config().get("tracking", {})
    return {"ping_interval_s": t.get("ping_interval_s", 10), "stale_after_s": t.get("stale_after_s", 300)}


def _vehicle_track(db: dict, user: dict) -> dict:
    vid = user.get("vehicle_id")
    if not vid:
        raise AuthError(400, "Tài khoản chưa được gán xe")
    tracks = db.setdefault("tracking", {})
    tr = tracks.get(vid)
    if not tr or tr.get("driver") != user["username"]:
        # New driver on this vehicle: start a fresh track.
        tr = tracks[vid] = {"driver": user["username"], "sharing": False, "points": [], "last": None, "events": []}
    return tr


def set_sharing(user: dict, on: bool) -> dict:
    with store.lock:
        db = store.load()
        tr = _vehicle_track(db, user)
        if on and not tr.get("sharing"):
            tr["since"] = time.time()
        tr["sharing"] = bool(on)
        tr["events"] = (tr.get("events", []) + [{"at": now_iso(), "event": "start" if on else "stop"}])[-50:]
        audit(db, user["username"], "location_sharing_" + ("on" if on else "off"), {"vehicle_id": user["vehicle_id"]})
        store.save(db)
    return {"sharing": tr["sharing"], **settings()}


def record_points(user: dict, data: dict) -> dict:
    """Accepts one point or a batch {points: [...]} (the phone buffers while offline)."""
    raw = data.get("points") if isinstance(data.get("points"), list) else [data]
    now = time.time()
    pts = []
    for p in raw[:200]:
        lat, lng = num(p.get("latitude")), num(p.get("longitude"))
        if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        ts = num(p.get("ts"))
        ts = ts / 1000 if ts and ts > 1e11 else ts  # accept ms or s
        if not ts or ts > now + 120 or ts < now - RETAIN_S:
            ts = now
        acc, spd, hdg = num(p.get("accuracy_m")), num(p.get("speed_mps")), num(p.get("heading"))
        pts.append({"lat": round(lat, 6), "lng": round(lng, 6), "acc": None if acc is None else round(acc),
                    "spd": None if spd is None or spd < 0 else round(spd, 1), "hdg": None if hdg is None else round(hdg), "ts": round(ts, 1)})
    if not pts:
        raise AuthError(400, "Không có tọa độ hợp lệ")
    with store.lock:
        db = store.load()
        tr = _vehicle_track(db, user)
        if not tr["sharing"]:
            raise AuthError(409, "Chưa bật chia sẻ vị trí (Bắt đầu ca)")
        merged = sorted(tr["points"] + pts, key=lambda x: x["ts"])
        tr["points"] = [p for p in merged if p["ts"] >= now - RETAIN_S][-MAX_POINTS:]
        tr["last"] = tr["points"][-1]
        tr["last_rx"] = now  # server clock: phone clocks can be off
        store.save(db)
    return {"stored": len(pts)}


def _downsample(points: list, n: int) -> list:
    if len(points) <= n:
        return points
    step = math.ceil(len(points) / n)
    return points[::step] + [points[-1]]


def _trail_km(points: list) -> float:
    km = 0.0
    for a, b in zip(points, points[1:]):
        # Ignore jumps from poor fixes (> 150 km/h implied).
        d = haversine_km({"latitude": a["lat"], "longitude": a["lng"]}, {"latitude": b["lat"], "longitude": b["lng"]})
        dt = max(b["ts"] - a["ts"], 1)
        if d / dt * 3600 <= 150:
            km += d
    return km


def board(db: dict) -> dict:
    """Live view for staff: last position, trail and progress per vehicle in the published plan."""
    s = settings()
    now = time.time()
    plan = status_board(db)
    drivers = drivers_by_vehicle(db)
    tracks = db.get("tracking", {})
    vehicles = []
    route_ids = [r["vehicle_id"] for r in plan["routes"]] if plan else []
    for vid in route_ids + [v for v in tracks if v not in route_ids]:
        tr = tracks.get(vid, {})
        drv = drivers.get(vid)
        route = next((r for r in plan["routes"] if r["vehicle_id"] == vid), None) if plan else None
        last = tr.get("last")
        age = None if not last else round(now - last["ts"])
        sharing = bool(tr.get("sharing")) and tr.get("driver") == (drv or {}).get("username")
        since = tr.get("since") or 0
        # Shift just started and the phone has not sent a fix yet: waiting, not "signal lost".
        waiting = sharing and (tr.get("last_rx") or 0) < since and now - since <= s["stale_after_s"]
        stops = route["stops"] if route else []
        nxt = next((x for x in stops if x["status"] == "pending"), None)
        done = sum(1 for x in stops if x["status"] != "pending")
        vehicles.append({
            "vehicle_id": vid,
            "driver": drv and {"username": drv["username"], "full_name": drv["full_name"]},
            "sharing": sharing, "waiting_gps": waiting,
            "last": last, "age_s": age, "stale": not waiting and (age is None or age > s["stale_after_s"]),
            "trail": [[p["lat"], p["lng"]] for p in _downsample(tr.get("points", []), TRAIL_POINTS)],
            "trail_km": round(_trail_km(tr.get("points", [])), 2),
            "stops": [{k: x.get(k) for k in ("order_id", "latitude", "longitude", "arrival", "window", "status")} for x in stops],
            "done": done, "total": len(stops),
            "next_stop": nxt and {"order_id": nxt["order_id"], "arrival": nxt["arrival"],
                                  "distance_km": None if not last else round(haversine_km({"latitude": last["lat"], "longitude": last["lng"]}, nxt), 2)},
        })
    return {"settings": s, "server_time": now, "plan": plan and {k: plan[k] for k in ("run_id", "published_at", "published_by", "counts")},
            "depot": db.get("depot"), "vehicles": vehicles}


def driver_state(user: dict) -> dict:
    tr = store.load().get("tracking", {}).get(user.get("vehicle_id") or "", {})
    mine = tr.get("driver") == user["username"]
    return {"sharing": bool(tr.get("sharing")) and mine, "last": tr.get("last") if mine else None, **settings()}
