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
| A12 | Chưa có geocoding (đơn chỉ có địa chỉ bị báo lỗi) | 3.2 bước 3, 5.1 | ⏳ Cần chọn nhà cung cấp và chi phí (B5) |
| A13 | ML dự đoán thời gian | F-08, G4 | ⏳ Chờ dữ liệu thật; A7 bắt đầu thu thập |

## 3. Gap tài liệu (B): cần chủ dự án chốt

| # | Câu hỏi | Đề xuất đang áp dụng |
|---|---|---|
| B1 | Tài xế có dùng hệ thống không? | Có, ở mức tối thiểu: xem tuyến và báo kết quả giao. GPS trực tiếp vẫn để sau (F-10) |
| B2 | Một tài xế gắn cố định với một xe, hay đổi theo ca? | Admin gán tài xế ↔ xe; đổi ca thì gán lại |
| B3 | Đơn giao thất bại xử lý thế nào: giao lại, hoàn kho, tạo đơn mới? | Hiện chỉ ghi nhận lý do; quy trình xử lý chưa có |
| B4 | Ai phê duyệt thay đổi hệ số phát thải? Cần 2 bước (đề xuất → duyệt) không? | Hiện admin sửa trực tiếp, bắt buộc ghi lý do, có lịch sử phiên bản |
| B5 | Nhà cung cấp geocoding/routing và ai trả phí? | Chưa chọn; hỗ trợ OSRM qua `OSRM_URL` |
| B6 | Khách hàng cuối có cần nhận thông báo hoặc link theo dõi không? | Ngoài phạm vi MVP |
| B7 | Chính sách mật khẩu, khóa tài khoản, thời hạn phiên, có cần SSO không? | Mật khẩu ≥ 8 ký tự, phiên 12 giờ, admin khóa được tài khoản |
| B8 | Thời gian lưu dữ liệu khách hàng và lịch sử giao hàng | Chưa có chính sách xóa/ẩn danh |
| B9 | Nhiều kho, nhiều chuyến/ngày cho một xe | Ngoài MVP (tài liệu ghi "một kho") |
| B10 | Mức phạt giao trễ (ràng buộc mềm) | Hiện khung giờ là ràng buộc cứng |
