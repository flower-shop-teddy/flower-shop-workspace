"""Sinh Postman collection (v2.1) cho Flower Shop. Sửa file này rồi chạy lại khi thêm/đổi API:
    python3 postman/generate.py postman/flower-shop.postman_collection.json
"""
import json
import re
import sys
import uuid

GW = "{{gatewayUrl}}"
NUMERIC_VARS = ["flowerVersion", "customerVersion", "addressVersion", "myProfileVersion", "myAddressVersion", "myAddressId"]


def script(lines):
    return {"type": "text/javascript", "exec": lines}


def tests(*extra, status=None, ok=True):
    lines = []
    if status:
        lines.append(f'pm.test("HTTP {status}", () => pm.response.to.have.status({status}));')
    if ok:
        lines.append('pm.test("code = 00", () => pm.expect(pm.response.json().code).to.eql("00"));')
    lines.extend(extra)
    return lines


def save(var, path):
    return f'if (pm.response.json().data) pm.collectionVariables.set("{var}", pm.response.json().data{path});'


def req(name, method, url, body=None, auth="inherit", test=None, pre=None, desc=None, headers=None):
    r = {
        "method": method,
        "header": [],
        "url": url_object(url),
    }
    if desc:
        r["description"] = desc
    if body is not None:
        raw_body = json.dumps(body, ensure_ascii=False, indent=2)
        # Biến kiểu số (version, id) phải nằm trong JSON KHÔNG có dấu nháy
        for var in NUMERIC_VARS:
            raw_body = raw_body.replace('"{{' + var + '}}"', '{{' + var + '}}')
        r["body"] = {"mode": "raw", "raw": raw_body, "options": {"raw": {"language": "json"}}}
        r["header"].append({"key": "Content-Type", "value": "application/json"})
    for k, v in (headers or {}).items():
        r["header"].append({"key": k, "value": v})
    if auth == "none":
        r["auth"] = {"type": "noauth"}
    elif auth != "inherit":
        r["auth"] = bearer(auth)
    item = {"name": name, "request": r, "event": []}
    if pre:
        item["event"].append({"listen": "prerequest", "script": script(pre)})
    if test is not None:
        item["event"].append({"listen": "test", "script": script(test)})
    return item


def url_object(raw):
    """URL đầy đủ như Postman tự export (raw + host + path + query): Postman bản mới đọc host/path khi import,
    chỉ có raw thì request hiện ra với URL trống."""
    base, _, query = raw.partition("?")
    m = re.match(r"^(\{\{\w+\}\})(/.*)?$", base)
    if m:
        host, path = [m.group(1)], m.group(2) or ""
    else:   # http://host:port/... (không dùng trong file này, để phòng)
        scheme_host, _, path = base.partition("://")[2].partition("/")
        host, path = scheme_host.split("."), "/" + path
    url = {"raw": raw, "host": host, "path": [seg for seg in path.split("/") if seg]}
    if query:
        url["query"] = [{"key": k, "value": v} for k, _, v in (pair.partition("=") for pair in query.split("&"))]
    return url


def bearer(var):
    return {"type": "bearer", "bearer": [{"key": "token", "value": "{{" + var + "}}", "type": "string"}]}


def folder(name, items, auth=None, desc=None):
    f = {"name": name, "item": items}
    if auth == "none":
        f["auth"] = {"type": "noauth"}
    elif auth:
        f["auth"] = bearer(auth)
    if desc:
        f["description"] = desc
    return f


ADMIN_LOGIN_TEST = tests(
    save("adminToken", ".accessToken"),
    save("adminRefreshToken", ".refreshToken"),
    'pm.test("Không còn bị buộc đổi mật khẩu", () => pm.expect(pm.response.json().data.passwordChangeRequired).to.eql(false));',
    status=200)

