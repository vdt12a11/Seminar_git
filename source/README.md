# Source DBUnit và SQL — demo tính tiền, payment, trigger

> **Phạm vi tương thích:** Hướng dẫn này ghi các bước chung cho Windows, nhưng không thể bảo đảm chạy nguyên trạng trên mọi máy. SQL Server có thể khác phiên bản, tên instance, cổng, kiểu xác thực và quyền tài khoản. Đối chiếu các mục cấu hình theo máy ở Bước 3 trước khi chạy. Ví dụ giả định Windows, SQL Server 2019/2022, JDK 17 x64 và JDBC tới SQL Server.

Thư mục này chứa hai bộ kiểm thử DBUnit, schema SQL Server và bộ dữ liệu XML gốc. Cả hai bộ test chạy trên database riêng `hotel_booking_dbunit_demo`. Mục 4 được kiểm thử bằng DBUnit; các script SQL ở đây chỉ dùng để tạo schema, nạp dữ liệu ban đầu và kiểm tra database trong SSMS.

## Nội dung

- `dbunit/`: dự án Maven chạy kiểm thử DBUnit.
- `dbunit/src/test/java/vn/hotelbooking/BookingProcedureDbUnitTest.java`: sáu ca kiểm thử procedure đặt phòng.
- `dbunit/src/test/java/vn/hotelbooking/PaymentTriggerDbUnitTest.java`: chín ca kiểm thử tiền phòng, payment và trigger.
- `dbunit/src/test/resources/datasets/`: bốn fixture XML được nạp lại trước từng test.
- `dbunit/src/test/resources/expected/`: bảng Booking mong đợi cho các ca đặt phòng.
- `dbunit/src/test/resources/sql/hotel_booking_schema.sql`: schema mà mã Java dùng để tự khởi tạo database khi chưa có procedure hoặc trigger.
- `datasets.zip` và `datasets/`: bản zip được cung cấp và bốn XML đã giải nén (`Guest.xml`, `Room.xml`, `Booking.xml`, `Payment.xml`). Các XML này giống với fixture được đóng gói trong dự án Maven.
- `sql/hotel_booking_sqlserver.sql`: schema SQL gốc được cung cấp để tham khảo; tạo database `hotel_booking_demo`.
- `sql/hotel_booking_dbunit_schema.sql`: cùng schema nhưng nhắm tới database riêng `hotel_booking_dbunit_demo`.
- `sql/seed_dbunit_dataset.sql`: nạp lại dữ liệu ban đầu từ các fixture XML vào database DBUnit để xem trong SSMS.
- `sql/verify_dbunit_dataset.sql`: truy vấn kiểm tra schema và các bảng sau khi nạp dữ liệu.

## Công cụ cần cài

1. **Microsoft SQL Server 2019/2022** (Developer hoặc Express) đã cài Database Engine và đang chạy. SSMS riêng lẻ không bao gồm SQL Server Engine. Tài khoản chạy test cần quyền kết nối `master`, tạo database nếu chưa có, rồi tạo bảng, procedure và trigger trong database demo.
2. **SQL Server Management Studio (SSMS)** để chạy schema, seed và xem kết quả SQL.
3. **JDK 17**. Kiểm tra bằng `java -version`.
4. **Apache Maven 3.9 trở lên**, hoặc dùng Maven tích hợp trong IntelliJ IDEA. Kiểm tra bằng `mvn -version`.
5. **IntelliJ IDEA** nếu muốn chạy test bằng nút Run. Test cũng có thể chạy hoàn toàn từ terminal bằng Maven.

Maven tự tải JUnit, DBUnit và Microsoft JDBC Driver từ `pom.xml`; không cần tải các thư viện Java này thủ công.

Máy cần truy cập Maven Central ít nhất ở lần build đầu để tải thư viện. Nếu dùng proxy hoặc mạng trường/công ty chặn Maven Central, cấu hình proxy trong Maven `settings.xml` hoặc nhờ quản trị mạng mở truy cập. IntelliJ có thể dùng Maven tích hợp, nhưng phải cấu hình đúng JDK và Maven settings.

## Cài công cụ trên Windows từ đầu

Các link tải dưới đây là trang chính thức của nhà phát hành. Nếu máy đã có đúng công cụ và phiên bản, bỏ qua mục đó. Cài SQL Server Database Engine trước SSMS: SSMS là ứng dụng quản lý, không cài database server.

### 1. Cài SQL Server Express 2022

