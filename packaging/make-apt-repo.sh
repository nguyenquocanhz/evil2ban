#!/usr/bin/env bash
# Dung APT repo flat tu host tu cac file .deb. Tuy chon ky GPG.
#   bash packaging/make-apt-repo.sh [REPO_DIR] [DEB_GLOB]
#   GPG_KEY=<keyid> bash packaging/make-apt-repo.sh ./apt-repo
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${1:-$ROOT/packaging/apt-repo}"
DEB_GLOB="${2:-$(cd "$ROOT/.." && pwd)/evil2ban_*_all.deb}"

mkdir -p "$REPO"
# shellcheck disable=SC2086
cp $DEB_GLOB "$REPO/" 2>/dev/null || { echo "Khong thay .deb: $DEB_GLOB"; exit 1; }

cd "$REPO"
dpkg-scanpackages --multiversion . > Packages
gzip -9c Packages > Packages.gz
apt-ftparchive release . > Release

if [ -n "${GPG_KEY:-}" ]; then
  rm -f Release.gpg InRelease
  gpg --default-key "$GPG_KEY" -abs -o Release.gpg Release
  gpg --default-key "$GPG_KEY" --clearsign -o InRelease Release
  echo ">> Da ky bang GPG_KEY=$GPG_KEY"
fi

echo ">> APT repo san sang tai: $REPO"
echo "   Client:"
echo "     echo 'deb [trusted=yes] https://apt.your-domain.com/evil2ban ./' \\"
echo "       | sudo tee /etc/apt/sources.list.d/evil2ban.list"
echo "     sudo apt update && sudo apt install evil2ban"