auth_folder = folder("1. Đăng nhập & tài khoản", [
    req("Đăng nhập ADMIN lần đầu (mật khẩu mặc định)", "POST", f"{GW}/api/v1/auth/login",
        {"loginId": "{{adminUsername}}", "password": "{{adminInitialPassword}}"}, auth="none",
        test=['const body = pm.response.json();',
              '// DB mới: đăng nhập được bằng mật khẩu mặc định và bị buộc đổi. DB đã đổi rồi: 401, request sau tự bỏ qua',
              'const mustChange = pm.response.code === 200 && body.data && body.data.passwordChangeRequired === true;',
              'pm.collectionVariables.set("adminMustChangePassword", mustChange ? "true" : "false");',
              'if (mustChange) pm.collectionVariables.set("adminToken", body.data.accessToken);',
              'pm.test("Đăng nhập được (DB mới) hoặc mật khẩu đã đổi từ trước", () => pm.expect([200, 401]).to.include(pm.response.code));'],
        desc="CHỈ cần ở lần chạy đầu tiên trên DB mới (profile local tạo admin / FlowerShop2026, bắt buộc đổi mật khẩu).\n"
             "Đã đổi rồi thì request này trả IDN-401-001: bỏ qua, chạy thẳng 'Đăng nhập ADMIN'."),
    req("Đổi mật khẩu ADMIN (lần đầu)", "POST", f"{GW}/api/v1/auth/change-password",
        {"currentPassword": "{{adminInitialPassword}}", "newPassword": "{{adminPassword}}"}, auth="adminToken",
        pre=['if (pm.collectionVariables.get("adminMustChangePassword") !== "true") {',
             '    pm.execution.skipRequest();   // mật khẩu đã đổi từ trước: không cần chạy',
             '}'],
        test=tests(status=200), desc="Tự bỏ qua nếu mật khẩu ADMIN đã đổi từ trước. Đổi xong mọi phiên cũ bị thu hồi: đăng nhập lại."),
    req("Đăng nhập ADMIN", "POST", f"{GW}/api/v1/auth/login",
        {"loginId": "{{adminUsername}}", "password": "{{adminPassword}}"}, auth="none", test=ADMIN_LOGIN_TEST,
        desc="Lưu adminToken (sống 15 phút) và adminRefreshToken. Hết hạn thì chạy lại request này hoặc 'Làm mới token'."),
    req("Tôi là ai (/auth/me)", "GET", f"{GW}/api/v1/auth/me", auth="adminToken", test=tests(status=200)),
    req("Làm mới token (refresh)", "POST", f"{GW}/api/v1/auth/refresh", {"refreshToken": "{{adminRefreshToken}}"},
        auth="none", test=tests(save("adminToken", ".accessToken"), save("adminRefreshToken", ".refreshToken"), status=200),
        desc="Refresh token xoay vòng: dùng lại refresh token CŨ sẽ thu hồi cả phiên (phát hiện trộm token)."),
    req("Public key (JWKS)", "GET", f"{GW}/.well-known/jwks.json", auth="none",
        test=['pm.test("Có ít nhất một khóa", () => pm.expect(pm.response.json().keys.length).to.be.above(0));']),
], desc="Chạy theo thứ tự. Token tự lưu vào biến của collection.")

users_folder = folder("2. Quản trị nhân viên & phân quyền", [
    req("Danh sách role + permission", "GET", f"{GW}/api/v1/roles", test=tests(status=200)),
    req("Tạo nhân viên (mật khẩu tạm hiện MỘT lần)", "POST", f"{GW}/api/v1/users",
        {"username": "{{staffUsername}}", "roles": ["SHOP_STAFF"]},
        pre=['pm.collectionVariables.set("staffUsername", "nv" + Date.now().toString().slice(-8));'],
        test=tests(save("staffPublicId", ".user.publicId"), save("staffTempPassword", ".temporaryPassword"), status=201)),
    req("Danh sách tài khoản nhân viên", "GET", f"{GW}/api/v1/users?type=STAFF&page=0&size=20", test=tests(status=200)),
    req("Chi tiết tài khoản", "GET", f"{GW}/api/v1/users/{{{{staffPublicId}}}}", test=tests(status=200)),
    req("Gán role", "PUT", f"{GW}/api/v1/users/{{{{staffPublicId}}}}/roles", {"roles": ["SHOP_STAFF", "SHOP_MANAGER"]},
        test=tests(status=200), desc="Đổi role xong nhân viên phải đăng nhập lại mới có quyền mới (permission chụp vào token)."),
    req("Khóa tài khoản", "POST", f"{GW}/api/v1/users/{{{{staffPublicId}}}}/disable", test=tests(status=200)),
    req("Mở lại tài khoản", "POST", f"{GW}/api/v1/users/{{{{staffPublicId}}}}/enable", test=tests(status=200)),
    req("Mở khóa (sai mật khẩu 5 lần)", "POST", f"{GW}/api/v1/users/{{{{staffPublicId}}}}/unlock", test=tests(status=200)),
    req("Đặt lại mật khẩu (trả mật khẩu tạm mới)", "POST", f"{GW}/api/v1/users/{{{{staffPublicId}}}}/reset-password",
        test=tests(save("staffTempPassword", ".temporaryPassword"))),
], desc="Cần adminToken (chạy '1. Đăng nhập ADMIN' trước).")

