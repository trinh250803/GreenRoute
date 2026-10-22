"""Builds the role guide as HTML (docs/guide/GreenRoute_AI_Huong_dan_su_dung.html).

Screenshots live in docs/guide/img and are referenced relatively; to_docx.ps1 turns the
HTML into a Word file with the images embedded.
"""
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
URL = "https://greenroute-ai-mewj.onrender.com"
FIG = {"n": 0}


def n(k):
    return f'<b class="num">({k})</b>'


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def fig(name, caption, phone=False, width=None):
    FIG["n"] += 1
    w = width or (270 if phone else 620)
    iw, ih = png_size(HERE / "img" / f"{name}.png")
    h = round(w * ih / iw)  # Word keeps the natural height unless both are given
    return (f'<p class="fig"><img src="img/{name}.png" width="{w}" height="{h}" alt="{caption}"></p>'
            f'<p class="cap">Hình {FIG["n"]}. {caption}</p>')


def steps(*items):
    return "<ol>" + "".join(f"<li>{i}</li>" for i in items) + "</ol>"


def bullets(*items):
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def table(head, rows, widths=None):
    th = "".join(f'<th{f" width=\"{widths[i]}\"" if widths else ""}>{h}</th>' for i, h in enumerate(head))
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"


def note(text, kind="info"):
    return f'<p class="note {kind}">{text}</p>'


Y, N = "✔", "—"
body = []
add = body.append

# ------------------------------------------------------------------ cover
add(f"""
<h1 class="title">GreenRoute AI</h1>
<p class="subtitle">Hướng dẫn sử dụng theo vai trò</p>
<p class="meta">Phiên bản 1.0 · 22/10/2026 · Môi trường nghiên cứu, chưa áp dụng chính thức</p>
<p class="meta">Web quản lý: <a href="{URL}">{URL}</a><br>App tài xế: <a href="{URL}/driver.html">{URL}/driver.html</a></p>
<h3>Nội dung</h3>
<ol class="toc">
<li><a href="#s1">Bắt đầu: truy cập, vai trò, đăng nhập</a></li>
<li><a href="#s2">Quản trị hệ thống (Admin)</a></li>
<li><a href="#s3">Quản lý đội xe</a></li>
<li><a href="#s4">Điều phối viên</a></li>
<li><a href="#s5">Tài xế (app điện thoại)</a></li>
<li><a href="#s6">Quản lý vận hành</a></li>
<li><a href="#s7">Câu hỏi thường gặp và lưu ý</a></li>
</ol>
<p>Trong ảnh, các ô viền đỏ có số {n(1)}, {n(2)}… là chỗ cần bấm hoặc cần xem. Số trong ảnh khớp với số trong các bước hướng dẫn ngay bên dưới.</p>
""")

# ------------------------------------------------------------------ 1. start
add('<h1 id="s1">1. Bắt đầu</h1>')
add("<h2>1.1 Truy cập</h2>")
add(bullets(
    f"<b>Web quản lý</b> (Admin, Điều phối, Quản lý đội xe, Quản lý vận hành): mở <a href=\"{URL}\">{URL}</a> bằng Chrome hoặc Edge trên máy tính.",
    f"<b>App tài xế</b>: mở <a href=\"{URL}/driver.html\">{URL}/driver.html</a> bằng Chrome (Android) hoặc Safari (iPhone) trên điện thoại.",
    "Máy chủ đang dùng gói miễn phí: nếu không có ai dùng khoảng 15 phút, máy chủ tạm ngủ. Lần mở đầu tiên sau đó có thể mất khoảng 1 phút.",
))
add("<h2>1.2 Vai trò và quyền</h2>")
add("<p>Mỗi tài khoản có đúng một vai trò. Menu chỉ hiện những màn hình vai trò đó được dùng.</p>")
add(table(["Chức năng", "Quản trị", "Điều phối", "Quản lý đội xe", "Quản lý vận hành", "Tài xế"], [
    ["Tổng quan, Theo dõi trực tiếp, Lịch sử & báo cáo", Y, Y, Y, Y, N],
    ["Đơn hàng: xem", Y, Y, N, Y, N],
    ["Đơn hàng: thêm, sửa, xóa, nhập file", Y, Y, N, "chỉ xem", N],
    ["Đội xe: xem", Y, Y, Y, Y, N],
    ["Đội xe: thêm, sửa, nhập file", Y, N, Y, N, N],
    ["Lập tuyến, phát hành cho tài xế", Y, Y, "chỉ xem", "chỉ xem", N],
    ["Kịch bản nhiên liệu", Y, Y, Y, Y, N],
    ["Quản trị: tài khoản, hệ số, dữ liệu, nhật ký", Y, N, N, N, N],
    ["App tài xế: tuyến của mình, giao hàng, chia sẻ vị trí", N, N, N, N, Y],
]))
add("<h2>1.3 Quy trình hằng ngày</h2>")
add(table(["Bước", "Ai làm", "Việc cần làm", "Màn hình"], [
    ["1", "Quản trị", "Tạo tài khoản, cấu hình giá nhiên liệu và hệ số (làm một lần, cập nhật khi giá đổi)", "Quản trị"],
    ["2", "Quản lý đội xe", "Khai báo xe, đánh dấu xe sẵn sàng trong ngày", "Đội xe"],
    ["3", "Điều phối", "Nhập đơn hàng trong ngày (form hoặc file CSV/XLSX)", "Đơn hàng"],
    ["4", "Điều phối", "Chạy tối ưu, kiểm tra kết quả và so sánh với baseline", "Lập tuyến"],
    ["5", "Điều phối", "Phát hành tuyến cho tài xế", "Lập tuyến"],
    ["6", "Tài xế", "Bắt đầu ca, giao từng điểm, ghi nhận đã giao / không giao được", "App tài xế"],
    ["7", "Điều phối", "Theo dõi vị trí và tiến độ, xử lý đơn thất bại", "Theo dõi trực tiếp"],
    ["8", "Quản lý vận hành", "Xem chỉ số, so sánh nhiên liệu, xuất báo cáo", "Tổng quan, Kịch bản, Lịch sử"],
], widths=[40, 110, 330, 140]))
add("<p>Thanh <b>Quy trình hôm nay</b> trên trang Tổng quan hiện các bước 1–5 của ngày và nút <b>Làm ngay</b> ở bước tiếp theo cần làm.</p>")

