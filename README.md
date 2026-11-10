# Flower Shop Microservice — Giai đoạn 1 (chuẩn ngân hàng)

Java 21 · Spring Boot 3.5 · Spring Cloud 2025.0 · PostgreSQL 16 · Flyway · Eureka · Spring Cloud Gateway

## 1. Cấu trúc

Mỗi phần là **một repo riêng** trong GitHub org [`flower-shop-teddy`](https://github.com/flower-shop-teddy) (polyrepo).
Repo này (`flower-shop-workspace`) gom chúng lại để chạy và debug ở local.

| Repo | Thư mục local | Nội dung |
|---|---|---|
| `flower-shop-workspace` | `./` | Hạ tầng local, script chạy, aggregator pom cho IntelliJ |
| `flower-shop-platform` | `platform/` | Parent POM (version tập trung) + `common-lib` |
| `flower-shop-discovery-server` | `discovery-server/` | Eureka :8761 |
| `flower-shop-api-gateway` | `api-gateway/` | Cửa vào duy nhất :8080 |
| `flower-shop-catalog-service` | `catalog-service/` | Danh mục hoa :8081 |
| `flower-shop-customer-service` | `customer-service/` | Khách hàng + sổ địa chỉ :8082 |
| `flower-shop-identity-service` | `identity-service/` | Đăng nhập + phân quyền (JWT, RBAC) :8083 |
| `flower-shop-inventory-service` | `inventory-service/` | Tồn kho theo lô, xuất FEFO, giữ hàng cho đơn :8084 |

```
flower-shop/                 ← repo flower-shop-workspace
├── pom.xml                  Aggregator CHỈ cho local: build mọi repo một lần, mở chung trong IntelliJ
├── clone-all.sh             Clone các repo bên dưới vào đúng chỗ (+ cài hook commit)
├── install-hooks.sh         Bật hook kiểm tra commit message cho mọi repo
├── set-platform-version.sh  Đổi version platform + parent của mọi service cùng lúc
├── create-repo.sh           Tạo repo GitHub cho service mới, cấu hình giống repo có sẵn
├── githooks/commit-msg      Hook Conventional Commits
├── run-local.sh             Chạy cả hệ thống bằng một lệnh
├── docker-compose.yml       Hạ tầng local (Postgres)
├── .env.example             Mẫu biến môi trường -> copy thành .env
├── infra/postgres/init/     Tạo database + user riêng cho từng service
├── platform/                ← repo riêng (bị .gitignore của workspace bỏ qua)
│   ├── pom.xml              flower-shop-parent: version thư viện, plugin dùng chung
│   └── common-lib/          Response chuẩn, mã lỗi, xử lý lỗi, correlation id, che dữ liệu, mảnh security dùng chung
├── discovery-server/        ← repo riêng
├── api-gateway/             ← repo riêng
├── catalog-service/         ← repo riêng
    └── src/main/java/com/flowershop/catalog/
        ├── config/          Cấu hình audit (created_by, updated_by)
        ├── domain/          Entity + enum
        ├── dto/             Request/Response (không lộ entity ra ngoài)
        ├── error/           Mã lỗi riêng của service (CAT-xxx-xxx)
        ├── mapper/
        ├── repository/
        ├── service/         Logic nghiệp vụ + transaction
        └── web/             Controller /api/v1/...
├── customer-service/        ← repo riêng, cùng cấu trúc package (com.flowershop.customer)
├── identity-service/        ← repo riêng: tài khoản, role/permission, ký JWT, JWKS (com.flowershop.identity)
└── inventory-service/       ← repo riêng: lô hàng, giữ hàng, sổ cái kho (com.flowershop.inventory)
```

## 2. Chuẩn ngân hàng đã áp dụng ở giai đoạn này

| Nguyên tắc | Ở đâu trong code |
|---|---|
| Tiền dùng `BigDecimal` + `NUMERIC(19,4)`, có mã tiền tệ | `Flower.unitPrice`, `V1__create_flower_table.sql` |
| DB chỉ đổi qua migration, Hibernate chỉ `validate` | `db/migration/`, `ddl-auto: validate` |
| Mỗi service một DB + một user riêng | `infra/postgres/init/01-create-databases.sql` |
| Không có mật khẩu trong `application.yml` | `${DB_PASSWORD}`, file `.env` bị gitignore |
| Response và mã lỗi chuẩn hóa (`00` = thành công) | `ApiResponse`, `ErrorCode`, `CatalogErrorCode` |
| Không lộ stack trace / SQL ra client | `GlobalExceptionHandler` |
| Correlation ID xuyên suốt + chống log injection | `CorrelationIdGlobalFilter`, `CorrelationIdFilter` |
| Audit: ai tạo/sửa, lúc nào | `AuditConfig`, các cột `created_by`, `updated_at`... |
| Optimistic lock chống ghi đè khi sửa đồng thời | `@Version`, `UpdateFlowerRequest.version` |
| Ràng buộc ở cả code lẫn DB (UNIQUE, CHECK) | `FlowerService.create`, file migration |
| Soft delete, không xóa cứng | `FlowerStatus.INACTIVE` |
| API có version, giới hạn page size | `/api/v1/...`, `MAX_PAGE_SIZE = 100` |
| Swagger tắt mặc định, chỉ bật ở local | `application.yml` / `application-local.yml` |
| Test với DB thật, không dùng H2 | `FlowerApiIntegrationTest` (Testcontainers) |
| Lưu thời gian theo UTC | `hibernate.jdbc.time_zone: UTC`, `TIMESTAMPTZ` |
| PII: danh sách che SĐT/email, log không ghi SĐT đầy đủ | `CustomerSummaryResponse`, `CustomerMapper.maskPhone` |
| Tìm theo SĐT bằng so khớp chính xác, không `LIKE` (chống dò dữ liệu) | `CustomerRepository.findByStatusAndPhone` |
| Đọc/sửa tài nguyên con luôn kèm id chủ sở hữu, sai chủ trả 404 | `DeliveryAddressRepository.findByIdAndCustomerId` |
| Khóa dòng (`SELECT ... FOR UPDATE`) khi luật nghiệp vụ phụ thuộc nhiều dòng | `CustomerRepository.findByIdForUpdate` |
| Mã nghiệp vụ (kiểu số CIF) tách khỏi id kỹ thuật | `customer_code` `KH_CN_0000001`, `customer_code_seq` |

### Tồn kho

Chi tiết: [inventory-service/README.md](inventory-service/README.md).

| Nguyên tắc | Ở đâu trong code |
|---|---|
| Quản lý theo lô, xuất FEFO, lọc lô còn hạn tới giờ giao | `StockLotRepository.findFefoForUpdate` |
| Khóa lô (`FOR UPDATE`) khi giữ hàng: không bán vượt dù nhiều đơn cùng lúc | `ReservationService.reserve`, test `concurrentReservations_neverOversell` |
| Giữ hàng tất cả hoặc không; khóa theo thứ tự SKU để không deadlock | `ReservationService` |
| Idempotent theo mã đơn (UNIQUE `order_code`) | `stock_reservation`, `ReservationService.reserve` |
| Sổ cái kho chỉ thêm, đối soát được với số lượng lô | `stock_movement`, test `ledger_alwaysReconcilesWithLotQuantities` |
| Job nhiều instance an toàn (`FOR UPDATE SKIP LOCKED`) | `StockReservationRepository.findOverdueForUpdate` |
| Không gọi service khác trong lúc giữ transaction DB | `LotService.receive` |

### Đăng nhập và phân quyền

Chi tiết và lý do từng quyết định: [identity-service/README.md](identity-service/README.md).

| Nguyên tắc | Ở đâu trong code |
|---|---|
| Một service riêng giữ tài khoản + ký token; service khác chỉ kiểm tra | `identity-service`, `JwtKeyService` |
| JWT ký RS256 (khóa bất đối xứng), public key công khai qua JWKS, có `kid` để xoay khóa | `/.well-known/jwks.json`, `TokenService` |
| Access token ngắn hạn (15'), refresh token opaque lưu hash, xoay vòng + phát hiện dùng lại | `RefreshTokenService`, `AuthService.doRefresh` |
| RBAC user → role → permission; code chỉ kiểm tra permission | `V2__seed_roles_permissions.sql`, `@PreAuthorize("hasAuthority('flower:write')")` |
| Kiểm tra 2 lớp (zero trust): gateway + từng service tự kiểm tra lại JWT | `api-gateway/.../SecurityConfig`, `ApiSecurity.configure` |
| Chặn quyền ở tầng URL trước khi validate body (không lộ luật validate cho người không có quyền) | `SecurityConfig` của catalog/customer |
| Khách chỉ dùng API `/me`, id lấy từ token | `MyProfileController`, `CurrentUser.requireCustomerId` |
| Sai user/sai mật khẩu cùng một mã lỗi; khóa sau 5 lần sai; bộ đếm không bị rollback | `AuthService.doLogin` |
| Nhật ký bảo mật chỉ thêm, có IP + correlation id; `created_by` = `sub` của token | `auth_event`, `JwtAuditorAware` |
| Đăng ký khách trải trên 2 service: saga + bù trừ | `RegistrationService` |
| Service xin token gọi service khác bằng client_credentials, `/internal/**` bị gateway chặn | `ServiceTokenService`, `ServiceTokenClient` |
| Gọi service khác: timeout bắt buộc, tự gắn token + correlation id, mọi lỗi thành `RemoteServiceException` mang mã lỗi gốc | `common-lib/.../client/ServiceClientFactory`, `CustomerClient` |

## 3. Cài đặt

- JDK 21+ (khuyên dùng Eclipse Temurin 21 LTS; JDK 22 cũng build được vì Maven compile với `--release 21`)
- Maven 3.9+ (hoặc dùng Maven có sẵn trong IntelliJ)

**Kiểm tra Maven đang dùng JDK nào** (lỗi `release version 21 not supported` = Maven đang chạy JDK cũ hơn 21):

```bash
mvn -v                                              # xem dòng "Java version"
export JAVA_HOME=$(/usr/libexec/java_home -v 22)    # chỉ áp dụng cho cửa sổ terminal hiện tại
```
- Docker Desktop
- IntelliJ IDEA (bật plugin Lombok, và Settings → Build → Compiler → Annotation Processors → Enable)

## 4. Chạy

**Bước 0: Lấy code các repo** (cần GitHub CLI đã đăng nhập: `gh auth login`)

```bash
git clone https://github.com/flower-shop-teddy/flower-shop-workspace.git flower-shop
cd flower-shop
./clone-all.sh
```

`clone-all.sh` cấu hình xác thực GitHub **riêng trong từng repo** (`.git/config`), không sửa `~/.gitconfig`,
nên không ảnh hưởng các repo khác trên máy.

**Bước 1: Dựng database**

```bash
cp .env.example .env
docker compose up -d
docker compose ps        # đợi postgres ở trạng thái healthy
```

**Bước 2: Build toàn bộ**

```bash
mvn clean install -DskipTests     # lần đầu tải thư viện sẽ hơi lâu
```

### Cách nhanh: chạy cả hệ thống bằng một thao tác

**Terminal (cả VSCode):**

```bash
./run-local.sh              # bật Postgres -> build -> discovery -> identity + catalog + customer + gateway, đợi tới khi gọi API được
./run-local.sh --no-build   # code không đổi thì bỏ qua build cho nhanh
# Ctrl+C: tắt service theo thứ tự ngược (gateway/catalog/customer trước, discovery sau). Log nằm trong logs/
```

**IntelliJ:** chọn cấu hình **All Services** ở góc trên bên phải rồi bấm Run hoặc Debug (file trong `.run/`).
Compound bật 5 service cùng lúc. Eureka client tự thử lại nên vẫn chạy đúng, chỉ mất khoảng 30–40 giây để gateway thấy catalog và customer.

### Cách thủ công

**Bước 3: Chạy service theo đúng thứ tự** (trong IntelliJ, chạy class `main` của từng module)

1. `DiscoveryServerApplication`, đợi mở được http://localhost:8761
2. `CatalogServiceApplication`, nhớ đặt **Active profiles: `local`** trong Run Configuration
3. `ApiGatewayApplication`
4. `CustomerServiceApplication`, cũng đặt **Active profiles: `local`**
5. `IdentityServiceApplication`, cũng đặt **Active profiles: `local`**

Sau 10–30 giây, trang Eureka sẽ hiện `CATALOG-SERVICE`, `CUSTOMER-SERVICE`, `IDENTITY-SERVICE` và `API-GATEWAY`.

**Mẹo:** mở tab **Services** (Alt+8) trong IntelliJ để quản lý cả 5 service một chỗ.

## 5. Gọi thử API (qua gateway, cổng 8080)

Xem danh mục hoa không cần đăng nhập, mọi API còn lại cần `Authorization: Bearer <accessToken>`. Cần `jq` (`brew install jq`).

**Đăng nhập ADMIN** (profile local tự tạo `admin` / `FlowerShop2026`, lần đầu bị buộc đổi mật khẩu):

```bash
# Lần đầu: token chưa có quyền gì, chỉ dùng để đổi mật khẩu
T=$(curl -s -X POST http://localhost:8080/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"loginId":"admin","password":"FlowerShop2026"}' | jq -r .data.accessToken)
curl -X POST http://localhost:8080/api/v1/auth/change-password -H "Authorization: Bearer $T" \
  -H "Content-Type: application/json" -d '{"currentPassword":"FlowerShop2026","newPassword":"QuanTri2026x"}'

# Đăng nhập lại: token có đủ quyền ADMIN (sống 15 phút, hết hạn thì gọi /refresh hoặc đăng nhập lại)
export TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"loginId":"admin","password":"QuanTri2026x"}' | jq -r .data.accessToken)

# Xem bên trong token (phần giữa của JWT là JSON base64): sub, roles, perms, exp...
curl -s http://localhost:8080/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
```

Mỗi lần restart identity-service ở local, khóa ký được sinh lại nên token cũ mất hiệu lực: đăng nhập lại. Mật khẩu đã đổi vẫn giữ (nằm trong DB).

**Hoa:**

```bash
# Tạo hoa (cần flower:write)
curl -i -X POST http://localhost:8080/api/v1/flowers -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sku":"ROSE-RED-10","name":"Bó hồng đỏ 10 bông","category":"ROSE","unitPrice":350000,"currency":"VND"}'

# Danh sách / chi tiết: public
curl "http://localhost:8080/api/v1/flowers?page=0&size=20"
curl http://localhost:8080/api/v1/flowers/1

# Sửa (phải gửi kèm version vừa đọc được)
curl -X PUT http://localhost:8080/api/v1/flowers/1 -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Bó hồng đỏ 12 bông","category":"ROSE","unitPrice":400000,"version":0}'

# Ngừng kinh doanh
curl -X DELETE http://localhost:8080/api/v1/flowers/1 -H "Authorization: Bearer $TOKEN"
```

**Khách hàng (API nhân viên):**

```bash
# Tạo khách hàng -> nhận customerCode dạng KH_CN_0000001
curl -X POST http://localhost:8080/api/v1/customers -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fullName":"Nguyễn Thị Lan","phone":"0912345678","email":"lan@gmail.com","dateOfBirth":"1995-03-20"}'

# Tìm theo SĐT (so khớp chính xác). Danh sách trả SĐT/email đã che
curl "http://localhost:8080/api/v1/customers?phone=0912345678" -H "Authorization: Bearer $TOKEN"

# Thêm địa chỉ người nhận (địa chỉ đầu tiên tự thành mặc định)
curl -X POST http://localhost:8080/api/v1/customers/1/addresses -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"recipientName":"Trần Văn Bình","recipientPhone":"0987654321","addressLine":"12 Lý Thường Kiệt","ward":"Phường Cửa Nam","province":"Hà Nội"}'

# Xem sổ địa chỉ / đặt địa chỉ 2 làm mặc định
curl http://localhost:8080/api/v1/customers/1/addresses -H "Authorization: Bearer $TOKEN"
curl -X PUT http://localhost:8080/api/v1/customers/1/addresses/2/default -H "Authorization: Bearer $TOKEN"
```

**Tồn kho** (SKU phải có trong catalog và đang bán, ví dụ `ROSE-RED-10` tạo ở trên):

```bash
# Nhập lô (cần inventory:write). Thời điểm nhập lấy giờ server, hạn dùng do người nhập khai
curl -X POST http://localhost:8080/api/v1/inventory/lots -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sku":"ROSE-RED-10","quantity":20,"unitCost":120000,"currency":"VND","expiresAt":"2026-12-01T00:00:00Z","supplier":"Vườn Đà Lạt"}'

curl "http://localhost:8080/api/v1/inventory/stock?sku=ROSE-RED-10" -H "Authorization: Bearer $TOKEN"   # {sellable, expired}
curl "http://localhost:8080/api/v1/inventory/lots?sku=ROSE-RED-10" -H "Authorization: Bearer $TOKEN"    # lô sắp hết hạn lên đầu
curl "http://localhost:8080/api/v1/inventory/availability?sku=ROSE-RED-10"                               # public: chỉ còn/hết

# Hoa hỏng: ghi nhận hủy (vào sổ cái, kèm lý do)
curl -X POST http://localhost:8080/api/v1/inventory/lots/LO_0000001/waste -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"quantity":2,"reason":"DAMAGED","note":"dập khi vận chuyển"}'
curl http://localhost:8080/api/v1/inventory/lots/LO_0000001/movements -H "Authorization: Bearer $TOKEN"
```

Giữ hàng (`/internal/v1/reservations`) chỉ dành cho order-service bằng service token, không gọi được qua gateway.

**Khách tự đăng ký và dùng API `/me`:**

```bash
curl -X POST http://localhost:8080/api/v1/auth/register -H "Content-Type: application/json" \
  -d '{"phone":"0901234567","password":"KhachHang1","fullName":"Lê Minh Anh","dateOfBirth":"1998-07-01"}'

CT=$(curl -s -X POST http://localhost:8080/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"loginId":"0901234567","password":"KhachHang1"}' | jq -r .data.accessToken)

curl http://localhost:8080/api/v1/customers/me -H "Authorization: Bearer $CT"            # 200: hồ sơ của mình
curl http://localhost:8080/api/v1/customers/me/addresses -H "Authorization: Bearer $CT"
curl http://localhost:8080/api/v1/customers/1 -H "Authorization: Bearer $CT"             # 403: API của nhân viên
```

**Tạo tài khoản nhân viên** (mật khẩu tạm chỉ hiện một lần, nhân viên phải đổi ở lần đăng nhập đầu):

```bash
curl -X POST http://localhost:8080/api/v1/users -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"username":"lan.nv","roles":["SHOP_STAFF"]}'
curl http://localhost:8080/api/v1/roles -H "Authorization: Bearer $TOKEN"                # role + permission
```

Thử zero trust: `curl -i http://localhost:8082/api/v1/customers` (gọi thẳng service, bỏ qua gateway) vẫn nhận 401.

Thử gửi lại lệnh sửa với `"version":0` lần nữa: bạn sẽ nhận lỗi `COM-409-001` vì version đã tăng lên 1.

Mỗi response có header `X-Correlation-Id`. Lấy mã đó tìm trong log của gateway và catalog-service sẽ thấy cùng một request.

Swagger UI (chỉ profile local): http://localhost:8081/swagger-ui.html (catalog), http://localhost:8082/swagger-ui.html (customer), http://localhost:8083/swagger-ui.html (identity)

## 6. Debug

- Chạy `CatalogServiceApplication` bằng nút **Debug** thay vì Run, đặt breakpoint trong `FlowerService`.
- Gọi API qua gateway như bình thường: request vẫn đi qua Eureka và dừng đúng breakpoint.

## 7. Chạy test

```bash
mvn -pl catalog-service test     # cần Docker đang chạy (Testcontainers tự bật Postgres)
mvn -pl customer-service test
mvn -pl identity-service test
mvn -pl inventory-service test
mvn -pl api-gateway test         # không cần Docker
```

## 8. Lỗi thường gặp

- `release version 21 not supported`: Maven đang chạy bằng JDK < 21, xem mục 3. Lưu ý `~/.mavenrc` có thể ghi đè `JAVA_HOME`.
- Test báo `Could not find a valid Docker environment`: Docker Desktop chưa chạy, hoặc Testcontainers quá cũ so với Docker Engine (đã ghim `testcontainers.version` trong pom gốc).
- `docker compose up` lỗi thiếu mật khẩu postgres: chưa tạo file `.env` từ `.env.example`.
- `Could not resolve placeholder 'DB_URL'`: quên đặt profile `local` cho catalog-service / customer-service.
- `Schema-validation: missing table [flower]`: Flyway chưa chạy hoặc kết nối nhầm database.
- Sửa file `01-create-databases.sql` nhưng không thấy tác dụng: script chỉ chạy khi volume trống, cần `docker compose down -v` (sẽ XÓA dữ liệu local).
- `FATAL: database "customer_db" does not exist`: máy đã có volume Postgres từ trước nên script init không chạy lại. Chạy tay một lần: `docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER"' < infra/postgres/init/02-create-customer-db.sql` (không cần xóa volume).
- Gateway trả 503: service đích chưa đăng ký xong lên Eureka, đợi thêm vài giây.
- `FATAL: database "identity_db" does not exist`: như trên, chạy tay `infra/postgres/init/03-create-identity-db.sql`.
- `FATAL: database "inventory_db" does not exist`: như trên, chạy tay `infra/postgres/init/04-create-inventory-db.sql`.
- `401 COM-401-001` dù vừa đăng nhập: token quá 15 phút, hoặc identity-service vừa restart ở local (khóa ký mới). Đăng nhập lại.
- `403 COM-403-001`: token hợp lệ nhưng thiếu permission. Token của tài khoản mới/được reset mật khẩu không có permission nào cho tới khi đổi mật khẩu. Đổi role xong phải đăng nhập lại mới có quyền mới.
- `423 IDN-423-001`: sai mật khẩu 5 lần, đợi 15 phút hoặc ADMIN gọi `POST /api/v1/users/{publicId}/unlock`.

## 9. Làm việc với nhiều repo

- Mỗi thư mục `platform/`, `discovery-server/`... có `git status`, `git commit`, `git push` riêng. Commit ở thư mục gốc chỉ chứa file của workspace.
- Service tìm parent ở `../platform/pom.xml` trước. Vì vậy trong workspace, sửa `platform` là service thấy ngay, không cần publish.
- Khi build một repo service đứng riêng (CI, máy khác), parent được lấy từ `~/.m2` hoặc GitHub Packages.
- Push lên `dev` của `flower-shop-platform` sẽ tự publish parent + `common-lib` lên GitHub Packages (workflow `publish.yml`).

### Thêm repo service mới

1. Tạo thư mục service (copy cấu trúc từ `catalog-service`), commit lần đầu trên nhánh `dev`.
2. Chạy `./create-repo.sh <thư-mục> "<mô tả>"`. Script tạo repo public `flower-shop-<thư-mục>`, push `dev`, tạo `production` **không kích hoạt release**, rồi copy ruleset từ repo catalog. Chạy lại nhiều lần vẫn an toàn.
3. Thêm thư mục vào `pom.xml`, `clone-all.sh`, `install-hooks.sh`, `set-platform-version.sh`, `run-local.sh`.

Claude Code được phép chạy `./create-repo.sh` mà không phải hỏi (quyền ghi trong `.claude/settings.local.json`, file này không commit).

## 10. Quy tắc commit (Conventional Commits)

```
<type>(<scope>): <mô tả>
```

| type | Khi nào | Ví dụ |
|---|---|---|
| `feat` | Thêm tính năng | `feat(catalog): thêm API tìm hoa theo giá` |
| `fix` | Sửa lỗi | `fix(gateway): sửa lỗi mất header X-Correlation-Id` |
| `docs` | Chỉ sửa tài liệu | `docs: cập nhật hướng dẫn release` |
| `refactor` | Sửa code, không đổi hành vi | `refactor(catalog): tách FlowerMapper` |
| `test` | Thêm/sửa test | `test(catalog): thêm test sửa đồng thời` |
| `perf` / `style` | Hiệu năng / format code | |
| `build` | pom.xml, version, dependency | `build: nâng platform lên 0.2.0-SNAPSHOT` |
| `ci` | GitHub Actions | `ci: thêm bước build Docker image` |
| `chore` / `revert` | Việc vặt / hoàn tác | |

- `scope` (tùy chọn, chữ thường) là phần bị ảnh hưởng: `catalog`, `gateway`, `common`...
- Thêm `!` nếu phá vỡ tương thích: `feat(api)!: đổi format response`.
- **Chặn ở 2 lớp:** hook `githooks/commit-msg` chặn ngay lúc `git commit` (`./install-hooks.sh` hoặc `clone-all.sh` tự cài), và workflow `commit-lint` báo đỏ trên GitHub.
- `dev` cấm force push, nên commit sai đã push lên `dev` **không sửa được**. Vì vậy bắt buộc phải cài hook.

## 11. CI/CD và release

### Luồng tổng quát

```
 push dev ──► CI: build + test (ci / build), commit-lint
          └─► (platform) publish X.Y.Z-SNAPSHOT lên GitHub Packages

 PR dev → production ──► only-from-dev, ci / build, release-check (chạy thử release, không publish)
                         └─ cả 3 xanh mới Merge được (ruleset)

 merge ──► push production ──► release:
            platform: publish flower-shop-parent + common-lib X.Y.Z lên GitHub Packages
            service : push Docker image ghcr.io/flower-shop-teddy/<repo>:X.Y.Z
            cả hai  : tạo tag vX.Y.Z + GitHub Release
```

CI dùng chung nằm ở repo **flower-shop-platform** (`.github/workflows/maven-ci.yml`, `service-release.yml`, `commit-lint.yml`, `.github/actions/setup-maven`). Các service chỉ có vài dòng `uses: ...` gọi tới đó.

### Quy ước version

1. Trên `dev` mọi version là `X.Y.Z-SNAPSHOT`. Service trỏ parent tới **đúng version SNAPSHOT hiện tại** của platform.
2. Version release **không được commit** (production chỉ nhận PR). CI bỏ `-SNAPSHOT` ngay trong máy build, publish, rồi gắn tag `vX.Y.Z`. Commit tại tag vẫn ghi `-SNAPSHOT` trong pom, đó là chủ ý.
3. Release service sẽ tự đổi parent `X.Y.Z-SNAPSHOT` thành `X.Y.Z`, nên **platform phải release trước**.
4. Release xong phải **tăng version trên dev**, nếu không lần release sau bị chặn ("vX.Y.Z đã release").
5. Thứ tự: platform → discovery-server → identity-service → catalog-service → customer-service → inventory-service → api-gateway.

### Các bước release

```bash
# 1. Platform
gh pr create -R flower-shop-teddy/flower-shop-platform -B production -H dev --fill
#    đợi check xanh rồi Merge (chọn "Create a merge commit")

# 2. Từng service
gh pr create -R flower-shop-teddy/flower-shop-catalog-service -B production -H dev --fill
#    Merge → ghcr.io/flower-shop-teddy/flower-shop-catalog-service:X.Y.Z

# 3. Tăng version trên dev cho vòng sau (chọn version theo SemVer)
./set-platform-version.sh 0.2.0-SNAPSHOT        # platform + parent ở 5 service (chỉ khi platform có thay đổi)
cd catalog-service && mvn -q versions:set -DnewVersion=0.2.0-SNAPSHOT -DgenerateBackupPoms=false
git commit -am "build: bắt đầu phát triển 0.2.0" && git push
```

**SemVer:** sửa lỗi → `0.1.1`; thêm tính năng tương thích → `0.2.0`; phá vỡ tương thích → `1.0.0`.

### Chạy image đã release

Chạy cả hệ thống từ image trên GHCR, không cần code, không cần build (image đang public nên không phải đăng nhập).

**Lần đầu:** image chạy profile thật nên identity-service không tự sinh khóa ký JWT. Thêm khóa vào `.env`:

```bash
echo "JWT_PRIVATE_KEY=$(openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 | tr -d '\n')" >> .env
echo "JWT_KEY_ID=dev-$(date +%Y-%m)" >> .env
echo "BOOTSTRAP_ADMIN_USERNAME=admin" >> .env
echo "BOOTSTRAP_ADMIN_PASSWORD=FlowerShop2026" >> .env      # lần đăng nhập đầu bị buộc đổi
```

Khóa nằm trong `.env` nên restart container token cũ vẫn dùng được (khác với `./run-local.sh`).

```bash
docker compose -f docker-compose.app.yml up -d --wait   # postgres -> discovery -> identity -> catalog + customer -> inventory -> gateway
docker compose -f docker-compose.app.yml logs -f        # xem log
docker compose -f docker-compose.app.yml down           # tắt theo thứ tự ngược (dữ liệu DB vẫn giữ trong volume)
```

- Thứ tự bật do `depends_on` + `condition: service_healthy` quyết định: service chỉ bật khi service nó cần đã healthy.
- Trong container, catalog/customer/gateway lấy public key qua `IDENTITY_JWKS_URI=http://identity-service:8083/...` (không phải `localhost`).
- Chạy version khác: đặt `DISCOVERY_VERSION`, `IDENTITY_VERSION`, `CATALOG_VERSION`, `CUSTOMER_VERSION`, `INVENTORY_VERSION`, `GATEWAY_VERSION` trong `.env` (mặc định xem trong `docker-compose.app.yml`).
- Dùng chung cổng với `./run-local.sh`: chỉ bật một trong hai.
- Gọi thử API: như mục 5, đăng nhập bằng `BOOTSTRAP_ADMIN_USERNAME` / `BOOTSTRAP_ADMIN_PASSWORD`.

## 12. Giai đoạn tiếp theo

**Bảo mật, phần còn lại:** OTP khi đăng ký/đổi SĐT, rate limit theo IP ở gateway (Redis), denylist access token theo `jti`, refresh token trong cookie HttpOnly cho web, mTLS giữa các service (client_credentials đã có), private key trong Vault/KMS.

**Giai đoạn 2:** ~~`inventory-service`~~ (đã có), tiếp theo `order-service` gọi đồng bộ qua OpenFeign, kèm Resilience4j (timeout, retry, circuit breaker). Đơn hàng lưu **snapshot** giá tại thời điểm đặt.