catalog_folder = folder("3. Danh mục hoa", [
    req("Tạo hoa (cần flower:write)", "POST", f"{GW}/api/v1/flowers",
        {"sku": "{{sku}}", "name": "Bó hồng đỏ 10 bông", "description": "Hồng Đà Lạt", "category": "ROSE",
         "unitPrice": 350000, "currency": "VND"},
        pre=['pm.collectionVariables.set("sku", "ROSE-PM-" + Date.now().toString().slice(-8));'],
        test=tests(save("flowerId", ".id"), save("flowerVersion", ".version"), status=201),
        desc="Mỗi lần chạy sinh SKU mới (ROSE-PM-xxxxxxxx) để không trùng."),
    req("Danh sách hoa đang bán (public)", "GET", f"{GW}/api/v1/flowers?page=0&size=20", auth="none", test=tests(status=200)),
    req("Chi tiết theo id (public)", "GET", f"{GW}/api/v1/flowers/{{{{flowerId}}}}", auth="none",
        test=tests(save("flowerVersion", ".version"), status=200)),
    req("Chi tiết theo SKU (public)", "GET", f"{GW}/api/v1/flowers/sku/{{{{sku}}}}", auth="none", test=tests(status=200)),
    req("Sửa hoa (phải gửi version vừa đọc)", "PUT", f"{GW}/api/v1/flowers/{{{{flowerId}}}}",
        {"name": "Bó hồng đỏ 12 bông", "description": "Hồng Đà Lạt", "category": "ROSE", "unitPrice": 400000,
         "version": "{{flowerVersion}}"},
        test=tests(save("flowerVersion", ".version"), status=200),
        desc="Gửi lại request này lần nữa mà không đọc version mới: COM-409-001 (optimistic lock).\n"
             "Đơn hàng đã đặt giữ nguyên giá cũ (bản chụp)."),
    req("Ngừng kinh doanh (soft delete)", "DELETE", f"{GW}/api/v1/flowers/{{{{flowerId}}}}", test=tests(status=200),
        desc="Chạy SAU khi thử xong tồn kho và đơn hàng: hoa ngừng bán thì không nhập lô / đặt đơn được nữa."),
], desc="Cần adminToken cho tạo/sửa/ngừng bán. Xem thì public.")

