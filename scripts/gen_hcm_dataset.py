"""Generate the synthetic HCMC dataset in data/sample_hcm (deterministic).

Everything here is illustrative: street names are real, house numbers, customers and
phone numbers are invented. Phones use the retired 0120 prefix so they cannot reach anyone.
Run: python scripts/gen_hcm_dataset.py
"""
import csv
import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "sample_hcm"
rng = random.Random(2026)

DEPOT = {"name": "Kho Tân Bình (minh họa)", "latitude": 10.8015, "longitude": 106.6527}

# district: (center lat, center lng, spread deg, streets, share of orders)
DISTRICTS = {
    "Quận 1": (10.7769, 106.7009, 0.010, ["Lê Lợi", "Nguyễn Huệ", "Hai Bà Trưng", "Pasteur", "Lý Tự Trọng", "Nguyễn Thị Minh Khai"], 14),
    "Quận 3": (10.7843, 106.6844, 0.010, ["Võ Văn Tần", "Nam Kỳ Khởi Nghĩa", "Cách Mạng Tháng 8", "Lê Văn Sỹ", "Trần Quốc Thảo"], 12),
    "Quận 4": (10.7579, 106.7013, 0.007, ["Khánh Hội", "Hoàng Diệu", "Tôn Đản", "Đoàn Văn Bơ"], 6),
    "Quận 5": (10.7540, 106.6634, 0.009, ["Trần Hưng Đạo", "Nguyễn Trãi", "An Dương Vương", "Châu Văn Liêm"], 10),
    "Quận 7": (10.7340, 106.7215, 0.014, ["Nguyễn Thị Thập", "Huỳnh Tấn Phát", "Nguyễn Văn Linh", "Lê Văn Lương"], 10),
    "Quận 8": (10.7240, 106.6286, 0.012, ["Phạm Thế Hiển", "Dương Bá Trạc", "Tạ Quang Bửu"], 6),
    "Quận 10": (10.7746, 106.6670, 0.008, ["3 Tháng 2", "Sư Vạn Hạnh", "Thành Thái", "Tô Hiến Thành"], 12),
    "Bình Thạnh": (10.8106, 106.7091, 0.013, ["Xô Viết Nghệ Tĩnh", "Điện Biên Phủ", "Bạch Đằng", "Phan Văn Trị", "Nơ Trang Long"], 14),
    "Phú Nhuận": (10.7991, 106.6802, 0.008, ["Phan Xích Long", "Hoàng Văn Thụ", "Phan Đình Phùng", "Nguyễn Kiệm"], 10),
    "Tân Bình": (10.8015, 106.6527, 0.011, ["Cộng Hòa", "Trường Chinh", "Hoàng Hoa Thám", "Lạc Long Quân", "Bàu Cát"], 14),
    "Tân Phú": (10.7900, 106.6283, 0.010, ["Lũy Bán Bích", "Tân Sơn Nhì", "Âu Cơ", "Thoại Ngọc Hầu"], 8),
    "Gò Vấp": (10.8387, 106.6653, 0.014, ["Quang Trung", "Nguyễn Oanh", "Phan Văn Trị", "Lê Đức Thọ"], 12),
    "Bình Tân": (10.7653, 106.6031, 0.014, ["Tên Lửa", "Kinh Dương Vương", "Lê Văn Quới"], 6),
    "Thủ Đức": (10.8494, 106.7537, 0.018, ["Võ Văn Ngân", "Kha Vạn Cân", "Lê Văn Việt", "Đặng Văn Bi"], 6),
}

LAST = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"]
MID = ["Văn", "Thị", "Minh", "Ngọc", "Thanh", "Đức", "Quốc", "Hoàng", "Thu", "Gia"]
FIRST = ["An", "Bình", "Chi", "Dũng", "Giang", "Hà", "Hải", "Hùng", "Khánh", "Lan", "Linh", "Long", "Mai", "Nam", "Nhung",
         "Phong", "Phúc", "Quân", "Tâm", "Thảo", "Trang", "Tuấn", "Uyên", "Vy", "Yến"]
NOTES = ["", "", "", "", "Gọi trước khi giao", "Giao giờ hành chính", "Để ở bảo vệ tòa nhà", "Hàng dễ vỡ", "Không giao trưa 12h–13h", "Thu tiền COD"]

# (weight range kg, volume range m3, share)
PARCELS = [((0.3, 3), (0.002, 0.02), 55), ((3, 10), (0.02, 0.06), 25), ((10, 30), (0.05, 0.15), 14), ((40, 120), (0.2, 0.8), 6)]
WINDOWS = [None] * 12 + [("08:00", "11:00")] * 3 + [("09:00", "12:00")] * 2 + [("11:00", "14:00")] * 2 + [("13:30", "17:00")] * 3 + [("16:00", "19:00")] * 2


