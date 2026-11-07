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

```
flower-shop/                 ← repo flower-shop-workspace
├── pom.xml                  Aggregator CHỈ cho local: build mọi repo một lần, mở chung trong IntelliJ
├── clone-all.sh             Clone các repo bên dưới vào đúng chỗ (+ cài hook commit)
├── install-hooks.sh         Bật hook kiểm tra commit message cho mọi repo
├── set-platform-version.sh  Đổi version platform + parent của mọi service cùng lúc
├── githooks/commit-msg      Hook Conventional Commits
├── run-local.sh             Chạy cả hệ thống bằng một lệnh
├── docker-compose.yml       Hạ tầng local (Postgres)
├── .env.example             Mẫu biến môi trường -> copy thành .env
├── infra/postgres/init/     Tạo database + user riêng cho từng service
├── platform/                ← repo riêng (bị .gitignore của workspace bỏ qua)
│   ├── pom.xml              flower-shop-parent: version thư viện, plugin dùng chung
│   └── common-lib/          Response chuẩn, mã lỗi, xử lý lỗi, correlation id, che dữ liệu
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
└── customer-service/        ← repo riêng, cùng cấu trúc package (com.flowershop.customer)
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
./run-local.sh              # bật Postgres -> build -> discovery -> catalog + customer + gateway, đợi tới khi gọi API được
./run-local.sh --no-build   # code không đổi thì bỏ qua build cho nhanh
# Ctrl+C: tắt service theo thứ tự ngược (gateway/catalog/customer trước, discovery sau). Log nằm trong logs/
```

**IntelliJ:** chọn cấu hình **All Services** ở góc trên bên phải rồi bấm Run hoặc Debug (file trong `.run/`).
Compound bật 4 service cùng lúc. Eureka client tự thử lại nên vẫn chạy đúng, chỉ mất khoảng 30–40 giây để gateway thấy catalog và customer.

### Cách thủ công

**Bước 3: Chạy service theo đúng thứ tự** (trong IntelliJ, chạy class `main` của từng module)

1. `DiscoveryServerApplication`, đợi mở được http://localhost:8761
2. `CatalogServiceApplication`, nhớ đặt **Active profiles: `local`** trong Run Configuration
3. `ApiGatewayApplication`
4. `CustomerServiceApplication`, cũng đặt **Active profiles: `local`**

Sau 10–30 giây, trang Eureka sẽ hiện `CATALOG-SERVICE`, `CUSTOMER-SERVICE` và `API-GATEWAY`.

**Mẹo:** mở tab **Services** (Alt+8) trong IntelliJ để quản lý cả 4 service một chỗ.

## 5. Gọi thử API (qua gateway, cổng 8080)

```bash
# Tạo hoa
curl -i -X POST http://localhost:8080/api/v1/flowers \
  -H "Content-Type: application/json" \
  -d '{"sku":"ROSE-RED-10","name":"Bó hồng đỏ 10 bông","category":"ROSE","unitPrice":350000,"currency":"VND"}'

# Danh sách
curl "http://localhost:8080/api/v1/flowers?page=0&size=20"

# Xem chi tiết
curl http://localhost:8080/api/v1/flowers/1

# Sửa (phải gửi kèm version vừa đọc được)
curl -X PUT http://localhost:8080/api/v1/flowers/1 \
  -H "Content-Type: application/json" \
  -d '{"name":"Bó hồng đỏ 12 bông","category":"ROSE","unitPrice":400000,"version":0}'

# Ngừng kinh doanh
curl -X DELETE http://localhost:8080/api/v1/flowers/1
```

Khách hàng và sổ địa chỉ:

```bash
# Tạo khách hàng -> nhận customerCode dạng KH_CN_0000001
curl -X POST http://localhost:8080/api/v1/customers \
  -H "Content-Type: application/json" \
  -d '{"fullName":"Nguyễn Thị Lan","phone":"0912345678","email":"lan@gmail.com","dateOfBirth":"1995-03-20"}'

# Tìm theo SĐT (so khớp chính xác). Danh sách trả SĐT/email đã che
curl "http://localhost:8080/api/v1/customers?phone=0912345678"

# Thêm địa chỉ người nhận (địa chỉ đầu tiên tự thành mặc định)
curl -X POST http://localhost:8080/api/v1/customers/1/addresses \
  -H "Content-Type: application/json" \
  -d '{"recipientName":"Trần Văn Bình","recipientPhone":"0987654321","addressLine":"12 Lý Thường Kiệt","ward":"Phường Cửa Nam","province":"Hà Nội"}'

# Xem sổ địa chỉ / đặt địa chỉ 2 làm mặc định
curl http://localhost:8080/api/v1/customers/1/addresses
curl -X PUT http://localhost:8080/api/v1/customers/1/addresses/2/default
```

