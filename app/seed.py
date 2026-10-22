"""Test-phase seeding for hosts without persistent disk (e.g. Render free tier).

When SEED_ACCOUNTS_JSON is set and the store holds no vehicles yet, load the synthetic
sample data and create the listed accounts. Passwords come only from the environment
(a host secret), never from the repository.

SEED_ACCOUNTS_JSON = [{"username": "...", "password": "...", "role": "...", "full_name": "...", "vehicle_id": "..."}]
"""
import json
import logging
import os
from pathlib import Path

from . import auth, store
from .emissions import load_fuel_config
from .io_files import parse_csv
from .validation import validate_orders, validate_vehicles

log = logging.getLogger("greenroute")


def parse_accounts(raw: str):
    """Tolerate common paste mistakes from a dashboard: a leading 'SEED_ACCOUNTS_JSON=',
    or objects pasted without the surrounding [ ]."""
    raw = raw.strip()
    if raw.startswith("SEED_ACCOUNTS_JSON="):
        raw = raw[len("SEED_ACCOUNTS_JSON="):].strip()
    for candidate in (raw, f"[{raw}]"):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            data = [data]
        if isinstance(data, list) and all(isinstance(a, dict) for a in data):
            return data
    return None


def seed_from_env() -> None:
    raw = os.environ.get("SEED_ACCOUNTS_JSON")
    if not raw:
        return
    accounts = parse_accounts(raw)
    if accounts is None:
        log.error("SEED_ACCOUNTS_JSON không phải JSON hợp lệ — bỏ qua seed")
        return
    with store.lock:
        db = store.load()
        if db["vehicles"]:
            return
        d = Path(__file__).resolve().parent.parent / "data" / "sample"
        db["depot"] = json.loads((d / "depot.json").read_text(encoding="utf-8"))
        db["orders"] = validate_orders(parse_csv((d / "orders.csv").read_text(encoding="utf-8")))["valid"]
        db["vehicles"] = validate_vehicles(parse_csv((d / "vehicles.csv").read_text(encoding="utf-8")), load_fuel_config())["valid"]
        existing = {u["username"] for u in db.get("users", [])}
        for a in accounts:
            if a.get("username") in existing or a.get("role") not in auth.ROLES or len(a.get("password") or "") < auth.MIN_PASSWORD:
                continue
            db.setdefault("users", []).append({
                "username": a["username"], "full_name": a.get("full_name") or a["username"], "role": a["role"], "active": True,
                "vehicle_id": a.get("vehicle_id") if a["role"] == "driver" else None,
                "password_hash": auth.hash_password(a["password"]), "must_change_password": False,
                "created_at": auth.now_iso(), "last_login_at": None})
        auth.audit(db, None, "seed_test_data", {"accounts": [a.get("username") for a in accounts]})
        store.save(db)
    log.warning("Đã nạp dữ liệu minh họa và %d tài khoản test từ SEED_ACCOUNTS_JSON", len(accounts))

