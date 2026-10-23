Bối cảnh nghiệp vụ và quy tắc database
1. Bối cảnh
Database hotel_booking_demo mô phỏng hệ thống đặt phòng khách sạn nhỏ. Khách hàng đặt một phòng trong một khoảng ngày, hệ thống tính tiền theo số đêm và giá phòng, có thể áp dụng chiết khấu cho kỳ lưu trú dài. Khách có thể thanh toán thành nhiều lần. Database lưu booking và payment, đồng thời cập nhật trạng thái booking theo số tiền đã thu.
Script triển khai tương ứng là hotel_booking_sqlserver.sql và dành cho SQL Server.
2. Các thực thể và quan hệ
•	Guest: khách đặt phòng. Một khách có thể có nhiều booking.
•	Room: phòng khách sạn. Một phòng có thể xuất hiện trong nhiều booking ở các khoảng ngày khác nhau.
•	Booking: lần đặt phòng của một khách cho một phòng trong khoảng ngày cụ thể. Mỗi booking thuộc về đúng một khách và một phòng.
•	Payment: khoản thanh toán thuộc về một booking. Một booking có thể có nhiều payment để hỗ trợ trả từng phần.
Quan hệ khóa ngoại:
•	Booking.guest_id tham chiếu Guest.guest_id.
•	Booking.room_id tham chiếu Room.room_id.
•	Payment.booking_id tham chiếu Booking.booking_id.
•	Xóa khách hoặc phòng đang được booking sử dụng bị từ chối. Xóa booking sẽ xóa các payment liên quan theo ON DELETE CASCADE.
3. Quy tắc dữ liệu
Khách và phòng
•	Mỗi khách phải có email; email là duy nhất.
•	Mỗi phòng phải có số phòng; số phòng là duy nhất.
•	Giá mỗi đêm phải lớn hơn 0.
•	Phòng active = 0 không nhận booking mới qua procedure.
Booking
•	Ngày checkout phải sau ngày check-in.
•	Số đêm là số ngày giữa check-in và checkout.
•	Một phòng không được có hai booking còn hiệu lực với khoảng ngày chồng lấn.
•	Hai khoảng ngày được coi là chồng lấn khi ngày bắt đầu booking mới nhỏ hơn checkout hiện tại, đồng thời ngày checkout mới lớn hơn check-in hiện tại. Vì vậy booking nối tiếp ngay ngày checkout được phép.
•	Booking CANCELLED không chiếm lịch khi procedure tạo booking kiểm tra trùng.
•	Trạng thái booking thuộc một trong ba giá trị: BOOKED, PAID, CANCELLED.
Giá và chiết khấu
•	nights = DATEDIFF(DAY, check_in, check_out).
•	Booking từ 3 đêm trở lên được giảm 10%; booking ngắn hơn không được giảm.
•	total_amount = ROUND(nights × price_per_night × (1 - discount_rate), 2).
•	Giá và tổng tiền dùng DECIMAL(12,2); tỷ lệ giảm dùng DECIMAL(5,4).
Thanh toán
•	Mỗi payment phải lớn hơn 0 và tham chiếu một booking tồn tại.
•	Tổng payment không được vượt Booking.total_amount khi ghi qua dbo.record_booking_payment.
•	Có thể thanh toán thành nhiều lần.
•	Khi tổng payment đạt hoặc vượt tổng booking, trạng thái chuyển thành PAID; nếu tổng payment thấp hơn, trạng thái là BOOKED.
•	Booking đã CANCELLED không nhận payment mới qua dbo.record_booking_payment.
4. Stored procedures và trigger
dbo.create_booking
Tạo booking trong transaction. Procedure kiểm tra khoảng ngày, sự tồn tại của khách, tình trạng phòng, lịch chồng lấn và khoản thanh toán ban đầu. Sau đó tính số đêm/chiết khấu/tổng tiền, thêm booking và nếu có thì thêm payment ban đầu. Lỗi trong transaction được rollback và trả lại cho bên gọi.
Khoản thanh toán ban đầu phải từ 0 đến tổng tiền booking. Việc kiểm tra này hiện xảy ra trước khi insert booking.
dbo.record_booking_payment
Ghi nhận payment cho booking còn hiệu lực trong transaction. Procedure đọc tổng booking và tổng đã thanh toán, thêm payment, sau đó kiểm tra tổng mới. Nếu vượt tiền booking, procedure phát sinh lỗi và rollback payment mới. Lỗi được ném lại cho bên gọi.
dbo.trg_Payment_UpdateBookingStatus
Trigger chạy sau INSERT, UPDATE hoặc DELETE trên Payment. Trigger tính lại tổng payment của các booking bị ảnh hưởng và cập nhật trạng thái thành PAID khi đủ tiền, nếu chưa đủ thì BOOKED. Booking đã CANCELLED được giữ nguyên trạng thái.
5. Quy tắc và giới hạn khi kiểm thử
•	Dùng JUnit để gọi procedure và khẳng định kết quả/lỗi; dùng DBUnit để nạp dataset ban đầu và so sánh dữ liệu sau test.
•	Nạp dữ liệu theo thứ tự khóa ngoại: Guest, Room, Booking, Payment.
•	Để kiểm tra lịch trùng, gọi dbo.create_booking; hiện schema chưa có trigger/procedure bảo vệ thao tác INSERT trực tiếp hoặc UPDATE ngày trên Booking.
•	Để bảo vệ quy tắc tổng payment không vượt tổng booking trên mọi đường ghi, ứng dụng cần chỉ được cấp quyền ghi qua procedure hoặc cần bổ sung kiểm tra tương ứng trong database. Trigger trạng thái hiện tại không tự chặn payment vượt tiền nếu ai đó ghi trực tiếp vào Payment.
•	nights, discount_rate và total_amount được procedure tính khi tạo booking; schema hiện chưa tự tính lại các cột này nếu booking hoặc giá phòng được sửa trực tiếp.
•	Chính sách hoàn tiền/hủy sau khi đã thu tiền chưa được mô hình hóa. Trigger hiện giữ trạng thái CANCELLED khi payment thay đổi, nhưng bảng chưa có thực thể refund.
6. Bộ dữ liệu demo gợi ý
•	Hai khách với email khác nhau.
•	Hai phòng đang hoạt động với giá 1.000.000 và 1.500.000 mỗi đêm.
•	Một booking 2 đêm để kiểm tra không giảm giá.
•	Một booking 3 đêm để kiểm tra giảm 10%.
•	Với booking tổng 2.700.000: payment 2.000.000 rồi 700.000 để kiểm tra chuyển BOOKED sang PAID; sau đó thử payment vượt số dư để kiểm tra lỗi và rollback.
