"""Tiny, dependency-free SQL sandbox for the database testing seminar."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import closing
from pathlib import Path
import json
import re
import sqlite3
import uuid

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
DB_ID = re.compile(r"^[a-f0-9-]{36}$")


def database(db_id):
    path = DATA / f"{db_id}.sqlite3"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")  # Deliberate seminar defect.
    if not path.exists() or path.stat().st_size == 0:
        conn.executescript("""
            CREATE TABLE members (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE workshops (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                registered_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE enrollments (
                id INTEGER PRIMARY KEY,
                member_id INTEGER,
                workshop_id INTEGER,
                enrolled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TRIGGER enrollment_added AFTER INSERT ON enrollments
            BEGIN
                UPDATE workshops SET registered_count = registered_count + 1
                WHERE id = NEW.workshop_id;
            END;
            INSERT INTO members (name, email) VALUES
                ('An Nguyen', 'an@example.test'),
                ('Minh Tran', 'minh@example.test'),
                ('Linh Pham', 'linh@example.test');
            INSERT INTO workshops (title, capacity) VALUES
                ('Database Testing 101', 2),
                ('SQL Clinic', 12),
                ('Bug Hunt Lab', 8);
        """)
        conn.commit()
    return conn


def flaw_status(conn):
    checks = {
        "empty_name": "SELECT EXISTS(SELECT 1 FROM members WHERE trim(name) = '')",
        "null_email": "SELECT EXISTS(SELECT 1 FROM members WHERE email IS NULL)",
        "long_name": "SELECT EXISTS(SELECT 1 FROM members WHERE length(name) > 30)",
        "orphan_enrollment": "SELECT EXISTS(SELECT 1 FROM enrollments e LEFT JOIN members m ON m.id=e.member_id LEFT JOIN workshops w ON w.id=e.workshop_id WHERE m.id IS NULL OR w.id IS NULL)",
        "duplicate_enrollment": "SELECT EXISTS(SELECT 1 FROM (SELECT member_id, workshop_id FROM enrollments GROUP BY member_id, workshop_id HAVING count(*) > 1))",
        "trigger_drift": "SELECT EXISTS(SELECT 1 FROM workshops w WHERE w.registered_count != (SELECT count(*) FROM enrollments e WHERE e.workshop_id=w.id))",
        "over_capacity": "SELECT EXISTS(SELECT 1 FROM workshops WHERE registered_count > capacity)",
    }
    return {key: bool(conn.execute(sql).fetchone()[0]) for key, sql in checks.items()}


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, value):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def get_id(self):
        value = self.headers.get("X-Database-Id", "")
        if not DB_ID.fullmatch(value):
            raise ValueError("Database ID không hợp lệ")
        return value

    def do_GET(self):
        if self.path == "/api/state":
            try:
                with closing(database(self.get_id())) as conn:
                    tables = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
                    schema = []
                    for table in tables:
                        cols = conn.execute(f'PRAGMA table_info("{table["name"]}")').fetchall()
                        schema.append({"name": table["name"], "sql": table["sql"], "columns": [dict(c) for c in cols]})
                    self.send_json(200, {"schema": schema, "flaws": flaw_status(conn)})
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
            return
        if self.path == "/" or self.path == "/index.html":
            body = (ROOT / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/app.css" or self.path == "/app.js":
            body = (ROOT / self.path.lstrip("/")).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8" if self.path.endswith("js") else "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/query":
            self.send_error(404)
            return
        try:
            db_id = self.get_id()
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            sql = payload.get("sql", "").strip()
            if not sql:
                self.send_json(400, {"error": "Hãy nhập một câu SQL trước."})
                return
            with closing(database(db_id)) as conn:
                cur = conn.execute(sql)  # One statement per run; parameterized UI is unnecessary for this sandbox.
                rows = [dict(row) for row in cur.fetchmany(500)] if cur.description else []
                result = {"columns": [d[0] for d in cur.description] if cur.description else [], "rows": rows,
                          "changes": conn.total_changes, "flaws": flaw_status(conn)}
                conn.commit()
                self.send_json(200, result)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})
        except sqlite3.Error as exc:
            self.send_json(400, {"error": str(exc)})

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("Seminar SQL lab: http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
