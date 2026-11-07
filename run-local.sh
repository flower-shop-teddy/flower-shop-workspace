#!/usr/bin/env bash
# Chạy TOÀN BỘ hệ thống ở local bằng một lệnh:  ./run-local.sh
# Ctrl+C để tắt tất cả service (Postgres vẫn chạy, tắt bằng: docker compose stop).
#
# Tùy chọn:
#   ./run-local.sh --no-build   bỏ qua bước build (khi code không đổi, khởi động nhanh hơn)
#
# Lưu ý: dù chạy bằng một lệnh, đây VẪN là 3 process riêng nói chuyện với nhau qua HTTP + Eureka,
# không phải một monolith. Script chỉ tự động hóa việc bật chúng đúng thứ tự.

set -euo pipefail
cd "$(dirname "$0")"

LOG_DIR=logs
mkdir -p "$LOG_DIR"

# 1. Chọn JDK: ưu tiên đúng 21 (LTS), không có thì lấy bản >= 21 (máy hiện tại: 22).
#    Chỉ áp dụng trong script này, không ảnh hưởng terminal hay project khác.
#    java_home -v 21 trả đúng JDK 21 nếu có; nếu không có, nó lặng lẽ trả về JDK khác,
#    nên phải hỏi lại chính JDK đó là version mấy.
JAVA_HOME="$(/usr/libexec/java_home -v 21)"
export JAVA_HOME
JAVA="$JAVA_HOME/bin/java"
JAVA_MAJOR="$("$JAVA" -XshowSettings:properties -version 2>&1 | awk -F'= ' '/java.specification.version/ {print $2}')"
if [ "${JAVA_MAJOR:-0}" -lt 21 ]; then
  echo "✖ Cần JDK 21 trở lên, máy chỉ tìm thấy JDK $JAVA_MAJOR. Cài: brew install --cask temurin@21" >&2
  exit 1
fi
echo "▶ JDK: $("$JAVA" -version 2>&1 | head -1)"

# 2. Hạ tầng: Postgres trong Docker
if ! docker info >/dev/null 2>&1; then
  echo "✖ Docker chưa chạy. Mở Docker Desktop rồi chạy lại." >&2
  exit 1
fi
[ -f .env ] || { echo "✖ Thiếu file .env, chạy: cp .env.example .env" >&2; exit 1; }
# Mỗi thư mục dưới đây là một repo git riêng
for repo in platform discovery-server api-gateway catalog-service; do
  [ -f "$repo/pom.xml" ] || { echo "✖ Thiếu repo $repo/, chạy: ./clone-all.sh" >&2; exit 1; }
done
echo "▶ Bật Postgres..."
docker compose up -d --wait   # --wait: đợi tới khi healthcheck báo healthy

# 3. Build (bỏ test cho nhanh; muốn chạy test: mvn test)
if [ "${1:-}" != "--no-build" ]; then
  echo "▶ Build..."
  mvn -q -B install -DskipTests
fi

# 4. Bật service. Khi script thoát (Ctrl+C hoặc lỗi) thì tắt hết process con.
PIDS=()
cleanup() {
  trap - EXIT INT TERM   # tránh chạy cleanup 2 lần
  echo
  echo "▶ Đang tắt service..."
  # Tắt theo thứ tự NGƯỢC lúc bật: gateway/catalog trước, discovery sau cùng.
  # Nếu tắt discovery cùng lúc, các service kia không hủy đăng ký được với Eureka -> log báo lỗi.
  # PIDS[0] = discovery, phần còn lại = catalog, gateway.
  if [ ${#PIDS[@]} -gt 1 ]; then
    kill "${PIDS[@]:1}" 2>/dev/null || true
    wait "${PIDS[@]:1}" 2>/dev/null || true
  fi
  if [ ${#PIDS[@]} -gt 0 ]; then
    kill "${PIDS[0]}" 2>/dev/null || true
    wait 2>/dev/null || true
  fi
  echo "✔ Đã tắt. (Postgres vẫn chạy)"
}
trap cleanup EXIT INT TERM

start() { # start <tên> <cổng> [tham số thêm...]
  local name=$1 port=$2 jar; shift 2
  # Mỗi service có version riêng nên không ghi cứng tên file: lấy jar mới build nhất
  jar=$(ls -t "$name"/target/"$name"-*.jar 2>/dev/null | head -1)
  [ -n "$jar" ] || { echo "✖ Chưa có jar của $name, chạy lại không kèm --no-build" >&2; exit 1; }
  "$JAVA" -jar "$jar" "$@" > "$LOG_DIR/$name.log" 2>&1 &
  PIDS+=($!)
  echo "  - $name (:$port) pid=$!  log: $LOG_DIR/$name.log"
}

wait_http() { # wait_http <url> <mô tả> <số giây tối đa>
  local url=$1 label=$2 max=$3
  for _ in $(seq 1 "$max"); do
    curl -sf -o /dev/null "$url" && return 0
    sleep 1
  done
  echo "✖ Hết thời gian chờ $label. Xem log trong $LOG_DIR/" >&2
  exit 1
}

echo "▶ Bật service..."
# Discovery bật trước: các service khác cần nó để đăng ký.
start discovery-server 8761
wait_http http://localhost:8761/actuator/health "discovery-server" 60

start catalog-service 8081 --spring.profiles.active=local
start api-gateway 8080
wait_http http://localhost:8081/actuator/health "catalog-service" 90
wait_http http://localhost:8080/actuator/health "api-gateway" 90

# Service đã lên nhưng gateway cần thêm thời gian để thấy catalog trên Eureka.
echo "▶ Đợi gateway nhận ra catalog-service qua Eureka (thường ~30s)..."
wait_http http://localhost:8080/api/v1/flowers "route gateway -> catalog" 90

cat <<EOF

✔ Hệ thống đã sẵn sàng
  API (qua gateway): http://localhost:8080/api/v1/flowers
  Eureka:            http://localhost:8761
  Swagger:           http://localhost:8081/swagger-ui.html
  Xem log:           tail -f $LOG_DIR/*.log

Ctrl+C để tắt.
EOF

wait