Thử gửi lại lệnh sửa với `"version":0` lần nữa: bạn sẽ nhận lỗi `COM-409-001` vì version đã tăng lên 1.

Mỗi response có header `X-Correlation-Id`. Lấy mã đó tìm trong log của gateway và catalog-service sẽ thấy cùng một request.

Swagger UI (chỉ profile local): http://localhost:8081/swagger-ui.html (catalog), http://localhost:8082/swagger-ui.html (customer)

## 6. Debug

- Chạy `CatalogServiceApplication` bằng nút **Debug** thay vì Run, đặt breakpoint trong `FlowerService`.
- Gọi API qua gateway như bình thường: request vẫn đi qua Eureka và dừng đúng breakpoint.

## 7. Chạy test

```bash
mvn -pl catalog-service test     # cần Docker đang chạy (Testcontainers tự bật Postgres)
mvn -pl customer-service test
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

## 9. Làm việc với nhiều repo

- Mỗi thư mục `platform/`, `discovery-server/`... có `git status`, `git commit`, `git push` riêng. Commit ở thư mục gốc chỉ chứa file của workspace.
- Service tìm parent ở `../platform/pom.xml` trước. Vì vậy trong workspace, sửa `platform` là service thấy ngay, không cần publish.
- Khi build một repo service đứng riêng (CI, máy khác), parent được lấy từ `~/.m2` hoặc GitHub Packages.
- Push lên `dev` của `flower-shop-platform` sẽ tự publish parent + `common-lib` lên GitHub Packages (workflow `publish.yml`).

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
5. Thứ tự: platform → discovery-server → catalog-service → customer-service → api-gateway.

### Các bước release

```bash
# 1. Platform
gh pr create -R flower-shop-teddy/flower-shop-platform -B production -H dev --fill
#    đợi check xanh rồi Merge (chọn "Create a merge commit")

# 2. Từng service
gh pr create -R flower-shop-teddy/flower-shop-catalog-service -B production -H dev --fill
#    Merge → ghcr.io/flower-shop-teddy/flower-shop-catalog-service:X.Y.Z

# 3. Tăng version trên dev cho vòng sau (chọn version theo SemVer)
./set-platform-version.sh 0.2.0-SNAPSHOT        # platform + parent ở 4 service (chỉ khi platform có thay đổi)
cd catalog-service && mvn -q versions:set -DnewVersion=0.2.0-SNAPSHOT -DgenerateBackupPoms=false
git commit -am "build: bắt đầu phát triển 0.2.0" && git push
```

**SemVer:** sửa lỗi → `0.1.1`; thêm tính năng tương thích → `0.2.0`; phá vỡ tương thích → `1.0.0`.

### Chạy image đã release

Chạy cả hệ thống từ image trên GHCR, không cần code, không cần build (image đang public nên không phải đăng nhập):

```bash
docker compose -f docker-compose.app.yml up -d --wait   # postgres -> discovery -> catalog -> gateway
docker compose -f docker-compose.app.yml logs -f        # xem log
docker compose -f docker-compose.app.yml down           # tắt theo thứ tự ngược (dữ liệu DB vẫn giữ trong volume)
```

- Thứ tự bật do `depends_on` + `condition: service_healthy` quyết định: service chỉ bật khi service nó cần đã healthy.
- Chạy version khác: đặt `DISCOVERY_VERSION`, `CATALOG_VERSION`, `GATEWAY_VERSION` trong `.env` (mặc định `0.1.0`).
- Dùng chung cổng với `./run-local.sh`: chỉ bật một trong hai.

## 12. Giai đoạn tiếp theo

**Giai đoạn 2:** thêm `inventory-service` (tồn kho theo lô, xuất FEFO) và `order-service` gọi đồng bộ qua OpenFeign, kèm Resilience4j (timeout, retry, circuit breaker). Đơn hàng lưu **snapshot** giá tại thời điểm đặt.