add("<h2>1.4 Đăng nhập</h2>")
add(fig("01_login", "Màn hình đăng nhập", width=320))
add(steps(f"Nhập tên đăng nhập {n(1)}.", f"Nhập mật khẩu {n(2)}.", f"Bấm <b>Đăng nhập</b> {n(3)}."))
add(bullets(
    "Lần đăng nhập đầu tiên, hệ thống bắt đổi mật khẩu tạm do Quản trị cấp (xem 1.6).",
    "Nhập sai mật khẩu 5 lần liên tiếp: tài khoản bị khóa đăng nhập 5 phút.",
    "Phiên đăng nhập giữ trong 24 giờ, không tự đăng xuất khi đang dùng. Hết 24 giờ thì đăng nhập lại.",
    "Tài khoản và mật khẩu thử nghiệm: xin IT gửi riêng. Không ghi mật khẩu vào tài liệu hay tin nhắn nhóm.",
))
add("<h2>1.5 Giao diện chung</h2>")
add(fig("02_layout", "Bố cục chung của web quản lý"))
add(table(["Số", "Thành phần", "Ý nghĩa"], [
    [n(1), "Banner cam", "Nhắc đây là môi trường nghiên cứu, số liệu chưa dùng chính thức."],
    [n(2), "Menu", "Các màn hình theo vai trò. Trên điện thoại, bấm nút ☰ để mở menu."],
    [n(3), "VI · EN · 中文", "Đổi ngôn ngữ giao diện. Thông báo lỗi từ máy chủ hiện vẫn bằng tiếng Việt."],
    [n(4), "Đổi mật khẩu", "Xem 1.6."],
    [n(5), "Đăng xuất", "Thoát tài khoản trên máy này."],
], widths=[40, 130, 450]))
add("<p>Ở mọi màn hình, bấm vào <b>mã đơn</b> (ví dụ HCM001) hoặc <b>mã xe</b> (ví dụ MOTO-01) để mở ngăn chi tiết bên phải. Nhấn Esc hoặc dấu × để đóng.</p>")
add("<h2>1.6 Đổi mật khẩu</h2>")
add(fig("03_change_pw", "Đổi mật khẩu", width=320))
add(steps(f"Bấm <b>Đổi mật khẩu</b> ở góc dưới bên trái.", f"Nhập mật khẩu hiện tại {n(1)}.", f"Nhập mật khẩu mới, tối thiểu 8 ký tự {n(2)}, và nhập lại {n(3)}.", f"Bấm <b>Lưu mật khẩu</b> {n(4)}. Các phiên đăng nhập cũ trên máy khác sẽ bị đăng xuất."))
add(note("Quên mật khẩu: nhờ Quản trị bấm <b>Đặt lại MK</b> cho tài khoản của bạn (xem 2.2)."))

