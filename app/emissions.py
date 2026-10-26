"""Energy, cost and CO2 calculations (Phụ lục 1 §3, Phụ lục 2 §2).

Factors and prices come from config/fuels.json — never hard-coded here.
Missing consumption or factor yields None plus a warning, never an invented number.
"""
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def config_path() -> Path:
    """Factory default shipped with the code."""
    return Path(os.environ.get("FUELS_CONFIG") or ROOT / "config" / "fuels.json")


def active_config_path() -> Path:
    """Admin-edited copy, stored next to the database."""
    from .store import db_path
    return db_path().parent / "fuels_active.json"


def load_fuel_config() -> dict:
    p = active_config_path()
    return json.loads((p if p.exists() else config_path()).read_text(encoding="utf-8"))


def num(v):
    """'' / None / non-numeric → None; otherwise float."""
    if v is None or v == "" or isinstance(v, bool):
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def rnd(v, d):
    return None if v is None else round(v + 0.0, d)


def resolve_factor(fuel_code: str, cfg: dict, override: dict | None = None) -> dict:
    """EF_blend ≈ (1 − x)·EF_gasoline + x·EF_ethanol. A vehicle-level admin override always wins."""
    override = override or {}
    fuel = cfg["fuels"].get(fuel_code)
    if not fuel:
        return {"value": None, "warnings": [f'Nhiên liệu "{fuel_code}" chưa được cấu hình']}

    ov = num(override.get("emission_factor_value"))
    if ov is not None:
        return {
            "value": ov,
            "unit": override.get("emission_factor_unit") or ("kg CO2/kWh" if fuel["kind"] == "electric" else "kg CO2/L"),
            "fossil_share": 1, "biogenic_share": 0,
            "source": override.get("factor_source") or "Người dùng nhập", "year": override.get("factor_year"),
            "official": False, "warnings": ["Hệ số do người dùng nhập — cần đối chiếu nguồn"],
        }

    base = cfg["base_factors"]
    if fuel["kind"] == "electric" or fuel.get("factor_key"):
        f = base[fuel["factor_key"]]
        return {"value": f["value"], "unit": f["unit"], "fossil_share": 1, "biogenic_share": 0,
                "source": f["source"], "year": f["year"], "official": fuel["official"], "warnings": []}

    if fuel["status"] == "unverified":
        return {"value": None, "warnings": [f'{fuel["label"]}: chưa có hệ số phát thải đáng tin cậy — quản trị viên cần nhập hệ số']}

    x = fuel["ethanol_share_volume"]
    g, e = base["gasoline"], base["ethanol"]
    fossil, bio = (1 - x) * g["value"], x * e["value"]
    value = fossil + bio
    warnings = []
    if fuel["status"] == "simulation":
        warnings.append(f'{fuel["label"]}: hệ số ước tính theo tỷ lệ thể tích — chỉ dùng mô phỏng, không phải số chính thức')
    return {
        "value": value, "unit": "kg CO2/L", "fossil_share": fossil / value, "biogenic_share": bio / value,
        "source": f"Pha trộn {x * 100:.0f}% ethanol: (1−x)·EF_xăng + x·EF_ethanol", "year": g["year"],
        "official": fuel["official"], "warnings": warnings,
    }


ELECTRICITY_CUSTOM = "custom"


def resolve_price(vehicle: dict, cfg: dict) -> dict:
    """Energy price for a vehicle: its own price > its electricity price source > the fuel's default.
    Never invents a number: a chosen source without a price gives None and a warning."""
    fuel = cfg["fuels"].get(vehicle.get("fuel_blend_code")) or {}
    own = num(vehicle.get("fuel_price"))
    if own is not None:
        return {"price": own, "source": "Giá nhập riêng cho xe", "warning": None}
    key = vehicle.get("electricity_price_source")
    if fuel.get("kind") == "electric" and key:
        if key == ELECTRICITY_CUSTOM:
            return {"price": None, "source": "Tự nhập", "warning": "chọn nguồn giá điện “Tự nhập” nhưng chưa nhập giá"}
        src = (cfg.get("electricity_price_sources") or {}).get(key)
        if src:
            p = num(src.get("price_vnd"))
            return {"price": p, "source": src["label"],
                    "warning": None if p is not None else f'nguồn giá điện “{src["label"]}” chưa có giá — quản trị viên cần nhập'}
    p = num(fuel.get("price_vnd"))
    return {"price": p, "source": fuel.get("price_source"),
            "warning": None if p is not None else f'chưa có giá {fuel.get("label", "")} — không tính chi phí năng lượng'}


