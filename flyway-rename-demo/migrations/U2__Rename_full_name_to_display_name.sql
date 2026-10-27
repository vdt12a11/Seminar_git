-- Tệp: migrations/U2__Rename_full_name_to_display_name.sql
ALTER TABLE users RENAME COLUMN display_name TO full_name;