# ------------------------------------------------------------------ 2. admin
add('<h1 id="s2">2. Quản trị hệ thống (Admin)</h1>')
add("<p>Quản trị tạo tài khoản, quản lý hệ số phát thải và giá nhiên liệu, nạp dữ liệu mẫu và xem nhật ký. Menu <b>Quản trị</b> có 4 thẻ: Tài khoản &amp; phân quyền, Hệ số, giá &amp; trọng số, Dữ liệu mẫu, Nhật ký.</p>")
add("<h2>2.1 Tạo tài khoản</h2>")
add(fig("11_admin_user_form", "Tạo tài khoản mới (ví dụ tài xế)"))
add(steps(
    "Vào <b>Quản trị</b> → thẻ <b>Tài khoản &amp; phân quyền</b>.",
    f"Nhập tên đăng nhập {n(1)} (viết liền, không dấu, ví dụ taixe13) và họ tên.",
    f"Chọn vai trò {n(2)}.",
    f"Nếu là tài xế: chọn xe {n(3)}. Mỗi xe chỉ gán cho một tài xế đang hoạt động.",
    f"Nhập mật khẩu tạm, tối thiểu 8 ký tự {n(4)}.",
    f"Bấm <b>Tạo tài khoản</b> {n(5)}. Gửi tên đăng nhập và mật khẩu tạm cho người dùng; họ sẽ phải đổi ở lần đăng nhập đầu.",
))
add("<h2>2.2 Sửa, khóa tài khoản, đặt lại mật khẩu</h2>")
add(fig("10_admin_users", "Danh sách tài khoản"))
add(bullets(
    f"Trong bảng {n(2)}, sửa họ tên, vai trò, xe hoặc <b>Trạng thái</b> (Hoạt động / Khóa) rồi bấm <b>Lưu</b> trên dòng đó.",
    "<b>Đặt lại MK</b>: tạo mật khẩu tạm mới cho người quên mật khẩu.",
    "Khóa tài khoản thay vì xóa, để lịch sử thao tác vẫn còn tên người làm.",
    "Hệ thống không cho khóa Quản trị cuối cùng.",
))
add("<h2>2.3 Hệ số phát thải, giá nhiên liệu và tham số</h2>")
add(fig("12_admin_config", "Bảng hệ số và giá"))
add(fig("12b_admin_config_save", "Ghi lý do và lưu phiên bản mới"))
add(steps(
    f"Vào thẻ <b>Hệ số, giá &amp; trọng số</b>. Sửa giá trị cần đổi trong các bảng {n(1)}: hệ số phát thải nền, giá nhiên liệu và ngày áp dụng, tốc độ theo loại xe, khung giờ cao điểm, giá trị mặc định cho đơn mới.",
    f"Ghi lý do, nguồn hoặc quyết định phê duyệt {n(2)} — bắt buộc.",
    f"Bấm <b>Lưu phiên bản mới</b> {n(3)}.",
))
add(bullets(
    "Mỗi lần lưu tạo một phiên bản mới, ghi lại người sửa, thời điểm, giá trị cũ → mới và lý do (bảng Lịch sử phiên bản bên dưới).",
    "Các lần tối ưu đã chạy giữ nguyên phiên bản cũ. Muốn số liệu theo giá mới thì chạy tối ưu lại.",
    "Giá để trống = chưa có giá: hệ thống không tính chi phí cho nhiên liệu đó và hiện cảnh báo, không tự đoán số.",
))
add(note("Giá xăng E5, E10, diesel đang theo kỳ điều hành 15/10/2026. Giá điện 3.000 ₫/kWh là giả định. Cần cập nhật khi Bộ Công Thương điều chỉnh giá.", "warn"))
add("<h2>2.4 Nạp dữ liệu mẫu</h2>")
add(fig("13_admin_data", "Nạp dữ liệu mẫu"))
add(steps(f"Vào thẻ <b>Dữ liệu mẫu</b>, chọn bộ dữ liệu {n(1)}: TP.HCM (151 đơn, 12 xe) hoặc bộ nhỏ.", f"Bấm nút nạp {n(2)} và xác nhận."))
add(note("Nạp dữ liệu mẫu <b>thay thế toàn bộ</b> đơn hàng và đội xe hiện có. Chỉ dùng khi muốn làm lại từ đầu.", "warn"))
add("<h2>2.5 Nhật ký</h2>")
add(fig("14_admin_audit", "Nhật ký thao tác"))
add(f"<p>Thẻ <b>Nhật ký</b> {n(1)} ghi ai làm gì, lúc nào: đăng nhập, tạo/sửa tài khoản, sửa cấu hình, nạp dữ liệu, chạy tối ưu, phát hành, tài xế bắt đầu/kết thúc ca.</p>")
add("<h2>2.6 Kho xuất phát</h2>")
add(fig("35_plan_setup", "Kho xuất phát và nút chạy tối ưu (trang Lập tuyến)"))
add(steps(
    f"Vào <b>Lập tuyến</b>. Sửa tên kho {n(1)}, hoặc bấm <b>Chọn trên bản đồ</b> {n(2)} rồi bấm vào vị trí kho.",
    f"Bấm <b>Lưu kho</b> {n(3)}. Kho hiện tại: 118 Bạch Đằng, Bình Thạnh.",
))

