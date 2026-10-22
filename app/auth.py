"""Accounts, sessions and role-based access (mục 3.1, F-11, 12).

Passwords: PBKDF2-SHA256 with per-user salt. Session tokens are random and stored only as
SHA-256 hashes, so a leaked db file does not expose live sessions.
"""
import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import datetime, timezone

from fastapi import Request

from . import store

log = logging.getLogger("greenroute")

ROLES = {
    "admin": "Quản trị hệ thống",
    "dispatcher": "Điều phối viên",
    "fleet_manager": "Quản lý đội xe",
    "ops_manager": "Quản lý vận hành",
    "driver": "Tài xế",
}
STAFF = ("admin", "dispatcher", "fleet_manager", "ops_manager")
SESSION_TTL_S = 12 * 3600
MAX_FAILED = 5
LOCK_S = 5 * 60
PBKDF2_ITER = 200_000
MIN_PASSWORD = 8


class AuthError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, PBKDF2_ITER)
    return f"pbkdf2_sha256${PBKDF2_ITER}${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, it, salt, dk = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(calc.hex(), dk)
    except (ValueError, AttributeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def public_user(u: dict) -> dict:
    return {k: u.get(k) for k in ("username", "full_name", "role", "active", "vehicle_id", "must_change_password", "created_at", "last_login_at")} | \
        {"role_label": ROLES.get(u.get("role"), u.get("role"))}


def audit(db: dict, user: str | None, action: str, detail=None) -> None:
    db.setdefault("audit", []).insert(0, {"at": now_iso(), "user": user, "action": action, "detail": detail})
    db["audit"] = db["audit"][:2000]


def check_password_policy(pw) -> None:
    if not isinstance(pw, str) or len(pw) < MIN_PASSWORD:
        raise AuthError(400, f"Mật khẩu phải có ít nhất {MIN_PASSWORD} ký tự")


def bootstrap_admin() -> None:
    """First start: create the admin account from ADMIN_USERNAME / ADMIN_PASSWORD.
    Without ADMIN_PASSWORD a one-time random password is printed once and must be changed at first login."""
    with store.lock:
        db = store.load()
        if db.get("users"):
            return
        username = os.environ.get("ADMIN_USERNAME") or "admin"
        pw = os.environ.get("ADMIN_PASSWORD")
        generated = not pw
        if generated:
            pw = secrets.token_urlsafe(9)
        db["users"] = [{"username": username, "full_name": "Quản trị hệ thống", "role": "admin", "active": True, "vehicle_id": None,
                        "password_hash": hash_password(pw), "must_change_password": generated, "created_at": now_iso(), "last_login_at": None}]
        audit(db, None, "bootstrap_admin", {"username": username})
        store.save(db)
    if generated:
        print(f"\n*** Tài khoản admin khởi tạo: {username} / {pw}  (bắt buộc đổi mật khẩu khi đăng nhập lần đầu) ***\n", flush=True)


def login(username: str, password: str) -> dict:
    with store.lock:
        db = store.load()
        u = next((x for x in db.get("users", []) if x["username"] == username), None)
        fails = db.setdefault("login_failures", {})
        f = fails.get(username, {"count": 0, "until": 0})
        if f["until"] > time.time():
            raise AuthError(429, "Tài khoản tạm khóa do nhập sai nhiều lần, thử lại sau 5 phút")
        if not u or not verify_password(password or "", u["password_hash"]):
            f["count"] += 1
            if f["count"] >= MAX_FAILED:
                f = {"count": 0, "until": time.time() + LOCK_S}
            fails[username] = f
            audit(db, username, "login_failed")
            store.save(db)
            raise AuthError(401, "Sai tên đăng nhập hoặc mật khẩu")
        if not u["active"]:
            raise AuthError(403, "Tài khoản đã bị khóa")
        fails.pop(username, None)
        token = secrets.token_urlsafe(32)
        sessions = {k: s for k, s in db.setdefault("sessions", {}).items() if s["expires"] > time.time()}
        sessions[_token_hash(token)] = {"username": username, "expires": time.time() + SESSION_TTL_S}
        db["sessions"] = sessions
        u["last_login_at"] = now_iso()
        audit(db, username, "login")
        store.save(db)
        return {"token": token, "user": public_user(u)}


def logout(token: str) -> None:
    with store.lock:
        db = store.load()
        db.get("sessions", {}).pop(_token_hash(token), None)
        store.save(db)


def _token(request: Request) -> str | None:
    h = request.headers.get("authorization", "")
    return h[7:] if h.lower().startswith("bearer ") else None


def current_user(request: Request) -> dict:
    token = _token(request)
    if not token:
        raise AuthError(401, "Chưa đăng nhập")
    db = store.load()
    s = db.get("sessions", {}).get(_token_hash(token))
    if not s or s["expires"] < time.time():
        raise AuthError(401, "Phiên đăng nhập hết hạn")
    u = next((x for x in db.get("users", []) if x["username"] == s["username"]), None)
    if not u or not u["active"]:
        raise AuthError(401, "Tài khoản không còn hiệu lực")
    request.state.token = token
    return u


def require(*roles: str):
    """FastAPI dependency: logged-in user with one of `roles`. A user who must change
    their password can only reach the change-password endpoint."""
    def dep(request: Request) -> dict:
        u = current_user(request)
        if u.get("must_change_password"):
            raise AuthError(403, "Cần đổi mật khẩu trước khi tiếp tục")
        if roles and u["role"] not in roles:
            raise AuthError(403, "Bạn không có quyền thực hiện thao tác này")
        return u
    return dep


def change_password(user: dict, old: str, new: str) -> None:
    check_password_policy(new)
    with store.lock:
        db = store.load()
        u = next(x for x in db["users"] if x["username"] == user["username"])
        if not verify_password(old or "", u["password_hash"]):
            raise AuthError(400, "Mật khẩu hiện tại không đúng")
        if old == new:
            raise AuthError(400, "Mật khẩu mới phải khác mật khẩu cũ")
        u["password_hash"] = hash_password(new)
        u["must_change_password"] = False
        audit(db, u["username"], "change_password")
        store.save(db)


def create_user(actor: dict, data: dict) -> dict:
    username = str(data.get("username") or "").strip()
    if not username or not all(c.isalnum() or c in "._-" for c in username):
        raise AuthError(400, "Tên đăng nhập chỉ gồm chữ, số và . _ -")
    if data.get("role") not in ROLES:
        raise AuthError(400, f"Vai trò không hợp lệ ({', '.join(ROLES)})")
    check_password_policy(data.get("password"))
    with store.lock:
        db = store.load()
        if any(u["username"] == username for u in db.get("users", [])):
            raise AuthError(409, "Tên đăng nhập đã tồn tại")
        _check_vehicle(db, data.get("role"), data.get("vehicle_id"), username)
        u = {"username": username, "full_name": data.get("full_name") or username, "role": data["role"], "active": True,
             "vehicle_id": data.get("vehicle_id") or None if data["role"] == "driver" else None,
             "password_hash": hash_password(data["password"]), "must_change_password": True,
             "created_at": now_iso(), "last_login_at": None}
        db.setdefault("users", []).append(u)
        audit(db, actor["username"], "create_user", {"username": username, "role": u["role"], "vehicle_id": u["vehicle_id"]})
        store.save(db)
        return public_user(u)


def _check_vehicle(db, role, vehicle_id, username):
    if role != "driver" or not vehicle_id:
        return
    if not any(v["vehicle_id"] == vehicle_id for v in db["vehicles"]):
        raise AuthError(400, f'Xe "{vehicle_id}" không tồn tại')
    other = next((u for u in db["users"] if u.get("vehicle_id") == vehicle_id and u["username"] != username and u["active"]), None)
    if other:
        raise AuthError(409, f'Xe "{vehicle_id}" đã gán cho tài xế {other["username"]}')


def update_user(actor: dict, username: str, data: dict) -> dict:
    with store.lock:
        db = store.load()
        u = next((x for x in db.get("users", []) if x["username"] == username), None)
        if not u:
            raise AuthError(404, "Không tìm thấy tài khoản")
        before = public_user(u)
        role = data.get("role", u["role"])
        if role not in ROLES:
            raise AuthError(400, "Vai trò không hợp lệ")
        active = bool(data.get("active", u["active"]))
        if u["role"] == "admin" and (role != "admin" or not active):
            if sum(1 for x in db["users"] if x["role"] == "admin" and x["active"]) <= 1:
                raise AuthError(400, "Không thể bỏ quyền/khóa admin cuối cùng")
        vehicle_id = (data.get("vehicle_id", u.get("vehicle_id")) or None) if role == "driver" else None
        _check_vehicle(db, role, vehicle_id, username)
        u.update(role=role, active=active, vehicle_id=vehicle_id, full_name=data.get("full_name", u["full_name"]))
        if data.get("password"):
            check_password_policy(data["password"])
            u["password_hash"] = hash_password(data["password"])
            u["must_change_password"] = True
        if not active or data.get("password"):
            db["sessions"] = {k: s for k, s in db.get("sessions", {}).items() if s["username"] != username}
        audit(db, actor["username"], "update_user", {"username": username, "before": {k: before[k] for k in ("role", "active", "vehicle_id")},
                                                   "after": {"role": role, "active": active, "vehicle_id": vehicle_id},
                                                   "password_reset": bool(data.get("password"))})
        store.save(db)
        return public_user(u)