1. Mở [trang tải SQL Server 2022 Express của Microsoft](https://www.microsoft.com/en-us/download/details.aspx?id=104781), bấm **Download**, chọn `SQL2022-SSEI-Expr.exe` rồi bấm **Next**.
2. Mở file vừa tải. Chọn **Basic** để cài nhanh SQL Server Express với thiết lập mặc định; đọc và chấp nhận điều khoản, chọn **Install**. Nếu cần đổi thư mục hoặc cấu hình instance, chọn **Custom** và ghi lại instance name ở bước cấu hình.
3. Khi cài xong, ghi lại tên instance. Với thiết lập Express mặc định thường là `SQLEXPRESS`; thử kết nối bằng `localhost\SQLEXPRESS`. Có thể kiểm tra trong **SQL Server Configuration Manager → SQL Server Services** xem service `SQL Server (SQLEXPRESS)` có trạng thái Running không.
4. Dùng Windows Authentication trước. Tài khoản cài đặt thường có quyền quản trị SQL; nếu dùng tài khoản Windows khác chạy Maven, cần cấp quyền phù hợp hoặc chọn SQL Authentication theo chính sách máy.

Nếu nhóm yêu cầu Developer edition, tải từ [trang tải SQL Server của Microsoft](https://www.microsoft.com/en-us/sql-server/sql-server-downloads), chọn Developer rồi làm theo trình cài. Với bài này Express đủ dùng cho local testing. SQL Server 2022 là phiên bản đã dùng để kiểm tra dự án này.

### 2. Cài SSMS

1. Mở [hướng dẫn cài SSMS 22 của Microsoft](https://learn.microsoft.com/en-us/ssms/install/install?view=sql-server-ver16), bấm link **Download SQL Server Management Studio 22 installer** để tải `vs_SSMS.exe`.
2. Mở `vs_SSMS.exe`, chấp nhận quyền cài đặt nếu Windows hỏi, rồi trong Visual Studio Installer bấm **Install**. Không cần cài workload tùy chọn cho bài này.
3. Mở SSMS → **Connect → Database Engine**. Với Express mặc định nhập **Server name** `localhost\SQLEXPRESS`, **Authentication** `Windows Authentication`, rồi bấm **Connect**. Nếu dùng tên instance/cổng khác, nhập giá trị thực tế theo Bước 3.

### 3. Cài JDK 17 x64

1. Mở [Eclipse Temurin JDK 17](https://adoptium.net/temurin/releases/?version=17), chọn **Operating System: Windows**, **Architecture: x64**, **Package Type: JDK**, tải file **MSI**.
2. Chạy MSI → **Next** → chấp nhận license → giữ các tùy chọn thêm Java vào `PATH` và đặt `JAVA_HOME` nếu hiện ra → **Install** → **Finish**.
3. Đóng rồi mở lại PowerShell; chạy `java -version`. Kết quả phải bắt đầu bằng phiên bản `17`. Nếu lệnh không tìm thấy, khởi động lại terminal hoặc cấu hình lại `JAVA_HOME`/`PATH` trong Windows Environment Variables.

### 4. Cài IntelliJ IDEA

1. Mở [trang tải IntelliJ IDEA của JetBrains](https://www.jetbrains.com/idea/download/), chọn Windows và tải installer.
2. Chạy installer, giữ thành phần Java mặc định, bật tùy chọn tạo shortcut nếu muốn, rồi hoàn tất cài đặt. Bản IntelliJ hiện dùng installer thống nhất; các tính năng Java cơ bản dùng để mở Maven project và chạy test có thể dùng miễn phí.
3. Lần đầu mở dự án, nếu hỏi **Trust Project**, chọn trust cho thư mục source bạn nhận được để IntelliJ cho phép nạp Maven project và chạy test.

### 5. Maven: dùng IntelliJ hoặc cài riêng

Nếu chỉ chạy trong IntelliJ, có thể dùng Maven tích hợp và bỏ qua cài Maven riêng. Nếu cần chạy lệnh `mvn` trong PowerShell:

1. Mở [trang tải Apache Maven](https://maven.apache.org/download.cgi), ở mục Maven 3 tải **Binary zip archive** (không tải Source zip). Giải nén, ví dụ vào `C:\Tools\apache-maven-3.9.16`.
2. Mở Windows **Edit the system environment variables → Environment Variables**. Tạo biến `MAVEN_HOME` trỏ tới thư mục vừa giải nén; sửa `Path` và thêm `%MAVEN_HOME%\bin`; bấm **OK** để lưu.
3. Đóng rồi mở PowerShell mới, chạy `mvn -version`. Dòng Maven phải là 3.9 trở lên và Java phải là JDK 17.

### 6. Chép source và dataset vào máy mới

1. Sao chép toàn bộ thư mục `source` sang máy đích, giữ nguyên các thư mục con. Mở `source/dbunit` trong IntelliJ, không mở riêng thư mục `source/dbunit/src`.
2. Dataset đã được kèm sẵn trong gói ở cả `source/datasets/` và `source/dbunit/src/test/resources/datasets/`. Không phải tải hoặc chép thêm dataset để chạy 15 test hiện tại. Bốn file phải có tên `Guest.xml`, `Room.xml`, `Booking.xml`, `Payment.xml`.
3. Nếu nhận một `datasets.zip` mới và muốn thay fixture: trong File Explorer bấm phải zip → **Extract All… → Extract**; mở thư mục giải nén (vào thư mục `datasets` nếu zip đã có thư mục con đó); chọn `Guest.xml`, `Room.xml`, `Booking.xml`, `Payment.xml`; copy vào `source/dbunit/src/test/resources/datasets/`; chọn **Replace the files in the destination** khi Windows hỏi. Giữ tên bảng trong XML đúng với schema (`Guest`, `Room`, `Booking`, `Payment`), tên thuộc tính đúng tên cột, và khóa ngoại hợp lệ. Thứ tự nạp hiện tại là Guest → Room → Booking → Payment.
4. Nếu muốn xem cùng dữ liệu trong SSMS, cập nhật/chạy `sql/seed_dbunit_dataset.sql` tương ứng. Chỉ thay XML thì test sẽ dùng dữ liệu mới, nhưng script seed SQL xem thủ công trong SSMS sẽ tiếp tục nạp bộ dữ liệu cũ cho tới khi cập nhật nó.

### 7. Nạp Maven dependencies trong IntelliJ

1. Trong IntelliJ chọn **File → Open**, chọn thư mục `source/dbunit` (thư mục có `pom.xml`), rồi chọn **Open as Project** nếu được hỏi.
2. Chọn JDK: **File → Project Structure → Project → SDK → Add SDK → JDK**, trỏ tới thư mục cài JDK 17; đặt **Language level** theo SDK mặc định.
3. Chọn **File → Settings → Build, Execution, Deployment → Build Tools → Maven**. Đặt **Maven home path** là Maven tích hợp hoặc Maven vừa cài; đặt **JDK for importer** là JDK 17; bảo đảm **Work offline** không được chọn. Bấm **Apply → OK**.
4. Mở Maven tool window: **View → Tool Windows → Maven**. Bấm **Reload All Maven Projects** (nút làm mới/đồng bộ ở đầu cửa sổ Maven). Nếu nút không thấy, bấm phải `pom.xml` → **Maven → Reload project**.
5. Để tải và kiểm tra dependencies lần đầu, mở Maven tool window → **Lifecycle → test** hoặc dùng terminal IntelliJ tại `source/dbunit` chạy `mvn -U test`. Chờ tiến trình kết thúc; lần đầu có thể mất vài phút. Dependencies được lấy theo `pom.xml`, gồm DBUnit, JUnit, Microsoft JDBC Driver và DLL xác thực Windows.
6. Kiểm tra **External Libraries** có thư viện Maven và không còn chỉ báo đồng bộ đang chạy. Nếu báo lỗi tải, mở **View → Tool Windows → Build** hoặc Maven Console để xem artifact/URL lỗi; kiểm tra internet, proxy và trạng thái **Work offline**, rồi bấm **Reload All Maven Projects** lần nữa. Không cần tự tải từng JAR hoặc bấm **Download Sources** để chạy test.

Sau khi IntelliJ đồng bộ Maven xong, chạy `mvn test` theo Bước 4 bên dưới hoặc bấm biểu tượng Run ở test/class theo mục “Chạy bằng IntelliJ IDEA”.

## Bước 1 — tạo schema cho DBUnit trong SQL Server

Mở SSMS, kết nối tới đúng SQL Server instance, mở `sql/hotel_booking_dbunit_schema.sql` rồi bấm **Execute**. Tệp này tạo database `hotel_booking_dbunit_demo`, bốn bảng, procedure `dbo.create_booking` và trigger `dbo.trg_Payment_UpdateBookingStatus`. Có thể bỏ qua bước chạy tay này: test tự tạo database/schema nếu thiếu, nhưng tài khoản JDBC khi đó phải có quyền tạo tương ứng.

Chạy schema một lần trên database mới. Tệp dùng `CREATE TABLE`, vì vậy nếu các bảng đã tồn tại thì bỏ qua bước này; không chạy lặp lại trên database đã được tạo.

Schema gốc `sql/hotel_booking_sqlserver.sql` tạo database `hotel_booking_demo` và được giữ để đối chiếu với tệp được cung cấp. Bộ test DBUnit mặc định kết nối `hotel_booking_dbunit_demo`, tách biệt với database đó. Schema dùng cú pháp SQL Server; không chạy trên MySQL, PostgreSQL hoặc SQLite.

## Bước 2 — nạp và kiểm tra dữ liệu trong SSMS

Mở `sql/seed_dbunit_dataset.sql` trong SSMS và bấm **Execute**. Script xóa các dòng hiện có trong bốn bảng của riêng `hotel_booking_dbunit_demo`, sau đó nạp lại dữ liệu khớp với `datasets/Guest.xml`, `Room.xml`, `Booking.xml` và `Payment.xml`. Có thể chạy lại script này để trở về cùng trạng thái ban đầu.

Mở tiếp `sql/verify_dbunit_dataset.sql` và chạy để xem database, procedure, trigger cùng các dòng Guest, Room, Booking và Payment. Kết quả mong đợi gồm hai booking ban đầu (ID 100 và 101), ba phòng và hai khoản payment.

Các XML trong `datasets.zip` là dữ liệu DBUnit, không phải tệp SQL chạy trực tiếp trong SSMS. `seed_dbunit_dataset.sql` là bản SQL tương ứng để nạp cùng các dòng đó khi cần xem dữ liệu bằng SSMS. Khi chạy test, DBUnit đọc trực tiếp các XML trong `dbunit/src/test/resources/datasets/` và nạp lại fixture trước từng ca; vì thế test không phụ thuộc vào dữ liệu còn lại từ lần chạy trước.

## Bước 3 — cấu hình kết nối

Mặc định, cả hai lớp test dùng Windows Integrated Authentication trên `localhost` và database `hotel_booking_dbunit_demo`. URL mặc định không chỉ rõ cổng; JDBC tìm SQL Server theo cơ chế discovery của driver. Nếu discovery không hoạt động, đặt cổng TCP tĩnh theo cấu hình thực tế, ví dụ:

```text
jdbc:sqlserver://localhost;databaseName=hotel_booking_dbunit_demo;encrypt=true;trustServerCertificate=true;integratedSecurity=true
```

Nếu server/instance khác, đặt biến môi trường `HOTEL_DBUNIT_JDBC_URL` trước khi chạy Maven, ví dụ:

```powershell
$env:HOTEL_DBUNIT_JDBC_URL = 'jdbc:sqlserver://localhost:1433;databaseName=hotel_booking_dbunit_demo;encrypt=true;trustServerCertificate=true;integratedSecurity=true'
```

Hoặc truyền property Java `-Dhotel.db.url="jdbc:sqlserver://..."`. Property `hotel.db.url` được ưu tiên hơn biến môi trường. Tài khoản kết nối cần quyền đọc/ghi dữ liệu trong `hotel_booking_dbunit_demo`; lần khởi tạo tự động cũng cần quyền tạo database và schema.

`pom.xml` tải Microsoft JDBC authentication DLL x64 vào `dbunit/target/native` khi Maven chuẩn bị tài nguyên test và cấu hình thư viện này cho Surefire. Nếu chạy trực tiếp bằng IntelliJ mà gặp lỗi không tìm thấy DLL xác thực Windows, chạy test bằng Maven theo bước tiếp theo hoặc đặt VM option `-Djava.library.path=<đường-dẫn-tuyệt-đối-tới-dbunit/target/native>` cho cấu hình JUnit.

### Những giá trị cần kiểm tra trên từng máy

- **Tên SQL Server / instance**: xem giá trị đang dùng ở ô **Server name** trong cửa sổ Connect của SSMS. Máy dùng default instance thường là `localhost` hoặc `COMPUTERNAME`; SQL Server Express thường là `localhost\SQLEXPRESS` hoặc `COMPUTERNAME\SQLEXPRESS`. Nếu dùng named instance, sửa host trong JDBC URL, ví dụ:

  ```powershell
  $env:HOTEL_DBUNIT_JDBC_URL = 'jdbc:sqlserver://localhost\SQLEXPRESS;databaseName=hotel_booking_dbunit_demo;encrypt=true;trustServerCertificate=true;integratedSecurity=true'
  ```

- **Cổng TCP**: nếu biết cổng cố định, dùng dạng `jdbc:sqlserver://localhost:1433;databaseName=...`. Trên máy khác hoặc máy chủ từ xa, bật TCP/IP trong SQL Server Configuration Manager, cho phép cổng đó qua firewall và dùng tên máy/IP cùng cổng trong URL.
- **SSMS kết nối được nhưng JDBC không kết nối được**: SSMS có thể đang dùng shared memory hoặc named pipe. Kiểm tra SQL Server Configuration Manager để xác nhận TCP/IP, cổng và trạng thái service; sau đó dùng `host:port` trong JDBC URL. Named instance như `localhost\SQLEXPRESS` có thể cần SQL Server Browser hoặc cấu hình cổng tĩnh.
- **Bật discovery cho Express instance**: mở **SQL Server Configuration Manager → SQL Server Services**, bấm phải **SQL Server Browser → Properties → Service**, đặt **Start Mode: Automatic**, bấm **Apply**, rồi bấm phải service đó → **Start**. Nếu vẫn không kết nối được, vào **SQL Server Network Configuration → Protocols for SQLEXPRESS → TCP/IP → Enable**; mở **TCP/IP → Properties → IP Addresses → IPAll**, xóa **TCP Dynamic Ports**, điền **TCP Port** (ví dụ `1433` nếu cổng đó đang trống), bấm **Apply**, khởi động lại **SQL Server (SQLEXPRESS)** và đặt JDBC URL là `jdbc:sqlserver://localhost:1433;databaseName=hotel_booking_dbunit_demo;encrypt=true;trustServerCertificate=true;integratedSecurity=true`. Chỉ cần mở cổng Windows Firewall khi kết nối từ máy khác.
- **Kiểu đăng nhập**: mặc định là Windows Integrated Authentication. Chạy SSMS, IntelliJ và Maven bằng cùng tài khoản Windows có quyền trên database. Trên máy khác hoặc máy domain, xác thực Windows có thể cần cấu hình native authentication riêng; nếu không phù hợp, dùng SQL Server Authentication theo chính sách của máy. Bật Mixed Mode nếu cần, cấp quyền cho login trên `master` và `hotel_booking_dbunit_demo`, rồi bỏ `integratedSecurity=true` và thêm `;user=<login>;password=<mật-khẩu>` vào JDBC URL lưu trong `HOTEL_DBUNIT_JDBC_URL`. Không ghi mật khẩu thật vào README, mã nguồn hay lệnh chia sẻ; nếu có thể, cấu hình biến môi trường qua Windows Settings thay vì gõ mật khẩu vào câu lệnh để tránh lưu trong PowerShell history.
- **Tên database**: giữ nguyên `hotel_booking_dbunit_demo` để các script schema, seed và URL mặc định khớp nhau. Nếu đổi tên, phải sửa đồng bộ `databaseName` trong schema/seed và cấu hình kết nối.
- **JDK**: dùng JDK 17; trên Windows nên dùng JDK 64-bit vì Maven tải DLL xác thực x64. Kiểm tra `java -version` và `mvn -version` trong đúng terminal mà IntelliJ/Maven sẽ dùng.
- **Kiến trúc JVM**: Windows Integrated Authentication trong cấu hình hiện tại dùng DLL x64. JVM 32-bit hoặc hệ điều hành khác không tương thích trực tiếp; cần điều chỉnh native authentication theo môi trường hoặc dùng SQL Server Authentication nếu được phép.
- **Server không ở máy hiện tại**: thay `localhost` bằng hostname/IP thật; kiểm tra SQL Server đang chạy, TCP/IP đã bật, firewall cho phép cổng SQL Server và tài khoản có quyền trên database đích.

## Bước 4 — chạy DBUnit bằng Maven

Mở PowerShell tại thư mục `source/dbunit`:

```powershell
cd "D:\vscode\Software testing\hotel-booking-demo\source\dbunit"
mvn clean test-compile
```

Chạy một test cụ thể:

```powershell
mvn "-Dtest=BookingProcedureDbUnitTest#rejectsPartialOverlap" test
mvn "-Dtest=PaymentTriggerDbUnitTest#calculatesTwoNightsWithoutDiscount" test
```

Chạy toàn bộ sáu test lịch đặt phòng:

```powershell
mvn "-Dtest=BookingProcedureDbUnitTest" test
```

Chạy toàn bộ chín test tính tiền và trigger:

```powershell
mvn "-Dtest=PaymentTriggerDbUnitTest" test
```

Chạy cả hai lớp:

```powershell
mvn test
```

Kết quả Maven phải báo `BUILD SUCCESS`. Báo cáo chi tiết nằm trong `dbunit/target/surefire-reports/`. Mỗi test dùng `@BeforeEach` để xóa các dòng cũ rồi nạp lại XML fixtures theo thứ tự Guest, Room, Booking, Payment. Sau test, database giữ trạng thái của ca vừa chạy; ca tiếp theo sẽ nạp lại dữ liệu ban đầu.

## Chạy bằng IntelliJ IDEA

1. Chọn **File → Open**, mở thư mục `source/dbunit` (thư mục có `pom.xml`).
2. Chọn JDK 17 cho Project SDK và chờ IntelliJ import Maven dependencies.
3. Mở `src/test/java/vn/hotelbooking/PaymentTriggerDbUnitTest.java` hoặc `BookingProcedureDbUnitTest.java`.
4. Bấm biểu tượng Run màu xanh cạnh một phương thức `@Test` để chỉ chạy ca đó; bấm cạnh tên lớp để chạy toàn bộ lớp.
5. Xem kết quả trong cửa sổ Run. Dấu kiểm xanh và `BUILD SUCCESS`/`tests passed` cho biết expected values khớp với dữ liệu thực tế đã truy vấn từ SQL Server.

## Kiểm tra dữ liệu bằng SQL Server Management Studio

Các ca kiểm thử procedure, tiền phòng, payment và trigger đều được chạy bằng hai lớp DBUnit trong `dbunit/src/test/java/vn/hotelbooking/`. Các tệp trong `sql/` không phải test case: schema dùng dựng database, seed dùng nạp dataset XML tương ứng để xem trong SSMS, verify dùng kiểm tra dữ liệu. Chạy test bằng Maven hoặc IntelliJ theo hướng dẫn phía trên.

Schema gốc `sql/hotel_booking_sqlserver.sql` chỉ được giữ để tham khảo; không cần chạy nó cho DBUnit. Để xem dữ liệu của test, chạy `sql/hotel_booking_dbunit_schema.sql`, sau đó `sql/seed_dbunit_dataset.sql` và `sql/verify_dbunit_dataset.sql` trên `hotel_booking_dbunit_demo`.

## Khắc phục lỗi thường gặp

- **Không kết nối được SQL Server**: kiểm tra service SQL Server đang chạy, tên instance/cổng trong JDBC URL, quyền Windows và khả năng kết nối từ SSMS.
- **Login failed / không có quyền tạo database**: cấp quyền tạo database cho tài khoản dùng chạy test, hoặc tạo trước `hotel_booking_dbunit_demo` và schema bằng SSMS; tài khoản vẫn cần quyền ghi dữ liệu và tạo booking.
- **Không tìm thấy procedure/trigger**: chạy `sql/hotel_booking_dbunit_schema.sql` một lần trên đúng database `hotel_booking_dbunit_demo`, sau đó chạy lại test.
- **Không tìm thấy authentication DLL**: dùng Maven để chạy test để dependency plugin thiết lập `target/native`, hoặc cấu hình `java.library.path` như hướng dẫn phía trên.
- **Test báo thiếu dataset XML**: mở đúng thư mục `source/dbunit` làm Maven project; không chạy Maven từ `source/`.

## Giới hạn tương thích

Hướng dẫn này giúp chuyển bộ test sang máy Windows khác khi máy đó có SQL Server tương thích và người cài điền đúng thông tin instance, cổng, quyền và kiểu đăng nhập. Không có bộ hướng dẫn nào bảo đảm cài được trên mọi cấu hình máy: máy không chạy Windows, dùng JVM 32-bit, SQL Server không hỗ trợ các cú pháp trong schema, bị chặn tải Maven dependencies, hoặc không cấp quyền database sẽ cần thay đổi riêng. Trước khi cài hàng loạt, nên thử quy trình trên một máy đích và ghi lại Server name/instance, cổng TCP, kiểu xác thực, phiên bản JDK/SQL Server và thông báo lỗi thực tế để cập nhật hướng dẫn cho môi trường đó.