# ------------------------------------------------------------------ 3. fleet
add('<h1 id="s3">3. Quản lý đội xe</h1>')
add("<p>Đăng nhập xong, Quản lý đội xe vào thẳng màn hình <b>Đội xe</b>.</p>")
add("<h2>3.1 Danh sách xe và nhập file</h2>")
add(fig("20_vehicles", "Màn hình Đội xe"))
add(steps(
    f"Muốn nhập nhiều xe một lần: chọn file CSV hoặc XLSX {n(1)}.",
    f"Chọn chế độ {n(2)}: <b>Thay thế toàn bộ</b> (xóa danh sách cũ) hoặc <b>Thêm vào</b> (thêm xe mới, xe trùng mã được cập nhật).",
    f"Bấm <b>Nhập file</b> {n(3)}. Nếu file có dòng lỗi, hệ thống báo từng dòng và <b>không lưu gì</b>; sửa file rồi nhập lại.",
))
add("<p>Cột của file xe: <code>vehicle_id, vehicle_type, capacity_weight_kg, capacity_volume_m3, cost_per_km, fixed_cost_vnd, fuel_blend_code, consumption_rate, fuel_price, available, start_time, end_time</code>. File mẫu: <code>data/sample_hcm/vehicles.csv</code> trong mã nguồn.</p>")
add(f"<p>Bảng {n(5)} liệt kê từng xe: tài xế, nhiên liệu, tải trọng, chi phí, tiêu hao, giá năng lượng, ca làm và trạng thái.</p>")
add("<h2>3.2 Thêm hoặc sửa một xe</h2>")
add(fig("21_vehicle_form", "Form thêm / sửa xe"))
add(steps(
    f"Mở mục <b>Thêm / sửa xe</b> {n(4)} ở hình trước.",
    f"Nhập mã xe {n(1)}. Nhập mã đã có = sửa xe đó.",
    f"Chọn loại xe {n(2)}. Danh sách nhiên liệu {n(3)} chỉ hiện loại hợp với xe (ví dụ xe máy xăng: E0, E5, E10).",
    f"Nhập chi phí vận hành <b>chưa gồm nhiên liệu</b> {n(4)} và mức tiêu hao {n(5)}.",
    f"Tích <b>Sẵn sàng</b> {n(6)} nếu xe chạy hôm nay. Bỏ tích = xe không được phân đơn.",
    f"Bấm <b>Lưu xe</b> {n(7)}.",
))
add(table(["Trường", "Cách nhập"], [
    ["Tải trọng (kg), Thể tích (m³)", "Sức chứa tối đa. Bộ tối ưu không bao giờ xếp vượt."],
    ["Chi phí vận hành (VND/km)", "Khấu hao, bảo dưỡng, nhân công… <b>Không gồm tiền xăng/điện</b>, vì tiền năng lượng được tính riêng = lượng tiêu thụ × giá. Nhập cả tiền xăng sẽ bị tính 2 lần."],
    ["Chi phí cố định/ngày", "Tính một lần cho mỗi xe được dùng trong ngày."],
    ["Tiêu hao (/100 km)", "Xe xăng/dầu: lít/100 km. Xe điện: kWh/100 km. Để trống = không tính được nhiên liệu và CO₂ (có cảnh báo)."],
    ["Giá năng lượng", "Để trống = dùng giá mặc định do Quản trị cấu hình."],
    ["Hệ số phát thải tùy chỉnh, Nguồn hệ số", "Chỉ nhập khi có hệ số riêng có nguồn rõ ràng. Để trống = dùng hệ số chung."],
    ["Bắt đầu ca, Kết thúc ca", "Giờ xe rời kho và giờ phải về kho (HH:MM)."],
    ["Xác nhận nhiên liệu mô phỏng", "Bắt buộc khi chọn E20, E25, E85: hệ số các loại này chỉ là ước tính."],
], widths=[200, 420]))
add("<h2>3.3 Xem chi tiết một xe</h2>")
add(fig("22_vehicle_drawer", "Ngăn chi tiết xe"))
add("<p>Bấm mã xe ở bất kỳ bảng nào để xem thông số, tài xế, tuyến hôm nay, quãng đường, chi phí, CO₂ và tiến độ giao.</p>")

# ------------------------------------------------------------------ 4. dispatcher
add('<h1 id="s4">4. Điều phối viên</h1>')
add("<h2>4.1 Quản lý đơn hàng</h2>")
add(fig("30_orders", "Màn hình Đơn hàng"))
add(table(["Số", "Chức năng"], [
    [n(1), "Tìm theo mã đơn, tên khách, địa chỉ, số điện thoại."],
    [n(2), "Chọn file đơn hàng CSV hoặc XLSX."],
    [n(3), "Chế độ nhập: <b>Thay thế toàn bộ</b> hoặc <b>Thêm vào</b>."],
    [n(4), "Nhập file. Có dòng lỗi thì không lưu gì, sửa file rồi nhập lại. Thiếu thể tích chỉ là cảnh báo, đơn vẫn được lưu."],
    [n(5), "Mở form thêm một đơn (4.2)."],
    [n(6), "Sửa đơn (4.3). Nút <b>Xóa</b> bên dưới xóa đơn sau khi xác nhận."],
    [n(7), "Bấm mã đơn để xem chi tiết (4.4)."],
], widths=[40, 580]))
add("<p>Cột của file đơn: <code>order_id, customer_name, phone, address, latitude, longitude, weight_kg, volume_m3, delivery_window_start, delivery_window_end, service_time_min, priority, note</code>. Bắt buộc: mã đơn và tọa độ (hoặc địa chỉ đã định vị được). Giờ giao đến phải sau giờ giao từ.</p>")
add("<h2>4.2 Thêm đơn bằng địa chỉ</h2>")
add(fig("31_order_address", "Gõ địa chỉ, chọn trong danh sách gợi ý"))
add(steps(f"Bấm <b>Thêm đơn hàng</b>. Gõ địa chỉ vào ô {n(1)}, ví dụ “118 Bạch Đằng Bình Thạnh”.", f"Chọn đúng địa chỉ trong danh sách gợi ý {n(2)} (dùng chuột hoặc phím ↑ ↓ rồi Enter)."))
add(fig("32_order_form", "Các ô tự điền sau khi chọn địa chỉ (nền xanh nhạt)"))
add(steps(
    f"Hệ thống tự điền mã đơn tiếp theo {n(1)}, vĩ độ/kinh độ {n(2)}, khung giờ giao {n(3)} và thời gian dừng {n(4)}. Mọi ô đều sửa được.",
    f"Kiểm tra ghim trên bản đồ {n(5)}. Nếu lệch, bấm vào đúng vị trí trên bản đồ hoặc kéo ghim; tọa độ và địa chỉ cập nhật theo.",
    "Nhập tên khách, số điện thoại, khối lượng, thể tích, ghi chú.",
    f"Bấm <b>Lưu đơn</b> {n(6)}.",
))
add(note("Dòng chữ nhỏ dưới ô địa chỉ có thể nhắc “kiểm tra lại số nhà”: dịch vụ bản đồ đôi khi chỉ tìm được tới đầu hẻm hoặc tên đường. Hãy kiểm tra ghim trước khi lưu.", "warn"))
add("<h2>4.3 Sửa đơn</h2>")
add(fig("33_order_edit", "Sửa đơn: form mở sẵn dữ liệu của đơn"))
add(steps(f"Bấm <b>Sửa</b> trên dòng đơn. Form đổi thành <b>Sửa đơn hàng</b> {n(1)}; mã đơn bị khóa {n(2)}.", f"Sửa thông tin cần đổi rồi bấm <b>Cập nhật đơn</b> {n(3)}.", "Bấm <b>Làm mới form</b> nếu muốn hủy sửa."))
add("<h2>4.4 Chi tiết đơn</h2>")
add(fig("34_order_drawer", "Ngăn chi tiết đơn hàng"))
add("<p>Ngăn chi tiết cho biết khách, địa chỉ, khung giờ, xe được phân, thứ tự ghé, giờ dự kiến, trạng thái giao và vị trí ghi nhận khi tài xế bấm giao.</p>")

