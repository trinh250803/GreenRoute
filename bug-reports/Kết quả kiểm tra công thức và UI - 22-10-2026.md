# Kết quả kiểm tra công thức và UI — 22/10/2026

Người kiểm tra: IT. Phạm vi: các công thức trong tài liệu bàn giao (Phụ lục 1 §3, Phụ lục 2 §1–2, mục 6) và độ dễ dùng của giao diện.

## 1. Kết luận

- **Công thức: tính đúng.** Một chương trình kiểm tra độc lập (không dùng code của hệ thống) tính lại toàn bộ số liệu từ dữ liệu gốc và so với số hệ thống hiển thị:
  - Local: 323/323 phép kiểm tra khớp.
  - Online (greenroute-ai-mewj.onrender.com): 337/337 khớp.
  - Số phép kiểm tra phụ thuộc số xe trong lần chạy.
- Có 2 chỗ chưa đúng tinh thần tài liệu, đã sửa (mục 4).
- Có 6 điểm cần nhóm dự án ra quyết định nghiệp vụ (mục 5). Đây không phải lỗi code.

## 2. Công thức đã đối chiếu

| # | Công thức trong tài liệu | Kết quả |
|---|---|---|
| 1 | Nhiên liệu (L) = km × tiêu hao (L/100km) / 100 | Đúng |
| 2 | CO₂ (kg) = L × hệ số phát thải (kg CO₂/L) | Đúng |
| 3 | Chi phí nhiên liệu = L × giá (VND/L) | Đúng |
| 4 | Điện (kWh) = km × kWh/100km / 100; CO₂ lưới = kWh × EF lưới; chi phí = kWh × giá điện | Đúng. CO₂ ống xả xe điện = 0; CO₂ lưới báo riêng, không cộng vào tổng (theo quyết định "CO₂ trực tiếp") |
| 5 | EF pha ethanol = (1 − x)·EF_xăng + x·EF_ethanol | Đúng: E5 = 2,27; E10 = 2,23 kg CO₂/L |
| 6 | Tổng chi phí = km × chi phí vận hành/km + chi phí cố định + chi phí năng lượng | Đúng |
| 7 | CO₂/km, CO₂/đơn, chi phí/đơn | Đúng (chia cho số đơn **đã giao**) |
| 8 | % thay đổi = (phương án mới − gốc) / gốc × 100 | Đúng cho cả 11 chỉ số |
| 9 | Ràng buộc: không vượt tải trọng/thể tích, đến trong khung giờ, về kho trong ca | Đúng, không vi phạm |
| 10 | Mỗi đơn giao đúng 1 lần; đơn không giao được phải có lý do | Đúng: đã giao + chưa giao = tổng đơn |
| 11 | Thiếu giá / thiếu hệ số → không đưa ra con số giả | Đúng: hiện "—" kèm cảnh báo |
| 12 | Nhiên liệu mô phỏng (E20/E25/E85) phải xác nhận; nhiên liệu không hợp xe bị chặn | Đúng |

Hệ số trong cấu hình cũng được kiểm tra lại bằng tính tay:

| Hệ số | Giá trị | Kiểm tra |
|---|---|---|
| Ethanol | 1,51 kg CO₂/L | 0,789 kg/L × 88/46 ≈ 1,51 |
| Diesel | 2,68 kg CO₂/L | Giá trị mặc định IPCC 2006 |
| Xăng | 2,31 kg CO₂/L | Giá trị mặc định IPCC 2006 |

## 3. Ví dụ tính tay — tester có thể bấm máy tính để kiểm tra

Xe MOTO-01, xe máy xăng E5, tiêu hao 2,2 L/100km. Số liệu lấy từ lần chạy online ngày 22/10/2026:

| Bước | Phép tính | Kết quả | Hệ thống |
|---|---|---|---|
| Quãng đường | Σ chặng × 1,3 | 13,487 km | 13,487 |
| Hệ số E5 | (1 − 0,05) × 2,31 + 0,05 × 1,51 | 2,2700 kg CO₂/L | 2,27 |
| Nhiên liệu | 13,487 × 2,2 / 100 | 0,2967 L | 0,2967 |
| CO₂ | 0,2967 × 2,27 | 0,6735 kg | 0,6735 |
| Chi phí xăng | 0,2967 × 26.971 | 8.002 ₫ | 8.002 |
| Chi phí vận hành | 13,487 × 1.500 + 50.000 | 70.230 ₫ | 70.230 |

**Cách tự chạy lại kiểm tra:** IT chạy lệnh dưới đây. Lệnh lấy lần tối ưu mới nhất, tính lại toàn bộ và in PASS/FAIL cho từng mục.

```
python scripts/verify_formulas.py https://greenroute-ai-mewj.onrender.com
```

## 4. Đã sửa trong lần kiểm tra này

