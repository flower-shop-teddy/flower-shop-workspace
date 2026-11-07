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

```
flower-shop/                 ← repo flower-shop-workspace
├── pom.xml                  Aggregator CHỈ cho local: build mọi repo một lần, mở chung trong IntelliJ
├── clone-all.sh             Clone các repo bên dưới vào đúng chỗ
├── run-local.sh             Chạy cả hệ thống bằng một lệnh
├── docker-compose.yml       Hạ tầng local (Postgres)
├── .env.example             Mẫu biến môi trường -> copy thành .env
├── infra/postgres/init/     Tạo database + user riêng cho từng service
├── platform/                ← repo riêng (bị .gitignore của workspace bỏ qua)
│   ├── pom.xml              flower-shop-parent: version thư viện, plugin dùng chung
│   └── common-lib/          Response chuẩn, mã lỗi, xử lý lỗi, correlation id, che dữ liệu
├── discovery-server/        ← repo riêng
├── api-gateway/             ← repo riêng
└── catalog-service/         ← repo riêng
    └── src/main/java/com/flowershop/catalog/
        ├── config/          Cấu hình audit (created_by, updated_by)
        ├── domain/          Entity + enum
        ├── dto/             Request/Response (không lộ entity ra ngoài)
        ├── error/           Mã lỗi riêng của service (CAT-xxx-xxx)
        ├── mapper/
        ├── repository/
        ├── service/         Logic nghiệp vụ + transaction
        └── web/             Controller /api/v1/...
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
./run-local.sh              # bật Postgres -> build -> discovery -> catalog + gateway, đợi tới khi gọi API được
./run-local.sh --no-build   # code không đổi thì bỏ qua build cho nhanh
# Ctrl+C: tắt service theo thứ tự ngược (gateway/catalog trước, discovery sau). Log nằm trong logs/
```

**IntelliJ:** chọn cấu hình **All Services** ở góc trên bên phải rồi bấm Run hoặc Debug (file trong `.run/`).
Compound bật 3 service cùng lúc. Eureka client tự thử lại nên vẫn chạy đúng, chỉ mất khoảng 30–40 giây để gateway thấy catalog.

### Cách thủ công

**Bước 3: Chạy service theo đúng thứ tự** (trong IntelliJ, chạy class `main` của từng module)

1. `DiscoveryServerApplication`, đợi mở được http://localhost:8761
2. `CatalogServiceApplication`, nhớ đặt **Active profiles: `local`** trong Run Configuration
3. `ApiGatewayApplication`

Sau 10–30 giây, trang Eureka sẽ hiện `CATALOG-SERVICE` và `API-GATEWAY`.

**Mẹo:** mở tab **Services** (Alt+8) trong IntelliJ để quản lý cả 3 service một chỗ.

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

Thử gửi lại lệnh sửa với `"version":0` lần nữa: bạn sẽ nhận lỗi `COM-409-001` vì version đã tăng lên 1.

Mỗi response có header `X-Correlation-Id`. Lấy mã đó tìm trong log của gateway và catalog-service sẽ thấy cùng một request.

Swagger UI (chỉ profile local): http://localhost:8081/swagger-ui.html

## 6. Debug

- Chạy `CatalogServiceApplication` bằng nút **Debug** thay vì Run, đặt breakpoint trong `FlowerService`.
- Gọi API qua gateway như bình thường: request vẫn đi qua Eureka và dừng đúng breakpoint.

## 7. Chạy test

```bash
mvn -pl catalog-service test     # cần Docker đang chạy (Testcontainers tự bật Postgres)
```

## 8. Lỗi thường gặp

- `release version 21 not supported`: Maven đang chạy bằng JDK < 21, xem mục 3. Lưu ý `~/.mavenrc` có thể ghi đè `JAVA_HOME`.
- Test báo `Could not find a valid Docker environment`: Docker Desktop chưa chạy, hoặc Testcontainers quá cũ so với Docker Engine (đã ghim `testcontainers.version` trong pom gốc).
- `docker compose up` lỗi thiếu mật khẩu postgres: chưa tạo file `.env` từ `.env.example`.
- `Could not resolve placeholder 'DB_URL'`: quên đặt profile `local` cho catalog-service.
- `Schema-validation: missing table [flower]`: Flyway chưa chạy hoặc kết nối nhầm database.
- Sửa file `01-create-databases.sql` nhưng không thấy tác dụng: script chỉ chạy khi volume trống, cần `docker compose down -v` (sẽ XÓA dữ liệu local).
- Gateway trả 503: catalog-service chưa đăng ký xong lên Eureka, đợi thêm vài giây.

## 9. Làm việc với nhiều repo

- Mỗi thư mục `platform/`, `discovery-server/`... có `git status`, `git commit`, `git push` riêng. Commit ở thư mục gốc chỉ chứa file của workspace.
- Service tìm parent ở `../platform/pom.xml` trước. Vì vậy trong workspace, sửa `platform` là service thấy ngay, không cần publish.
- Khi build một repo service đứng riêng (CI, máy khác), parent được lấy từ `~/.m2` hoặc GitHub Packages.
- Push lên `dev` của `flower-shop-platform` sẽ tự publish parent + `common-lib` lên GitHub Packages (workflow `publish.yml`).

## 10. Giai đoạn tiếp theo

**Giai đoạn 2:** thêm `inventory-service` (tồn kho theo lô, xuất FEFO) và `order-service` gọi đồng bộ qua OpenFeign, kèm Resilience4j (timeout, retry, circuit breaker). Đơn hàng lưu **snapshot** giá tại thời điểm đặt.
