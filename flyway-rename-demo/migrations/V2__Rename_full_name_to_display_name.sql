-- Tệp: migrations/V2__Rename_full_name_to_display_name.sql
ALTER TABLE users RENAME COLUMN full_name TO display_name;
