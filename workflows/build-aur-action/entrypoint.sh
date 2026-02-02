#!/bin/bash

set -euo pipefail

pkgname=$1

# 检查是否存在缓存的包文件
if ls "$pkgname"/*.pkg.tar.zst 1> /dev/null 2>&1; then
    echo "Found cached package files, skipping build"
    echo "Cached files:"
    ls -lh "$pkgname"/*.pkg.tar.zst
    exit 0
fi

echo "No cached package found, starting build"

useradd builder -m
echo "builder ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
chmod -R a+rw .

cat << EOM >> /etc/pacman.conf
[archlinuxcn]
Server = https://repo.archlinuxcn.org/x86_64
EOM

pacman-key --init
pacman-key --lsign-key "farseerfc@archlinux.org"
pacman -Sy --noconfirm && pacman -S --noconfirm archlinuxcn-keyring
pacman -Syu --noconfirm archlinux-keyring
pacman -S --noconfirm yay
if [ ! -z "$INPUT_PREINSTALLPKGS" ]; then
    pacman -S --noconfirm "$INPUT_PREINSTALLPKGS"
fi

# 清理可能残留的构建目录，以避免 git clone 失败
rm -rf "$pkgname"
sudo --set-home -u builder yay -S --noconfirm --builddir=./ "$pkgname"

# Find the actual build directory (pkgbase) created by yay.
# Some AUR packages use a different pkgbase directory name,
# e.g. otf-space-grotesk has a pkgbase 38c3-styles,
# when using yay -S otf-space-grotesk, it's built under folder 38c3-styles.
function get_pkgbase(){
  local pkg="$1"
  url="https://aur.archlinux.org/rpc/?v=5&type=info&arg=${pkg}"
  resp="$(curl -sS "$url")"
  pkgbase="$(printf '%s' "$resp" | jq -r '.results[0].PackageBase // .results[0].Name')"
  echo "$pkgbase"
}

if [[ -d "$pkgname" ]];
  then
    pkgdir="$pkgname"
  else
    pacman -S --needed --noconfirm jq
    pkgdir="$(get_pkgbase "$pkgname")"
fi



echo "The pkgdir is $pkgdir"
echo "The pkgname is $pkgname"
cd "$pkgdir"

# Rename files to remove invalid characters (colons, etc.)
echo "Renaming files to remove invalid characters..."
for file in *.pkg.tar.zst*; do
    [ -e "$file" ] || continue
    newfile="${file//:/_}"
    if [ "$file" != "$newfile" ]; then
        mv "$file" "$newfile"
        echo "Renamed: $file -> $newfile"
    fi
done
