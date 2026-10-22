======================================================
Báo lỗi (Bug) và yêu cầu thay đổi (CR) — GreenRoute AI
======================================================

Thư mục này dành cho nhóm dự án (BA kiêm Tester) ghi lại bug và CR khi kiểm thử.

- Web quản lý: https://greenroute-ai-mewj.onrender.com
- App tài xế: https://greenroute-ai-mewj.onrender.com/driver.html
- Tài khoản test: xin IT gửi riêng (không ghi mật khẩu vào file báo lỗi).

Bug hay CR?
-----------

Loại | Khi nào dùng                                                        | Ví dụ
-----+---------------------------------------------------------------------+----------------------------------------------------------
Bug  | Hệ thống làm khác với tài liệu yêu cầu hoặc khác với chính nó mô tả | Tổng CO₂ trên tổng quan khác tổng CO₂ trong báo cáo Excel
CR   | Hệ thống làm đúng như tài liệu, nhưng nhóm muốn đổi hoặc thêm       | Muốn thêm cột "Mã khách hàng" vào bảng đơn hàng

Cách đặt tên file
-----------------

Bug 001 Màn hình <XX> - Chức năng <XXX> đang <A> thay vì đúng theo <B>.txt
CR 001 Màn hình <XX> - Chức năng <XXX> đề xuất <thay đổi>.txt

- Copy file mẫu (_MAU Bug.txt / _MAU CR.txt), đổi tên theo quy tắc trên rồi điền nội dung. Mở bằng Notepad hoặc bất kỳ trình soạn văn bản nào.
- Số thứ tự tăng dần, 3 chữ số, Bug và CR đánh số riêng.
- Tên màn hình lấy đúng theo menu: Tổng quan, Lập tuyến, Theo dõi trực tiếp, Đơn hàng, Đội xe, Kịch bản nhiên liệu, Lịch sử & báo cáo, Quản trị, Phương pháp & giả định, App tài xế, Đăng nhập.

Ảnh bằng chứng
--------------

- Lưu ảnh vào thư mục images/ và đặt tên theo số bug, ví dụ bug001_image1.png, bug001_image2.png.
- File .txt không hiện ảnh, nên trong file bug ghi đường dẫn ảnh, ví dụ: [Ảnh: images/bug001_image1.png].
- Ảnh nên chụp cả màn hình, gồm cả banner trên cùng và tên tài khoản góc dưới bên trái.

Mẫu
---

- _MAU Bug.txt — mẫu báo lỗi
- _MAU CR.txt — mẫu yêu cầu thay đổi
- Bug 001 Màn hình Đơn hàng - … .txt — ví dụ đã điền đầy đủ
- Kết quả kiểm tra công thức và UI - 22-10-2026.txt — kết quả IT tự kiểm tra

Gợi ý phạm vi kiểm tra
----------------------

1. Quy trình theo vai trò: Admin nạp dữ liệu → Điều phối tối ưu và phát hành → Tài xế bắt đầu ca, giao/không giao → Điều phối theo dõi → Báo cáo. Mỗi vai trò chỉ thấy đúng menu được phép.
2. Công thức: đối chiếu số trên màn hình với công thức trong trang Phương pháp & giả định và tài liệu yêu cầu. Nên tính tay 1–2 xe (quãng đường, nhiên liệu, CO₂, chi phí) rồi so sánh.
3. Số liệu khớp nhau: cùng một chỉ số phải giống nhau ở Tổng quan, Lập tuyến, Lịch sử và file CSV/Excel xuất ra.
4. Dữ liệu sai: nhập/ import đơn thiếu tọa độ, khối lượng âm, giờ giao ngược (từ > đến), xe quá tải.
5. Ngôn ngữ VI / EN / 中文 và giao diện điện thoại (app tài xế).

Lưu ý: trên host miễn phí, dữ liệu tự quay về bộ mẫu mỗi khi server khởi động lại. Nếu số liệu "tự thay đổi", hãy ghi lại giờ xảy ra trong bug.