| # | Vấn đề | Căn cứ tài liệu | Đã sửa |
|---|---|---|---|
| 1 | Kịch bản nhiên liệu: đổi E5 → E85 mà không nhập mức tiêu hao mới thì hệ thống âm thầm dùng lại mức tiêu hao của E5 | Phụ lục 2 §2: "không mặc định mọi hỗn hợp có cùng mức tiêu hao L/100 km" | Hiện cảnh báo "đang dùng lại mức tiêu hao… nhập mức tiêu hao thực tế nếu có" |
| 2 | Ô "Chi phí vận hành (VND/km)" không nói rõ có gồm tiền xăng không. Nếu người dùng nhập cả tiền xăng thì chi phí xăng bị cộng 2 lần | F-03, 5.2: "ghi rõ gồm những khoản nào" | Đổi nhãn thành "Chi phí vận hành, chưa gồm nhiên liệu (VND/km)" và thêm chú thích khi rê chuột |
| 3 | Màn hình Đơn hàng không có nút **Sửa**, chỉ có Xóa | F-02: "Tạo/sửa/xóa đơn" | Thêm nút Sửa: mở form với dữ liệu sẵn, mã đơn khóa lại, bấm "Cập nhật đơn" |
| 4 | Thẻ KPI ở Lập tuyến hiện "Xe −27% / km −71%" màu xanh, trong khi baseline giao ít đơn hơn. Con số này dễ hiểu nhầm là tối ưu tiết kiệm 71% | Mục 6.3: so sánh cùng điều kiện | Khi số đơn hai bên khác nhau, thẻ hiện "baseline chỉ giao 126 đơn". So sánh công bằng xem ở chỉ số /đơn |
| 5 | Chú thích cuối trang có chữ kỹ thuật "Đặt OSRM_URL…" | — | Đổi thành "(ước tính, chưa theo đường thực tế)", có bản dịch EN/中文 |

Bộ test tự động cũng được bổ sung (`tests/test_formulas.py`): 32/32 test đạt. Các test này chạy lại mỗi khi sửa code, để công thức không bị sai về sau.

## 5. Cần nhóm dự án quyết định (nghiệp vụ, không phải lỗi code)

1. **CO₂ sinh học trong "CO₂ trực tiếp".**
   - Hiện tại tổng CO₂ trực tiếp gồm cả phần ethanol (sinh học). Phần này chiếm 3,3% với E5 và 6,8% với E10. Phần hóa thạch và sinh học đã được tách và hiển thị riêng ở Kịch bản nhiên liệu.
   - Cần chốt: con số chính trên dashboard là *tổng* hay *chỉ hóa thạch*? Phụ lục 2 cho phép cả hai, miễn ghi rõ.
2. **Nguồn hệ số.** Đang dùng giá trị mặc định quốc tế (IPCC 2006). Hệ số lưới điện VN 0,6592 kg/kWh đang ghi "cần xác minh". Nghiệp vụ cần phê duyệt nguồn chính thức cho Việt Nam (theo câu trả lời trong Phụ lục 1 §6).
3. **Giá điện 3.000 ₫/kWh là giả định.** Giá xăng E5/E10/diesel lấy theo kỳ điều hành 15/10/2026; cần người cập nhật định kỳ.
4. **E20/E25/E85.** Hệ số đang tính theo công thức pha trộn và gắn nhãn "mô phỏng". Cần xác nhận cách này đáp ứng yêu cầu "đánh dấu chưa hỗ trợ tính chính thức". E100 chưa có hệ số.
5. **Định nghĩa baseline.**
   - Baseline hiện tại: xếp đơn theo thứ tự nhập vào xe đầu tiên còn chỗ. Cách này giao được ít đơn hơn (126/151), nên so sánh km tổng không ngang hàng.
   - Cần chốt: baseline nào phản ánh đúng cách điều phối hiện tại của công ty?
6. **Giả định quãng đường và thời gian.**
   - Khoảng cách = đường chim bay × 1,3, chưa theo đường thật.
   - Tốc độ cố định theo loại xe. Giờ cao điểm chỉ là ước tính (tốc độ còn 60%).
   - Nếu cần số km sát thực tế: phải có dịch vụ bản đồ đường (OSRM). Cần quyết định chi phí và hạ tầng.

## 6. Đánh giá UI

**Đã tốt:**
- Trang Tổng quan có thanh quy trình 5 bước: Đơn hàng → Đội xe → Lập tuyến → Phát hành → Theo dõi. Người mới biết bước tiếp theo cần làm.
- Bấm vào mã đơn hoặc mã xe ở bất kỳ đâu đều mở ra chi tiết.
- App tài xế có nút lớn, dễ bấm trên điện thoại: Gọi khách, Chỉ đường, Đã giao.
- Có 3 ngôn ngữ. Mỗi kết quả CO₂ đều ghi phạm vi và nguồn hệ số.

**Chưa tốt — đề xuất log thành Bug/CR để làm tiếp:**

| # | Màn hình | Vấn đề | Mức |
|---|---|---|---|
| 1 | Tất cả | Thông báo lỗi do server trả về chỉ có tiếng Việt (xem Bug 001) | Thấp |
| 2 | Lập tuyến | Ô "Giá CO₂ (VND/kg)" và "Thời gian giải (giây)" là thuật ngữ kỹ thuật. Người điều phối không biết nên nhập gì, cần giải thích hoặc ẩn vào phần "Nâng cao" | Trung bình |
| 3 | Tổng quan | Tổng chi phí hiển thị "2.382k ₫", dễ đọc nhầm. Nên ghi "2,38 triệu ₫" | Thấp |
| 4 | Tổng quan | Nếu mạng chặn thư viện biểu đồ, các khung biểu đồ để trống, không có thông báo | Thấp |
| 5 | Đơn hàng | Nút chọn file hiện chữ tiếng Anh "Choose File / No file chosen" (do trình duyệt) | Thấp |
| 6 | Đơn hàng | Nút "Xóa tất cả" màu đỏ nằm ngay cạnh "Nhập file". Đã có hộp xác nhận, nhưng nên tách xa hoặc chuyển vào Quản trị | Thấp |

Ghi chú: UI chưa được kiểm thử với người dùng thật (điều phối viên, tài xế). Cách đánh giá chắc chắn nhất là cho 2–3 người dùng thật làm thử luồng chính và ghi lại chỗ họ bị vướng.
