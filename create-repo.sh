#!/usr/bin/env bash
# Đưa một thư mục service trong workspace lên GitHub thành repo riêng, cấu hình GIỐNG các repo đang có:
#   ./create-repo.sh <thư mục> "<mô tả>"
#   ./create-repo.sh order-service "Order service: đơn hàng"
#
# Script làm:
#   1. repo local: nhánh dev, email commit noreply, xác thực qua gh (như clone-all.sh), hook commit
#   2. tạo repo PUBLIC flower-shop-teddy/flower-shop-<thư mục>
#   3. tạo nhánh production từ dev mà KHÔNG kích hoạt release (tắt Actions trong lúc tạo)
#   4. push dev (CI chạy), đặt dev làm nhánh mặc định
#   5. copy ruleset từ TEMPLATE_REPO (đổi luật ở repo mẫu thì repo tạo sau tự theo)
# Chạy lại nhiều lần vẫn an toàn: bước nào đã làm thì bỏ qua.
#
# Script KHÔNG sửa clone-all.sh, install-hooks.sh, set-platform-version.sh, run-local.sh, pom.xml:
# các danh sách repo đó vẫn phải thêm tay (hoặc nhờ Claude) khi có service mới.
set -euo pipefail
cd "$(dirname "$0")"

ORG=flower-shop-teddy
TEMPLATE_REPO=$ORG/flower-shop-catalog-service

die() { echo "✖ $*" >&2; exit 1; }

DIR=${1:?Cách dùng: ./create-repo.sh <thư mục> \"<mô tả>\"}
DESC=${2:?Thiếu mô tả repo}
[[ "$DIR" =~ ^[a-z0-9-]+$ ]] || die "Tên thư mục chỉ gồm chữ thường, số, dấu '-': $DIR"
[ -f "$DIR/pom.xml" ] || die "Không thấy $DIR/pom.xml"
REPO=$ORG/flower-shop-$DIR
URL=https://github.com/$REPO.git
command -v gh >/dev/null || die "Chưa cài GitHub CLI: brew install gh"
command -v jq >/dev/null || die "Chưa có jq"

# 1. Repo local ---------------------------------------------------------------
[ -d "$DIR/.git" ] || git -C "$DIR" init -q -b dev
[ "$(git -C "$DIR" symbolic-ref --short HEAD)" = dev ] || die "$DIR phải đang ở nhánh dev"
git -C "$DIR" rev-parse -q --verify HEAD >/dev/null || die "$DIR chưa có commit nào, commit trước rồi chạy lại"
[ -z "$(git -C "$DIR" status --porcelain)" ] || die "$DIR còn thay đổi chưa commit"

# Email noreply: repo public không lộ email cá nhân (giống các repo khác trong workspace)
NOREPLY=$(gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"')
git -C "$DIR" config user.email "$NOREPLY"
git -C "$DIR" config --replace-all credential.helper ''
git -C "$DIR" config --add credential.helper '!gh auth git-credential'
git -C "$DIR" config core.hooksPath ../githooks
echo "✔ $DIR: cấu hình git local"

# 2. Repo trên GitHub ----------------------------------------------------------
if gh repo view "$REPO" >/dev/null 2>&1; then
  echo "• $REPO: đã có, bỏ qua bước tạo"
else
  gh repo create "$REPO" --public --description "$DESC" >/dev/null
  echo "✔ Tạo $REPO (public)"
fi
git -C "$DIR" remote get-url origin >/dev/null 2>&1 || git -C "$DIR" remote add origin "$URL"

# 3. Nhánh production -------------------------------------------------------------
# Push vào production = release (workflow release.yml). Tạo nhánh không phải là release,
# nên tắt Actions trong lúc tạo, đợi GitHub xử lý xong sự kiện push rồi mới bật lại.
if git ls-remote --exit-code --heads "$URL" production >/dev/null 2>&1; then
  echo "• production: đã có"
else
  gh api -X PUT "repos/$REPO/actions/permissions" -F enabled=false >/dev/null
  trap 'gh api -X PUT "repos/$REPO/actions/permissions" -F enabled=true -f allowed_actions=all >/dev/null' EXIT
  git -C "$DIR" push -q origin dev:production
  sleep 15
  gh api -X PUT "repos/$REPO/actions/permissions" -F enabled=true -f allowed_actions=all >/dev/null
  trap - EXIT
  echo "✔ Tạo production (không release)"
fi

# 4. Nhánh dev ---------------------------------------------------------------------
git -C "$DIR" push -q -u origin dev
gh repo edit "$REPO" --default-branch dev >/dev/null
git -C "$DIR" fetch -q origin
git -C "$DIR" rev-parse -q --verify production >/dev/null || git -C "$DIR" branch -q --track production origin/production
echo "✔ Push dev, dev là nhánh mặc định"

# 5. Ruleset (làm SAU cùng: ruleset production chặn push thẳng, kể cả lần tạo nhánh) -----
existing=$(gh api "repos/$REPO/rulesets" --jq '.[].name')
for id in $(gh api "repos/$TEMPLATE_REPO/rulesets" --jq '.[].id'); do
  rs=$(gh api "repos/$TEMPLATE_REPO/rulesets/$id")
  name=$(jq -r .name <<<"$rs")
  if grep -qxF "$name" <<<"$existing"; then
    echo "• ruleset \"$name\": đã có"
    continue
  fi
  jq '{name, target, enforcement, conditions, rules, bypass_actors}' <<<"$rs" \
    | gh api -X POST "repos/$REPO/rulesets" --input - >/dev/null
  echo "✔ ruleset \"$name\""
done

echo "✔ Xong: https://github.com/$REPO"
echo "  Nhớ thêm $DIR vào clone-all.sh, install-hooks.sh, set-platform-version.sh, run-local.sh, pom.xml nếu chưa có."
