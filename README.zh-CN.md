# WonderLantern Z7 实验项目

[English](README.md)

**实验性固件可能存在数据丢失、死机、失去官方质保等风险。目前尚无经过验证的应急恢复方案。** [风险说明](RISK_NOTICE.md)

本仓库是面向**初代尼康 Z7 C 3.80** 的独立研究分支。项目来源和各组件的提交记录见 [上游清单](UPSTREAMS.json)。

## 当前版本 · 第 4 版取景显示

第 4 版包含以下显示屏功能。

- **更多取景网格**：可选 4×4（官方）、3×3 和 2×2，可在自定义设定 d9 控制。
- **Type A 电子水平仪**按 Z8 C 3.12 的后屏几何、角度取整和俯仰限幅实现。横滚和俯仰各自调平时变绿。
- **直方图与水平仪同框**：可选直方图、直方图与水平仪同框、仅水平仪三种显示设置，通过 Disp 按键切换。
- **电量百分比**以带抗锯齿的字形显示在取景页的电池图标内。电量在 20% 及以下时显示红色。

作者已在尼康 Z7 实机上成功刷入第 4 版，并确认运行正常。 [第 4 版验证说明](docs/DISPLAY_V4.md#verification)

### 在 Linux 或 WSL 构建第 4 版

准备 Python 3.12、Clang 和 LLD，从尼康下载原版 `Z_7_0380.bin`。将命令中的固件路径替换为本地文件。 [尼康官网下载](https://downloadcenter.nikonimglib.com/zh-cn/download/fw/558.html)

```sh
python -m pip install -e "./z7-firmware-extensions[type-a]"
python tools/build_display_type_a.py --source /path/to/Z_7_0380.bin --output .private/build/display-v4
```

构建器先校验官方输入的 SHA-256，再在新的本地目录生成含 CRC 的完整 EG、用于 QEMU 的 MAIN 和构建清单。 [第 4 版构建和验证说明](docs/DISPLAY_V4.md)

第 4 版已在 QEMU 验证照片模式后屏。 [验证摘要与 QEMU 截图](docs/DISPLAY_V4.md#verification)

### 原生 Windows 构建 · 暂未完成

第 4 版构建器的原生 Windows 验证尚未完成。仓库中的 `Setup-Z7.ps1` 和 `Start-Z7.cmd` 属于上游工作流。 [上游 Windows 模拟器说明](docs/archive/WINDOWS_BUILD.md)

## 源码与许可

- `z7-firmware-extensions/` 包含固件构建器及 Type A 绘制源码。
- `z7-qemu/` 包含 QEMU 源码覆盖层、显示行序修正和模拟器工具。 [QEMU 构建说明](z7-qemu/docs/build.md)
- `tools/` 包含本地构建及验证脚本。 [实验交接记录](docs/archive/HANDOFF.md)

本仓库按各组件原有许可发布源码。官方固件由使用者自行下载，生成的 EG、MAIN、固件转储和相机截图保存在本地。 [第三方来源与版本](DISPLAY_TYPE_A.md#sources-and-licenses) · [固件扩展许可](z7-firmware-extensions/THIRD_PARTY_NOTICES.md) · [QEMU 版权与许可](z7-qemu/NOTICE.md)

## 上游历史文档

早期网格预览、模拟器环境、快门声音等实验记录见 [上游文档归档](docs/archive/README.md)。
