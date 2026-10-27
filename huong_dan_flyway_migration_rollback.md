# Hướng Dẫn Vận Hành Flyway 13.10.3 An Toàn: Quản Lý Migration & Kiểm Thử Rollback

Tài liệu này cung cấp hướng dẫn thực chiến về cách sử dụng [Redgate Flyway](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fflyway%2Fflyway) (phiên bản mới nhất **Flyway CLI 13.10.3**, phát hành tháng 10/2026) để triển khai thay đổi cơ sở dữ liệu an toàn, phân tích các chế độ lỗi dễ gây hiểu lầm (`Failure Modes`), và thực hành kịch bản đổi tên cột (`RENAME COLUMN`) kèm kiểm thử hoàn tác (`Rollback Test`).

## 1. Chức năng cốt lõi: Kiểm soát phiên bản Schema và Hỗ trợ Rollback

[Flyway](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fflyway-open-source-277579296.html) hoạt động dựa trên nguyên lý đưa cơ sở dữ liệu vào quy trình kiểm soát phiên bản (Version Control) tương tự như mã nguồn ứng dụng, xoay quanh hai trụ cột chính:

* **Quản lý Migration theo phiên bản (Version-Controlled Migrations)**:
  * Mỗi thay đổi lên cấu trúc hoặc dữ liệu được định nghĩa trong một tệp SQL (hoặc Java) có tiền tố `V` theo quy ước đặt tên nghiêm ngặt: `V<Phiên_bản>__<Mô_tả>.sql` (ví dụ: `V1__Create_users_table.sql`, `V2__Rename_full_name_to_display_name.sql`).
  * Flyway tự động khởi tạo và duy trì bảng siêu dữ liệu [flyway\_schema\_history](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fflyway-schema-history-table-273973417.html) ngay trong schema mục tiêu để lưu trữ lịch sử từng bản nâng cấp, thời gian chạy, người thực thi, trạng thái (`Success`, `Failed`, `Undone`) và mã băm kiểm tra toàn vẹn (`checksum` CRC32).
  * Bên cạnh migration có phiên bản (`V`), Flyway hỗ trợ **Repeatable Migrations** (`R__<Mô_tả>.sql`) tự động chạy lại mỗi khi mã băm thay đổi, phù hợp để quản lý Views, Stored Procedures và Functions.
