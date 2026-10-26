"""Minimal JSON-file store. Swap for PostgreSQL behind the same load/save interface when scaling."""
import copy
import json
import os
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EMPTY = {"depot": None, "orders": [], "vehicles": [], "runs": []}
lock = threading.RLock()


def db_path() -> Path:
    return Path(os.environ.get("DB_PATH") or ROOT / "data" / "db.json")


def _read_text(p: Path) -> str:
    # Windows: the file is briefly locked while save() swaps it in (or a scanner holds it); retry.
    for attempt in range(10):
        try:
            return p.read_text(encoding="utf-8")
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.05 * (attempt + 1))


def load() -> dict:
    try:
        return {**copy.deepcopy(EMPTY), **json.loads(_read_text(db_path()))}
    except (FileNotFoundError, json.JSONDecodeError):
        return copy.deepcopy(EMPTY)


def save(db: dict) -> None:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")
    # Windows: a virus scanner or editor can hold the file for a moment; retry instead of failing the request.
    for attempt in range(10):
        try:
            os.replace(tmp, p)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.05 * (attempt + 1))