add("<h2>4.5 Lập tuyến (chạy tối ưu)</h2>")
add(fig("35_plan_setup", "Thiết lập trước khi chạy"))
add(steps(
    "Kiểm tra kho xuất phát (2.6), danh sách đơn (4.1) và xe sẵn sàng (3.2).",
    f"<b>Thời gian giải (giây)</b> {n(4)}: thời gian cho thuật toán tìm phương án, từ 1 đến 60 giây. 5–10 giây là đủ cho khoảng 150 đơn; nhiều đơn hơn nên tăng.",
    f"Bấm <b>Chạy tối ưu</b> {n(5)} và chờ đến khi nút trở lại bình thường.",
))
add(note("Ô <b>Giá CO₂ (VND/kg)</b>: để 0 thì bộ tối ưu chỉ giảm chi phí. Nhập một số dương (ví dụ 5.000) thì mỗi kg CO₂ được tính như một khoản chi phí, nên bộ tối ưu ưu tiên xe ít phát thải hơn. Mức này cần nghiệp vụ phê duyệt."))
add(fig("36_plan_result", "Kết quả tối ưu"))
add(table(["Số", "Đọc kết quả"], [
    [n(1), "Chỉ số chính: số đơn được phân công, số xe dùng, tổng km, tổng chi phí, CO₂ trực tiếp, CO₂ gián tiếp từ điện lưới (báo riêng), số chặng chạy giờ cao điểm. Khi baseline giao được ít đơn hơn, thẻ ghi “baseline chỉ giao … đơn” thay vì % để tránh so sánh không công bằng."],
    [n(2), "Bản đồ: mỗi xe một màu; số trên chấm = thứ tự giao. Nét đứt = xe điện. Chấm đỏ = đơn chưa phân công. Nét đỏ đứt = chặng có thể kẹt giờ cao điểm (ước tính)."],
    [n(3), "Các thẻ: <b>Tuyến theo xe</b>, <b>So sánh baseline</b>, <b>Chưa phân công</b>."],
    [n(4), "<b>Phát hành cho tài xế</b> (4.7)."],
], widths=[40, 580]))
add(fig("36b_plan_route", "Một tuyến: điểm, km, chi phí, CO₂, tải; mở “Thứ tự giao & hệ số phát thải”"))
add("<p>Mỗi thẻ xe cho biết số điểm, km, chi phí, CO₂, giờ chạy, mức tải và cảnh báo nguy cơ trễ. Mở <b>Thứ tự giao &amp; hệ số phát thải</b> để xem giờ dự kiến tới từng điểm và hệ số dùng để tính CO₂ (kèm nguồn, năm).</p>")
add("<h2>4.6 So sánh baseline và đơn chưa phân công</h2>")
add(fig("37_plan_compare", "So sánh với phương án cơ sở (baseline)"))
add(bullets(
    "<b>Baseline</b>: xếp đơn theo thứ tự nhập vào xe đầu tiên còn chỗ, không sắp xếp lại. Hai phương án dùng cùng đơn, cùng đội xe, cùng ràng buộc.",
    "Mũi tên xanh ▼ = phương án tối ưu tốt hơn. Mũi tên đỏ ▲ = kém hơn.",
    "Nếu hai bên giao số đơn khác nhau, hệ thống hiện cảnh báo vàng. Khi đó hãy so các chỉ số <b>/đơn</b> (chi phí/đơn, CO₂/đơn), không so tổng km.",
))
add(fig("38_plan_unassigned", "Đơn chưa phân công và lý do"))
add(table(["Lý do hiện trên màn hình", "Nên làm gì"], [
    ["Không có xe sẵn sàng", "Đánh dấu xe Sẵn sàng ở Đội xe."],
    ["Đơn vượt sức chứa mọi xe", "Kiểm tra khối lượng/thể tích đơn, hoặc dùng xe lớn hơn."],
    ["Không xe nào đến kịp khung giờ / quay về kho trong ca", "Nới khung giờ giao hoặc kéo dài ca xe."],
    ["Đội xe hết tải trọng/thời gian", "Thêm xe hoặc nới khung giờ, rồi chạy lại."],
], widths=[300, 320]))
add("<h2>4.7 Phát hành cho tài xế</h2>")
add(fig("39_published", "Phát hành phương án"))
add(steps(f"Khi hài lòng với kết quả, bấm <b>Phát hành cho tài xế</b> {n(1)}.", f"Dòng xác nhận {n(2)} hiện thời điểm phát hành. Từ lúc này, mỗi tài xế thấy tuyến của mình trên app."))
add(note("Phát hành phương án mới sẽ thay phương án đang chạy. Chỉ phát hành lại khi thật sự cần đổi tuyến trong ngày.", "warn"))
add("<h2>4.8 Theo dõi trực tiếp</h2>")
add(fig("40_live", "Theo dõi vị trí và tiến độ"))
add(table(["Số", "Ý nghĩa"], [
    [n(1), "Bản đồ: vị trí hiện tại của tài xế đang chia sẻ, vệt đường đã đi và các điểm giao. Tự làm mới mỗi 15 giây."],
    [n(2), "Số tài xế đang online / số xe trong kế hoạch."],
    [n(3), "Từng xe: trạng thái (Online, Chưa bắt đầu ca, Mất tín hiệu), thanh tiến độ (xanh = đã giao, đỏ = thất bại), điểm tiếp theo và khoảng cách."],
], widths=[40, 580]))
add("<p>“Mất tín hiệu” nghĩa là xe đang trong ca nhưng quá 5 phút không gửi vị trí: có thể tài xế tắt màn hình, mất mạng hoặc tắt GPS. Hãy gọi tài xế.</p>")

