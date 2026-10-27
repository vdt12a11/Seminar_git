# Kịch Bản & Báo Cáo Thực Thi Demo Flyway (Mục 4.2 & 4.3)

Tài liệu này đóng vai trò như một **Cheatsheet thực hành** để bạn copy-paste và trình chiếu trong buổi seminar. Toàn bộ kịch bản sử dụng **Flyway Community 13.10.3** chạy trên **Docker** với database SQLite (`demo_app.db`).

---

## 1. Thiết Lập Môi Trường (Setup)

- **Thư mục làm việc**: [flyway-rename-demo/](file:///d:/CNTT/2026-2027/KTPM/seminar/flyway-rename-demo/)
- **Cấu hình Flyway**: [flyway.toml](file:///d:/CNTT/2026-2027/KTPM/seminar/flyway-rename-demo/flyway.toml)
- **Container Runner**: [docker-compose.yml](file:///d:/CNTT/2026-2027/KTPM/seminar/flyway-rename-demo/docker-compose.yml)
- **Các tệp Migration có sẵn trong thư mục [migrations/](file:///d:/CNTT/2026-2027/KTPM/seminar/flyway-rename-demo/migrations/)**:
  - [V1__Create_users_table.sql](file:///d:/CNTT/2026-2027/KTPM/seminar/flyway-rename-demo/migrations/V1__Create_users_table.sql)
  - [V2__Rename_full_name_to_display_name.sql](file:///d:/CNTT/2026-2027/KTPM/seminar/flyway-rename-demo/migrations/V2__Rename_full_name_to_display_name.sql)
  - [V3__Rollback_display_name_to_full_name.sql](file:///d:/CNTT/2026-2027/KTPM/seminar/flyway-rename-demo/migrations/V3__Rollback_display_name_to_full_name.sql)

> [!TIP]
> **Không cần copy từng file vào trong lúc demo!**  
> Vì toàn bộ các file `V1`, `V2`, `V3` đã có sẵn trong `migrations/`, bạn chỉ cần dùng cờ **`-target="<version>"`** để điều khiển Flyway chạy từng nấc tương ứng.

---

## 2. Lệnh Dọn Sạch Môi Trường Để Bắt Đầu Demo Mới (Reset)

Trước khi bắt đầu buổi demo (hoặc khi muốn demo lại từ đầu):

**Trên Windows (PowerShell):**
```powershell
cd d:\CNTT\2026-2027\KTPM\seminar\flyway-rename-demo
docker rm -f flyway-runner 2>$null
Remove-Item demo_app.db -Force -ErrorAction SilentlyContinue
```

**Trên Linux / macOS:**
```bash
cd flyway-rename-demo
docker rm -f flyway-runner 2>/dev/null || true
rm -f demo_app.db
```

---

## 3. Các Bước Thực Hành Demo Từng Bước

### Bước 1: Áp dụng Migration nền tảng (`V1`) — Khởi tạo bảng `users`

Chỉ định Flyway dừng lại ở phiên bản `1`:

```bash
docker compose run --rm flyway -target="1" migrate
```
*(Hoặc dùng lệnh Docker trực tiếp: `docker run --rm -v "d:/CNTT/2026-2027/KTPM/seminar/flyway-rename-demo:/flyway/project" -w /flyway/project redgate/flyway:13.10.3 -target="1" migrate`)*

**Kết quả mong đợi:**
```text
Flyway Community Edition 13.10.3 by Redgate
Database: jdbc:sqlite:demo_app.db (SQLite 3.50)
Successfully applied 1 migration to schema "main", now at version v1
```

**Xác minh dữ liệu mẫu ban đầu:**
```bash
sqlite3 demo_app.db "SELECT id, email, full_name FROM users;"
```
Output:
```text
1|an.nguyen@example.com|Nguyen Van An
2|binh.tran@example.com|Tran Thi Binh
```

---

### Bước 2: Kiểm tra trạng thái hàng đợi bằng `flyway info`

Cho khán giả thấy `V1` đã thành công, còn `V2` và `V3` đang ở trạng thái `Pending`:

```bash
docker compose run --rm flyway info
```

**Kết quả mong đợi:**
```text
+-----------+---------+------------------------------------+------+---------------------+---------+
| Category  | Version | Description                        | Type | Installed On        | State   |
+-----------+---------+------------------------------------+------+---------------------+---------+
| Versioned | 1       | Create users table                 | SQL  | 2026-10-27 09:20:00 | Success |
| Versioned | 2       | Rename full name to display name   | SQL  |                     | Pending |
| Versioned | 3       | Rollback display name to full name | SQL  |                     | Pending |
+-----------+---------+------------------------------------+------+---------------------+---------+
```

---

### Bước 3: Áp dụng Migration `V2` — Đổi tên cột (`full_name` -> `display_name`)

Chỉ định Flyway nâng cấp lên đến `-target="2"` (chưa chạy `V3`):

```bash
docker compose run --rm flyway -target="2" migrate
```

**Kết quả mong đợi:**
```text
Migrating schema "main" to version "2 - Rename full name to display name"
Successfully applied 1 migration to schema "main", now at version v2
```

**Xác minh cột đã được đổi tên và dữ liệu vẫn nguyên vẹn:**
```bash
sqlite3 demo_app.db "PRAGMA table_info(users);"
sqlite3 demo_app.db "SELECT id, email, display_name FROM users;"
```
Output:
```text
1|an.nguyen@example.com|Nguyen Van An
2|binh.tran@example.com|Tran Thi Binh
```

---

### Bước 4: Kiểm thử Rollback bằng Compensating Migration `V3` (Chuẩn Flyway Community)

Thực thi hoàn tác (đổi `display_name` trở lại `full_name`) bằng cách chạy tiếp đến `-target="3"` (hoặc chạy lệnh `migrate` bình thường):

```bash
docker compose run --rm flyway -target="3" migrate
```

**Kiểm tra bảng lịch sử sau Rollback:**
```bash
docker compose run --rm flyway info
```

Output:
```text
+-----------+---------+------------------------------------+------+---------------------+---------+
| Category  | Version | Description                        | Type | Installed On        | State   |
+-----------+---------+------------------------------------+------+---------------------+---------+
| Versioned | 1       | Create users table                 | SQL  | 2026-10-27 09:20:00 | Success |
| Versioned | 2       | Rename full name to display name   | SQL  | 2026-10-27 09:22:00 | Success |
| Versioned | 3       | Rollback display name to full name | SQL  | 2026-10-27 09:24:00 | Success |
+-----------+---------+------------------------------------+------+---------------------+---------+
```

**Xác nhận cấu trúc và dữ liệu đã quay về `full_name`:**
```bash
sqlite3 demo_app.db "PRAGMA table_info(users);"
sqlite3 demo_app.db "SELECT id, email, full_name FROM users;"
```
Output:
```text
1|an.nguyen@example.com|Nguyen Van An
2|binh.tran@example.com|Tran Thi Binh
```

---

## 4. Tóm Tắt Thông Điệp Thuyết Trình
1. **Kiểm soát phiên bản rõ ràng:** Dù có sẵn tất cả các file migration, Flyway cho phép áp dụng từng phiên bản an toàn qua cờ `-target`.
2. **Flyway Community Rollback:** Bản miễn phí không có lệnh `undo`, do đó thực tế doanh nghiệp áp dụng mẫu **Compensating Migration (Roll-Forward)** để hoàn tác mà vẫn giữ trọn vẹn lịch sử kiểm toán trong `flyway_schema_history`.
3. **Tính toàn vẹn dữ liệu:** Toàn bộ quá trình đổi tên cột xuôi và ngược đều bảo toàn 100% dữ liệu có sẵn.