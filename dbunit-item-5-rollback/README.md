# DBUnit — Mục 5: Rollback và kịch bản phức tạp

Dự án Maven độc lập chạy ba test case trong `PaymentItem5DbUnitTest.java` trên SQL Server. JUnit tạo fixture cho mỗi ca; DBUnit đối chiếu dữ liệu bảng `Booking` và `Payment` với kết quả mong đợi.

## Các test case

| Case | Tình huống | Kỳ vọng |
|---|---|---|
| TC01 | Thanh toán lần lượt 2.000.000 rồi 700.000 cho booking 2.700.000 | Tổng payment 2.700.000; booking `PAID` |
| TC02 | Thanh toán 2.000.000 rồi thử thêm 800.000 | Procedure từ chối khoản vượt; transaction rollback; tổng vẫn 2.000.000 và booking `BOOKED` |
| TC03 | Hai kết nối cùng gửi 600.000 trên booking đã thanh toán 2.000.000 | Chỉ một khoản được nhận; tổng 2.600.000, không vượt tổng booking |

TC02 được thiết kế để phát hiện lỗi trong procedure của schema demo: giới hạn thanh toán đang tính từ giá gốc trước giảm thay vì tổng booking sau giảm. Vì vậy khi chạy với schema demo hiện tại, TC02 có thể thất bại và là bằng chứng cho bug được mô tả trong test.

## Chạy test

1. Cài SQL Server Database Engine, JDK 17 và IntelliJ IDEA (hoặc Maven 3.9+).
2. Mở thư mục `dbunit-item-5-rollback` bằng IntelliJ, đặt Project SDK là JDK 17.
3. Trong cửa sổ Maven, bấm **Reload All Maven Projects** để tải JUnit, DBUnit và SQL Server JDBC driver.
4. Cấu hình kết nối SQL Server qua biến `HOTEL_DBUNIT_JDBC_URL` hoặc system property `hotel.db.url`. Mặc định là database `hotel_booking_dbunit_demo` tại `localhost`, dùng Windows Integrated Authentication.
5. Chạy `PaymentItem5DbUnitTest` trong IntelliJ; hoặc từ terminal trong thư mục này chạy:

   ```powershell
   mvn test -Dtest=PaymentItem5DbUnitTest
   ```

`src/test/resources/sql/hotel_booking_schema.sql` chứa schema demo và procedure dùng cho test. Fixture XML trong `src/test/resources/datasets/` được nạp lại để mỗi test có dữ liệu đầu vào xác định.
