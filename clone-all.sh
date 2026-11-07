#!/usr/bin/env bash
# Lấy về tất cả repo của Flower Shop vào đúng chỗ trong workspace:  ./clone-all.sh
# Repo đã có thì bỏ qua (không ghi đè code đang sửa dở).
#
# Mỗi repo được cấu hình xác thực RIÊNG (trong .git/config của repo đó) qua GitHub CLI,
# nên token flower-shop chỉ dùng cho repo flower-shop, không đụng tới repo khác trên máy
# (ví dụ repo công ty vẫn dùng SSH key / keychain như cũ).
# Yêu cầu: đã cài gh và chạy gh auth login.

set -euo pipefail
cd "$(dirname "$0")"

ORG=flower-shop-teddy

# <thư mục local>  <tên repo trên GitHub>
REPOS=(
  "platform          flower-shop-platform"
  "discovery-server  flower-shop-discovery-server"
  "api-gateway       flower-shop-api-gateway"
  "catalog-service   flower-shop-catalog-service"
  "customer-service  flower-shop-customer-service"
)

# Xác thực chỉ áp dụng cho một repo (không đổi ~/.gitconfig)
use_gh_credential() { # use_gh_credential <thư mục repo>
  git -C "$1" config --replace-all credential.helper ''                     # bỏ helper chung của máy
  git -C "$1" config --add credential.helper '!gh auth git-credential'
}

command -v gh >/dev/null || { echo "✖ Chưa cài GitHub CLI: brew install gh" >&2; exit 1; }

# Chính repo workspace cũng dùng token flower-shop
[ -d .git ] && use_gh_credential .

for entry in "${REPOS[@]}"; do
  read -r dir repo <<<"$entry"
  if [ -d "$dir/.git" ]; then
    echo "• $dir: đã có, bỏ qua"
  else
    echo "▶ Clone $ORG/$repo -> $dir"
    # -c chỉ áp dụng cho lệnh clone này, sau đó ghi hẳn vào .git/config của repo
    git -c credential.helper= -c 'credential.helper=!gh auth git-credential' \
      clone "https://github.com/$ORG/$repo.git" "$dir"
  fi
  use_gh_credential "$dir"
done

# Bật hook kiểm tra commit message cho mọi repo
./install-hooks.sh

echo "✔ Xong. Tiếp theo: cp .env.example .env (nếu chưa có) rồi ./run-local.sh"
