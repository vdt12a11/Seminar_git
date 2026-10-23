# DBUnit — Mục 3: Kiểm tra lịch đặt phòng

Dự án Maven độc lập chứa 6 test case cho procedure `dbo.create_booking`. JUnit gọi procedure thật trên SQL Server; DBUnit nạp dataset XML và so sánh bảng `Booking` với dữ liệu kỳ vọng.

## Các test case

| Test | Tình huống | Kỳ vọng |
|---|---|---|
| `rejectsPartialOverlap` | Booking mới 11–13 chồng lấn một phần với booking 10–12 | Bị từ chối; dữ liệu booking giữ nguyên |
| `rejectsOverlapAtStart` | Booking mới 09–11 chồng lấn đầu kỳ | Bị từ chối; dữ liệu booking giữ nguyên |
| `rejectsExactOverlap` | Booking mới 10–12 trùng hoàn toàn | Bị từ chối; dữ liệu booking giữ nguyên |
| `acceptsAdjacentCheckout` | Booking mới bắt đầu ngày checkout 12–14 | Được nhận |
| `acceptsSameDatesForAnotherRoom` | Cùng ngày nhưng chọn phòng khác | Được nhận |
| `acceptsDatesReleasedByCancelledBooking` | Booking cũ đã `CANCELLED`, đặt lại cùng ngày | Được nhận |

## Công cụ cần có

- Windows 64-bit
- SQL Server 2019/2022 Database Engine đang chạy
- JDK 17 x64
- Maven 3.9 trở lên; có thể dùng Maven tích hợp của IntelliJ IDEA
- Internet ở lần build đầu để Maven tải dependencies từ Maven Central

## Mở và nạp Maven dependencies trong IntelliJ

1. Chọn **File → Open**, mở thư mục `dbunit-item-3-booking-calendar` (thư mục chứa `pom.xml`).
2. Đặt Project SDK là JDK 17: **File → Project Structure → Project → SDK**.
3. Mở **File → Settings → Build, Execution, Deployment → Build Tools → Maven**; chọn Maven home phù hợp, đặt **JDK for importer** là JDK 17 và bỏ chọn **Work offline**.
4. Mở **View → Tool Windows → Maven**, bấm **Reload All Maven Projects**. Nếu không thấy nút, bấm phải `pom.xml` → **Maven → Reload project**.
5. Chờ đồng bộ hoàn tất. Maven tải JUnit, DBUnit, Microsoft JDBC Driver và thư viện xác thực Windows từ các khai báo trong `pom.xml`; không tải JAR riêng lẻ.

## Kết nối tới SQL Server

Mặc định test dùng Windows Integrated Authentication và URL `localhost`. Với SQL Server Express mặc định, mở PowerShell và đặt URL theo instance của máy trước khi chạy:

```powershell
$env:HOTEL_DBUNIT_JDBC_URL = 'jdbc:sqlserver://localhost\SQLEXPRESS;databaseName=hotel_booking_dbunit_demo;encrypt=true;trustServerCertificate=true;integratedSecurity=true'
```

Thay `localhost\SQLEXPRESS` bằng server/instance thực tế. Nếu named instance không được JDBC tìm thấy, bật TCP/IP và dùng cổng cố định, ví dụ `localhost:1433`. Maven/IntelliJ phải chạy bằng tài khoản Windows có quyền kết nối `master`, tạo database và ghi vào database thử nghiệm.

## Chạy test

Từ PowerShell:

```powershell
cd "D:\path\to\dbunit-item-3-booking-calendar"
mvn "-Dtest=BookingProcedureDbUnitTest" test
```

Chạy riêng từng test bằng cách thay tên method sau dấu `#`, ví dụ:

```powershell
mvn "-Dtest=BookingProcedureDbUnitTest#rejectsPartialOverlap" test
```

Kết quả thành công cần báo `Tests run: 6, Failures: 0, Errors: 0` và `BUILD SUCCESS`. Có thể chạy từng method bằng biểu tượng Run cạnh `@Test` trong IntelliJ.

## Database và dataset

Trước test đầu, mã test tự tạo database riêng `hotel_booking_dbunit_demo` nếu chưa có; schema resource `src/test/resources/sql/hotel_booking_schema.sql` dựng bảng và procedure. Mỗi test xóa dữ liệu trong các bảng fixture rồi nạp lại XML theo thứ tự khóa ngoại: `Guest.xml`, `Room.xml`, `Booking.xml`, `Payment.xml`. Các file expected trong `src/test/resources/expected/` định nghĩa trạng thái Booking mong đợi cho ba tình huống được nhận.

Các test chỉ reset các bảng trong `hotel_booking_dbunit_demo`, không reset database `hotel_booking_demo`. Dùng một SQL Server instance có quyền tạo database và schema; không chạy test trên database production.

Nếu chạy test từ IntelliJ thay vì terminal, đặt cùng biến `HOTEL_DBUNIT_JDBC_URL` trong **Run → Edit Configurations → Environment variables** cho cấu hình test. Sau khi sửa biến, chạy lại test.