customer_staff_folder = folder("4. Khách hàng (API nhân viên)", [
    req("Tạo hồ sơ khách", "POST", f"{GW}/api/v1/customers",
        {"fullName": "Nguyễn Thị Lan", "phone": "{{staffCustomerPhone}}", "email": None, "dateOfBirth": "1995-03-20"},
        pre=['pm.collectionVariables.set("staffCustomerPhone", "09" + Math.floor(10000000 + Math.random() * 89999999));'],
        test=tests(save("customerId", ".id"), save("customerVersion", ".version"), status=201),
        desc="Trả customerCode dạng KH_CN_0000001."),
    req("Tìm theo SĐT (so khớp chính xác)", "GET", f"{GW}/api/v1/customers?phone={{{{staffCustomerPhone}}}}",
        test=tests(status=200), desc="Danh sách trả SĐT/email đã che."),
    req("Chi tiết khách", "GET", f"{GW}/api/v1/customers/{{{{customerId}}}}", test=tests(save("customerVersion", ".version"), status=200)),
    req("Sửa khách (gửi version)", "PUT", f"{GW}/api/v1/customers/{{{{customerId}}}}",
        {"fullName": "Nguyễn Thị Lan Anh", "email": "lan.{{staffCustomerPhone}}@example.com", "dateOfBirth": "1995-03-20",
         "version": "{{customerVersion}}"}, test=tests(save("customerVersion", ".version"), status=200)),
    req("Thêm địa chỉ người nhận", "POST", f"{GW}/api/v1/customers/{{{{customerId}}}}/addresses",
        {"recipientName": "Trần Văn Bình", "recipientPhone": "0987654321", "addressLine": "12 Lý Thường Kiệt",
         "ward": "Phường Cửa Nam", "province": "Hà Nội", "note": "Gọi trước khi giao"},
        test=tests(save("addressId", ".id"), save("addressVersion", ".version"), status=201),
        desc="Địa chỉ đầu tiên tự thành mặc định."),
    req("Sổ địa chỉ của khách", "GET", f"{GW}/api/v1/customers/{{{{customerId}}}}/addresses", test=tests(status=200)),
    req("Sửa địa chỉ (gửi version)", "PUT", f"{GW}/api/v1/customers/{{{{customerId}}}}/addresses/{{{{addressId}}}}",
        {"recipientName": "Trần Văn Bình", "recipientPhone": "0987654321", "addressLine": "14 Lý Thường Kiệt",
         "ward": "Phường Cửa Nam", "province": "Hà Nội", "note": None, "version": "{{addressVersion}}"},
        test=tests(save("addressVersion", ".version"), status=200)),
    req("Đặt làm địa chỉ mặc định", "PUT", f"{GW}/api/v1/customers/{{{{customerId}}}}/addresses/{{{{addressId}}}}/default",
        test=tests(status=200)),
    req("Xóa địa chỉ", "DELETE", f"{GW}/api/v1/customers/{{{{customerId}}}}/addresses/{{{{addressId}}}}", test=tests(status=200)),
    req("Ngừng hoạt động khách", "DELETE", f"{GW}/api/v1/customers/{{{{customerId}}}}", test=tests(status=200)),
], desc="Cần adminToken (hoặc token nhân viên có customer:*).")

customer_self_folder = folder("5. Khách tự đăng ký & /me", [
    req("Khách tự đăng ký", "POST", f"{GW}/api/v1/auth/register",
        {"phone": "{{customerPhone}}", "password": "{{customerPassword}}", "fullName": "Lê Minh Anh",
         "email": None, "dateOfBirth": "1998-07-01"},
        auth="none",
        pre=['pm.collectionVariables.set("customerPhone", "09" + Math.floor(10000000 + Math.random() * 89999999));'],
        test=tests(status=201), desc="Saga 2 service: tài khoản ở identity + hồ sơ ở customer. Mỗi lần chạy sinh SĐT mới."),
    req("Khách đăng nhập (bằng SĐT)", "POST", f"{GW}/api/v1/auth/login",
        {"loginId": "{{customerPhone}}", "password": "{{customerPassword}}"}, auth="none",
        test=tests(save("customerToken", ".accessToken"), status=200)),
    req("Hồ sơ của tôi", "GET", f"{GW}/api/v1/customers/me", auth="customerToken",
        test=tests(save("myProfileVersion", ".version"), status=200)),
    req("Sửa hồ sơ của tôi", "PUT", f"{GW}/api/v1/customers/me",
        {"fullName": "Lê Minh Anh", "email": "minh.anh.{{customerPhone}}@example.com", "dateOfBirth": "1998-07-01",
         "version": "{{myProfileVersion}}"}, auth="customerToken", test=tests(status=200)),
    req("Thêm địa chỉ của tôi", "POST", f"{GW}/api/v1/customers/me/addresses",
        {"recipientName": "Trần Văn Bình", "recipientPhone": "0987654321", "addressLine": "12 Lý Thường Kiệt",
         "ward": "Phường Cửa Nam", "province": "Hà Nội", "note": "Giao giờ hành chính"},
        auth="customerToken", test=tests(save("myAddressId", ".id"), save("myAddressVersion", ".version"), status=201),
        desc="Địa chỉ này dùng để đặt đơn ở mục 7."),
    req("Sổ địa chỉ của tôi", "GET", f"{GW}/api/v1/customers/me/addresses", auth="customerToken", test=tests(status=200)),
    req("Sửa địa chỉ của tôi", "PUT", f"{GW}/api/v1/customers/me/addresses/{{{{myAddressId}}}}",
        {"recipientName": "Trần Văn Bình", "recipientPhone": "0987654321", "addressLine": "12 Lý Thường Kiệt",
         "ward": "Phường Cửa Nam", "province": "Hà Nội", "note": "Gọi trước 15 phút", "version": "{{myAddressVersion}}"},
        auth="customerToken", test=tests(status=200)),
    req("Đặt địa chỉ mặc định", "PUT", f"{GW}/api/v1/customers/me/addresses/{{{{myAddressId}}}}/default",
        auth="customerToken", test=tests(status=200)),
    req("Khách gọi API nhân viên → 403", "GET", f"{GW}/api/v1/customers", auth="customerToken",
        test=['pm.test("HTTP 403", () => pm.response.to.have.status(403));',
              'pm.test("COM-403-001", () => pm.expect(pm.response.json().code).to.eql("COM-403-001"));']),
], desc="Khách chỉ dùng API /me: id lấy từ token, không truyền id.")

