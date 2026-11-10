#!/usr/bin/env bash
# Bật hook kiểm tra commit message (githooks/commit-msg) cho workspace và mọi repo bên trong.
# Chỉ ghi vào .git/config của từng repo (core.hooksPath), không đổi ~/.gitconfig.
set -euo pipefail
cd "$(dirname "$0")"

# Đường dẫn tương đối: git chạy hook từ thư mục gốc của từng repo
git config core.hooksPath githooks
echo "✔ workspace"
for dir in platform discovery-server api-gateway catalog-service customer-service identity-service inventory-service order-service; do
  if [ -d "$dir/.git" ]; then
    git -C "$dir" config core.hooksPath ../githooks
    echo "✔ $dir"
  fi
done
