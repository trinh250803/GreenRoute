"""Address search and reverse geocoding through a Photon server (OpenStreetMap data).

Photon is built for search-as-you-type. The default public instance (photon.komoot.io) is
fair-use only, and typed addresses leave our server — for production set GEOCODER_URL to a
self-hosted Photon or a contracted provider (GAPS B5).
"""
import json
import logging
import os
import urllib.parse
import urllib.request
from collections import OrderedDict
from threading import Lock

from .auth import AuthError

log = logging.getLogger("greenroute")
BASE = os.environ.get("GEOCODER_URL", "https://photon.komoot.io").rstrip("/")
VN_BBOX = "102.1,8.4,109.5,23.4"
UA = "GreenRouteAI/0.4 (test environment)"
_cache: "OrderedDict[str, list]" = OrderedDict()
_lock = Lock()


def _get(url: str) -> dict:
    with _lock:
        if url in _cache:
            _cache.move_to_end(url)
            return _cache[url]
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 — any provider failure becomes one clear message
        log.warning("geocoder error: %s", e)
        raise AuthError(502, "Không tra được địa chỉ lúc này — hãy chọn vị trí trên bản đồ hoặc nhập tọa độ")
    with _lock:
        _cache[url] = data
        if len(_cache) > 500:
            _cache.popitem(last=False)
    return data


def _feature(f: dict) -> dict | None:
    p, g = f.get("properties", {}), f.get("geometry", {})
    if p.get("countrycode") not in (None, "VN") or g.get("type") != "Point":
        return None
    lng, lat = g["coordinates"]
    street = " ".join(x for x in (p.get("housenumber"), p.get("street")) if x)
    name = p.get("name") or street
    parts = [name]
    if street and street != name:
        parts.append(street)
    for k in ("locality", "district", "city"):
        if p.get(k) and p[k] not in parts:
            parts.append(p[k])
    return {
        "label": ", ".join(x for x in parts if x), "name": name, "street": street,
        "district": p.get("district") or p.get("county") or "", "city": p.get("city") or p.get("state") or "",
        "latitude": round(lat, 6), "longitude": round(lng, 6), "kind": p.get("osm_value") or p.get("type") or "",
    }


def search(q: str, lat: float | None = None, lon: float | None = None, limit: int = 7) -> list[dict]:
    q = (q or "").strip()
    if len(q) < 3:
        return []
    params = {"q": q[:120], "limit": limit, "bbox": VN_BBOX}
    if lat is not None and lon is not None:
        params.update(lat=round(lat, 4), lon=round(lon, 4))  # bias toward the depot
    data = _get(f"{BASE}/api/?{urllib.parse.urlencode(params)}")
    out, seen = [], set()
    for f in data.get("features", []):
        item = _feature(f)
        if item and item["label"] not in seen:
            seen.add(item["label"])
            out.append(item)
    return out


def reverse(lat: float, lon: float) -> dict | None:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise AuthError(400, "Tọa độ không hợp lệ")
    data = _get(f"{BASE}/reverse?{urllib.parse.urlencode({'lat': round(lat, 6), 'lon': round(lon, 6), 'limit': 1})}")
    feats = [x for x in (_feature(f) for f in data.get("features", [])) if x]
    return feats[0] if feats else None
