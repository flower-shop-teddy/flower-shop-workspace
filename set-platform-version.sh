#!/usr/bin/env bash
# Đổi version của platform VÀ parent của mọi service trong một lần, để workspace luôn khớp nhau.
#   ./set-platform-version.sh 0.2.0-SNAPSHOT
# Script chỉ sửa file, KHÔNG commit. Xem lại bằng git diff rồi commit ở từng repo, ví dụ:
#   git commit -am "build: nâng platform lên 0.2.0-SNAPSHOT"
#
# Chỉ chạy khi platform có thay đổi cần release: service chỉ release được khi
# platform đã release đúng version parent mà service đang trỏ tới.
set -euo pipefail
cd "$(dirname "$0")"

NEW=${1:?Cách dùng: ./set-platform-version.sh <version>, ví dụ 0.2.0-SNAPSHOT}
SERVICES=(discovery-server api-gateway catalog-service customer-service identity-service)

JAVA_HOME="$(/usr/libexec/java_home -v 21)"; export JAVA_HOME

OLD=$(mvn -B -q -f platform/pom.xml help:evaluate -Dexpression=project.version -DforceStdout)
echo "▶ platform: $OLD -> $NEW"
mvn -B -q -f platform/pom.xml versions:set -DnewVersion="$NEW" -DprocessAllModules -DgenerateBackupPoms=false
mvn -B -q -f platform/pom.xml versions:set-property -Dproperty=flower-shop-common.version -DnewVersion="$NEW" -DgenerateBackupPoms=false

for s in "${SERVICES[@]}"; do
  NEW="$NEW" perl -0pi -e 's|(<artifactId>flower-shop-parent</artifactId>\s*<version>)[^<]+(</version>)|${1}$ENV{NEW}${2}|' "$s/pom.xml"
  echo "▶ $s: parent -> $NEW"
done

echo "▶ Build kiểm tra..."
mvn -B -q install -DskipTests
echo "✔ Xong. Xem lại: git -C platform diff, git -C <service> diff. Rồi commit + push ở từng repo."
