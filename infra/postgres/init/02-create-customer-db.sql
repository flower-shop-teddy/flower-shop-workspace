-- DB riêng cho customer-service (mỗi service một database + một user, như 01-create-databases.sql).
-- Mật khẩu dưới đây CHỈ dùng cho máy dev.
--
-- Volume postgres TRỐNG: script tự chạy khi container bật lần đầu.
-- Volume đã có dữ liệu (máy đang chạy catalog từ trước): chạy tay MỘT lần, không cần xóa volume:
--   docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER"' < infra/postgres/init/02-create-customer-db.sql

CREATE USER customer_user WITH PASSWORD 'customer_pass_local';
CREATE DATABASE customer_db OWNER customer_user;
