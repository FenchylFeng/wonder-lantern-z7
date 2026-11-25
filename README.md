# WonderLantern Z7 实验项目

[English](README.en.md)

**实验性固件可能存在数据丢失、死机、失去官方质保等风险。如果您选择接受并使用了我的固件，则出现的任何问题，本人不负任何责任。目前尚无经过验证的应急恢复方案。** [风险说明](RISK_NOTICE.md)

本仓库是面向**初代尼康 Z7 C 3.80** 的独立研究分支。项目来源和各组件的提交记录见 [上游清单](UPSTREAMS.json)。

## 功能介绍

第 4 版包含以下功能：

- **更多取景网格**：可选 4×4（官方）、3×3 和 2×2，可在自定义设定 d9 控制。
- **新版电子水平仪**：实现类似 Z8 C 3.12 的 Type A 型电子水平仪。
- **直方图与水平仪同框**：可选直方图、直方图与水平仪同框、仅水平仪三种显示设置，通过 Disp 按键切换。
- **电量百分比**：在取景页的电池图标内显示电量百分比。电量在 20% 及以下时显示红色。

作者已在尼康 Z7 实机上成功刷入第 4 版，并确认运行正常。 [第 4 版验证说明](docs/DISPLAY_V4.md#verification)

## Windows 免安装工具

`Z7_FirmwarePatch_V4.exe` 是面向 Windows x64 的单文件工具，双击即可运行，无需安装 Python 或 LLVM。可按打包说明从源码生成 EXE。 [GitHub 发布页](https://github.com/FenchylFeng/wonder-lantern-z7/releases) · [使用与打包说明](docs/DISPLAY_V4.md#standalone-windows-patcher)

1. 下载初代 Z7 C 3.80 的原厂固件 `Z_7_0380.bin`。 [尼康下载中心](https://downloadcenter.nikonimglib.com/zh-cn/download/fw/558.html)
2. 打开工具，点击「选择文件」选中原厂固件，再点击「选择位置」指定保存目录。若目录中已有 `EG161080.BIN`，请选择其他目录。
3. 点击「生成V4固件」，阅读风险提示后选择「同意并生成固件」。程序会校验原厂固件的 SHA-256，并在生成的完整 EG 通过 SHA-256 和 CRC 校验后保存为 `EG161080.BIN`。

## 刷写步骤

刷写实验性固件可能导致数据丢失或相机永久无法启动。目前尚无经过验证的应急恢复方案。 [风险说明](RISK_NOTICE.md)

1. 确认机身为初代尼康 Z7，当前固件为 C 3.80，且未安装付费 RAW 视频升级。
2. 用免安装工具生成 `EG161080.BIN`。如从源码构建，将生成的完整 EG 文件 `display.emulator.eg.bin` 直接重命名为 `EG161080.BIN`。确认完整文件的 SHA-256 与下方参考值一致。
3. 备份相机设定和卡内数据。准备一张已在相机中格式化的兼容存储卡，将 `EG161080.BIN` 复制到卡的根目录，确保根目录中只有这一份固件文件。核对卡上文件的 SHA-256 后，安全弹出存储卡。
4. 在相机关机时插卡，使用充满电的电池开机。进入「设定菜单 → 固件版本 → 更新」。机身版本号在更新后可能仍显示为 C 3.80。若没有「更新」项、相机提示不兼容，或确认画面显示的目标版本并非 3.80，请在确认前停止操作。
5. 确认开始更新后，保持供电并保留存储卡在机内，直至相机明确提示完成。按屏幕指示关机、取卡并重启。 [尼康原厂固件更新参考](https://downloadcenter.nikonimglib.com/zh-cn/download/fw/558.html)
6. 重启后，在照片模式后屏检查自定义设定 d9 的 3×3 和 2×2 网格、DISP 切换的水平仪与直方图画面，以及电池图标中的电量百分比。

V4 完整 EG 的 SHA-256 如下。 [参考哈希](evidence/v4-validation.json)

```text
b4c5d8ce38cbda332aa0fa24bfdc5e833ee17bcb2f7fe56be4895d8386e2c006
```

## 由源代码构建

### 在 Linux 或 WSL 构建第 4 版

准备 Python 3.12、Clang 和 LLD，从尼康下载原版 `Z_7_0380.bin`。将命令中的固件路径替换为本地文件。 [尼康官网下载](https://downloadcenter.nikonimglib.com/zh-cn/download/fw/558.html)

```sh
python -m pip install -e "./z7-firmware-extensions[type-a]"
python tools/build_display_type_a.py --source /path/to/Z_7_0380.bin --output .private/build/display-v4
```

构建器先校验官方输入的 SHA-256，再在新的本地目录生成含 CRC 的完整 EG、用于 QEMU 的 MAIN 和构建清单。 [第 4 版构建和验证说明](docs/DISPLAY_V4.md)

第 4 版已在 QEMU 验证照片模式后屏。 [验证摘要与 QEMU 截图](docs/DISPLAY_V4.md#verification)

在构建命令中加上 `--iso-double-click`，并指定新的输出目录，可生成带机身 ISO 键双击快捷键的 V4 实验版。在「自定义设定菜单 → f 控制 → f8 连按ISO按钮切换ISO AUTO」开启后，双击机身 ISO 键切换自动 ISO。首次使用默认关闭，相机正常重启后恢复上次确认的选择。快捷键用于照片 P、S、A、M 档和视频 M 档。 [使用与验证](docs/DISPLAY_V4.md#iso-button-double-click)

用 `--af-on-af-c` 构建同时含 f8 和「f9 AF-ON对焦使用AF-C」的版本。f9 首次使用默认关闭，并通过原厂设置保存确认后的选择。开启时，按下机身 AF-ON 立即从 AF-S 切到 AF-C，松开后恢复 AF-S。修正机身 AF-ON 映射后的合并版已通过实机验证。 [使用与验证](docs/DISPLAY_V4.md#af-on-focus-mode)

### 在原生 Windows 构建第 4 版

在 64 位 Windows 上使用 PowerShell。下载原版固件 `Z_7_0380.bin`，然后在仓库目录执行下列命令。 [尼康官网下载](https://downloadcenter.nikonimglib.com/zh-cn/download/fw/558.html)

```powershell
.\Setup-Z7.ps1 -SourceFirmware 'C:\path\to\Z_7_0380.bin'
```

脚本使用 Python 3.12+，按需在私有工作目录安装第 4 版所需的 Python 包和 LLVM 23.1.5。可用 `-PythonPath` 或 `-LlvmBin` 指定已有工具。产物默认写到 `.private/builds/` 下的新目录。脚本会读取磁盘上的 EG 和 MAIN，确认其 SHA-256 与第 4 版参考值一致后才保存构建配置。 [参考哈希](evidence/v4-validation.json)

如需原生 QEMU 模拟器，在构建命令中加上 `-BuildQemu`，然后运行 `.\Run-Z7.ps1 -OpenBrowser` 或打开 `Start-Z7.cmd`。如需构建归档预设，使用 `-Legacy`。 [QEMU 历史构建说明](docs/archive/WINDOWS_BUILD.md)

## 源码与许可

- `z7-firmware-extensions/` 包含固件构建器及 Type A 绘制源码。
- `z7-qemu/` 包含 QEMU 源码覆盖层、显示行序修正和模拟器工具。 [QEMU 构建说明](z7-qemu/docs/build.md)
- `tools/` 包含本地构建及验证脚本。 [实验交接记录](docs/archive/HANDOFF.md)

本仓库按各组件原有许可发布源码。官方固件由使用者自行下载，生成的 EG、MAIN、固件转储和相机截图保存在本地。 [第三方来源与版本](DISPLAY_TYPE_A.md#sources-and-licenses) · [固件扩展许可](z7-firmware-extensions/THIRD_PARTY_NOTICES.md) · [QEMU 版权与许可](z7-qemu/NOTICE.md)

## 上游历史文档

早期网格预览、模拟器环境、快门声音等实验记录见 [上游文档归档](docs/archive/README.md)。