LOT_PRE = ['const d = new Date(Date.now() + 4 * 24 * 3600 * 1000);',
           'pm.collectionVariables.set("lotExpiresAt", d.toISOString().replace(/\\.\\d{3}Z$/, "Z"));']
inventory_folder = folder("6. Tồn kho", [
    req("Nhập lô (hỏi catalog SKU còn bán)", "POST", f"{GW}/api/v1/inventory/lots",
        {"sku": "{{sku}}", "quantity": 20, "unitCost": 120000, "currency": "VND", "expiresAt": "{{lotExpiresAt}}",
         "supplier": "Vườn Đà Lạt"},
        pre=LOT_PRE, test=tests(save("lotCode", ".lotCode"), status=201),
        desc="Dùng SKU vừa tạo ở mục 3. Hạn dùng = 4 ngày sau. SKU không có trong catalog: INV-422-001."),
    req("Tồn kho theo SKU", "GET", f"{GW}/api/v1/inventory/stock?sku={{{{sku}}}}", test=tests(status=200),
        desc="sellable: còn bán được; expired: còn trong lô đã hết hạn (cần ghi hủy)."),
    req("Còn hàng không (public)", "GET", f"{GW}/api/v1/inventory/availability?sku={{{{sku}}}}", auth="none",
        test=tests(status=200), desc="Cho khách xem: chỉ còn/hết, không lộ số lượng."),
    req("Danh sách lô (sắp hết hạn lên đầu)", "GET", f"{GW}/api/v1/inventory/lots?sku={{{{sku}}}}&includeEmpty=false&page=0&size=20",
        test=tests(status=200)),
    req("Chi tiết lô", "GET", f"{GW}/api/v1/inventory/lots/{{{{lotCode}}}}", test=tests(status=200)),
    req("Sổ cái của lô", "GET", f"{GW}/api/v1/inventory/lots/{{{{lotCode}}}}/movements", test=tests(status=200),
        desc="RECEIVE / RESERVE / RELEASE / EXPIRE_HOLD / WASTE, kèm ai làm (nhân viên hoặc order-service)."),
    req("Ghi nhận hoa hỏng", "POST", f"{GW}/api/v1/inventory/lots/{{{{lotCode}}}}/waste",
        {"quantity": 1, "reason": "DAMAGED", "note": "dập khi vận chuyển"}, test=tests(status=200),
        desc="reason: EXPIRED | DAMAGED | OTHER. Hủy nhiều hơn số còn: INV-422-003."),
], desc="Cần adminToken (inventory:read / inventory:write).")

