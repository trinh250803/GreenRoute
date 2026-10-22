# GreenRoute AI — MVP

Tối ưu giao hàng chặng cuối cho đội xe nhiều loại (xe máy xăng/điện, van, xe tải nhỏ): phân đơn, xếp thứ tự giao, so sánh với baseline, tính chi phí và CO₂ theo từng nhiên liệu (E0/E5/E10/E20/E25/E85/E100, diesel, điện).

> ⚠ Toàn bộ hệ số phát thải, giá năng lượng và dữ liệu mẫu đang là **dữ liệu minh họa**. Nghiệp vụ cần xác minh và phê duyệt trước khi dùng chính thức. Xem [config/fuels.json](config/fuels.json).

## Chạy local

Yêu cầu: Python 3.12.

```powershell
py -3.12 -m venv .venv            # hoặc: python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -q                       # 14 test
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

Lần chạy đầu, console in tài khoản `admin` với mật khẩu tạm (hoặc đặt `ADMIN_PASSWORD` trước khi chạy). Đăng nhập tại http://localhost:8000 rồi đổi mật khẩu.

Luồng thử: **admin** → Nạp dữ liệu minh họa → Quản trị → tạo tài khoản điều phối viên và tài xế (gán xe) → **điều phối viên** chạy tối ưu → Phát hành cho tài xế → **tài xế** mở http://localhost:8000/driver.html trên điện thoại, báo Đã giao/Thất bại → điều phối viên xem tab *Theo dõi giao hàng*.

Vai trò, quyền và danh sách gap: xem [GAPS.md](GAPS.md). Tài liệu API tự sinh (Swagger): http://localhost:8000/docs. Cấu hình môi trường: xem `.env.example`.

## Kiến trúc

| Thành phần | Công nghệ | Mã nguồn |
|---|---|---|
| Backend/API | **Python FastAPI** | [app/main.py](app/main.py) |
| Bộ tối ưu | **Google OR-Tools** RoutingModel (CVRPTW, đội xe không đồng nhất): PARALLEL_CHEAPEST_INSERTION + GUIDED_LOCAL_SEARCH | [app/solver.py](app/solver.py) |
| Phát thải/chi phí | Bảng cấu hình có phiên bản | [app/emissions.py](app/emissions.py), [config/fuels.json](config/fuels.json) |
| Bản đồ | Leaflet + OpenStreetMap | [public/](public/) |
| Routing | Haversine × 1.3, hoặc OSRM `/table` qua `OSRM_URL` (lỗi → fallback + cảnh báo) | [app/distance.py](app/distance.py) |
| Lưu trữ | File JSON (giai đoạn sau: PostgreSQL) | [app/store.py](app/store.py) |
| ML | Chưa có; API trả heuristic `model_status: not_trained` | G4 |

Mô hình OR-Tools: chi phí cung đường tính riêng theo từng xe (VND/km vận hành + năng lượng + giá CO₂ quy đổi), chi phí cố định cho mỗi xe được dùng, ràng buộc tải trọng (gram) và thể tích (cm³), chiều thời gian (giây) có khung giờ và ca làm việc. Đơn bất khả thi được loại qua disjunction với mức phạt lớn (đơn ưu tiên có mức phạt cao hơn). Sau khi giải, mọi tuyến được **kiểm tra lại độc lập** bằng cùng mô hình số nguyên.

## API

| Endpoint | Mục đích |
|---|---|
| `GET /api/config` | Bảng nhiên liệu, hệ số, loại xe |
| `GET/PUT /api/depot` | Kho xuất phát |
| `GET/POST /api/orders`, `PUT/DELETE /api/orders/:id`, `DELETE /api/orders` | CRUD đơn |
| `POST /api/orders/import?mode=replace\|append` | Nhập CSV/XLSX (multipart `file`) hoặc JSON `{rows}`. Có lỗi → 422, không ghi gì |
| `GET/POST /api/vehicles`, `PUT/DELETE /api/vehicles/:id`, `POST /api/vehicles/import` | Đội xe |
| `POST /api/sample/load` | Nạp dữ liệu synthetic |
| `POST /api/optimization/run` `{weights:{co2_vnd_per_kg,time_vnd_per_min}, time_limit_s, vehicle_ids?}` | Chạy tối ưu + baseline |
| `GET /api/optimization`, `GET /api/optimization/:id` | Lịch sử / chi tiết |
| `POST /api/optimization/:id/fuel-scenario` `{overrides:{VEH:{fuel_blend_code,consumption_rate,fuel_price,emission_factor_value,confirm_simulation_fuel}}, mode:"same_route"\|"reoptimize"}` | Kịch bản nhiên liệu |
| `POST /api/predictions/travel-time` | Dự đoán thời gian (heuristic, chờ model) |
| `GET /api/reports/:id?format=json\|csv\|xlsx` | Báo cáo (XLSX gồm summary, routes, unassigned, scenarios, assumptions) |

## Định dạng file nhập

**orders**: `order_id, address, latitude, longitude, weight_kg, volume_m3, delivery_window_start, delivery_window_end, service_time_min, priority`. Giờ dạng `HH:MM`.

**vehicles**: `vehicle_id, vehicle_type, capacity_weight_kg, capacity_volume_m3, cost_per_km, fixed_cost_vnd, fuel_blend_code, consumption_rate, fuel_price, emission_factor_value, factor_source, factor_year, available, start_time, end_time, confirm_simulation_fuel`.
`vehicle_type` ∈ `motorbike_petrol, motorbike_electric, van, small_truck, ev_van`. `cost_per_km` là chi phí vận hành **không gồm năng lượng** (năng lượng tính riêng từ tiêu hao × giá).

Mẫu: [data/sample/](data/sample/) (bộ dữ liệu cố định). `DH041` (vượt tải) và `DH042` (khung giờ bất khả thi) được cài cố ý để kiểm thử cảnh báo.

## Đối chiếu tiêu chí nghiệm thu (mục 10 + Phụ lục)

| Tiêu chí | Trạng thái | Bằng chứng |
|---|---|---|
| Nhập đơn bằng form / CSV / XLSX | ✅ | Tab Đơn hàng; `app/io_files.py` |
| Cấu hình nhiều nhóm xe với tải trọng, chi phí khác nhau | ✅ | Tab Đội xe; 5 loại xe |
| Phát hiện dữ liệu sai, địa chỉ chưa định vị, ràng buộc không khả thi | ✅ | `app/validation.py`; mã lỗi `EXCEEDS_CAPACITY`, `TIME_WINDOW_INFEASIBLE`, `FLEET_CAPACITY_EXHAUSTED` |
| Tuyến hợp lệ, không vượt sức chứa, không bỏ sót đơn mà không báo | ✅ | test `test_solver_constraints` |
| Bản đồ kho, điểm giao, tuyến theo xe | ✅ | Leaflet, màu theo xe, nét đứt = xe điện |
| km, thời gian, chi phí, CO₂ với công thức/giả định rõ | ✅ | Tab Phương pháp; mỗi tuyến ghi hệ số, nguồn, năm |
| Baseline và tối ưu trên cùng dữ liệu, cùng ràng buộc | ✅ | `baseline()` dùng chung evaluator và ma trận |
| Chọn xăng/diesel/điện, chặn nhiên liệu không tương thích | ✅ | `checkCompatibility`; nhiên liệu mô phỏng cần xác nhận |
| Đổi tiêu hao/giá/hệ số thì kết quả cập nhật đúng | ✅ | test `test_inputs_change_results` |
| So sánh cùng tuyến và tối ưu lại tuyến | ✅ | `mode: same_route / reoptimize`, có ghi chú căn cứ |
| Thiếu hệ số → cảnh báo, không bịa số | ✅ | E100 hoặc thiếu tiêu hao thì trả `null` kèm cảnh báo |
| CO₂ sinh học (ethanol) tách riêng | ✅ | `co2_fossil_kg` / `co2_biogenic_kg` |
| Xuất CSV/XLSX | ✅ | `/api/reports/:id` |
| ML: test độc lập, MAE/RMSE | ⏳ | Chưa có dữ liệu thật (G4) |
| Đăng nhập / phân quyền | ⏳ | Later (F-11) |

## Gaps còn lại / cần chủ dự án quyết định

1. **Hệ số phát thải Việt Nam**: các giá trị hiện tại lấy từ IPCC 2006 và hệ số lưới điện 2023, **chưa được xác minh**. Nghiệp vụ cần duyệt rồi cập nhật `config/fuels.json` và tăng `version`.
2. **Giá nhiên liệu/điện mặc định** là số minh họa. Người dùng có thể nhập giá theo từng xe.
3. **Trọng số hàm mục tiêu** (giá CO₂ quy đổi, chi phí thời gian) mặc định = 0, chờ duyệt.
4. **Geocoding** chưa tích hợp: đơn chỉ có địa chỉ sẽ bị báo lỗi để người dùng sửa (đúng quy tắc 5.3). Cần chọn nhà cung cấp (Nominatim / Google / Vietmap) và kiểm tra chi phí.
5. **Routing thật**: cần dựng OSRM với dữ liệu OSM Việt Nam, hoặc chọn nhà cung cấp có hỗ trợ hạn chế đường cho xe tải. `road_access_constraints` chưa được áp dụng.
6. **Khung giờ là ràng buộc cứng**; chưa có chi phí trễ giao (ràng buộc mềm). Cần thống nhất mức phạt.
7. **Một kho, một ca/ngày, mỗi xe một chuyến**, đúng phạm vi MVP.
8. **Thời gian giải**: OR-Tools chạy hết `time_limit_s` (mặc định 5 giây, tối đa 60) để cải thiện nghiệm. Cần thống nhất giới hạn thời gian chấp nhận được.
9. **Lưu trữ JSON** (chưa dùng PostgreSQL) chỉ phù hợp cho demo một người dùng; triển khai thật cần PostgreSQL và backup.
10. **Bảo mật**: chưa có auth. Log không ghi request body. Không có secrets trong mã nguồn.
