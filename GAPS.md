# GreenRoute AI — Phân tích gap

Đối chiếu tài liệu bàn giao v1.0 (17/10/2026) với hệ thống. Có hai loại gap:
- **A. Gap triển khai**: tài liệu có yêu cầu nhưng hệ thống chưa làm.
- **B. Gap tài liệu**: tài liệu thiếu hoặc chưa rõ, phải chốt với chủ dự án.

## 1. Đối tượng sử dụng

| Vai trò | Nguồn | Việc làm trên hệ thống | Quyền |
|---|---|---|---|
| Quản trị hệ thống (`admin`) | Mục 3.1 | Tạo/khóa tài khoản, gán vai trò, gán tài xế cho xe; cấu hình hệ số phát thải, giá nhiên liệu/điện, trọng số tối ưu; xem nhật ký | Toàn quyền |
| Điều phối viên (`dispatcher`) | Mục 3.1 | Kho, đơn hàng, chạy tối ưu, kịch bản nhiên liệu, **phát hành tuyến cho tài xế**, theo dõi trạng thái giao | Đơn, tối ưu, phát hành |
| Quản lý đội xe (`fleet_manager`) | Mục 3.1 | Khai báo xe, sức chứa, chi phí, nhiên liệu, tiêu hao, tình trạng sẵn sàng | Đội xe |
| Quản lý vận hành (`ops_manager`) | Mục 3.1 | Xem KPI, so sánh phương án, chạy kịch bản, xuất báo cáo | Xem, báo cáo, kịch bản |
| **Tài xế (`driver`)** | **Không có trong tài liệu (gap B1)** | Đăng nhập trên điện thoại, xem tuyến hôm nay của xe mình, mở chỉ đường, báo *Đã giao* / *Thất bại* kèm lý do | Chỉ tuyến của xe mình |

## 2. Gap triển khai (A)

| # | Gap | Căn cứ | Trạng thái |
|---|---|---|---|
| A1 | Không có đăng nhập, ai cũng sửa được mọi thứ | 3.1, F-11, 12 | ✅ Đăng nhập, phiên có hạn, mật khẩu băm PBKDF2 |
| A2 | Không phân quyền theo vai trò | 3.1, 5.3 (hạn chế truy cập dữ liệu khách hàng) | ✅ Phân quyền 5 vai trò ở cả API và giao diện |
| A3 | Admin không quản lý được tài khoản | 3.1 | ✅ Tạo, sửa vai trò, khóa, đặt lại mật khẩu, gán xe cho tài xế |
| A4 | Hệ số phát thải và giá chỉ sửa được bằng file JSON | Phụ lục 1 §4 + câu hỏi 2–3 ("quản trị viên cấu hình", "IT quản lý phiên bản"); Phụ lục 2 §5 ("người quản trị nhập hệ số") | ✅ Màn hình cấu hình; mỗi lần sửa tăng phiên bản, ghi người sửa, giá trị cũ/mới và lý do |
| A5 | Trọng số hàm mục tiêu không có nơi cấu hình chính thức | 6.2 ("chủ dự án duyệt trọng số") | ✅ Admin đặt trọng số mặc định; mỗi lần chạy lưu trọng số đã dùng |
| A6 | Tuyến tối ưu chưa đến được tay tài xế | Đầu ra mục 1 ("phân công xe/đơn") | ✅ Điều phối viên phát hành; tài xế xem trên điện thoại |
| A7 | Không ghi nhận kết quả giao hàng thực tế | 5.1 `delivery_status`; 7.1–7.3 (nhãn để huấn luyện ML, kế hoạch thu thập dữ liệu thật) | ✅ Tài xế báo Đã giao/Thất bại + lý do + thời điểm; điều phối viên theo dõi; xuất CSV |
| A8 | Không có nhật ký thao tác | 12 (log, trách nhiệm cập nhật hệ số) | ✅ Nhật ký: đăng nhập, sửa cấu hình, tài khoản, phát hành, chạy tối ưu |
| A9 | Chưa có PostgreSQL | 8 | ⏳ Đang dùng file JSON; cần cài PostgreSQL |
| A10 | Frontend chưa dùng React/Next.js + TypeScript | 8 | ⏳ Đang là HTML/JS thuần |
| A11 | Chưa có Docker và hướng dẫn triển khai, backup/khôi phục | 8, 10, 12 | ⏳ |
| A12 | Chưa có geocoding | 3.2 bước 3, 5.1 | ✅ Thử nghiệm: form tạo đơn tìm địa chỉ (Photon/OpenStreetMap), ghim trên bản đồ, tự điền tọa độ. ⚠ Dùng máy chủ Photon công cộng — địa chỉ gõ vào được gửi tới komoot; khi chạy thật cần tự host hoặc ký hợp đồng (B5). Nhập file CSV/XLSX vẫn cần tọa độ |
| A13 | ML dự đoán thời gian | F-08, G4 | ⏳ Chờ dữ liệu thật; A7 bắt đầu thu thập |
| A14 | Không biết tài xế đang ở đâu, di chuyển thế nào | F-10 (đưa lên sớm theo yêu cầu) | ✅ Tài xế bấm *Bắt đầu ca* → gửi vị trí mỗi 20 giây (có bộ đệm khi mất mạng); điều phối viên xem bản đồ trực tiếp: vị trí, vệt đường, km đã đi, điểm tiếp theo, cảnh báo mất tín hiệu. ⚠ Chỉ chạy khi trang tài xế đang mở — theo dõi nền cần app di động (B11) |
| A15 | Xác nhận vị trí khi giao | Chống khai khống | ✅ So GPS lúc báo giao với tọa độ đơn; ngưỡng do admin cấu hình |
| A17 | Giá nhiên liệu cũ, không rõ nguồn | Phụ lục 1 §4 | ✅ Giá E5/E10/diesel kỳ 22/10/2026 (Bộ Công Thương; cập nhật 26/10 theo bug log 002) kèm nguồn + ngày áp dụng; loại chưa có giá niêm yết để trống thay vì bịa số. Tự động cập nhật giá: giai đoạn sau |
| A18 | Không xem được chi tiết đơn/xe | 3.1 | ✅ Bấm mã đơn/mã xe ở mọi nơi (bảng, tuyến, bản đồ) → ngăn chi tiết: thông tin, phân công, kết quả giao, vị trí, lịch sử |
| A19 | Dashboard ít phân tích | F-01, F-07 | ✅ 8 biểu đồ + chỉ số hiệu quả (chi phí theo xe, so với baseline, lịch ghé theo giờ, CO₂ theo nhiên liệu, theo quận, tải, khung giờ, lý do thất bại) |
| A20 | Giờ cao điểm | Yêu cầu bổ sung | ⚠ Ước tính: đánh dấu chặng đi trong 07–09h / 16:30–19h, ước tính trễ và đơn có nguy cơ trễ. **Chưa có dữ liệu kẹt xe thực tế** (B13) |
| A21 | Trợ lý AI | Yêu cầu bổ sung | ✅ Claude trả lời về phương án (không gửi tên/SĐT/địa chỉ khách). Cần `ANTHROPIC_API_KEY` trên server (B14) |
| A22 | Song ngữ | Yêu cầu bổ sung | ✅ VI/EN cho giao diện; thông báo lỗi từ server vẫn tiếng Việt |
| A16 | Giao diện khó dùng, chưa theo quy trình | Mục 3.2 | ✅ Menu theo vai trò, trang Tổng quan 5 bước, trang tài xế tối ưu cho điện thoại; kiểm thử bằng trình duyệt tự động (`scripts/e2e_ui.py`) |

