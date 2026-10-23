# DBUnit — Mục 4: Tính tiền và trigger

Dự án Maven độc lập gồm 9 test case trong `PaymentTriggerDbUnitTest.java`. JUnit gọi `dbo.create_booking` và thực hiện các thao tác trên bảng `Payment`; DBUnit nạp dataset XML rồi so sánh các hàng thực tế trong `Booking` và `Payment`. Schema kèm theo chứa procedure tạo booking và trigger `dbo.trg_Payment_UpdateBookingStatus`.

## Test case

| Case | Tình huống | Kỳ vọng |
|---|---|---|
| TC01 | Booking 2 đêm, giá 1.000.000/đêm | Không giảm; tổng 2.000.000 |
| TC02 | Booking 3 đêm | Giảm 10%; tổng 2.700.000 |
| TC03 | Thanh toán 2.000.000 trên tổng 2.700.000 | Vẫn `BOOKED` |
| TC04 | Thanh toán thêm 700.000 | Tổng đủ; trigger chuyển sang `PAID` |
| TC05 | Sửa payment làm tổng còn 2.200.000 | Trigger chuyển lại `BOOKED` |
| TC06 | Xóa hai payment | Tổng về 0, trạng thái `BOOKED` |
| TC07 | Booking `CANCELLED`, thêm payment | Vẫn `CANCELLED` |
| TC08 | Booking `CANCELLED`, sửa payment | Vẫn `CANCELLED` |
| TC09 | Booking `CANCELLED`, xóa payment | Vẫn `CANCELLED` |

## Chuẩn bị

1. Cài SQL Server Database Engine, JDK 17 x64 và IntelliJ IDEA có Maven (hoặc Maven 3.9+). Bật SQL Server và dùng tài khoản Windows có quyền tạo database thử nghiệm trong `master`.
2. Mở thư mục này bằng **File → Open** trong IntelliJ; chọn Project SDK là JDK 17.
3. Mở **View → Tool Windows → Maven** và bấm **Reload All Maven Projects** để tải JUnit, DBUnit, SQL Server JDBC và thư viện xác thực Windows từ `pom.xml`. Cần có Internet ở lần tải dependencies đầu tiên.
4. Mặc định test kết nối `localhost` bằng Windows Integrated Authentication. Nếu SQL Server ở instance/cổng khác, đặt `HOTEL_DBUNIT_JDBC_URL`, ví dụ:

   ```powershell
   $env:HOTEL_DBUNIT_JDBC_URL = 'jdbc:sqlserver://localhost\SQLEXPRESS;databaseName=hotel_booking_dbunit_demo;encrypt=true;trustServerCertificate=true;integratedSecurity=true'
   ```

   Với IntelliJ, đặt cùng biến trong **Run → Edit Configurations → Environment variables**. Có thể dùng cổng cố định như `localhost:1433` nếu named instance không được tìm thấy.

## Chạy test

Trong IntelliJ, mở `src/test/java/vn/hotelbooking/PaymentTriggerDbUnitTest.java`, bấm biểu tượng Run cạnh lớp hoặc từng hàm `@Test`. Trong terminal tại thư mục này:

```powershell
mvn "-Dtest=PaymentTriggerDbUnitTest" test
```

Chạy riêng một case: `mvn "-Dtest=PaymentTriggerDbUnitTest#fullPaymentSetsPaid" test`. Kết quả đủ bộ là `Tests run: 9, Failures: 0, Errors: 0` và `BUILD SUCCESS`.

Trước mỗi case, mã test tạo database `hotel_booking_dbunit_demo` và schema nếu chưa có, sau đó nạp lại các fixture `Guest.xml`, `Room.xml`, `Booking.xml`, `Payment.xml` theo thứ tự khóa ngoại. Dữ liệu được reset **chỉ** trong database thử nghiệm này. File SQL của nhóm ở ngoài dự án không bị sửa.
