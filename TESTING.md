# Đối chiếu với .NET

Chạy từ repo app:

```powershell
python -m unittest discover -s tests -v
node --test tests/dashboard-tv.test.cjs
```

Test Python dùng dữ liệu giả và adapter Frappe trong bộ nhớ; không cần bench và không ghi dữ liệu site. Test JavaScript dùng DOM nhỏ trong bộ nhớ để kiểm tra giá trị thực được render, không thay thế kiểm tra trình duyệt.

`tests/reference/dotnet.json` được xuất bằng cách gọi các hàm thực của `DashboardProductivityPayloadService` qua reflection: 36 mốc mục tiêu, 30 tình huống hiển thị khung giờ, chọn báo cáo/kế hoạch. Các tỷ lệ chuẩn dùng Decimal và quy tắc làm tròn ratio 4 chữ số của .NET. Nguồn tham chiếu: FactoryManagement commit `6d556e209359efa3f99d768ae9f6627624c0d532`.

Tạo lại fixture khi chủ động thay đổi quy tắc chuẩn .NET:

```powershell
& tests/reference/export.ps1 -DotnetRoot D:\Code\FactoryManagement
```

Các test còn kiểm tra QC1, phân trang sự kiện, UQQC `rework / (pass + rework)`, tổng ca, ngày kết thúc thực tế, lấy báo cáo mới nhất, tổng hợp nhóm cùng mã hàng, chặn tổng hợp nhóm khác mã và cấu hình single/dual. `uqqc_input` tương ứng nguồn nhập tay `qcbrother_input` trong Dashboard .NET; số sự kiện `defect` không phải số hàng `rework`.

## Kiểm tra chỉ đọc trên Pilot

Đặt `FRAPPE_USER` và `FRAPPE_PASSWORD` trong môi trường, hoặc `FRAPPE_API_TOKEN` với dạng `key:secret`. Không ghi thông tin này vào repo.

```powershell
python tools/check_pilot.py --url http://192.168.52.75:8080 --device-id <device-id> --day 2026-11-17
```

Script đọc tài liệu nguồn bằng REST và chạy bản metrics cục bộ để so với API đang triển khai. Không gọi API lưu/xóa; chỉ POST khi đăng nhập. Mã thoát 1 nghĩa là có chênh lệch. Các trường phụ thuộc thời điểm hiện tại được đối chiếu bằng fixture cố định để tránh sai lệch do thời gian giữa hai lần gọi.

## Kết quả ngày 18/11/2026

- Sau sửa: 13 test Python (bao gồm các subtest mốc giờ/tỷ lệ) và 3 test JavaScript đạt.
- Test được thêm trước khi sửa và đã bắt được lỗi cộng nhiều báo cáo, chọn kế hoạch, tỷ lệ UQQC, clamp số lỗi QC, giá trị 0/mẫu số 0, giờ dạng timedelta và cờ hiển thị khi gộp chuyền.
- Kiểm tra đọc trên Pilot cho ngày 17/11/2026, hai chuyền trong phạm vi thiết bị: không có báo cáo năng suất; giá trị sản lượng đều 0. API đang triển khai trả tỷ lệ lỗi `null` thay vì `0` như .NET. Bản sửa trả `0`; cần cập nhật app qua Pilot.
- Chưa xác nhận dữ liệu sản lượng khác 0 trên Pilot do site chưa có báo cáo. Không có phép so sánh trực tiếp dữ liệu sản xuất giữa hai site .NET/Frappe.
- Đã chạy 28 test .NET liên quan: 26 đạt, 2 lỗi có sẵn trong `ProductivityProductionPlanClosedDateTests` ở hai trường hợp hợp nhất kế hoạch (`FinishAsync_SelfHealsLegacyMergedScopeOverlap_AndSavesClosedDate`, `UpdateClosedDateAsync_ReturnsRefreshMessage_WhenPlanIsAbsorbedByRepair`). Không thay đổi source .NET trong đợt này.
- Bộ test này không xác nhận quy trình sửa/hợp nhất dữ liệu legacy của .NET; không đồng bộ dữ liệu cũ vào Frappe.

## Kiểm tra ghi dữ liệu mẫu trên Pilot

Ngày 18/11/2026, đã tạo hai kế hoạch và hai báo cáo tạm cho ngày 10/11/2026, chuyền 315/316, cùng mã hàng `217H005B`. Mỗi báo cáo có sáu khung giờ. Script lưu bằng API Productivity, kiểm tra kế hoạch xuất hiện trong `open_plans`, đọc lại DocType và `list_reports`, rồi đối chiếu API `summary` và `display` với số chuẩn từ `tests/reference/dotnet.json`. Chế độ gộp hai chuyền dùng cấu hình TV tạm; script xóa cấu hình và toàn bộ bản ghi mẫu trong `finally`.

| Chỉ tiêu | Chuyền 315 | Chuyền 316 | Gộp |
|---|---:|---:|---:|
| Kế hoạch | 1.200 | 900 | 2.100 |
| Hoàn thành | 440 | 300 | 740 |
| Mục tiêu ngày / hiện tại | 500 | 400 | 900 |
| Tỷ lệ đạt | 88% | 75% | 82,22% |
| Công nhân | 20 | 15 | 35 |
| Lũy kế sáu khung giờ | 80, 180, 300, 440, 440, 440 | 50, 120, 200, 300, 300, 300 | 130, 300, 500, 740, 740, 740 |

Trước cập nhật, dữ liệu sản lượng khớp nhưng Dashboard trả tỷ lệ lỗi `null`/không khả dụng khi chưa có QC, khác quy tắc .NET là 0%/khả dụng: [kết quả trước](tests/reference/pilot-sample-before-0.1.9.json). Đã cập nhật checkout trên Pilot lên Productivity `043fa94`, Dashboard `5918204`, chạy `migrate` thành công (gồm patch `refresh_report_validation`) và khởi động lại web/worker. Sau cập nhật, toàn bộ phép so sánh đạt, không còn chênh lệch: [kết quả sau](tests/reference/pilot-sample-group-0.1.9.json).

Để chạy lại, đặt `FRAPPE_USER`/`FRAPPE_PASSWORD` hoặc `FRAPPE_API_TOKEN` trong môi trường, rồi chạy:

```powershell
python tools/verify_productivity_sample.py --url http://192.168.52.75:8080 --device-id 35b75945-db68-4cb8-b3c4-5a4575e72320 --day 2026-11-10 --output tests/reference/pilot-sample-rerun.json
```

Script dừng trước khi tạo nếu chuyền đã có kế hoạch mở hoặc đã có báo cáo trong ngày mẫu. Sau lần chạy này, kiểm tra lại trên site: còn một kế hoạch cũ, không có báo cáo năng suất và không có cấu hình TV. Phép thử QC chỉ xác nhận trường hợp nguồn QC bằng 0; chưa tạo sự kiện QC/UQQC mẫu khác 0.

## Cập nhật và quay lui

Cập nhật `factory_productivity` trước, rồi `factory_dashboard` trên nhánh `version-16` qua Pilot. Không đổi tên/kiểu trường API; tỷ lệ lỗi rỗng trở thành 0, `start_time`/`end_time` được chuẩn hóa thành HH:mm. Không xóa báo cáo trùng đã tồn tại: Dashboard chọn một báo cáo mới nhất; nhập mới bị chặn trùng.

Nếu cần quay lui app, dùng phiên bản trước trong Pilot: productivity 0.1.11, dashboard 0.1.8. Patch của bản productivity chỉ xóa cache metadata, không sửa dữ liệu lịch sử. Rollback không tự chạy.