def pick(weighted):
    total = sum(w[-1] for w in weighted)
    x = rng.uniform(0, total)
    for item in weighted:
        x -= item[-1]
        if x <= 0:
            return item
    return weighted[-1]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "depot.json").write_text(json.dumps(DEPOT, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rows = []
    district_list = [(name, *v) for name, v in DISTRICTS.items()]
    for i in range(1, 151):
        name, lat, lng, spread, streets, _ = pick([(d[0], d[1], d[2], d[3], d[4], d[5]) for d in district_list])
        (wlo, whi), (vlo, vhi), _ = pick(PARCELS)
        win = rng.choice(WINDOWS)
        rows.append({
            "order_id": f"HCM{i:03d}",
            "customer_name": f"{rng.choice(LAST)} {rng.choice(MID)} {rng.choice(FIRST)}",
            "phone": f"0120{rng.randint(0, 999999):06d}",
            "address": f"{rng.randint(1, 450)} {rng.choice(streets)}, {name} (minh họa)",
            "latitude": round(lat + rng.uniform(-spread, spread), 5),
            "longitude": round(lng + rng.uniform(-spread, spread), 5),
            "weight_kg": round(rng.uniform(wlo, whi), 1),
            "volume_m3": round(rng.uniform(vlo, vhi), 3),
            "delivery_window_start": win[0] if win else "",
            "delivery_window_end": win[1] if win else "",
            "service_time_min": rng.choice([3, 4, 5, 5, 6, 8, 10]),
            "priority": 1 if rng.random() < 0.1 else 0,
            "note": rng.choice(NOTES),
        })
    # One deliberately oversize order to demonstrate the "exceeds every vehicle" warning.
    rows.append({"order_id": "HCM151", "customer_name": "Công ty Minh Họa", "phone": "0120000151",
                 "address": "88 Cộng Hòa, Tân Bình (minh họa)", "latitude": 10.8030, "longitude": 106.6500,
                 "weight_kg": 2500, "volume_m3": 12, "delivery_window_start": "", "delivery_window_end": "",
                 "service_time_min": 20, "priority": 0, "note": "Cố ý vượt tải mọi xe để kiểm thử cảnh báo"})

    with open(OUT / "orders.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    vehicles = [
        # id, type, kg, m3, VND/km, fixed, fuel, consumption, available, start, end
        ("MOTO-01", "motorbike_petrol", 60, 0.25, 1500, 50000, "E5", 2.2, True),
        ("MOTO-02", "motorbike_petrol", 60, 0.25, 1500, 50000, "E10", 2.3, True),
        ("MOTO-03", "motorbike_petrol", 60, 0.25, 1500, 50000, "E5", 2.2, True),
        ("MOTO-04", "motorbike_petrol", 60, 0.25, 1500, 50000, "E10", 2.3, True),
        ("MOTO-05", "motorbike_petrol", 60, 0.25, 1500, 50000, "E5", 2.1, False),
        ("EMOTO-01", "motorbike_electric", 45, 0.2, 1200, 50000, "electricity", 3.0, True),
        ("EMOTO-02", "motorbike_electric", 45, 0.2, 1200, 50000, "electricity", 3.0, True),
        ("EMOTO-03", "motorbike_electric", 45, 0.2, 1200, 50000, "electricity", 3.2, True),
        ("VAN-01", "van", 600, 3, 4000, 200000, "E10", 9.5, True),
        ("VAN-02", "van", 650, 3.2, 4200, 200000, "diesel", 8.5, True),
        ("EVAN-01", "ev_van", 500, 3, 3500, 220000, "electricity", 20, True),
        ("TRUCK-01", "small_truck", 1500, 8, 6000, 350000, "diesel", 12, True),
    ]
    with open(OUT / "vehicles.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["vehicle_id", "vehicle_type", "capacity_weight_kg", "capacity_volume_m3", "cost_per_km", "fixed_cost_vnd",
                    "fuel_blend_code", "consumption_rate", "fuel_price", "available", "start_time", "end_time"])
        for vid, t, kg, m3, cpk, fixed, fuel, cons, avail in vehicles:
            start = "07:00" if t in ("van", "ev_van", "small_truck") else "07:30"
            w.writerow([vid, t, kg, m3, cpk, fixed, fuel, cons, "", str(avail).lower(), start, "19:00"])
    print(f"{len(rows)} orders, {len(vehicles)} vehicles → {OUT}")


if __name__ == "__main__":
    main()
