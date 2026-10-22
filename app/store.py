"""Minimal JSON-file store. Swap for PostgreSQL behind the same load/save interface when scaling."""
import copy
import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EMPTY = {"depot": None, "orders": [], "vehicles": [], "runs": []}
lock = threading.RLock()


def db_path() -> Path:
    return Path(os.environ.get("DB_PATH") or ROOT / "data" / "db.json")


def load() -> dict:
    try:
        return {**copy.deepcopy(EMPTY), **json.loads(db_path().read_text(encoding="utf-8"))}
    except (FileNotFoundError, json.JSONDecodeError):
        return copy.deepcopy(EMPTY)


def save(db: dict) -> None:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)
