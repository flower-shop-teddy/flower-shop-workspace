-- Script chỉ chạy MỘT LẦN khi volume postgres còn trống.
-- Nguyên tắc ngân hàng: mỗi service một database + một user riêng (least privilege).
-- catalog_user chỉ có quyền trên catalog_db, không đụng được DB của service khác.
-- Mật khẩu dưới đây CHỈ dùng cho máy dev.

CREATE USER catalog_user WITH PASSWORD 'catalog_pass_local';
CREATE DATABASE catalog_db OWNER catalog_user;

-- Các service khác: 02-, 03-, 04-, 05-... (mỗi service một file)
