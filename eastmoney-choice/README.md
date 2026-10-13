# eastmoney-choice (东方财富 Choice金融终端)

将东方财富 `ChoiceSetup_uos_x86.deb`（统信 UOS / Debian amd64）重打包为 Arch Linux 包。

## 前置条件

- Arch Linux（x86_64）
- 已安装 `base-devel`（提供 `makepkg` / `bsdtar`）
- 中文字体（`noto-fonts-cjk` 或 `wqy-microhei`），否则界面中文会显示为方块

## 构建与安装

```bash
# 1. 克隆仓库
# git clone git@github.com:wahoya996/buffett.git
# cd buffett/eastmoney-choice

# 2. 下载 Choice 官方 Linux(UOS) 安装包并放到本目录
#    从 Choice 官网 https://choice.eastmoney.com/ 或统信应用商店获取
#    文件名通常为 ChoiceSetup_uos_x86.deb（若改名，用 update.sh 会自动适配）

# 3. 构建（会自动校验 sha256、解包、生成 .pkg.tar.zst）
makepkg -si

# 4. 启动
emchoice
# 或从应用菜单选择「Choice金融终端」
```

## 产物与安装布局

| 路径 | 说明 |
|------|------|
| `/opt/apps/com.eastmoney.choice/files/` | 程序主体（自带 Qt5.14.2 / ICU / OpenSSL1.1 / CEF） |
| `/usr/bin/emchoice` | 启动脚本（cd 到程序目录后执行 `EMChoice`） |
| `/usr/share/applications/com.eastmoney.choice.desktop` | 桌面入口 |
| `/usr/share/icons/hicolor/*/apps/com.eastmoney.choice.*` | 图标 |

## 依赖说明

程序自带运行库位于 `files/lib`（通过 `$ORIGIN` RUNPATH 相对定位，无需 patchelf）。
系统级依赖已按 `ldd` / `readelf -d` 分析结果写入 `depends`，主要包括
GTK3 / GLib2 / NSS / ALSA / X11 系列 / Mesa 等（CEF 浏览器内核所需）。

## 已知注意事项

1. **首次运行可能需要给用户写权限**：程序可能在自身目录写日志/缓存。
   如遇启动报错，可临时执行：
   ```bash
   sudo chown -R "$USER" /opt/apps/com.eastmoney.choice/files
   ```
2. **WPS Excel 插件**（QsExcelWebJs）需要 WPS 的 Kingsoft 目录才生效，纯 Arch 环境可忽略。
3. 这是闭源商业软件，请遵守东方财富的授权条款（`/usr/share/licenses/eastmoney-choice/`）。

## 更新（官方发布新 deb 后）

新版本发布时只需改 PKGBUILD 的 `pkgver` 与 `sha256sums`（`depends` 一般不变）。

**一键方式（推荐）**：

```bash
# 下载新版 deb 后执行（会读版本号→算校验和→改 PKGBUILD）
./update.sh /path/to/新ChoiceSetup.deb

# 确认变更无误后构建安装
makepkg -si

# 或直接一步到位
./update.sh /path/to/新ChoiceSetup.deb --install
```

**手动方式**：

```bash
# 1. 读新版本号
bsdtar -xOf 新ChoiceSetup.deb control.tar.xz | bsdtar -xOf - control | grep '^Version:'
# 2. 算校验和
sha256sum 新ChoiceSetup.deb
# 3. 把两个值填进 PKGBUILD 的 pkgver= 和 sha256sums=，pkgrel 重置为 1
# 4. 重建
makepkg -si
```

## 卸载

```bash
sudo pacman -Rns eastmoney-choice
```