# ------------------------------------------------------------------ 5. driver
add('<h1 id="s5">5. Tài xế (app điện thoại)</h1>')
add("<h2>5.1 Mở app và đăng nhập</h2>")
add(fig("50_driver_login", "Đăng nhập trên điện thoại", phone=True))
add(steps(
    f"Mở {URL}/driver.html trên điện thoại. Mẹo: chọn “Thêm vào màn hình chính” để lần sau mở nhanh như một app.",
    f"Nhập tên đăng nhập {n(1)}, mật khẩu {n(2)}, bấm <b>Đăng nhập</b> {n(3)}.",
))
add("<h2>5.2 Bắt đầu ca và chia sẻ vị trí</h2>")
add(fig("51_driver_start", "Trước khi bắt đầu ca", phone=True))
add(steps(
    f"Bấm <b>▶ Bắt đầu ca</b> {n(1)}.",
    "Khi điện thoại hỏi quyền vị trí, chọn <b>Cho phép</b>. Nếu lỡ chặn, vào cài đặt trình duyệt để bật lại quyền vị trí cho trang này.",
    f"Bản đồ {n(2)} hiện tuyến và các điểm giao.",
))
add(fig("52_driver_sharing", "Đang chia sẻ vị trí", phone=True))
add(bullets(
    f"Khung xanh {n(1)} = đang chia sẻ vị trí, gửi mỗi 20 giây. Giữ màn hình mở và app ở phía trước để không bị gián đoạn.",
    f"Chấm xanh trên bản đồ {n(2)} là vị trí của bạn. Bấm <b>Vị trí của tôi</b> {n(3)} để đưa bản đồ về chỗ bạn đang đứng.",
    "Mất mạng: vị trí được lưu tạm trên máy và tự gửi khi có mạng lại.",
))
add("<h2>5.3 Giao đơn</h2>")
add(fig("53_driver_next", "Thẻ điểm tiếp theo", phone=True))
add(steps(
    "Thẻ <b>Điểm tiếp theo</b> cho biết tên khách, mã đơn, địa chỉ, giờ dự kiến, khối lượng, thời gian dừng và ghi chú (ví dụ “Hàng dễ vỡ”).",
    f"<b>Gọi khách</b> {n(1)}: gọi ngay số của khách.",
    f"<b>Chỉ đường</b> {n(2)}: mở Google Maps dẫn đường tới điểm giao.",
    f"Giao xong, bấm <b>Đã giao</b> {n(3)} khi đang đứng tại điểm giao.",
))
add(note("Khi bấm Đã giao, app ghi kèm vị trí GPS. Nếu bạn ở xa điểm giao quá 300 m, đơn vẫn được ghi nhận nhưng có cảnh báo “Xa điểm giao” để điều phối kiểm tra. Hãy bấm khi đã tới nơi."))
add("<h2>5.4 Không giao được</h2>")
add(fig("54_driver_fail", "Chọn lý do không giao được", phone=True))
add(steps(
    f"Bấm <b>Không giao được</b> ({n(4)} ở hình trước).",
    f"Chọn lý do {n(1)}: Khách vắng nhà / không liên lạc được; Sai địa chỉ / không tìm thấy; Khách từ chối nhận; Hàng hư hỏng; Không tiếp cận được; Hết thời gian ca; Lý do khác. Có thể ghi chú thêm.",
    f"Bấm <b>Xác nhận không giao được</b> {n(2)}. Điều phối thấy ngay trên màn hình của họ.",
))
add("<h2>5.5 Xem đơn đã xử lý, hoàn tác</h2>")
add(fig("55_driver_done", "Danh sách đã xử lý", phone=True))
add(bullets(
    f"Chuyển giữa <b>Còn lại</b> và <b>Đã xử lý</b> {n(1)}.",
    f"Bấm nhầm: bấm <b>Hoàn tác</b> {n(2)} để đưa đơn về trạng thái chưa giao.",
    "Nút ↻ trên cùng: tải lại tuyến (ví dụ khi điều phối vừa phát hành tuyến mới).",
    "Hết ca: bấm <b>Kết thúc ca</b> trong khung xanh để dừng chia sẻ vị trí. App không theo dõi vị trí ngoài ca.",
))

