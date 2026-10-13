#!/bin/bash
# 更新 Choice 的 deb 并重建 Arch 包
#
# 用法:
#   ./update.sh                            # 用当前目录下默认文件 ChoiceSetup_uos_x86.deb
#   ./update.sh /path/to/新ChoiceSetup.deb # 指定新 deb 路径
#   ./update.sh /path/to/新.deb --install  # 更新 PKGBUILD 后立即构建并安装
#
# 脚本会自动: 读版本号 → 算 sha256 → 更新 PKGBUILD 的 pkgver/pkgrel/source/sha256sums
set -euo pipefail
cd "$(dirname "$0")"

DEB="${1:-ChoiceSetup_uos_x86.deb}"
INSTALL=0
for a in "$@"; do
  [ "$a" = "--install" ] && INSTALL=1
done

if [ ! -f "$DEB" ]; then
  echo "错误: 找不到 deb 文件: $DEB" >&2
  echo "用法: ./update.sh [新deb文件路径] [--install]" >&2
  exit 1
fi

# 1. 从 deb 的 control 元数据读取版本号
VER="$(bsdtar -xOf "$DEB" control.tar.xz 2>/dev/null | bsdtar -xOf - control 2>/dev/null | sed -n 's/^Version:[[:space:]]*//p')"
if [ -z "$VER" ]; then
  echo "错误: 无法从 $DEB 读取 Version 字段" >&2
  exit 1
fi
# Arch 的 pkgver 不允许出现 '-'（那是 pkgrel 分隔符），统一转成 '.'
VER="${VER//-/.}"
echo "==> 检测到版本: $VER"

# 2. 计算 sha256
SUM="$(sha256sum "$DEB" | awk '{print $1}')"
echo "==> sha256: $SUM"

# 3. 复制 deb 到本目录（保持与 PKGBUILD 同级），统一文件名
NAME="$(basename "$DEB")"
if [ "$(realpath "$DEB")" != "$(realpath "$NAME")" ]; then
  cp -f "$DEB" "$NAME"
fi

# 4. 更新 PKGBUILD 的四个字段
sed -i "s/^pkgver=.*/pkgver=$VER/"              PKGBUILD
sed -i "s/^pkgrel=.*/pkgrel=1/"                 PKGBUILD
sed -i "s|^source=(.*)|source=('$NAME')|"       PKGBUILD
sed -i "s|^sha256sums=(.*)|sha256sums=('$SUM')|" PKGBUILD

echo "==> PKGBUILD 已更新: pkgver=$VER, pkgrel=1, source=('$NAME')"
echo "==> 变更摘要:"
grep -E "^pkgver=|^pkgrel=|^source=|^sha256sums=" PKGBUILD

if [ "$INSTALL" = "1" ]; then
  echo "==> 开始构建并安装..."
  makepkg -si
else
  echo ""
  echo "完成。确认无误后手动构建安装:"
  echo "  makepkg -si"
fi
