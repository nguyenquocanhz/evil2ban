#!/usr/bin/env bash
# Build .deb KHONG can debhelper (dung dpkg-deb). Dung duoc tren box toi gian.
# (Neu co debhelper: 'dpkg-buildpackage -us -uc -b' cung chay nho debian/.)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(grep -m1 '^version' "$ROOT/pyproject.toml" | sed -E 's/.*"(.*)".*/\1/')"
STAGE="$ROOT/packaging/stage"
OUT="${1:-$(cd "$ROOT/.." && pwd)}"

echo ">> Build evil2ban $VERSION"
rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/lib/evil2ban/build" "$STAGE/lib/systemd/system"

cp -r "$ROOT/src" "$ROOT/pyproject.toml" "$ROOT/requirements.txt" \
      "$ROOT/README.md" "$ROOT/LICENSE" "$STAGE/usr/lib/evil2ban/build/"
cp "$ROOT/systemd/evil2ban.service" "$STAGE/lib/systemd/system/"
# khong dong goi venv / db / pycache
find "$STAGE/usr/lib/evil2ban/build" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

cat > "$STAGE/DEBIAN/control" <<EOF
Package: evil2ban
Version: $VERSION
Section: admin
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-venv, fail2ban, curl
Maintainer: Evil2Ban contributors <noreply@example.com>
Description: Chu dong phat hien va chan brute-force/scan, dashboard localhost
 Doc log nginx + journald SSH + fail2ban, real-IP Cloudflare, bieu do ngay/thang,
 TUI, notifier Telegram/Slack/Discord. Dashboard bind 127.0.0.1 (SSH tunnel).
EOF

for s in postinst prerm postrm; do
  sed '/#DEBHELPER#/d' "$ROOT/debian/$s" > "$STAGE/DEBIAN/$s"
  chmod 0755 "$STAGE/DEBIAN/$s"
done

DEB="$OUT/evil2ban_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$DEB"
echo ">> Built: $DEB"