* **Hỗ trợ hoàn tác và giao dịch an toàn (Rollback Support & Transactional DDL)**:
  * **Tự động Rollback khi lỗi giao dịch ([Migration Transaction Handling](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fmigration-transaction-handling-273973399.html))**: Mặc định, Flyway đóng gói mỗi tệp migration trong một giao dịch (transaction) riêng biệt (hoặc gộp chung toàn bộ đợt chạy nếu bật `group = true`). Trên các hệ quản trị CSDL hỗ trợ Transactional DDL (như PostgreSQL, SQL Server, SQLite), nếu một câu lệnh thất bại giữa chừng, toàn bộ tệp migration đó được hoàn tác sạch sẽ.
  * **Hoàn tác chủ động bằng Undo Migrations ([Flyway Undo](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fundo-migrations-273973334.html))**: Trong phiên bản thương mại (Flyway Teams / Enterprise), mỗi tệp `V<Phiên_bản>__<Mô_tả>.sql` có thể đi kèm một tệp `U<Phiên_bản>__<Mô_tả>.sql` chứa câu lệnh đảo ngược. Lệnh `flyway undo` sẽ thực thi tệp `U` tương ứng và ghi nhận trạng thái `Undone` vào lịch sử kiểm toán.
  * **Hoàn tác theo hướng tiến (Roll-Forward / Compensating Migration) trên bản [Flyway Community](https://www.google.com/search?q=https%3A%2F%2Fwww.baeldung.com%2Fflyway-roll-back)**: Với bản mã nguồn mở miễn phí, việc hoàn tác được thực hiện bằng cách tạo một phiên bản mới tiếp theo (`V<N+1>__Rollback_...sql`) chứa câu lệnh khôi phục trạng thái cũ để bảo toàn tính bất biến của lịch sử triển khai.

## 2. Đánh giá Ưu điểm và Nhược điểm của Flyway

Bảng dưới đây tổng hợp các điểm mạnh và giới hạn kỹ thuật cần cân nhắc khi lựa chọn [Flyway](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fflyway%2Fflyway) cho hệ thống CI/CD:

| Tiêu chí đánh giá | Ưu điểm (Advantages) | Nhược điểm (Disadvantages) |
| :--- | :--- | :--- |
| **Ngôn ngữ định nghĩa Migration** | Sử dụng **SQL thuần túy (Plain SQL)** giúp lập trình viên và DBA viết, tối ưu hóa truy vấn và tận dụng tính năng riêng của từng CSDL mà không cần học cú pháp XML/YAML/JSON phức tạp như Liquibase ([Flyway GitHub](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Fflyway%2Fflyway)). | Phụ thuộc chặt vào cú pháp của hệ quản trị CSDL mục tiêu (Vendor Lock-in); khó dùng chung một bộ script cho nhiều loại CSDL khác nhau (ví dụ: vừa chạy trên Oracle vừa chạy trên PostgreSQL). |
| **Cơ chế Rollback (Hoàn tác)** | Cung cấp lịch sử kiểm toán (Audit Trail) rõ ràng khi dùng `flyway undo` (`State: Undone` và `UNDO_SQL`) và khuyến khích tư duy Roll-Forward an toàn trên môi trường Production ([Tutorial - Roll back using undo migrations](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Ftutorial-roll-back-using-undo-migrations-321586310.html)). | Lệnh `flyway undo` và khả năng tự động sinh script hoàn tác chỉ có trên bản trả phí (**Teams / Enterprise**); bản **Community** hoàn toàn không chạy được tệp tiền tố `U__` ([Baeldung Rollback Guide](https://www.google.com/search?q=https%3A%2F%2Fwww.baeldung.com%2Fflyway-roll-back)). |
| **Kiểm soát tính toàn vẹn** | Tự động tính toán và đối chiếu mã băm `checksum` qua [flyway\_schema\_history](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fflyway-schema-history-table-273973417.html); chặn đứng ngay lập tức nếu phát hiện tệp migration đã chạy bị chỉnh sửa trái phép trong mã nguồn. | Quy trình xử lý khi lệch checksum hoặc lỗi migration trên CSDL không hỗ trợ Transactional DDL đòi hỏi can thiệp thủ công phức tạp kết hợp với lệnh `flyway repair`. |
| **Triển khai & Tích hợp CI/CD** | Cực kỳ gọn nhẹ, khởi chạy nhanh qua [Flyway CLI 13.10.3](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fcommand-line-277579359.html), Docker (`redgate/flyway:13.10.3`), Maven, Gradle, Spring Boot hoặc [Redgate Flyway GitHub Actions](https://www.google.com/search?q=https%3A%2F%2Fwww.red-gate.com%2Fblog%2Fnew-redgate-flyway-github-actions-faster-setup-safer-deployments%2F). | Các tính năng nâng cao cho doanh nghiệp như Dry-run (xuất SQL xem trước mà không chạy), Drift Analysis (quét lệch cấu trúc thực tế) bị khóa sau gói bản quyền thương mại. |

## 3. Failure Modes: 3 cách thực tế Flyway có thể gây hiểu lầm cho người dùng

Khi vận hành trên môi trường thực tế, cơ chế báo cáo trạng thái của Flyway có thể tạo ra cảm giác an toàn giả tạo nếu kỹ sư không nắm rõ kiến trúc bên dưới. Dưới đây là 3 **Failure Modes** phổ biến nhất:

### Failure Mode 1: Ảo tưởng về "Transactional Rollback" trên CSDL có Implicit DDL Commit (MySQL, MariaDB, Oracle)

* **Cách công cụ gây hiểu lầm**: Tài liệu và thông báo mặc định của Flyway khẳng định mỗi tệp migration được bọc trong một transaction duy nhất ([Migration Transaction Handling](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fmigration-transaction-handling-273973399.html)). Điều này khiến người dùng tin rằng nếu một tệp `.sql` có 5 câu lệnh `ALTER TABLE` và bị lỗi ở câu lệnh thứ 3, thì 2 câu lệnh đầu sẽ tự động được rollback về trạng thái ban đầu.
* **Thực tế kỹ thuật**: Khác với PostgreSQL, SQL Server hay SQLite, các hệ quản trị như **MySQL, MariaDB và Oracle tự động phát lệnh `COMMIT` ngầm định (implicit commit) ngay trước và sau mỗi câu lệnh DDL**. Nếu câu lệnh thứ 3 bị lỗi cú pháp hoặc vi phạm ràng buộc, 2 câu lệnh DDL đầu tiên **đã ghi vĩnh viễn vào đĩa**, trong khi bảng [flyway\_schema\_history](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fflyway-schema-history-table-273973417.html) đánh dấu phiên bản đó là `Failed`. Nghiêm trọng hơn, nếu người dùng chạy `flyway repair`, Flyway chỉ xóa dòng `Failed` khỏi bảng lịch sử chứ **không hề hoàn tác 2 câu lệnh DDL đã chạy**, khiến lần chạy `flyway migrate` tiếp theo bị lỗi chồng lỗi (`Column/Table already exists`).
* **Cách phòng tránh**: Trên MySQL/Oracle, luôn tuân thủ nguyên tắc **mỗi câu lệnh DDL nằm trong một tệp migration `V` riêng biệt**, tuyệt đối không gộp nhiều lệnh `ALTER`/`CREATE` vào chung một tệp.

### Failure Mode 2: Ngộ nhận lệnh `flyway undo` có thể cứu một Migration bị lỗi giữa chừng hoặc khôi phục dữ liệu đã xóa

* **Cách công cụ gây hiểu lầm**: Khi chạy `flyway info`, cột `Undoable: Yes` xuất hiện cạnh các phiên bản có tệp `U__` đi kèm khiến nhiều kỹ sư tin rằng bất cứ khi nào quá trình nâng cấp gặp sự cố (failed deployment), chỉ cần gõ `flyway undo` là hệ thống sẽ tự động dọn dẹp và quay về phiên bản cũ ([Undo Migrations Documentation](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fundo-migrations-273973334.html)).
* **Thực tế kỹ thuật**: Theo [tài liệu chính thức của Redgate](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fundo-migrations-273973334.html), `flyway undo` **được thiết kế với giả định rằng toàn bộ phiên bản `V` tương ứng đã chạy thành công 100% (`State: Success`)**. Nếu `V2` bị lỗi ở câu lệnh thứ 2 trên tổng số 5 câu lệnh, bạn không thể dùng `flyway undo` để dọn dẹp `V2` vì tệp `U2` sẽ cố gắng đảo ngược cả các câu lệnh thứ 3, 4, 5 vốn chưa từng được thực thi. Ngoài ra, nếu `V2` chứa lệnh phá hủy dữ liệu (như `DROP COLUMN` hoặc `DELETE`), tệp `U2` khi chạy `ADD COLUMN` chỉ tạo lại được cột trống rỗng chứ không thể lấy lại dữ liệu đã mất.
* **Cách phòng tránh**: Luôn tạo bản sao lưu (Database Snapshot / Backup) trước khi chạy migration có tính chất phá hủy và chỉ dùng `flyway undo` cho các phiên bản đã ở trạng thái `Success`.

### Failure Mode 3: Cảm giác an toàn giả tạo từ thông báo `"Successfully validated"` của `flyway validate` trước Schema Drift

* **Cách công cụ gây hiểu lầm**: Khi chạy `flyway validate` (hoặc bước kiểm tra tự động trước `flyway migrate`), Flyway in ra thông báo `"Successfully validated X migrations"`. Nhiều nhóm phát triển hiểu nhầm rằng Flyway vừa kiểm tra cấu trúc các bảng, cột, khóa ngoại thực tế trong Database và xác nhận chúng khớp 100% với các tệp SQL trong kho lưu trữ Git ([Flyway Schema History Table](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fflyway-schema-history-table-273973417.html)).
* **Thực tế kỹ thuật**: Lệnh `flyway validate` **hoàn toàn không đọc cấu trúc bảng thực tế (database metadata/catalog) của CSDL**. Nó chỉ tính lại mã băm CRC32 của các tệp `.sql` trên ổ đĩa và so sánh với cột `checksum` lưu trong bảng `flyway_schema_history`. Nếu một ai đó đăng nhập trực tiếp vào DB để sửa tên cột, xóa index (Out-of-band change / Schema Drift), hoặc nếu lập trình viên sửa nội dung tệp `V1.sql` rồi chạy `flyway repair` để ghi đè lại checksum mới vào bảng lịch sử, `flyway validate` vẫn báo **thành công tuyệt đối**, che giấu hoàn toàn sự sai lệch giữa môi trường Staging và Production.
* **Cách phòng tránh**: Khóa quyền chỉnh sửa DDL trực tiếp (chỉ cấp quyền DDL cho tài khoản chạy Flyway CI/CD) và kiểm thử toàn bộ chuỗi migration từ đầu (`flyway clean` -> `flyway migrate` -> `Rollback Test`) trên một database sạch (Shadow/Test DB) trong pipeline.

## 4. Kịch bản Demo Thực Tế: Cài đặt từ ban đầu, Đổi tên cột và Kiểm thử Rollback

Kịch bản dưới đây hướng dẫn từng bước từ khâu cài đặt phiên bản mới nhất **Flyway 13.10.3** ([Redgate Command-line Reference](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fcommand-line-277579359.html)), khởi tạo dự án chuẩn với tệp cấu hình [flyway.toml](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fquickstart-command-line-184127576.html), thực hiện migration đổi tên cột (`full_name` thành `display_name`), và kiểm thử quá trình hoàn tác (Rollback Test).

### Phần 4.1: Cài đặt Flyway 13.10.3 từ ban đầu (Installation from Scratch)

Bạn có thể cài đặt **Flyway CLI 13.10.3** (phát hành ngày 15/10/2026) trên Linux, macOS, Windows hoặc chạy qua Docker theo [hướng dẫn cài đặt chính thức của Redgate](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fcommand-line-277579359.html):

**Cách 1: Cài đặt trên Linux (x64)**
```bash
wget -qO- https://download.red-gate.com/maven/release/com/redgate/flyway/flyway-commandline/13.10.3/flyway-commandline-13.10.3-linux-x64.tar.gz | tar -xvz
sudo ln -s "$(pwd)/flyway-13.10.3/flyway" /usr/local/bin/flyway
flyway -v
```

**Cách 2: Cài đặt trên macOS (Apple Silicon ARM64 / Intel x64) hoặc Windows**
```bash
# Trên macOS (Apple Silicon ARM64):
curl -L https://download.red-gate.com/maven/release/com/redgate/flyway/flyway-commandline/13.10.3/flyway-commandline-13.10.3-macosx-arm64.tar.gz | tar -xvz
export PATH="$(pwd)/flyway-13.10.3:$PATH"

# Trên Windows (PowerShell):
Invoke-WebRequest -Uri "https://download.red-gate.com/maven/release/com/redgate/flyway/flyway-commandline/13.10.3/flyway-commandline-13.10.3-windows-x64.zip" -OutFile "flyway-13.10.3.zip"
Expand-Archive -Path "flyway-13.10.3.zip" -DestinationPath "C:\tools\"
$env:Path += ";C:\tools\flyway-13.10.3"
```

**Cách 3: Sử dụng Docker Image chính thức (`redgate/flyway:13.10.3`)**
```bash
docker pull redgate/flyway:13.10.3
```

### Phần 4.2: Khởi tạo cấu trúc dự án và cấu hình chạy Docker

Từ Flyway 10+ đến **13.10.3**, định dạng cấu hình chuẩn được khuyến nghị là [flyway.toml](https://www.google.com/search?q=https%3A%2F%2Fdocumentation.red-gate.com%2Ffd%2Fflyway-projects-271585108.html) (thay thế cho `flyway.conf` cũ). Trong kịch bản này, chúng ta sử dụng **SQLite** (`demo_app.db`) đi kèm sẵn JDBC driver trong Flyway CLI và hỗ trợ đầy đủ lệnh `ALTER TABLE ... RENAME COLUMN` trong Transaction từ SQLite 3.25+.

**Bước 1: Cấu trúc thư mục dự án**
```text
flyway-rename-demo/
├── docker-compose.yml       # Cấu hình container chạy Flyway 13.10.3
├── flyway.toml              # Cấu hình kết nối DB và migrations folder
├── demo_app.db              # File SQLite DB (tự tạo khi migrate)
└── migrations/
    ├── V1__Create_users_table.sql
    ├── V2__Rename_full_name_to_display_name.sql
    ├── V3__Rollback_display_name_to_full_name.sql
    ├── U1__Create_users_table.sql                     (Teams/Enterprise)
    └── U2__Rename_full_name_to_display_name.sql       (Teams/Enterprise)
```

**Bước 2: Tệp cấu hình `flyway.toml`**
```toml
[flyway]
locations = ["filesystem:migrations"]
validateOnMigrate = true

[environments.default]
url = "jdbc:sqlite:demo_app.db"
user = ""
password = ""
```

**Bước 3: Tệp `docker-compose.yml` (Giúp gõ lệnh nhanh, không cần nhớ đường dẫn volume dài dòng)**
```yaml
services:
  flyway:
    image: redgate/flyway:13.10.3
    container_name: flyway-runner
    volumes:
      - .:/flyway/project
    working_dir: /flyway/project
    command: info
```

> [!TIP]
> **Mẹo Demo Chuyên Nghiệp: Quản lý theo từng bước bằng cờ `-target`**
> Bạn **không cần phải thêm/copy từng file vào thư mục `migrations/`** trong lúc thuyết trình. Hãy để sẵn toàn bộ các file `V1`, `V2`, `V3` trong thư mục. Khi muốn chạy dừng lại ở phiên bản nào, chỉ cần truyền thêm tham số `-target="<version>"`. Flyway sẽ chỉ migrate đến đúng phiên bản đó, các phiên bản lớn hơn sẽ được giữ nguyên ở trạng thái `Pending`.

---

### Phần 4.3: Kịch bản thực hành — Tạo bảng, Đổi tên cột (`RENAME COLUMN`), Chạy Migration và Rollback

> [!NOTE]
> Các câu lệnh bên dưới có thể chạy bằng **Docker Compose** (ngắn gọn nhất) hoặc **Docker run** trực tiếp. Bạn hãy đứng tại thư mục `flyway-rename-demo/` để thực thi.

#### Lệnh dọn sạch để demo lại từ đầu (Clean up / Reset)
Bất cứ khi nào bạn muốn reset database về trạng thái hoàn toàn mới để bắt đầu demo lại từ đầu:
- **PowerShell (Windows)**:
  ```powershell
  docker rm -f flyway-runner 2>$null
  Remove-Item demo_app.db -Force -ErrorAction SilentlyContinue
  ```
- **Bash (Linux / macOS)**:
  ```bash
  docker rm -f flyway-runner 2>/dev/null || true
  rm -f demo_app.db
  ```

---

#### Bước 1: Áp dụng Migration nền tảng (`V1`) — Khởi tạo bảng `users`

Nội dung `migrations/V1__Create_users_table.sql`:
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(150) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (id, email, full_name) VALUES (1, 'an.nguyen@example.com', 'Nguyen Van An');
INSERT INTO users (id, email, full_name) VALUES (2, 'binh.tran@example.com', 'Tran Thi Binh');
```

**Thực thi lệnh chỉ định `-target="1"`:**
- Với Docker Compose:
  ```bash
  docker compose run --rm flyway -target="1" migrate
  ```
- Với Docker run:
  ```bash
  docker run --rm -v "${PWD}:/flyway/project" -w /flyway/project redgate/flyway:13.10.3 -target="1" migrate
  ```

Kết quả:
```text
Database: jdbc:sqlite:demo_app.db (SQLite 3.50)
Successfully applied 1 migration to schema "main", now at version v1
```

Kiểm tra dữ liệu SQLite:
```bash
sqlite3 demo_app.db "SELECT id, email, full_name FROM users;"
# Kết quả:
# 1|an.nguyen@example.com|Nguyen Van An
# 2|binh.tran@example.com|Tran Thi Binh
```

---

#### Bước 2: Kiểm tra trạng thái hàng đợi bằng `flyway info`

Trước khi lên `V2`, chạy `info` để khán giả thấy `V2` và `V3` đang ở trạng thái `Pending`:
```bash
docker compose run --rm flyway info
```
Bảng trạng thái:
```text
+-----------+---------+----------------------------------+------+---------------------+---------+
| Category  | Version | Description                      | Type | Installed On        | State   |
+-----------+---------+----------------------------------+------+---------------------+---------+
| Versioned | 1       | Create users table               | SQL  | 2026-10-27 09:20:00 | Success |
| Versioned | 2       | Rename full name to display name | SQL  |                     | Pending |
| Versioned | 3       | Rollback display name to full... | SQL  |                     | Pending |
+-----------+---------+----------------------------------+------+---------------------+---------+
```

---

#### Bước 3: Áp dụng Migration `V2` — Đổi tên cột (`full_name` -> `display_name`)

Nội dung `migrations/V2__Rename_full_name_to_display_name.sql`:
```sql
ALTER TABLE users RENAME COLUMN full_name TO display_name;
```

**Thực thi nâng cấp đến `-target="2"`:**
```bash
docker compose run --rm flyway -target="2" migrate
```

Flyway sẽ chỉ chạy duy nhất `V2` và tạm dừng trước `V3`.

Kiểm tra cấu trúc schema và dữ liệu:
```bash
sqlite3 demo_app.db "PRAGMA table_info(users);"
sqlite3 demo_app.db "SELECT id, email, display_name FROM users;"
# Kết quả dữ liệu nguyên vẹn:
# 1|an.nguyen@example.com|Nguyen Van An
# 2|binh.tran@example.com|Tran Thi Binh
```

---

#### Bước 4: Thực hiện Kiểm thử Rollback (Rollback Test)

##### Phương pháp A: Rollback bằng lệnh `flyway undo` (Dành cho Flyway Teams / Enterprise)
Nếu có bản quyền Teams/Enterprise và file `migrations/U2__Rename_full_name_to_display_name.sql`:
```bash
docker compose run --rm flyway undo
```

##### Phương pháp B: Rollback bằng Compensating Migration `V3` (Chuẩn Flyway Community Open Source)
Nội dung `migrations/V3__Rollback_display_name_to_full_name.sql`:
```sql
ALTER TABLE users RENAME COLUMN display_name TO full_name;
```

**Thực thi hoàn tất đến `-target="3"` (hoặc chạy migrate thông thường):**
```bash
docker compose run --rm flyway -target="3" migrate
```

Kiểm tra trạng thái cuối cùng với `flyway info`:
```bash
docker compose run --rm flyway info
```
Bảng trạng thái:
```text
+-----------+---------+----------------------------------+------+---------------------+---------+
| Category  | Version | Description                      | Type | Installed On        | State   |
+-----------+---------+----------------------------------+------+---------------------+---------+
| Versioned | 1       | Create users table               | SQL  | 2026-10-27 09:20:00 | Success |
| Versioned | 2       | Rename full name to display name | SQL  | 2026-10-27 09:22:00 | Success |
| Versioned | 3       | Rollback display name to full... | SQL  | 2026-10-27 09:24:00 | Success |
+-----------+---------+----------------------------------+------+---------------------+---------+
```

Xác nhận dữ liệu cột đã quay về `full_name`:
```bash
sqlite3 demo_app.db "SELECT id, email, full_name FROM users;"
# 1|an.nguyen@example.com|Nguyen Van An
# 2|binh.tran@example.com|Tran Thi Binh
```

### Phần 4.4: Lưu ý thực chiến khi Đổi tên cột trên Production (Expand-and-Contract Pattern)

Trong môi trường Production đang có nhiều instance ứng dụng chạy song song (Zero-Downtime Deployment), lệnh `ALTER TABLE users RENAME COLUMN full_name TO display_name` trực tiếp có thể làm các instance ứng dụng phiên bản cũ bị lỗi ngay lập tức vì không tìm thấy cột `full_name`. Để triển khai và rollback an toàn tuyệt đối mà không gây gián đoạn dịch vụ, hãy chia nhỏ thao tác đổi tên cột thành 3 pha (**Expand - Migrate - Contract**):

1. **Pha Expand (`V2`)**: Thêm cột mới `display_name`, tạo Trigger hoặc cập nhật code ứng dụng để ghi song song (Dual-Write) vào cả `full_name` và `display_name`, đồng thời backfill dữ liệu từ `full_name` sang `display_name`. Nếu cần rollback code ứng dụng ở bước này, cột `full_name` vẫn còn nguyên vẹn nên không cần can thiệp DB.
2. **Pha Switch Read**: Chuyển toàn bộ ứng dụng sang đọc từ cột `display_name`.
3. **Pha Contract (`V3`)**: Khi chắc chắn không còn phiên bản ứng dụng nào dùng cột cũ và đã có bản sao lưu, mới thực thi migration xóa cột `full_name`.
