"""Distance matrix (km). OSRM /table when OSRM_URL is set, otherwise haversine × detour factor."""
import json
import math
import os
import urllib.request


def haversine_km(a: dict, b: dict) -> float:
    r = math.pi / 180
    dlat = (b["latitude"] - a["latitude"]) * r
    dlng = (b["longitude"] - a["longitude"]) * r
    s = math.sin(dlat / 2) ** 2 + math.cos(a["latitude"] * r) * math.cos(b["latitude"] * r) * math.sin(dlng / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(s))


def haversine_matrix(points: list[dict], cfg: dict) -> dict:
    k = cfg["routing"]["detour_factor"]
    return {"matrix": [[haversine_km(a, b) * k for b in points] for a in points],
            "source": "haversine_estimate",
            "note": f"Fallback: khoảng cách ≈ đường chim bay × {k} (ước tính, chưa theo đường thực tế). Bản chính thức dùng OSRM."}


def build_distance_matrix(points: list[dict], cfg: dict) -> dict:
    osrm = os.environ.get("OSRM_URL")
    if not osrm:
        return haversine_matrix(points, cfg)
    try:
        coords = ";".join(f'{p["longitude"]},{p["latitude"]}' for p in points)
        with urllib.request.urlopen(f"{osrm.rstrip('/')}/table/v1/driving/{coords}?annotations=distance", timeout=30) as res:
            body = json.load(res)
        if body.get("code") != "Ok":
            raise RuntimeError(f'OSRM {body.get("code")}')
        matrix = [[(m / 1000 if m is not None else math.inf) for m in row] for row in body["distances"]]
        return {"matrix": matrix, "source": "osrm", "note": f"OSRM {osrm}"}
    except Exception as e:  # noqa: BLE001 — any OSRM failure falls back, and is reported
        return {**haversine_matrix(points, cfg), "fallback_reason": f"OSRM lỗi ({e}) — dùng ước tính"}
