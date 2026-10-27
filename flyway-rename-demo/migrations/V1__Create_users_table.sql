-- Tệp: migrations/V1__Create_users_table.sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(150) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (id, email, full_name) VALUES (1, 'an.nguyen@example.com', 'Nguyen Van An');
INSERT INTO users (id, email, full_name) VALUES (2, 'binh.tran@example.com', 'Tran Thi Binh');
