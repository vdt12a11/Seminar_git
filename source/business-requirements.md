# Đặc tả nghiệp vụ — Hotel Booking Activity

Nguồn: [hotel_business_requirements.docx](https://docs.google.com/document/d/1kL4EosULG8VOZXuWE_mjcrfa0cOAnvZY/edit) trong thư mục Drive do người dùng cung cấp. Bản này chép lại nội dung nghiệp vụ để đối chiếu khi phát triển game.

Đơn giá tại thời điểm đặt là giá mỗi đêm áp dụng và lưu trên bản ghi đặt phòng khi tạo. Tổng thanh toán là tổng `amount` của các khoản gắn với đặt phòng. Hai booking chồng lấn khi khoảng ngày cùng phòng giao nhau; ngày trả phòng là điểm kết thúc, không tính thêm một đêm. Booking đã huỷ không chiếm phòng và không nhận tiền mới.

| ID | Quy tắc |
| --- | --- |
| BR-01 | Mỗi khách phải có email dạng `local-part@domain`, không khoảng trắng, đúng một `@`, domain có ít nhất một dấu chấm với phần trước/sau không rỗng. |
| BR-02 | Email khách duy nhất, không phân biệt hoa thường. |
| BR-03 | Tên khách bắt buộc, dài 1–100 ký tự sau khi bỏ khoảng trắng đầu/cuối. |
| BR-04 | Mỗi phòng có số phòng duy nhất và thuộc loại phòng xác định. |
| BR-05 | Chỉ phòng hoạt động mới được tạo booking mới. |
| BR-06 | Booking tham chiếu khách và phòng tồn tại. |
| BR-07 | Ngày trả sau ngày nhận; số đêm bằng hiệu số ngày. |
| BR-08 | Cùng phòng không có booking chồng lấn, trừ booking đã huỷ. |
| BR-09 | Khi tạo booking, lưu đơn giá mỗi đêm lúc đặt. Đổi giá phòng hiện tại không đổi đơn giá hoặc tổng tiền booking cũ. |
| BR-10 | Tỷ lệ giảm nằm trong 0–1; từ 3 đêm giảm 10%, dưới 3 đêm không giảm. |
| BR-11 | Tổng tiền = số đêm × đơn giá lúc đặt × (1 − tỷ lệ giảm), làm tròn 2 chữ số thập phân. |
| BR-12 | Mỗi payment > 0; tổng payment không vượt tổng tiền booking. |
| BR-13 | Booking chưa huỷ có trạng thái PAID khi tổng payment >= tổng tiền, ngược lại BOOKED. Trạng thái phản ánh cả thay đổi payment và total_amount. |
| BR-14 | Booking CANCELLED không nhận payment mới; cập nhật payment không đổi trạng thái huỷ. |

Script SQL Server nguyên gốc: [hotel_booking_activity.sql](./hotel_booking_activity.sql). Danh sách lỗi nguồn: [hotel_known_issues.docx](https://docs.google.com/document/d/1taD0AFjMX13TfVjvcKtShVqVHv9O8ztp/edit).
