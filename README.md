# Query Room — Hotel Booking Activity

Bản hoạt động trên lớp được phát triển từ tài liệu Hotel Booking trong [thư mục Drive](https://drive.google.com/drive/folders/1AnbpuaNg5PcQozpmVzC54HC41dNN2mHG). Bản workshop trước đó vẫn ở nhánh `main`. Script SQL Server nguyên gốc được giữ tại `source/hotel_booking_activity.sql`; game chạy bản chuyển sang SQLite, không chạy T-SQL trực tiếp.

## Chạy local

Yêu cầu Python 3.10+; không cần cài dependency.

```powershell
python server.py
```

Mở <http://127.0.0.1:8000/>. Nếu server bản demo đang chiếm cổng 8000, chạy `python server.py --port 8001` rồi mở <http://127.0.0.1:8001/>. Để học viên truy cập từ máy khác, chạy `python server.py --host 0.0.0.0 --port 8001` và dùng IP của máy giáo viên.

## Chơi và nộp phát hiện

1. Chọn một trong 11 nhóm còn trống. Cùng trình duyệt có thể mở lại phiên sau crash; nếu mất cookie, giáo viên dùng dashboard để kick phiên cũ rồi chọn lại.
2. Đọc 14 quy tắc BR trên trang, xem schema và dữ liệu mẫu. Mỗi lần chạy một câu SQLite. Dữ liệu ban đầu hợp lệ.
3. Dùng các câu ghi để tạo tình huống kiểm thử, rồi chạy `SELECT` lọc đúng dòng và trả về ID cùng các cột chứng minh lỗi.
4. Trong **Nộp phát hiện**, dán tất cả câu ghi đã chạy theo đúng thứ tự kể từ đầu lượt hoặc lần báo cáo được xác nhận trước, mỗi câu kết thúc bằng `;`. Dán một câu `SELECT` đã chạy sau đó. Chọn quy tắc bị vi phạm và nhập ID, giá trị quan sát, kết quả mong đợi.
5. Server đối chiếu lịch sử, trạng thái trước/sau và kết quả đọc. Chỉ báo cáo xác nhận mới được 100 điểm. Chạy SQL đơn lẻ không tự cộng điểm.

Nút **Nạp lại dữ liệu mẫu** mở lượt thử mới và giữ điểm. Nếu muốn thử một ca nhiều bước (ví dụ tạo khách, tạo booking, thêm payment), chạy đủ từng câu trong editor rồi nộp đủ chuỗi trong form. Không được bỏ qua câu tạo dữ liệu nền.

Nút **Thoát nhóm** giải phóng chỗ đang giữ và đưa trình duyệt về trang chọn nhóm. Điểm và lỗi đã xác nhận được lưu theo nhóm; chọn lại nhóm cũ sẽ tiếp tục điểm cũ trên dữ liệu SQL sạch. Các lỗi đã ghi nhận không được cộng điểm lần hai. Thao tác thử SQL và lịch sử riêng của phiên cũ không chuyển sang nhóm mới.

Chi tiết chấm, 15 tình huống lỗi tự chấm cùng ca đối chứng BR-06 và giới hạn: [SCORING.md](./SCORING.md). Đặc tả nguồn: [source/business-requirements.md](./source/business-requirements.md).

## Dashboard

Giáo viên mở `/dashboard`, đăng nhập tên `admin`. Mật khẩu đọc từ `QUERY_ROOM_ADMIN_PASSWORD` hoặc `data/admin-password.txt`; nếu chưa có, server sinh mật khẩu trong file local đó. Dashboard cập nhật mỗi 10 giây, hiển thị điểm server tính theo nhóm. Kick giải phóng nhóm và thu hồi phiên cũ nhưng giữ điểm. **Reset trạng thái tất cả** xóa điểm và báo cáo của ván hiện tại, giải phóng cả 11 nhóm và ngắt mọi phiên; các nhóm phải vào lại.

## Kiểm tra

```powershell
python -m unittest discover -s tests -v
node --check app.js
```

Dữ liệu runtime của bản Hotel nằm trong `data/hotel-game-v1/` để không đè database của bản demo.
