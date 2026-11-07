-- Script chỉ chạy MỘT LẦN khi volume postgres còn trống.
-- Nguyên tắc ngân hàng: mỗi service một database + một user riêng (least privilege).
-- catalog_user chỉ có quyền trên catalog_db, không đụng được DB của service khác.
-- Mật khẩu dưới đây CHỈ dùng cho máy dev.

CREATE USER catalog_user WITH PASSWORD 'catalog_pass_local';
CREATE DATABASE catalog_db OWNER catalog_user;

-- Giai đoạn sau sẽ thêm:
-- CREATE USER inventory_user WITH PASSWORD '...'; CREATE DATABASE inventory_db OWNER inventory_user;
-- CREATE USER order_user     WITH PASSWORD '...'; CREATE DATABASE order_db     OWNER order_user;