# ------------------------------------------------------------------ 6. ops
add('<h1 id="s6">6. Quản lý vận hành</h1>')
add("<h2>6.1 Tổng quan</h2>")
add(fig("60_overview", "Trang Tổng quan"))
add(table(["Số", "Ý nghĩa"], [
    [n(1), "Quy trình hôm nay: bước nào đã xong (dấu ✔), bước tiếp theo cần làm."],
    [n(2), "Chỉ số chính của phương án đang phát hành: đơn đã phân công, xe dùng, km, chi phí, CO₂, tiến độ giao, tài xế online."],
    [n(3), "Tiến độ theo xe: thanh tiến độ, điểm tiếp theo, khoảng cách."],
    [n(4), "Cần chú ý: đơn chưa phân công, xe mất tín hiệu, đơn giao thất bại. Bấm <b>Xem</b> để tới chỗ xử lý."],
], widths=[40, 580]))
add("<h2>6.2 Phân tích</h2>")
add(fig("61_analytics", "Phân tích: chỉ số hiệu quả, giờ cao điểm và biểu đồ"))
add(bullets(
    "Hàng chỉ số hiệu quả: km/đơn, điểm/xe, tải trung bình, tỷ lệ xe dùng, tỷ lệ km do xe điện chạy, khối lượng trung bình/đơn.",
    "<b>Giờ cao điểm (ước tính)</b>: số chặng rơi vào 07:00–09:00 và 16:30–19:00, số phút có thể trễ thêm, số đơn có nguy cơ trễ khung giờ. Đây là ước tính (tốc độ giờ cao điểm = 60% bình thường), chưa dùng dữ liệu giao thông thật.",
    "Biểu đồ: chi phí theo xe, % thay đổi so với baseline, lịch ghé theo giờ, phát thải theo nhiên liệu, đơn theo quận, mức sử dụng tải trọng, đơn theo khung giờ, kết quả giao và lý do thất bại. Rê chuột vào cột để xem số.",
))
add("<h2>6.3 Kịch bản nhiên liệu</h2>")
add(fig("62_fuel", "Thiết lập kịch bản đổi nhiên liệu"))
add(steps(
    "Vào <b>Kịch bản nhiên liệu</b>. Bảng dùng phương án tối ưu mới nhất; xe có nhãn “không dùng” không ảnh hưởng kết quả.",
    f"Chọn nhiên liệu mới cho xe muốn thử {n(1)}, ví dụ E5 → E10.",
    f"Nhập mức tiêu hao mới nếu biết {n(2)}. Để trống = giữ mức cũ, hệ thống sẽ cảnh báo vì nhiên liệu khác thường tiêu hao khác.",
    f"Chọn chế độ {n(3)}: <b>Cùng tuyến</b> (giữ nguyên tuyến, chỉ đổi nhiên liệu — để thấy riêng tác động của nhiên liệu) hoặc <b>Tối ưu lại tuyến</b> (chạy lại bộ tối ưu với cấu hình mới).",
    f"Bấm <b>Chạy kịch bản</b> {n(4)}.",
))
add(fig("63_fuel_result", "Kết quả kịch bản so với phương án hiện tại"))
add(bullets(
    "Bảng so sánh: km, thời gian, chi phí, chi phí năng lượng, CO₂ trực tiếp, CO₂ điện lưới, CO₂/km, chi phí/đơn, CO₂/đơn, % thay đổi.",
    "Dòng <b>CO₂ hóa thạch / sinh học</b>: phần CO₂ từ ethanol trong xăng sinh học được báo riêng.",
    "Khung vàng: cảnh báo (thiếu giá, hệ số chỉ để mô phỏng, đang dùng lại mức tiêu hao cũ…). Đọc kỹ trước khi dùng số liệu.",
    "Đổi sang E20, E25, E85 phải tích “Xác nhận mô phỏng”. Đổi xe xăng sang điện không được phép vì loại xe không tương thích.",
))
add("<h2>6.4 Lịch sử và xuất báo cáo</h2>")
add(fig("64_history", "Lịch sử các lần tối ưu"))
add(bullets(
    f"Bảng {n(1)} liệt kê các lần tối ưu (giữ 20 lần gần nhất), người chạy, số đơn, số xe, km, chi phí, CO₂. Nhãn “đang phát hành” đánh dấu phương án tài xế đang chạy.",
    "<b>Mở</b>: xem lại kết quả lần đó ở trang Lập tuyến.",
    "<b>XLSX</b> / <b>CSV</b>: tải báo cáo gồm so sánh baseline với tối ưu, từng tuyến (thứ tự điểm, km, nhiên liệu, chi phí, CO₂, hệ số và nguồn), đơn chưa phân công kèm lý do, các kịch bản nhiên liệu đã chạy, kết quả giao thực tế (nếu đã phát hành) và các giả định (phiên bản hệ số, phạm vi phát thải, cách tính quãng đường).",
))
add("<h2>6.5 Trợ lý AI</h2>")
add(fig("65_ai", "Trợ lý AI"))
add(steps(f"Bấm nút <b>Trợ lý AI</b> ở góc dưới bên phải.", f"Chọn một câu hỏi gợi ý {n(1)} hoặc tự gõ câu hỏi {n(2)}, ví dụ “Vì sao có đơn chưa được phân công?”."))
add(bullets(
    "Trợ lý chỉ dùng số liệu của phương án đang xem. Tên, số điện thoại, địa chỉ khách không được gửi đi.",
    "Hiện trợ lý <b>chưa bật</b> trên bản online vì chưa cấu hình khóa API (ANTHROPIC_API_KEY). IT bật khi nhóm dự án đồng ý chi phí.",
    "Câu trả lời của AI chỉ để tham khảo; số liệu chính thức là số trên các màn hình.",
))
add("<h2>6.6 Phương pháp và giả định</h2>")
add(fig("66_method", "Trang Phương pháp & giả định"))
add("<p>Trang này ghi công thức tính nhiên liệu, CO₂, chi phí, nguồn và năm của hệ số, phạm vi phát thải (CO₂ trực tiếp từ nhiên liệu khi vận hành), cách tính quãng đường và định nghĩa baseline. Dùng trang này khi cần đối chiếu số liệu.</p>")
add("<h2>6.7 Đổi ngôn ngữ</h2>")
add(fig("67_lang_en", "Giao diện tiếng Anh"))
add(f"<p>Bấm VI, EN hoặc 中文 {n(1)} ở góc trên bên phải. Lựa chọn được nhớ trên máy đó.</p>")

