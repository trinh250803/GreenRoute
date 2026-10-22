"""Input validation (mục 5.1–5.3). Never invents coordinates for un-geocoded addresses."""
import math
import re

from .emissions import check_compatibility, num

_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")
INVALID = float("nan")


def parse_time(v):
    """'08:30' | 510 → minutes since midnight; None if empty; NaN if invalid."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    m = _TIME.match(str(v).strip())
    if not m:
        return INVALID
    h, mi = int(m[1]), int(m[2])
    return float(h * 60 + mi) if h < 24 and mi < 60 else INVALID


def fmt_time(minutes):
    if minutes is None:
        return ""
    h, m = int(minutes // 60), int(round(minutes % 60))
    if m == 60:
        h, m = h + 1, 0
    return f"{h:02d}:{m:02d}"


def _isnan(v):
    return v is not None and math.isnan(v)


def truthy(v) -> bool:
    return v is True or v == 1 or str(v).strip().lower() in {"true", "1", "yes", "y", "có", "x"}


def validate_orders(rows: list[dict]) -> dict:
    errors, warnings, valid = [], [], []
    seen = set()
    for idx, r in enumerate(rows):
        line = idx + 1
        oid = str(r.get("order_id") or "").strip()
        errs = []
        if not oid:
            errs.append("thiếu order_id")
        elif oid in seen:
            errs.append(f'order_id "{oid}" bị trùng')
        if oid:
            seen.add(oid)

        lat, lng = num(r.get("latitude")), num(r.get("longitude"))
        if lat is None or lng is None:
            errs.append(f'địa chỉ "{r["address"]}" chưa định vị được (cần tọa độ hoặc geocoding)' if r.get("address") else "thiếu tọa độ/địa chỉ")
        elif not (-90 <= lat <= 90 and -180 <= lng <= 180):
            errs.append("tọa độ ngoài phạm vi")

        if r.get("weight_kg") not in (None, "") and num(r.get("weight_kg")) is None:
            errs.append("weight_kg không phải số")
        weight = num(r.get("weight_kg")) or 0.0
        volume = num(r.get("volume_m3")) or 0.0
        if weight < 0:
            errs.append("weight_kg âm")
        if volume < 0:
            errs.append("volume_m3 âm")
        if num(r.get("volume_m3")) is None:
            warnings.append({"line": line, "order_id": oid, "message": "thiếu volume_m3 — bỏ qua kiểm tra thể tích cho đơn này"})

        ws, we = parse_time(r.get("delivery_window_start")), parse_time(r.get("delivery_window_end"))
        if _isnan(ws) or _isnan(we):
            errs.append("khung giờ sai định dạng (HH:MM)")
        elif ws is not None and we is not None and we <= ws:
            errs.append("giờ kết thúc phải sau giờ bắt đầu")

        service = num(r.get("service_time_min"))
        service = 5.0 if service is None else service
        if service < 0:
            errs.append("service_time_min âm")

        if errs:
            errors.append({"line": line, "order_id": oid or None, "errors": errs})
            continue
        valid.append({
            "order_id": oid, "address": r.get("address") or "", "latitude": lat, "longitude": lng,
            "weight_kg": weight, "volume_m3": volume, "tw_start": ws, "tw_end": we,
            "service_time_min": service, "priority": num(r.get("priority")) or 0,
        })
    return {"valid": valid, "errors": errors, "warnings": warnings}


def validate_vehicles(rows: list[dict], cfg: dict) -> dict:
    errors, warnings, valid = [], [], []
    seen = set()
    types = cfg["vehicle_types"]
    for idx, r in enumerate(rows):
        line = idx + 1
        vid = str(r.get("vehicle_id") or "").strip()
        errs = []
        if not vid:
            errs.append("thiếu vehicle_id")
        elif vid in seen:
            errs.append(f'vehicle_id "{vid}" bị trùng')
        if vid:
            seen.add(vid)

        vtype = str(r.get("vehicle_type") or "").strip()
        if vtype not in types:
            errs.append(f'vehicle_type "{vtype}" không hợp lệ ({", ".join(types)})')
        cap_w = num(r.get("capacity_weight_kg"))
        if cap_w is None or cap_w <= 0:
            errs.append("capacity_weight_kg phải > 0")
        cap_v = num(r.get("capacity_volume_m3"))
        if cap_v is not None and cap_v <= 0:
            errs.append("capacity_volume_m3 phải > 0")
        cpk = num(r.get("cost_per_km"))
        if cpk is None or cpk < 0:
            errs.append("cost_per_km phải ≥ 0 (chi phí ngoài năng lượng: khấu hao, bảo dưỡng, nhân công…)")

        fuel = str(r.get("fuel_blend_code") or r.get("energy_type") or "").strip()
        if vtype in types:
            c = check_compatibility(vtype, fuel, cfg, truthy(r.get("confirm_simulation_fuel")))
            if not c["ok"]:
                errs.append(c["reason"])
        if num(r.get("consumption_rate")) is None:
            warnings.append({"line": line, "vehicle_id": vid, "message": "thiếu consumption_rate — sẽ không tính phát thải/chi phí năng lượng"})

        st = parse_time(r.get("start_time") if r.get("start_time") not in (None, "") else "07:00")
        et = parse_time(r.get("end_time") if r.get("end_time") not in (None, "") else "19:00")
        if _isnan(st) or _isnan(et) or et <= st:
            errs.append("start_time/end_time không hợp lệ")

        if errs:
            errors.append({"line": line, "vehicle_id": vid or None, "errors": errs})
            continue
        avail = r.get("available")
        valid.append({
            "vehicle_id": vid, "vehicle_type": vtype,
            "capacity_weight_kg": cap_w, "capacity_volume_m3": cap_v,
            "cost_per_km": cpk, "fixed_cost_vnd": num(r.get("fixed_cost_vnd")) or 0,
            "fuel_blend_code": fuel, "consumption_rate": num(r.get("consumption_rate")),
            "fuel_price": num(r.get("fuel_price")),
            "emission_factor_value": num(r.get("emission_factor_value")),
            "emission_factor_unit": r.get("emission_factor_unit") or None,
            "factor_source": r.get("factor_source") or None, "factor_year": num(r.get("factor_year")),
            "confirm_simulation_fuel": truthy(r.get("confirm_simulation_fuel")),
            "available": True if avail in (None, "") else truthy(avail),
            "start_time": st, "end_time": et,
            "speed_kmh": num(r.get("speed_kmh")) or types[vtype]["speed_kmh"],
        })
    return {"valid": valid, "errors": errors, "warnings": warnings}