ORDER_BODY = {"addressId": "{{myAddressId}}", "items": [{"sku": "{{sku}}", "quantity": 2}],
              "deliveryDate": "{{deliveryDate}}", "deliverySlot": "AFTERNOON", "cardMessage": "Chúc mừng sinh nhật!"}
ORDER_PRE = [
    '// Ngày mai theo giờ Việt Nam (UTC+7)',
    'const vn = new Date(Date.now() + 7 * 3600 * 1000 + 24 * 3600 * 1000);',
    'pm.collectionVariables.set("deliveryDate", vn.toISOString().slice(0, 10));',
    '// Mỗi lần bấm Send là một đơn mới: key mới. Muốn thử gửi lại, dùng request "Gửi lại cùng key"',
    'pm.collectionVariables.set("idempotencyKey", pm.variables.replaceIn("{{$guid}}"));',
]
order_customer_folder = folder("7. Đơn hàng (khách)", [
    req("Đặt đơn", "POST", f"{GW}/api/v1/orders/me", ORDER_BODY, auth="customerToken",
        headers={"Idempotency-Key": "{{idempotencyKey}}"}, pre=ORDER_PRE,
        test=tests(save("orderCode", ".orderCode"),
                   'pm.test("PENDING", () => pm.expect(pm.response.json().data.status).to.eql("PENDING"));', status=201),
        desc="Cần: customerToken + myAddressId (mục 5), sku có hàng (mục 3, 6).\n"
             "Giá lấy từ catalog phía server (body không có giá). Giữ hàng FEFO tới hết khung giờ giao.\n"
             "deliverySlot: MORNING (8-12h) | AFTERNOON (13-17h) | EVENING (18-21h)."),
    req("Gửi lại cùng Idempotency-Key → 200, cùng đơn", "POST", f"{GW}/api/v1/orders/me", ORDER_BODY,
        auth="customerToken", headers={"Idempotency-Key": "{{idempotencyKey}}"},
        test=tests('pm.test("Cùng mã đơn", () => pm.expect(pm.response.json().data.orderCode).to.eql(pm.collectionVariables.get("orderCode")));',
                   status=200),
        desc="Giả lập khách bấm 'Đặt hàng' hai lần: không tạo đơn thứ hai, không giữ thêm hàng."),
    req("Đơn của tôi", "GET", f"{GW}/api/v1/orders/me?page=0&size=20", auth="customerToken", test=tests(status=200)),
    req("Chi tiết đơn của tôi", "GET", f"{GW}/api/v1/orders/me/{{{{orderCode}}}}", auth="customerToken", test=tests(status=200)),
    req("Đặt đơn thứ hai rồi tự hủy", "POST", f"{GW}/api/v1/orders/me", ORDER_BODY, auth="customerToken",
        headers={"Idempotency-Key": "{{idempotencyKey}}"}, pre=ORDER_PRE,
        test=tests(save("orderToCancel", ".orderCode"), status=201)),
    req("Khách hủy đơn (PENDING / CONFIRMED)", "POST", f"{GW}/api/v1/orders/me/{{{{orderToCancel}}}}/cancel",
        {"reason": "Đặt nhầm ngày"}, auth="customerToken",
        test=tests('pm.test("CANCELLED", () => pm.expect(pm.response.json().data.status).to.eql("CANCELLED"));', status=200),
        desc="Hàng được trả về kho (xem lại '6. Tồn kho / Tồn kho theo SKU')."),
], desc="API của khách: customerId lấy từ token.")

