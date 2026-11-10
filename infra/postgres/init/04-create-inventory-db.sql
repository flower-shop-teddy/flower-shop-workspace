-- DB riêng cho inventory-service (lô hàng, phiếu giữ hàng, sổ cái kho).
-- Mật khẩu dưới đây CHỈ dùng cho máy dev.
--
-- Volume postgres TRỐNG: script tự chạy khi container bật lần đầu.
-- Volume đã có dữ liệu: chạy tay MỘT lần, không cần xóa volume:
--   docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER"' < infra/postgres/init/04-create-inventory-db.sql

CREATE USER inventory_user WITH PASSWORD 'inventory_pass_local';
CREATE DATABASE inventory_db OWNER inventory_user;
