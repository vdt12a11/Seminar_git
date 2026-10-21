# Query Room — Minigame điều tra database

Ứng dụng local dùng Python 3.10 trở lên và SQLite, không cần cài dependency.

## Chạy

```powershell
python server.py
```

Mở <http://127.0.0.1:8000/>. Nhấn Ctrl+C trong terminal chạy server để dừng.

## Vào nhóm và dashboard

- Người chơi mở `/`, chọn một trong 11 nhóm còn trống rồi bắt đầu điều tra. Mỗi nhóm chỉ có một phiên đang giữ chỗ; API SQL và nộp báo cáo yêu cầu phiên đã chọn nhóm.
- Trình duyệt gửi heartbeat mỗi 10 giây. Dashboard hiển thị **Đang làm** nếu nhận heartbeat trong 30 giây gần nhất; sau đó hiển thị **Mất kết nối · giữ chỗ**. Điểm và số bug được server tính từ báo cáo `confirmed`, không tin số do trình duyệt tự khai.
- Nếu trình duyệt crash, mở lại cùng trình duyệt để tiếp tục bằng cookie cũ. Nếu mất cookie, nhờ admin kick phiên cũ để giải phóng nhóm rồi chọn lại. Lần chọn lại bắt đầu với dữ liệu và điểm mới.
- Giáo viên mở `/dashboard`, đăng nhập tài khoản `admin` bằng mật khẩu đã thiết lập trên máy host. Dashboard cập nhật mỗi 10 giây, sắp theo số bug đã xác nhận, hiển thị trạng thái của cả 11 nhóm.
- **Kick** đặt trạng thái nhóm về 0, nhường chỗ cho phiên khác và thu hồi quyền của cookie người chơi cũ. Người bị kick có nút **Quay lại chọn nhóm** để bắt đầu phiên mới với dữ liệu mẫu. Nếu nhóm chỉ bị crash thì mở lại cùng trình duyệt để giữ tiến độ; kick không chuyển tiến độ cũ sang phiên mới.
- Mật khẩu được đọc từ biến môi trường `QUERY_ROOM_ADMIN_PASSWORD` hoặc file local `data/admin-password.txt` (không đưa lên Git). Nếu cả hai chưa có, server tạo mật khẩu ngẫu nhiên trong file đó. Khi cho cả lớp truy cập từ máy khác, chạy `python server.py --host 0.0.0.0` và mở địa chỉ IP của máy host, thay vì dùng localhost trên từng máy.

## Cách chơi

1. Đọc sáu yêu cầu nghiệp vụ và schema trên trang.
2. Tự thiết kế một thao tác ghi để kiểm tra yêu cầu.
3. Chạy một truy vấn đọc kiểm chứng ngay sau thao tác đó. Có thể chạy nhiều truy vấn đọc; không ghi dữ liệu xen giữa thao tác và bằng chứng.
4. Trong **Nộp phát hiện**, đọc hướng dẫn lọc dòng ở placeholder, chọn yêu cầu và tự nhập/dán nguyên văn hai câu SQL đã chạy (thao tác và truy vấn kiểm chứng), cùng ID bản ghi, giá trị quan sát và kết quả mong đợi. Truy vấn chứng minh cần chỉ ra dòng cụ thể và giá trị vi phạm; với tham chiếu mồ côi, cần LEFT JOIN tới bảng cha để xác nhận thiếu bản ghi. Viết thực tế và kết luận.
5. Server đối chiếu bằng chứng với snapshot dữ liệu và lịch sử của chính phiên chơi. Chỉ báo cáo hợp lệ mới xuất hiện trong **BUGS DISCOVERED**, mỗi dạng lỗi được 100 điểm một lần.

Chạy SQL không tự ghi nhận phát hiện. Danh sách lỗi chưa tìm được không gửi về trình duyệt. Máy xác minh các trường đối chiếu có cấu trúc; phần văn bản diễn giải được lưu lại để giáo viên xem, không được chấm ngữ nghĩa tự động.

Nút **Nạp lại dữ liệu mẫu** bắt đầu một lượt dữ liệu sạch, giữ báo cáo và điểm. Bằng chứng của lượt cũ được lưu trong nhật ký server nhưng không được dùng cho báo cáo của lượt mới.

## Bài thử đầu tiên: giới hạn tên

Trong một phiên sạch, chạy lần lượt, mỗi lần một câu:

```sql
INSERT INTO members (name, email)
VALUES ('ABCDEFGHIJKLMNOPQRSTUVWXYZ12345', 'long@example.test');
```

Lúc này **BUGS DISCOVERED** vẫn bằng 0. Sau đó chạy:

```sql
SELECT id, name, length(name) AS name_length
FROM members
WHERE email = 'long@example.test';
```

Nộp báo cáo với REQ-01, chọn INSERT và SELECT vừa chạy, nhập ID trả về và độ dài 31. Mong đợi: từ chối thao tác vi phạm. Mô tả thực tế bản ghi được lưu, kết luận tên vượt giới hạn 30 ký tự. Báo cáo đúng được xác nhận và cộng 100 điểm. Nếu nhập độ dài 30 hoặc dùng bằng chứng không liên quan, báo cáo không được xác nhận.

## Dữ liệu và phạm vi bản này

- Dữ liệu minigame và nhật ký nằm trong `data/game-v1/`; dữ liệu của sandbox cũ ở `data/` được giữ lại.
- Cookie HttpOnly định danh một phiên; các tab cùng trình duyệt dùng chung phiên. Chỉ phiên đã chiếm nhóm mới dùng được SQL và nộp báo cáo.
- Cấu trúc, nhật ký và bộ xác minh được bảo vệ khỏi SQL của người chơi. Số đếm workshop chỉ được cập nhật bởi trigger của hệ thống.
- Cho phép thao tác members/enrollments, sửa title/capacity của workshops; không đổi ID hiện có, không tạo/xóa workshop. Capacity là số nguyên từ 1 đến 1000. Mỗi bảng tối đa 1000 dòng; kết quả hiển thị tối đa 500 dòng.
- Tài khoản nhóm dựa trên cookie, không có mật khẩu riêng từng nhóm. Kick thu hồi cookie hiện tại, nhưng không thể chặn một người dùng trình duyệt/profile mới chọn một nhóm đang trống.

## Kiểm tra

```powershell
python -m unittest discover -s tests -v
node --check app.js
```

Các kiểm tra HTTP dùng database tạm riêng: đủ bảy dạng phát hiện, chống cộng điểm tự động, đối chiếu sai, báo cáo trùng, bằng chứng từ phiên/lượt khác, giới hạn quyền SQL và giữ điểm khi đặt lại.
