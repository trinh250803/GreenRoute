"""Admin-editable system configuration with versioning (Phụ lục 1 §4, Phụ lục 2 §5, mục 6.2).

The shipped config/fuels.json is the factory default. Admin edits are written to
data/fuels_active.json; every change bumps the version and records who/when/why/old/new.
"""
import copy
import json
import re
from datetime import datetime, timezone

from . import store
from .auth import AuthError, audit, now_iso
from .emissions import active_config_path, load_fuel_config, num

# Editable leaf paths. '*' matches any existing key at that level.
EDITABLE = {
    r"fuels\.[^.]+\.price_vnd": "number",
    r"fuels\.[^.]+\.price_source": "text",
    r"fuels\.[^.]+\.price_date": "text",
    r"fuels\.[^.]+\.ethanol_share_volume": "share",
    r"fuels\.[^.]+\.status": ("supported", "simulation", "unverified"),
    r"fuels\.[^.]+\.official": "bool",
    r"base_factors\.[^.]+\.value": "number",
    r"base_factors\.[^.]+\.source": "text",
    r"base_factors\.[^.]+\.year": "year",
    r"base_factors\.[^.]+\.geography": "text",
    r"vehicle_types\.[^.]+\.speed_kmh": "positive",
    r"routing\.detour_factor": "positive",
    r"default_weights\.co2_vnd_per_kg": "number",
    r"default_weights\.time_vnd_per_min": "number",
    r"default_weights\.time_limit_s": "limit",
    r"delivery_check\.max_distance_m": "positive",
    r"tracking\.ping_interval_s": "positive",
    r"tracking\.stale_after_s": "positive",
    r"traffic\.peak_speed_factor": "share",
    r"order_defaults\.window_start": "time",
    r"order_defaults\.window_end": "time",
    r"order_defaults\.service_time_min": "number",
    r"electricity_price_sources\.[^.]+\.price_vnd": "number",
    r"electricity_price_sources\.[^.]+\.price_source": "text",
    r"electricity_price_sources\.[^.]+\.price_date": "text",
    r"costs\.driver_vnd_per_hour": "number",
    r"illustrative": "bool",
    r"illustrative_note": "text",
}


def _kind(path: str):
    for pat, kind in EDITABLE.items():
        if re.fullmatch(pat, path):
            return kind
    return None


def _coerce(path: str, kind, value):
    if isinstance(kind, tuple):
        if value not in kind:
            raise AuthError(400, f"{path}: giá trị phải là một trong {', '.join(kind)}")
        return value
    if kind == "bool":
        if not isinstance(value, bool):
            raise AuthError(400, f"{path}: phải là true/false")
        return value
    if kind == "text":
        return str(value).strip()
    if kind == "time":
        v = str(value).strip()
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise AuthError(400, f"{path}: giờ dạng HH:MM")
        return v
    n = num(value)
    if n is None or n < 0:
        raise AuthError(400, f"{path}: phải là số ≥ 0")
    if kind == "share" and n > 1:
        raise AuthError(400, f"{path}: tỷ lệ ethanol trong khoảng 0–1")
    if kind == "positive" and n <= 0:
        raise AuthError(400, f"{path}: phải > 0")
    if kind == "year":
        if not 1990 <= n <= 2100:
            raise AuthError(400, f"{path}: năm không hợp lệ")
        return int(n)
    if kind == "limit" and not 1 <= n <= 60:
        raise AuthError(400, f"{path}: giới hạn thời gian 1–60 giây")
    return n


def _get(cfg: dict, path: str):
    node = cfg
    for k in path.split("."):
        if not isinstance(node, dict) or k not in node:
            return KeyError
        node = node[k]
    return node


def _set(cfg: dict, path: str, value):
    keys = path.split(".")
    node = cfg
    for k in keys[:-1]:
        node = node[k]
    node[keys[-1]] = value


def update_config(actor: dict, changes: dict, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AuthError(400, "Bắt buộc ghi lý do thay đổi (ví dụ: nguồn hệ số, quyết định phê duyệt)")
    if not isinstance(changes, dict):
        raise AuthError(400, "changes phải là đối tượng {đường_dẫn: giá_trị}")
    if not changes:
        raise AuthError(400, "Không có thay đổi")
    cfg = load_fuel_config()
    new = copy.deepcopy(cfg)
    diff = []
    for path, value in changes.items():
        kind = _kind(path)
        if kind is None:
            raise AuthError(400, f"Không được phép sửa '{path}'")
        old = _get(new, path)
        if old is KeyError and not path.startswith(("default_weights.", "delivery_check.", "tracking.", "order_defaults.")):
            raise AuthError(400, f"Không tồn tại '{path}'")
        v = _coerce(path, kind, value)
        if old == v:
            continue
        if "." in path:
            new.setdefault(path.split(".")[0], {})
        _set(new, path, v)
        diff.append({"path": path, "old": None if old is KeyError else old, "new": v})
    if not diff:
        raise AuthError(400, "Giá trị mới trùng giá trị hiện tại")

    with store.lock:
        db = store.load()
        history = db.setdefault("config_history", [])
        new["version"] = f"{datetime.now(timezone.utc):%Y.%m.%d}-r{len(history) + 1}"
        new["updated_at"], new["updated_by"] = now_iso(), actor["username"]
        p = active_config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
        entry = {"version": new["version"], "previous_version": cfg.get("version"), "at": new["updated_at"],
                 "user": actor["username"], "reason": reason.strip(), "changes": diff}
        history.insert(0, entry)
        audit(db, actor["username"], "update_config", {"version": new["version"], "changes": len(diff)})
        store.save(db)
    return {"config": new, "change": entry}