# ------------------------------------------------------------------ 7. faq
add('<h1 id="s7">7. Câu hỏi thường gặp và lưu ý</h1>')
add(table(["Tình huống", "Giải thích / cách xử lý"], [
    ["Số liệu, đơn hàng tự quay về như ban đầu", "Bản online dùng máy chủ miễn phí: mỗi lần máy chủ khởi động lại, dữ liệu quay về bộ mẫu và tài khoản thử nghiệm. Đây là giới hạn của môi trường thử, không phải lỗi."],
    ["Trang mở rất chậm lần đầu", "Máy chủ miễn phí đang “ngủ”. Chờ khoảng 1 phút rồi tải lại."],
    ["Điều phối không thấy vị trí tài xế", "Tài xế cần bấm Bắt đầu ca, cho phép quyền vị trí và giữ app mở. Quá 5 phút không gửi vị trí sẽ hiện “Mất tín hiệu”."],
    ["Tài xế không thấy tuyến", "Điều phối chưa phát hành, hoặc tài khoản tài xế chưa được gán xe (Quản trị kiểm tra), hoặc xe đó không có đơn trong phương án."],
    ["Đơn báo “Xa điểm giao”", "Tài xế bấm Đã giao khi cách điểm giao hơn 300 m (hoặc tọa độ đơn sai). Kiểm tra lại với tài xế và tọa độ đơn."],
    ["Chi phí hiện “—”", "Nhiên liệu của xe chưa có giá. Quản trị nhập giá ở Hệ số, giá & trọng số."],
    ["Số liệu có dùng chính thức được không?", "Chưa. Hệ số phát thải là giá trị mặc định quốc tế, giá điện là giả định, quãng đường là ước tính (đường chim bay × 1,3). Cần nghiệp vụ phê duyệt nguồn trước khi dùng chính thức."],
    ["Bị khóa đăng nhập", "Do nhập sai mật khẩu 5 lần. Chờ 5 phút hoặc nhờ Quản trị đặt lại mật khẩu."],
], widths=[200, 420]))
add("<h2>Báo lỗi và đề xuất thay đổi</h2>")
add("<p>Ghi lỗi (Bug) hoặc yêu cầu thay đổi (CR) theo mẫu trong thư mục <code>bug-reports/</code> của dự án: mỗi lỗi một file, có các bước tái hiện, kết quả thực tế kèm ảnh chụp màn hình và kết quả mong đợi. Ghi rõ tài khoản, vai trò, ngôn ngữ và thời điểm xảy ra.</p>")

CSS = """
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11pt; color: #1f2937; line-height: 1.5; max-width: 820px; margin: 24px auto; padding: 0 16px; background: #ffffff; }
h1 { page-break-before: always; font-size: 20pt; color: #166534; border-bottom: 2px solid #166534; padding-bottom: 4px; margin-top: 32px; }
h1.title { font-size: 30pt; border: none; margin: 40px 0 0; page-break-before: auto; }
h2 { font-size: 14pt; color: #14532d; margin-top: 22px; page-break-after: avoid; }
h1, h3 { page-break-after: avoid; }
h3 { font-size: 12pt; color: #14532d; }
p.subtitle { font-size: 18pt; color: #374151; margin: 4px 0 16px; }
p.meta { color: #4b5563; }
a { color: #1d4ed8; }
code { font-family: Consolas, monospace; font-size: 9.5pt; background: #f3f4f6; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 14px; }
th, td { border: 1px solid #d1d5db; padding: 3px 6px; vertical-align: top; text-align: left; font-size: 10pt; }
th { background: #dcfce7; color: #14532d; }
p.fig { text-align: center; margin: 12px 0 2px; }
p.fig img { border: 1px solid #d1d5db; }
@media screen and (max-width: 700px) { p.fig img { max-width: 100%; height: auto; } table { font-size: 9pt; } }
p.cap { text-align: center; font-size: 9.5pt; color: #6b7280; font-style: italic; margin: 0 0 12px; }
b.num { color: #e11d48; }
p.note { border-left: 4px solid #2563eb; background: #eff6ff; padding: 6px 10px; }
p.note.warn { border-left-color: #d97706; background: #fffbeb; }
ol.toc li { margin: 2px 0; }
"""

html = f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>GreenRoute AI — Hướng dẫn sử dụng</title><style>{CSS}</style></head>
<body>{''.join(body)}</body></html>"""
out = HERE / "GreenRoute_AI_Huong_dan_su_dung.html"
out.write_text(html, encoding="utf-8")
missing = [p for p in __import__("re").findall(r'img/([^"]+)\.png', html) if not (HERE / "img" / f"{p}.png").exists()]
print(out, "figures:", FIG["n"], "missing:", missing)