def compute_trip(distance_km: float, vehicle: dict, cfg: dict) -> dict:
    fuel_code = vehicle.get("fuel_blend_code")
    fuel = cfg["fuels"].get(fuel_code)
    vid = vehicle.get("vehicle_id")
    warnings: list[str] = []
    out = {
        "distance_km": rnd(distance_km, 3), "fuel_blend_code": fuel_code,
        "energy_amount": None, "energy_unit": None, "energy_cost_vnd": None,
        "co2_direct_kg": None, "co2_fossil_kg": None, "co2_biogenic_kg": None, "co2_grid_indirect_kg": None,
        "factor": None, "warnings": warnings,
    }
    if not fuel:
        warnings.append(f'Xe {vid}: nhiên liệu "{fuel_code}" không hợp lệ')
        return out
    rate = num(vehicle.get("consumption_rate"))
    if rate is None:
        warnings.append(f"Xe {vid}: thiếu mức tiêu hao — không tính được năng lượng/phát thải")
        return out

    amount = distance_km * rate / 100
    out["energy_amount"] = rnd(amount, 4)
    out["energy_unit"] = "kWh" if fuel["kind"] == "electric" else "L"
    pr = resolve_price(vehicle, cfg)
    price = pr["price"]
    out["price_used"] = price
    out["price_source_used"] = pr["source"]
    if price is None:
        warnings.append(f'Xe {vid}: {pr["warning"]}')
    else:
        out["energy_cost_vnd"] = round(amount * price)

    f = resolve_factor(fuel_code, cfg, vehicle)
    warnings.extend(f"Xe {vid}: {w}" for w in f.get("warnings", []))
    if f["value"] is None:
        return out
    out["factor"] = {"value": rnd(f["value"], 4), "unit": f["unit"], "source": f["source"], "year": f["year"], "official": f["official"]}

    if fuel["kind"] == "electric":
        out.update(co2_direct_kg=0, co2_fossil_kg=0, co2_biogenic_kg=0, co2_grid_indirect_kg=rnd(amount * f["value"], 4))
    else:
        total = amount * f["value"]
        out.update(co2_direct_kg=rnd(total, 4), co2_fossil_kg=rnd(total * f["fossil_share"], 4),
                   co2_biogenic_kg=rnd(total * f["biogenic_share"], 4), co2_grid_indirect_kg=0)
    return out


def check_compatibility(vehicle_type: str, fuel_code: str, cfg: dict, confirmed: bool = False) -> dict:
    vt = cfg["vehicle_types"].get(vehicle_type)
    if not vt:
        return {"ok": False, "reason": f'Loại xe "{vehicle_type}" chưa được cấu hình'}
    if fuel_code not in cfg["fuels"]:
        return {"ok": False, "reason": f'Nhiên liệu "{fuel_code}" chưa được cấu hình'}
    if fuel_code in vt["allowed"]:
        return {"ok": True}
    if fuel_code in vt["simulation_allowed"]:
        if confirmed:
            return {"ok": True, "simulation": True}
        return {"ok": False, "needs_confirmation": True, "reason": f'{vt["label"]} + {fuel_code} chỉ dùng mô phỏng — cần xác nhận'}
    return {"ok": False, "reason": f'{vt["label"]} không tương thích với {cfg["fuels"][fuel_code]["label"]}'}