order_staff_folder = folder("8. Đơn hàng (nhân viên)", [
    req("Danh sách đơn chờ xác nhận", "GET", f"{GW}/api/v1/orders?status=PENDING&page=0&size=20", test=tests(status=200)),
    req("Chi tiết đơn", "GET", f"{GW}/api/v1/orders/{{{{orderCode}}}}", test=tests(status=200)),
    req("Xác nhận (đã gọi khách)", "POST", f"{GW}/api/v1/orders/{{{{orderCode}}}}/confirm",
        test=tests('pm.test("CONFIRMED", () => pm.expect(pm.response.json().data.status).to.eql("CONFIRMED"));', status=200),
        desc="Phải xác nhận trong 60 phút, quá hạn đơn tự hủy."),
    req("Bắt đầu cắm hoa", "POST", f"{GW}/api/v1/orders/{{{{orderCode}}}}/prepare", test=tests(status=200),
        desc="Bấm hai lần: ORD-409-003 (không nhảy hai bước). Từ đây không hủy được nữa."),
    req("Giao hàng", "POST", f"{GW}/api/v1/orders/{{{{orderCode}}}}/ship", test=tests(status=200)),
    req("Hoàn tất", "POST", f"{GW}/api/v1/orders/{{{{orderCode}}}}/complete",
        test=tests('pm.test("DELIVERED", () => pm.expect(pm.response.json().data.status).to.eql("DELIVERED"));', status=200)),
    req("Lịch sử trạng thái", "GET", f"{GW}/api/v1/orders/{{{{orderCode}}}}/history", test=tests(status=200),
        desc="Ai chuyển trạng thái, lúc nào (khách, nhân viên, hay 'system' khi job tự hủy)."),
    req("Nhân viên hủy đơn", "POST", f"{GW}/api/v1/orders/{{{{orderCode}}}}/cancel", {"reason": "Hết hoa theo yêu cầu"},
        test=['pm.test("Đơn đã giao thì ORD-409-004", () => pm.expect(pm.response.json().code).to.be.oneOf(["00", "ORD-409-004"]));'],
        desc="Với đơn vừa giao xong ở trên sẽ trả ORD-409-004. Đổi {{orderCode}} sang một đơn PENDING/CONFIRMED để hủy thật."),
], desc="Cần adminToken (order:read / order:manage).")

internal_folder = folder("9. Nội bộ (gọi thẳng service, KHÔNG qua gateway)", [
    req("Xin service token của order-service", "POST", "{{identityUrl}}/internal/v1/service-token",
        {"clientId": "order-service", "clientSecret": "{{orderServiceSecret}}"}, auth="none",
        test=tests(save("serviceToken", ".accessToken"), status=200),
        desc="client_credentials. Secret mặc định là secret LOCAL của profile local (identity + order dùng chung)."),
    req("Giữ hàng (như order-service gọi)", "POST", "{{inventoryUrl}}/internal/v1/reservations",
        {"orderCode": "{{manualOrderCode}}", "items": [{"sku": "{{sku}}", "quantity": 1}], "holdMinutes": 15},
        auth="serviceToken", pre=['pm.collectionVariables.set("manualOrderCode", "PM_" + Date.now());'],
        test=tests(status=201), desc="Gọi lại cùng orderCode: 200 trả phiếu cũ (idempotent)."),
    req("Xem phiếu giữ hàng", "GET", "{{inventoryUrl}}/internal/v1/reservations/{{manualOrderCode}}", auth="serviceToken",
        test=tests(status=200)),
    req("Xác nhận phiếu", "POST", "{{inventoryUrl}}/internal/v1/reservations/{{manualOrderCode}}/confirm",
        auth="serviceToken", test=tests(status=200)),
    req("Nhả phiếu (trả hàng về kho)", "POST", "{{inventoryUrl}}/internal/v1/reservations/{{manualOrderCode}}/release",
        auth="serviceToken", test=tests(status=200)),
    req("/internal qua gateway → bị chặn", "POST", f"{GW}/internal/v1/service-token",
        {"clientId": "order-service", "clientSecret": "{{orderServiceSecret}}"}, auth="adminToken",
        test=['pm.test("Gateway chặn (403)", () => pm.response.to.have.status(403));']),
    req("Token ADMIN không giữ hàng được → 403", "POST", "{{inventoryUrl}}/internal/v1/reservations",
        {"orderCode": "PM_ADMIN_TRY", "items": [{"sku": "{{sku}}", "quantity": 1}]}, auth="adminToken",
        test=['pm.test("HTTP 403", () => pm.response.to.have.status(403));'],
        desc="inventory:reserve chỉ cấp cho service client, không role nào của người có."),
], desc="Chỉ chạy được trên máy dev (./run-local.sh hoặc docker-compose.app.yml) vì gọi thẳng cổng 8083/8084.\n"
        "Môi trường thật các cổng này không mở ra ngoài.")