## 3. Gap tài liệu (B): cần chủ dự án chốt

| # | Câu hỏi | Đề xuất đang áp dụng |
|---|---|---|
| B1 | Tài xế có dùng hệ thống không? | Có, ở mức tối thiểu: xem tuyến và báo kết quả giao. GPS trực tiếp vẫn để sau (F-10) |
| B2 | Một tài xế gắn cố định với một xe, hay đổi theo ca? | Admin gán tài xế ↔ xe; đổi ca thì gán lại |
| B3 | Đơn giao thất bại xử lý thế nào: giao lại, hoàn kho, tạo đơn mới? | Hiện chỉ ghi nhận lý do; quy trình xử lý chưa có |
| B4 | Ai phê duyệt thay đổi hệ số phát thải? Cần 2 bước (đề xuất → duyệt) không? | Hiện admin sửa trực tiếp, bắt buộc ghi lý do, có lịch sử phiên bản |
| B5 | Nhà cung cấp geocoding/routing và ai trả phí? | Chưa chọn; hỗ trợ OSRM qua `OSRM_URL` |
| B6 | Khách hàng cuối có cần nhận thông báo hoặc link theo dõi không? | Ngoài phạm vi MVP |
| B7 | Chính sách mật khẩu, khóa tài khoản, thời hạn phiên, có cần SSO không? | Mật khẩu ≥ 8 ký tự, phiên 24 giờ (token ký, không mất khi server khởi động lại), đăng xuất/khóa/đặt lại mật khẩu thu hồi ngay |
| B8 | Thời gian lưu dữ liệu khách hàng và lịch sử giao hàng | Chưa có chính sách xóa/ẩn danh |
| B9 | Nhiều kho, nhiều chuyến/ngày cho một xe | Ngoài MVP (tài liệu ghi "một kho") |
| B10 | Mức phạt giao trễ (ràng buộc mềm) | Hiện khung giờ là ràng buộc cứng |
| B11 | Có cần app di động (Android/iOS) để theo dõi khi tắt màn hình không? | Hiện là web app; trình duyệt dừng GPS khi khóa màn hình |
| B13 | Dùng nhà cung cấp giao thông thời gian thực nào (Google, TomTom, HERE, Vietmap)? Chi phí ai trả? | Hiện chỉ ước tính theo khung giờ |
| B14 | Ai cấp và trả phí API key cho trợ lý AI? | Hiện tắt khi chưa có key |
| B12 | Có cần thông báo pháp lý/đồng ý của tài xế về việc thu thập vị trí không? | Hiện tài xế chủ động bật/tắt; chỉ thu thập trong ca, lưu 24 giờ |
