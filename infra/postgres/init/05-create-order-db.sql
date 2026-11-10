-- DB riêng cho order-service (đơn hàng, lịch sử trạng thái, idempotency key).
-- Mật khẩu dưới đây CHỈ dùng cho máy dev.
--
-- Volume postgres TRỐNG: script tự chạy khi container bật lần đầu.
-- Volume đã có dữ liệu: chạy tay MỘT lần, không cần xóa volume:
--   docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER"' < infra/postgres/init/05-create-order-db.sql

CREATE USER order_user WITH PASSWORD 'order_pass_local';
CREATE DATABASE order_db OWNER order_user;