logout = folder("10. Đăng xuất", [
    req("Đăng xuất ADMIN (thu hồi refresh token)", "POST", f"{GW}/api/v1/auth/logout",
        {"refreshToken": "{{adminRefreshToken}}"}, auth="none", test=tests(status=200),
        desc="Access token vẫn dùng được tới khi hết hạn (tối đa 15 phút): đó là cái giá của JWT stateless."),
])

collection = {
    "info": {
        "_postman_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "flower-shop-postman")),
        "name": "Flower Shop API",
        "description": (
            "Toàn bộ API của Flower Shop qua api-gateway (cổng 8080) và API nội bộ (gọi thẳng service).\n\n"
            "**Cách dùng**\n"
            "1. Bật hệ thống: `./run-local.sh` (hoặc `docker compose -f docker-compose.app.yml up -d --wait`).\n"
            "2. Chạy theo thứ tự thư mục 1 → 10. Token, mã đơn, mã lô... tự lưu vào biến của collection "
            "(tab Variables), request sau dùng tiếp.\n"
            "3. Hoặc chạy cả collection: chuột phải → Run collection.\n\n"
            "**Mật khẩu ADMIN**: DB mới thì chạy 2 request đầu của mục 1 (đổi `FlowerShop2026` → `adminPassword`). "
            "Đã đổi rồi thì bỏ qua, chạy thẳng 'Đăng nhập ADMIN'. Mật khẩu khác thì sửa biến `adminPassword`.\n\n"
            "**docker-compose.app.yml**: biến `orderServiceSecret` phải bằng `ORDER_SERVICE_CLIENT_SECRET` trong `.env`.\n\n"
            "Mọi response có header `X-Correlation-Id`: dùng mã đó tìm log của mọi service liên quan."),
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "auth": bearer("adminToken"),
    "variable": [
        {"key": "gatewayUrl", "value": "http://localhost:8080"},
        {"key": "identityUrl", "value": "http://localhost:8083"},
        {"key": "inventoryUrl", "value": "http://localhost:8084"},
        {"key": "adminUsername", "value": "admin"},
        {"key": "adminInitialPassword", "value": "FlowerShop2026"},
        {"key": "adminPassword", "value": "QuanTri2026x"},
        {"key": "customerPassword", "value": "KhachHang1"},
        {"key": "orderServiceSecret", "value": "order-service-local-secret-0123456789"},
    ] + [{"key": k, "value": ""} for k in [
        "adminMustChangePassword", "adminToken", "adminRefreshToken", "customerToken", "serviceToken", "staffUsername", "staffPublicId",
        "staffTempPassword", "sku", "flowerId", "flowerVersion", "staffCustomerPhone", "customerId", "customerVersion",
        "addressId", "addressVersion", "customerPhone", "myProfileVersion", "myAddressId", "myAddressVersion",
        "lotExpiresAt", "lotCode", "deliveryDate", "idempotencyKey", "orderCode", "orderToCancel", "manualOrderCode"]],
    "item": [auth_folder, users_folder, catalog_folder, customer_staff_folder, customer_self_folder, inventory_folder,
             order_customer_folder, order_staff_folder, internal_folder, logout],
}

# Thứ tự hợp lý khi chạy cả collection: mục 3 "Ngừng kinh doanh" phải chạy SAU tồn kho + đơn hàng
deactivate = catalog_folder["item"].pop()
logout["item"].insert(0, deactivate)
deactivate["name"] = "Ngừng kinh doanh hoa vừa tạo (dọn dẹp)"

with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(collection, f, ensure_ascii=False, indent=2)
    f.write("\n")
count = sum(len(fo["item"]) for fo in collection["item"])
print(f"{count} requests trong {len(collection['item'])} thư mục -> {sys.argv[1]}")
