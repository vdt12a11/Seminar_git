# 1. Khóa và ràng buộc dữ liệu (CHọn 3 trong 5 cái) (Tuệ)
1.	Primary key: kiểm tra các bảng Guest, Room, Booking, Payment có PK trên đúng cột.
2.	Foreign key: thử tạo booking với khách/phòng không tồn tại và payment với booking không tồn tại; database phải từ chối.
5.	Xóa dữ liệu đang được tham chiếu: xóa khách/phòng có booking; FK phải từ chối. Xóa booking có payment thì payment bị xóa theo ON DELETE CASCADE.
# 2. CRUD và Quy tắc nghiệp vụ (Chọn 6 cái demo) (Tuệ)
1.	Create booking hợp lệ: gọi dbo.create_booking; xác nhận booking được tạo và có booking ID.
2.	Read booking: đọc booking và payment, đối chiếu với dữ liệu mong đợi.
3.	Update dữ liệu: sửa email, giá phòng hoặc payment; xác nhận cập nhật đúng và ràng buộc vẫn được áp dụng.
4.	Delete payment: xóa payment rồi kiểm tra trigger cập nhật trạng thái booking.
5.	Ngày không hợp lệ: checkout bằng hoặc trước check-in; procedure phải báo lỗi, không tạo booking.
6.	Khách không tồn tại: gọi procedure với guest ID không tồn tại; phải báo lỗi.
7.	Phòng không tồn tại hoặc inactive: procedure phải báo lỗi.
8.	Payment ban đầu không hợp lệ: truyền số âm hoặc lớn hơn tổng booking; procedure phải từ chối.
9.	Mỗi phòng phải có số phòng; số phòng là duy nhất
10.	Giá mỗi đêm phải lớn hơn 0.
