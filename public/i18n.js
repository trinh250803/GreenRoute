'use strict';
/* VI/EN switch. Vietnamese is the source language; English comes from the dictionary below.
   A MutationObserver translates every text node and placeholder/title as it appears, so
   dynamically rendered tables, toasts and map popups are covered without touching render code.
   Server messages (validation errors, reasons) stay in Vietnamese. */
const I18N = (() => {
  const EN = {
    // Navigation & shell
    'Tổng quan': 'Overview', 'Lập tuyến': 'Route planning', 'Theo dõi trực tiếp': 'Live tracking', 'Đơn hàng': 'Orders', 'Đội xe': 'Fleet',
    'Kịch bản nhiên liệu': 'Fuel scenarios', 'Lịch sử & báo cáo': 'History & reports', 'Quản trị': 'Administration', 'Phương pháp & giả định': 'Method & assumptions',
    'Vận hành': 'Operations', 'Dữ liệu': 'Data', 'Đổi mật khẩu': 'Change password', 'Đăng xuất': 'Sign out', 'Đăng nhập': 'Sign in', 'Thoát': 'Exit',
    'Quy trình, chỉ số và cảnh báo trong ngày': "Today's workflow, KPIs and alerts",
    'OR-Tools phân đơn cho đội xe, so sánh với phương án cơ sở': 'OR-Tools assigns orders to the fleet and compares with the baseline',
    'Vị trí tài xế, vệt di chuyển và tiến độ giao hàng': 'Driver positions, trails and delivery progress',
    'Nhập, kiểm tra và quản lý đơn': 'Import, validate and manage orders', 'Sức chứa, chi phí, nhiên liệu và tình trạng xe': 'Capacity, cost, fuel and availability',
    'So sánh chi phí và phát thải khi đổi nhiên liệu': 'Compare cost and emissions when switching fuel', 'Các lần tối ưu, xuất CSV/XLSX': 'Optimisation runs, CSV/XLSX export',
    'Tài khoản, cấu hình hệ số, dữ liệu mẫu, nhật ký': 'Accounts, factor configuration, sample data, audit log',
    'Công thức, nguồn hệ số, phạm vi phát thải': 'Formulas, factor sources, emission scope',
    'Tối ưu giao hàng chặng cuối đa phương tiện': 'Multi-vehicle last-mile delivery optimisation',
    'Tên đăng nhập': 'Username', 'Mật khẩu': 'Password', 'Mật khẩu hiện tại': 'Current password', 'Mật khẩu mới': 'New password',
    'Nhập lại mật khẩu mới': 'Repeat new password', 'Lưu mật khẩu': 'Save password', 'Tối thiểu 8 ký tự.': 'At least 8 characters.', 'Hủy': 'Cancel',
    'Quản trị hệ thống': 'System administrator', 'Điều phối viên': 'Dispatcher', 'Quản lý đội xe': 'Fleet manager', 'Quản lý vận hành': 'Operations manager', 'Tài xế': 'Driver',
    // Overview
    'Quy trình hôm nay': "Today's workflow", 'Đơn hàng ': 'Orders', 'Lập tuyến tối ưu': 'Optimise routes', 'Phát hành cho tài xế': 'Publish to drivers',
    'Theo dõi giao hàng': 'Track deliveries', 'Làm ngay →': 'Do it now →', 'Mở': 'Open', 'Chưa chạy': 'Not run yet', 'Chưa phát hành': 'Not published',
    'Chưa có tuyến chạy': 'No active routes', 'Điều phối viên phụ trách': "Dispatcher's task", 'Tiến độ theo xe': 'Progress by vehicle',
    'Xem bản đồ trực tiếp →': 'Open live map →', 'Cần chú ý': 'Needs attention', '✓ Không có cảnh báo.': '✓ No alerts.',
    'Đơn đã phân công': 'Orders assigned', 'Xe sử dụng': 'Vehicles used', 'Tổng quãng đường': 'Total distance', 'Tổng chi phí': 'Total cost',
    'CO₂ trực tiếp': 'Direct CO₂', 'Tiến độ giao': 'Delivery progress', 'Tài xế online': 'Drivers online', 'chưa tối ưu': 'not optimised', 'chưa phát hành': 'not published',
    'Chưa có tuyến được phát hành.': 'No published routes yet.', 'chưa gán tài xế': 'no driver', 'chưa gán': 'unassigned', '✓ Hoàn thành tuyến': '✓ Route completed',
    '⏸ Chưa bắt đầu ca': '⏸ Shift not started', 'Xem': 'View', 'Phân tích': 'Analytics', 'Hiệu quả': 'Efficiency', 'km / đơn': 'km / order',
    'Điểm / xe': 'Stops / vehicle', 'Tải trung bình': 'Average load', 'Xe dùng / xe sẵn sàng': 'Vehicles used / available', 'Tỷ lệ km xe điện': 'EV share of km',
    'Khối lượng TB / đơn': 'Avg parcel weight', 'Giờ cao điểm (ước tính)': 'Peak hours (estimate)', 'chặng đi giờ cao điểm': 'legs in peak hours',
    'phút trễ thêm (ước tính)': 'extra minutes (estimate)', 'đơn có nguy cơ trễ khung giờ': 'orders at risk of missing the window',
    'Chi phí theo xe': 'Cost by vehicle', 'Chi phí vận hành': 'Operating cost', 'Chi phí năng lượng': 'Energy cost', 'Phát thải theo nhiên liệu': 'Emissions by fuel',
    'CO₂ gián tiếp (điện lưới)': 'Indirect CO₂ (grid)', 'Đơn theo quận': 'Orders by district', 'Đơn theo khung giờ giao': 'Orders by delivery window',
    'Lịch ghé theo giờ': 'Planned stops by hour', 'Giờ thường': 'Normal hours', 'Giờ cao điểm': 'Peak hours', 'Mức sử dụng tải trọng theo xe': 'Load utilisation by vehicle',
    'Thay đổi so với baseline (%)': 'Change vs baseline (%)', 'Xanh = tốt hơn · Đỏ = kém hơn': 'Blue = better · Red = worse', 'Kết quả giao hàng': 'Delivery outcomes',
    'Lý do giao thất bại': 'Failure reasons',
    'Ước tính: trong giờ cao điểm tốc độ còn 60% tốc độ thường. Chưa dùng dữ liệu giao thông thời gian thực.': 'Estimate: peak-hour speed is 60% of normal. No real-time traffic data is used yet.',
    'Hiệu quả': 'Efficiency', 'Chưa có đơn thất bại.': 'No failed deliveries.', 'Đã xử lý': 'Processed', 'Đúng giờ': 'On time',
    'Đúng vị trí': 'At location', 'Xa điểm giao': 'Far from stop', 'Không có định vị': 'No location', 'đơn': 'orders', 'Đơn': 'Orders', 'Cả ngày': 'All day',
    'Sáng (<11h)': 'Morning (<11h)', 'Trưa (11–14h)': 'Midday (11–14h)', 'Chiều (14–17h)': 'Afternoon (14–17h)', 'Tối (≥17h)': 'Evening (≥17h)',
    'Chưa có dữ liệu phân tích — hãy chạy tối ưu.': 'No analytics yet — run an optimisation.', 'Xem bảng số liệu': 'Show data table',
    // Plan
    'Kho xuất phát': 'Depot', 'Vĩ độ': 'Latitude', 'Kinh độ': 'Longitude', 'Lưu kho': 'Save depot', '📍 Chọn trên bản đồ': '📍 Pick on map',
    'Giá CO₂ (VND/kg)': 'CO₂ price (VND/kg)', 'Thời gian giải (giây)': 'Solve time (s)', '▶ Chạy tối ưu': '▶ Optimise', '📤 Phát hành cho tài xế': '📤 Publish to drivers',
    '⏳ OR-Tools đang tính…': '⏳ OR-Tools is solving…', 'Bản đồ tuyến': 'Route map', 'Tuyến theo xe': 'Routes', 'So sánh baseline': 'Baseline comparison',
    'Chưa phân công': 'Unassigned', 'Nét đứt = xe điện · Chấm đỏ = chưa phân công': 'Dashed = electric · Red dot = unassigned',
    'Thứ tự giao & hệ số phát thải': 'Stop sequence & emission factor', 'Quãng đường': 'Distance', 'CO₂ gián tiếp (điện)': 'Indirect CO₂ (grid)',
    'báo cáo riêng, không cộng': 'reported separately, not added', '✓ Tất cả đơn đã được phân công.': '✓ All orders assigned.', 'Chỉ số': 'Metric',
    'Thay đổi': 'Change', 'Lý do': 'Reason', 'Kho': 'Depot', 'Xe': 'Vehicle', 'điểm': 'stops', 'Không có hệ số': 'No factor', 'mô phỏng': 'simulated',
    'Quãng đường (km)': 'Distance (km)', 'Tổng thời gian (phút)': 'Total time (min)', 'Tổng chi phí (VND)': 'Total cost (VND)', 'Chi phí năng lượng (VND)': 'Energy cost (VND)',
    'CO₂ trực tiếp (kg)': 'Direct CO₂ (kg)', 'CO₂ gián tiếp điện lưới (kg)': 'Indirect grid CO₂ (kg)', 'CO₂ / km (kg)': 'CO₂ / km (kg)', 'Chi phí / đơn (VND)': 'Cost / order (VND)',
    'CO₂ / đơn (kg)': 'CO₂ / order (kg)', 'Số xe dùng': 'Vehicles used', 'Đơn chưa phân công': 'Unassigned orders', 'Phương án hiện tại': 'Current plan', 'Kịch bản': 'Scenario',
    'Nét đỏ đứt = chặng đi giờ cao điểm (ước tính)': 'Red dashes = legs in peak hours (estimate)', 'nguy cơ trễ': 'late risk', 'giờ cao điểm': 'peak hours',
    'Chưa có phương án. Bấm': 'No plan yet. Click', 'để OR-Tools phân đơn cho đội xe.': 'to let OR-Tools assign orders to the fleet.', 'Chạy tối ưu': 'Optimise',
    // Live
    'Vị trí đội xe': 'Fleet positions', 'Xe đang chạy': 'Active vehicles', 'Chi tiết giao hàng': 'Delivery details', '↻ Làm mới': '↻ Refresh', 'Chưa giao': 'Pending',
    'Đã giao': 'Delivered', 'Thất bại': 'Failed', 'Dự kiến': 'Planned', 'Khung giờ': 'Window', 'Trạng thái': 'Status', 'Thực tế': 'Actual',
    'Xác nhận vị trí': 'Location check', 'Lý do / ghi chú': 'Reason / note', 'trễ': 'late', 'không có định vị': 'no location', '📍 đúng vị trí': '📍 at location',
    '⚠ xa điểm giao': '⚠ far from stop', 'xem': 'view', 'Chưa có phương án nào được phát hành.': 'No plan has been published yet.',
    // Orders / vehicles
    'Tìm kiếm': 'Search', 'Mã đơn, khách hàng, địa chỉ, SĐT…': 'Order ID, customer, address, phone…', 'Nhập CSV/XLSX': 'Import CSV/XLSX', 'Chế độ': 'Mode',
    'Thay thế toàn bộ': 'Replace all', 'Thêm vào': 'Append', '⬆ Nhập file': '⬆ Import file', 'Xóa tất cả': 'Delete all', 'Thêm đơn thủ công': 'Add order manually',
    'Mã đơn *': 'Order ID *', 'Khách hàng': 'Customer', 'Số điện thoại': 'Phone', 'Địa chỉ': 'Address', 'Vĩ độ *': 'Latitude *', 'Kinh độ *': 'Longitude *',
    'Khối lượng (kg)': 'Weight (kg)', 'Thể tích (m³)': 'Volume (m³)', 'Giao từ (HH:MM)': 'Window from (HH:MM)', 'Giao đến (HH:MM)': 'Window to (HH:MM)',
    'Thời gian dừng (phút)': 'Service time (min)', 'Ưu tiên': 'Priority', 'Thường': 'Normal', 'Ghi chú': 'Note', 'Lưu đơn': 'Save order', 'Mã đơn': 'Order ID',
    'Dừng': 'Stop', 'Xóa': 'Delete', 'ưu tiên': 'priority', 'cả ngày': 'all day', 'Chi tiết': 'Details',
    'Thêm / sửa xe (trùng mã xe sẽ cập nhật)': 'Add / edit vehicle (same ID updates it)', 'Mã xe *': 'Vehicle ID *', 'Loại xe': 'Vehicle type', 'Nhiên liệu': 'Fuel',
    'Tải trọng (kg) *': 'Payload (kg) *', 'Chi phí vận hành (VND/km) *': 'Operating cost (VND/km) *', 'Chi phí cố định/ngày': 'Fixed cost/day', 'Tiêu hao (/100 km)': 'Consumption (/100 km)',
    'Giá năng lượng (trống = mặc định)': 'Energy price (empty = default)', 'Hệ số phát thải tùy chỉnh': 'Custom emission factor', 'Nguồn hệ số': 'Factor source',
    'Bắt đầu ca': 'Shift start', 'Kết thúc ca': 'End shift', 'Sẵn sàng': 'Available', 'Xác nhận nhiên liệu mô phỏng': 'Confirm simulated fuel', 'Lưu xe': 'Save vehicle',
    'Tải trọng': 'Payload', 'Thể tích': 'Volume', 'Cố định': 'Fixed', 'Tiêu hao': 'Consumption', 'Giá NL': 'Energy price', 'Ca': 'Shift', 'sẵn sàng': 'available',
    'nghỉ': 'off', 'mặc định': 'default', 'thiếu': 'missing', 'thiếu dữ liệu': 'missing data', 'Xe máy xăng': 'Petrol motorbike', 'Xe máy điện': 'Electric motorbike',
    'Xe van': 'Van', 'Xe tải nhỏ': 'Small truck', 'Van điện': 'Electric van', 'Điện lưới': 'Grid electricity', 'Dầu diesel': 'Diesel', 'Xăng E5 RON92': 'E5 RON92 petrol',
    'Xăng E10': 'E10 petrol', 'Xăng nền (E0)': 'Base petrol (E0)', 'Tài xế': 'Driver',
    // Fuel / history / admin / method
    'Cấu hình kịch bản': 'Scenario setup', 'Tên kịch bản': 'Scenario name', 'Cùng tuyến': 'Same routes', 'Tối ưu lại tuyến': 'Re-optimise routes',
    '▶ Chạy kịch bản': '▶ Run scenario', 'Hiện tại': 'Current', 'Nhiên liệu mới': 'New fuel', 'Giá': 'Price', 'Xác nhận mô phỏng': 'Confirm simulation',
    'không dùng': 'unused', 'Thời điểm': 'Time', 'Người chạy': 'Run by', 'đang phát hành': 'published', '⬇ XLSX': '⬇ XLSX', '⬇ CSV': '⬇ CSV',
    'Chưa có lần tối ưu nào.': 'No optimisation runs yet.', '👥 Tài khoản & phân quyền': '👥 Accounts & roles', '⚙️ Hệ số, giá & trọng số': '⚙️ Factors, prices & weights',
    '🗂 Dữ liệu mẫu': '🗂 Sample data', '📜 Nhật ký': '📜 Audit log', 'Tạo tài khoản': 'Create account', 'Họ tên': 'Full name', 'Vai trò': 'Role',
    'Xe (cho tài xế)': 'Vehicle (drivers)', 'Mật khẩu tạm (≥ 8 ký tự) *': 'Temporary password (≥ 8 chars) *', 'Tài khoản': 'Account', 'Đăng nhập gần nhất': 'Last sign-in',
    'Hoạt động': 'Active', 'Đã khóa': 'Locked', 'Lưu': 'Save', 'Đặt lại MK': 'Reset password', 'chờ đổi MK': 'must change password',
    'Hệ số phát thải nền': 'Base emission factors', 'Khóa': 'Key', 'Giá trị': 'Value', 'Đơn vị': 'Unit', 'Nguồn': 'Source', 'Năm': 'Year', 'Khu vực': 'Region',
    'Nhiên liệu: giá mặc định & trạng thái': 'Fuels: default price & status', 'Mã': 'Code', 'Tên': 'Name', 'Giá mặc định': 'Default price',
    'Tỷ lệ ethanol (0–1)': 'Ethanol share (0–1)', 'Chính thức': 'Official', 'có': 'yes', 'không': 'no', 'Nguồn giá': 'Price source', 'Ngày áp dụng': 'Effective date',
    'Tốc độ trung bình theo loại xe': 'Average speed by vehicle type', 'Tối ưu, định tuyến & theo dõi': 'Optimisation, routing & tracking',
    'Giá CO₂ quy đổi (VND/kg)': 'CO₂ shadow price (VND/kg)', 'Chi phí thời gian (VND/phút)': 'Time cost (VND/min)', 'Thời gian giải mặc định (giây)': 'Default solve time (s)',
    'Hệ số đường vòng (khi không có OSRM)': 'Detour factor (without OSRM)', 'Ngưỡng xác nhận vị trí giao (m)': 'Delivery location threshold (m)',
    'Chu kỳ gửi vị trí tài xế (giây)': 'Driver location interval (s)', 'Coi là mất tín hiệu sau (giây)': 'Lost signal after (s)',
    'Tốc độ giờ cao điểm (0–1 × tốc độ thường)': 'Peak-hour speed (0–1 × normal)', 'Gắn nhãn “Dữ liệu minh họa”': 'Show “illustrative data” label',
    'Lý do / nguồn / quyết định phê duyệt *': 'Reason / source / approval *', 'Lưu phiên bản mới': 'Save new version', 'Lịch sử phiên bản': 'Version history',
    'Phiên bản': 'Version', 'Người sửa': 'Changed by', 'Nạp dữ liệu minh họa': 'Load sample data', 'Bộ dữ liệu': 'Dataset', 'Nạp dữ liệu': 'Load data',
    'Người dùng': 'User', 'Hành động': 'Action', 'hệ thống': 'system', 'Phạm vi phát thải': 'Emission scope', 'Công thức': 'Formulas', 'Hệ số nền': 'Base factors',
    'Định tuyến & baseline': 'Routing & baseline', 'Theo dõi vị trí': 'Location tracking', 'Giá nhiên liệu': 'Fuel prices',
    // Detail drawer & assistant
    'Chi tiết đơn hàng': 'Order details', 'Chi tiết xe': 'Vehicle details', 'Thông tin đơn': 'Order info', 'Phân công': 'Assignment', 'Giao hàng': 'Delivery',
    'Lịch sử': 'History', 'Quận': 'District', 'Tọa độ': 'Coordinates', 'Thứ tự': 'Sequence', 'Đến dự kiến': 'Planned arrival', 'Chờ': 'Wait',
    'Chặng': 'Leg', 'Dự kiến nếu kẹt giờ cao điểm': 'If peak traffic', 'Chưa có kết quả giao': 'No delivery outcome yet', 'Người ghi nhận': 'Recorded by',
    'Không có lịch sử thao tác.': 'No activity yet.', 'Thông số xe': 'Vehicle specs', 'Tuyến hôm nay': "Today's route", 'Theo dõi': 'Tracking',
    'Đang chia sẻ vị trí': 'Sharing location', 'Không chia sẻ': 'Not sharing', 'Không có tuyến trong phương án hiện tại.': 'No route in the current plan.',
    '✨ Trợ lý AI': '✨ AI assistant', 'Trợ lý AI': 'AI assistant', 'Hỏi về phương án, đơn hàng, chi phí, CO₂…': 'Ask about the plan, orders, cost, CO₂…', 'Gửi': 'Send',
    'Xe nào chạy xa nhất và vì sao?': 'Which vehicle drives furthest and why?', 'Vì sao có đơn chưa được phân công?': 'Why are some orders unassigned?',
    'Làm sao giảm CO₂ mà không tăng nhiều chi phí?': 'How can we cut CO₂ without much extra cost?', 'Tóm tắt tình hình giao hàng hôm nay': "Summarise today's deliveries",
    'Đang suy nghĩ…': 'Thinking…', 'Xóa hội thoại': 'Clear chat',
    'Trợ lý chỉ dùng số liệu của phương án đang xem; không gửi tên, SĐT, địa chỉ khách.': 'The assistant only sees plan figures; customer names, phones and addresses are never sent.',
    // Driver app
    'Tuyến của tôi': 'My route', 'Điểm tiếp theo': 'Next stop', '📞 Gọi khách': '📞 Call customer', '🧭 Chỉ đường': '🧭 Navigate', '✅ Đã giao': '✅ Delivered',
    '✖ Không giao được': '✖ Could not deliver', 'Xác nhận không giao được': 'Confirm failed delivery', '— Chọn lý do —': '— Choose a reason —',
    'Ghi chú (không bắt buộc)': 'Note (optional)', 'Còn lại': 'Remaining', '↩ Hoàn tác': '↩ Undo', '▶ Bắt đầu ca': '▶ Start shift', '📍 Vị trí của tôi': '📍 My location',
    'Chưa chia sẻ vị trí': 'Not sharing location', 'Bấm để điều phối viên thấy bạn đang ở đâu trong ca làm việc.': 'Tap so dispatch can see where you are during your shift.',
    'Giữ màn hình mở để không bị gián đoạn.': 'Keep the screen on to avoid interruptions.', 'Không còn điểm nào khác.': 'No other stops.',
    'Chưa xử lý điểm nào.': 'No stops processed yet.', '🎉': '🎉', 'Khách vắng nhà / không liên lạc được': 'Customer absent / unreachable',
    'Sai địa chỉ / không tìm thấy': 'Wrong / unknown address', 'Khách từ chối nhận': 'Customer refused', 'Hàng hư hỏng': 'Damaged goods',
    'Không tiếp cận được (cấm đường, khu hạn chế)': 'No access (road ban, restricted area)', 'Hết thời gian ca': 'Shift time ran out', 'Lý do khác': 'Other reason',
  };
  const PATTERNS = [
    [/^(\d+) đơn đã nhập$/, '$1 orders imported'], [/^(\d+)\/(\d+) xe sẵn sàng · (\d+) xe có tài xế$/, '$1/$2 vehicles available · $3 with a driver'],
    [/^(\d+) xe sẵn sàng$/, '$1 vehicles available'], [/^(\d+) xe trong kế hoạch$/, '$1 vehicles in plan'], [/^([\d.,]+)% đơn$/, '$1% of orders'],
    [/^(\d+)\/(\d+) thành công$/, '$1/$2 successful'], [/^Cập nhật (.+)$/, 'Updated $1'], [/^Đơn hàng \((.+)\)$/, 'Orders ($1)'],
    [/^Đội xe \((\d+) xe · (\d+) sẵn sàng\)$/, 'Fleet ($1 vehicles · $2 available)'], [/^(\d+) điểm$/, '$1 stops'], [/^tải (.+)$/, 'load $1'],
    [/^Tiếp: (.*)$/, 'Next: $1'], [/^\(dự kiến (.+)\)$/, '(planned $1)'], [/^cách (.+) km$/, '$1 km away'], [/^đã đi (.+) km$/, '$1 km travelled'],
    [/^(\d+) online$/, '$1 online'], [/^(\d+) xe$/, '$1 vehicles'], [/^Online · (.+) trước$/, 'Online · $1 ago'], [/^(\d+)s trước$/, '$1s ago'],
    [/^(\d+) phút trước$/, '$1 min ago'], [/^Tự làm mới 15 giây · (.+)$/, 'Auto-refresh 15 s · $1'], [/^(.+) giờ xe chạy$/, '$1 vehicle-hours'],
    [/^Đã lưu (\d+) dòng \(tổng (\d+)\)\.$/, 'Saved $1 rows (total $2).'], [/^Xe (\S+)$/, 'Vehicle $1'], [/^Điểm tiếp theo · (.+)$/, 'Next stop · $1'],
    [/^Dự kiến (.+)$/, 'Planned $1'], [/^dừng ~(.+)$/, 'stop ~$1'], [/^Còn lại \((\d+)\)$/, 'Remaining ($1)'], [/^Đã xử lý \((\d+)\)$/, 'Processed ($1)'],
    [/^Chưa phân công \((\d+)\)$/, 'Unassigned ($1)'], [/^\((\d+)\)$/, '($1)'],
  ];
  const ORIG = new WeakMap(), ORIG_ATTR = new WeakMap();
  let lang = 'vi';
  try { lang = localStorage.getItem('gr_lang') === 'en' ? 'en' : 'vi'; } catch { /* default vi */ }

  // Common fragments inside composite strings ("186 g/đơn · ▼", "(khác số đơn)") — applied only
  // when no whole-string entry matched, longest first.
  const FRAGMENTS = [
    ['Giờ cao điểm', 'Peak hours'], ['giờ cao điểm', 'peak hours'], ['Điểm tiếp theo', 'Next stop'],
    ['khác số đơn', 'different order count'], ['so với baseline', 'vs baseline'], ['đơn nguy cơ trễ', 'orders at late risk'], ['nguy cơ trễ', 'late risk'],
    ['ước tính', 'estimate'], ['Đã phát hành lúc', 'Published at'], ['Tài xế mở', 'Drivers open'], ['để nhận tuyến', 'to receive their route'],
    ['Phương án này đã phát hành lúc', 'This plan was published at'], ['chặng giờ cao điểm', 'peak-hour legs'], ['chặng', 'legs'], ['giờ xe chạy', 'vehicle-hours'],
    ['Phương án đang phát hành', 'Published plan'], ['Phương án mới nhất', 'Latest plan'], ['đã giao', 'delivered'], ['thất bại', 'failed'], ['còn lại', 'remaining'],
    ['Đã phát hành', 'Published'], ['bởi', 'by'], ['xe sẵn sàng', 'vehicles available'], ['xe có tài xế', 'with a driver'], ['đơn đã nhập', 'orders imported'],
    ['Mất tín hiệu', 'Lost signal'], ['phút trước', 'min ago'], ['đơn chưa phân công', 'unassigned orders'], ['trong phương án mới nhất', 'in the latest plan'],
    ['đơn giao thất bại', 'failed deliveries'], ['cần xử lý lại', 'needs follow-up'], ['xe chưa có tài xế', 'vehicles without a driver'],
    ['Phương án mới nhất', 'The latest plan'], ['tài xế chưa nhận được tuyến', 'drivers have not received routes'], ['chưa phát hành', 'not published'],
    ['Nét đứt = xe điện', 'Dashed = electric'], ['Chấm đỏ = chưa phân công', 'Red dot = unassigned'], ['Xa điểm giao', 'Far from stop'], ['Không có định vị', 'No location'],
    ['đã đi', 'travelled'], ['dự kiến', 'planned'], ['cách', ''], ['Tiếp:', 'Next:'], ['điểm', 'stops'], ['/đơn', '/order'], ['đơn', 'orders'], ['xe', 'vehicles'],
  ].sort((a, b) => b[0].length - a[0].length);
  const VI_CHARS = /[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]/i;

  const EDGE = /^([\s\p{P}\p{S}]*)(.*?)([\s\p{P}\p{S}]*)$/su;
  function lookup(core) {
    if (EN[core]) return EN[core];
    for (const [re, rep] of PATTERNS) if (re.test(core)) return core.replace(re, rep);
    return null;
  }
  function tr(text) {
    const trimmed = text.trim(); if (!trimmed) return null;
    const lead = text.slice(0, text.indexOf(trimmed)), trail = text.slice(text.indexOf(trimmed) + trimmed.length);
    let hit = lookup(trimmed);
    if (hit != null) return lead + hit + trail;
    const m = trimmed.match(EDGE);  // strip emoji / punctuation at both ends: "📦 Đơn đã phân công", "(khác số đơn)"
    if (m && m[2] && (hit = lookup(m[2])) != null) return lead + m[1] + hit + m[3] + trail;
    if (m && m[1] && (hit = lookup(trimmed.slice(m[1].length))) != null) return lead + m[1] + hit + trail;  // "🚦 Giờ cao điểm (ước tính)"
    if (!VI_CHARS.test(trimmed)) return null;
    let out = trimmed;
    for (const [vi, en] of FRAGMENTS) out = out.split(vi).join(en);
    return out === trimmed ? null : lead + out.replace(/\s{2,}/g, ' ') + trail;
  }
  function applyNode(n) {
    if (n.nodeType === 3) {
      if (!ORIG.has(n)) ORIG.set(n, n.nodeValue);
      const src = ORIG.get(n);
      const out = lang === 'en' ? (tr(src) ?? src) : src;
      if (n.nodeValue !== out) n.nodeValue = out;
      return;
    }
    if (n.nodeType !== 1 || n.matches?.('script,style,code,textarea')) return;
    for (const a of ['placeholder', 'title', 'aria-label']) {
      if (!n.hasAttribute?.(a)) continue;
      let o = ORIG_ATTR.get(n); if (!o) ORIG_ATTR.set(n, o = {});
      if (!(a in o)) o[a] = n.getAttribute(a);
      const out = lang === 'en' ? (tr(o[a]) ?? o[a]) : o[a];
      if (n.getAttribute(a) !== out) n.setAttribute(a, out);
    }
    n.childNodes.forEach(applyNode);
  }
  // Mutation records caused by our own rewrites are discarded with takeRecords(), so a
  // translated string is never mistaken for new source text.
  const obs = new MutationObserver(muts => {
    for (const m of muts) {
      if (m.type === 'characterData') { ORIG.set(m.target, m.target.nodeValue); applyNode(m.target); }
      else m.addedNodes.forEach(applyNode);
    }
    obs.takeRecords();
  });
  function set(l) {
    lang = l; try { localStorage.setItem('gr_lang', l); } catch { /* ignore */ }
    document.documentElement.lang = l;
    applyNode(document.body); obs.takeRecords();
    document.querySelectorAll('[data-lang]').forEach(b => b.classList.toggle('active', b.dataset.lang === l));
    window.dispatchEvent(new CustomEvent('langchange', { detail: l }));
  }
  function mountSwitch(el) {
    el.innerHTML = '<div class="seg lang-seg"><button type="button" data-lang="vi">VI</button><button type="button" data-lang="en">EN</button></div>';
    el.onclick = e => { const b = e.target.closest('[data-lang]'); if (b) set(b.dataset.lang); };
  }
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.lang-switch').forEach(mountSwitch);
    set(lang);
    obs.observe(document.body, { childList: true, subtree: true, characterData: true });
  });
  return { set, get: () => lang, t: s => (lang === 'en' ? (tr(s) ?? s) : s) };
})();
