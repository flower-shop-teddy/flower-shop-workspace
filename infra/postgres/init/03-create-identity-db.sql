-- DB riêng cho identity-service (tài khoản, role, permission, refresh token, nhật ký đăng nhập).
-- Đây là DB nhạy cảm nhất hệ thống: môi trường thật nên tách instance riêng, giới hạn người được truy cập.
-- Mật khẩu dưới đây CHỈ dùng cho máy dev.
--
-- Volume postgres TRỐNG: script tự chạy khi container bật lần đầu.
-- Volume đã có dữ liệu: chạy tay MỘT lần, không cần xóa volume:
--   docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER"' < infra/postgres/init/03-create-identity-db.sql

CREATE USER identity_user WITH PASSWORD 'identity_pass_local';
CREATE DATABASE identity_db OWNER identity_user;
