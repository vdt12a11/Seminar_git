-- Tệp: migrations/V3__Rollback_display_name_to_full_name.sql
ALTER TABLE users RENAME COLUMN display_name TO full_name;
