# Cách chấm và phạm vi bản hoạt động

Game chạy một bản chuyển có chủ đích của schema SQL Server sang SQLite. Script SQL Server từ Drive được lưu nguyên văn trong `source/hotel_booking_activity.sql`; không thể chạy script này trực tiếp qua editor SQLite. Dữ liệu mẫu và các thiếu sót nghiệp vụ chính được tái tạo trong `game.py`. Mỗi nhóm có database riêng.

## Quy trình chấm một báo cáo

1. Người chơi chạy từng câu SQL trong editor; mỗi lần chỉ một câu. Server lưu câu lệnh, kết quả, bảng/cột đã đọc hoặc ghi, snapshot trước và sau vào nhật ký của nhóm và lượt.
2. Ô **Chuỗi SQL thao tác** nhận các câu ghi đã chạy, theo thứ tự và ngăn cách bằng `;`. Server yêu cầu khớp **mọi câu ghi thành công** từ đầu lượt hoặc từ báo cáo đã xác nhận gần nhất đến câu `SELECT` được nộp. Không thể bỏ qua lệnh tạo dữ liệu nền trong chuỗi. Có thể chạy nhiều `SELECT` để điều tra, nhưng đơn nộp chọn một `SELECT` cuối để chứng minh.
3. Server so sánh trạng thái trước bước ghi đầu và sau bước ghi cuối bằng bộ quy tắc độc lập trong `witnesses()`. Dòng vi phạm phải **mới xuất hiện** sau chuỗi ghi và còn tồn tại lúc `SELECT` kiểm chứng. Báo cáo không được cộng điểm chỉ vì dữ liệu cũ đã sai.
4. `SELECT` phải được chạy trong cùng nhóm/lượt, sau các thao tác ghi, không có ghi xen giữa; kết quả phải chứa ID và các cột cụ thể của dòng vi phạm, với giá trị khớp snapshot server. Server kiểm tra bảng và cột thực sự được đọc. ID, giá trị quan sát và kết quả mong đợi trong form cũng phải khớp.
5. Mỗi dạng lỗi được tối đa 100 điểm một lần cho mỗi nhóm. Không có ô diễn giải tự do: chuỗi thao tác, `SELECT`, ID, giá trị quan sát và quy tắc đã chọn là toàn bộ bằng chứng được chấm.

Để bắt đầu chuỗi thử nghiệm mới không lẫn các thao tác ghi trước đó, dùng **Nạp lại dữ liệu mẫu**. Nút này giữ điểm đã được xác nhận nhưng thay database và mở lượt mới.

## Các quy tắc chấm tự động

| Quy tắc | Dạng phản ví dụ server kiểm tra | ID nộp / Giá trị quan sát |
| --- | --- | --- |
| BR-01 | Email không đúng định dạng đã nêu | `guest_id` / email |
| BR-02 | Hai email bằng nhau khi chuyển về chữ thường | `guest_id` / email của khách trùng |
| BR-03 | Tên rỗng hoặc >100 ký tự sau `strip()` | `guest_id` / độ dài sau `strip()` nếu tên rỗng, hoặc chính tên dài |
| BR-04 | `room_type` không tồn tại trong RoomType | `room_id` / room_type |
| BR-05 | Booking tham chiếu Room không hoạt động | `booking_id` / `active` (0) |
| BR-07 | `nights` khác hiệu hai ngày | `booking_id` / số đêm tính từ ngày |
| BR-08 | Booking giao khoảng ngày với booking khác cùng phòng, cả hai chưa huỷ | `booking_id` / ID booking còn lại |
| BR-10 | `discount_rate` sai chính sách theo nights | `booking_id` / discount_rate |
| BR-11 | total_amount không khớp phép tính từ đơn giá phòng hiện tại khi **tạo/sửa Booking** | `booking_id` / total_amount |
| BR-12 | Tổng payment > total_amount | `booking_id` / tổng payment |
| BR-13 | Booking chưa huỷ có status khác kết quả đối chiếu payment/total_amount | `booking_id` / status |
| BR-14 | Payment mới được thêm vào booking CANCELLED | `payment_id` / amount |

BR-06 được khóa ngoại bảo vệ nên không phải một lỗi để cộng điểm. BR-09 thiếu cột lưu đơn giá tại thời điểm đặt, là thiếu sót **cấu trúc**: cần giáo viên kiểm tra trực tiếp schema và thử đổi giá. Không tự chấm bằng một SELECT dòng dữ liệu. BR-11 chỉ chấm khi bước cuối ghi Booking vì không có snapshot giá lịch sử để phân biệt booking cũ đúng giá với giá phòng vừa bị đổi.

Đối chiếu 15 mục trong `hotel_known_issues.docx`: mục 1→BR-01, 2→BR-02, 3→BR-03, 4→BR-04, 5→BR-05, 6→BR-08, 7→BR-07, 8→BR-09 (giáo viên duyệt), 9→BR-10, 10→BR-11, 11→BR-12, 12→BR-14, 13 và 14→cùng dạng BR-13, 15→BR-13 với `total_amount = 0`. Vì mục 13–15 cùng vi phạm quy tắc trạng thái, bản này chỉ cộng điểm một lần cho BR-13. Quy tắc BR-06 từ đặc tả đã được khóa ngoại bảo vệ, nên không có phản ví dụ hợp lệ để cộng điểm.

Hai mục trong danh sách nguồn được xem là phụ thuộc môi trường hoặc diễn giải (collation của email và danh mục room type). Bản SQLite đặt so sánh email phân biệt hoa thường để BR-02 là tình huống thử được; RoomType được giữ như danh mục, nên BR-04 có căn cứ rõ. BR-03 dùng `strip()` của Python cho nghĩa whitespace, còn CHECK mẫu chỉ loại dấu cách thường. Việc chuyển này được công khai để tránh nhầm với hành vi SQL Server trong script gốc.

## Giới hạn của chấm tự động

- Bộ chấm xác minh giá trị có cấu trúc, không chứng minh rằng người chơi đã **hiểu** nguyên nhân. Nếu dùng làm điểm chính thức, giáo viên có thể yêu cầu nhóm giải thích trực tiếp cách họ tìm ra lỗi.
- Một truy vấn có thể tạo biểu thức hoặc alias bằng giá trị cố định trong khi vẫn đọc các cột bắt buộc; bộ chấm đối chiếu kết quả với snapshot nhưng không phân tích ngữ nghĩa toàn bộ SQL. Đây là rủi ro còn lại của chấm tự động bằng SQL tự do.
- Cú pháp SQLite không trùng hoàn toàn T-SQL: dùng `julianday` thay `DATEDIFF`, không dùng `GO`, `NVARCHAR` hay `dbo.` trong editor.
- `total_amount` bằng 0 và chính sách giảm giá/giá ở các trạng thái bất thường có thể làm nhiều quy tắc cùng sai; chỉ quy tắc và dòng được chứng minh trong đơn mới nhận điểm. Trường hợp gây tranh cãi nên được giáo viên duyệt.

Chạy kiểm tra: `python -m unittest discover -s tests -v` và `node --check app.js`. Bộ kiểm tra HTTP bao gồm 12 dạng xác nhận, chuỗi hai lệnh, thiếu bước, giá trị quan sát sai, lựa chọn mong đợi sai, truy vấn toàn bảng, lượt cũ và thao tác bị từ chối.
