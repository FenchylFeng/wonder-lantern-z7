# Z7 V4 photo-monitor display

V4 adds remaining charge inside the battery icon on the original Nikon Z7 C 3.80 photo monitor. The display uses the native BatteryCheckService reading and draws 11×19 glyphs with four coverage levels. The digit 1 follows the stock shooting readout's short flag and unfooted stem. At 20% and below, the numerals and battery frame are red. The camera draws its original icon when the active battery reading is unavailable.

The Type A horizon follows the 720×480 Z8 C 3.12 monitor profile. The fixed guides and roll stroke have a 120×120 center cutout. The pitch segments rotate with the roll angle and use the pitch channel selected by the camera's orientation. The foreground is two pixels wide over a four-pixel translucent backing. Each axis turns green independently after rounding to whole degrees. Pitch travel reaches 58 pixels at 30°. The display becomes visible below 55° and stays visible through 60°.

Use a new output directory for each build. [Linux and WSL build](../README.en.md#build-v4-on-linux-or-wsl) · [Native Windows build](../README.en.md#build-v4-on-native-windows)

The source for V3 is available at commit `f779db4`. Its hashes and hardware report are in the [V3 notes](../DISPLAY_TYPE_A.md).

V4 changes the MAIN engine's monitor drawing code. The battery feature handles the native LCD battery icon submission at `0x10430256` and reads the active slot from the camera's battery service. The horizon shares the existing paint and clear entry points.

The battery feature follows the approach documented in the Z5 project. The Z7 drawing and battery-service integration are implemented against the Z7 interfaces. [Z5 battery implementation](https://github.com/WonderLantern/wonder-lantern-z5/blob/cfa33e7d1f67439bf443606db321f67f8f2bf7bf/src/card_module/vui_card.inc#L1524-L1580)

## Standalone Windows patcher

Open `Z7_FirmwarePatch_V4.exe` on 64-bit Windows, select your copy of the original `Z_7_0380.bin`, and choose an existing output folder. The app builds after you accept the confirmation. It checks the stock SHA-256, then verifies the complete generated EG's SHA-256 and CRC before renaming it to `EG161080.BIN`. Choose another folder when that filename already exists. [Nikon Download Center](https://downloadcenter.nikonimglib.com/zh-cn/download/fw/558.html)

The EXE is an independent project build. It runs offline with its bundled Python, Tcl/Tk, Keystone, Capstone, and precompiled renderer. The stock Nikon firmware is supplied locally at runtime.

To reproduce the single-file EXE, run these commands after the native Windows setup. The packaging step uses the original update to verify that the bundled renderer reproduces the reference EG. The package contains the renderer and its dependency notices.

```powershell
.private\venv-v4\Scripts\python.exe -m pip install 'PyInstaller==6.22.3'
.private\venv-v4\Scripts\python.exe tools/package_windows_v4.py --source .private/stock/Z_7_0380.bin
```

The default destination is `.private/dist/z7-v4/`. Use `--output` with a new folder for additional builds. Use `--llvm-bin` to select the Clang and LLD 23.1.5 directory explicitly.

## Verification

On 2026-11-23, the author reported successfully installing V4 on a Nikon Z7 and confirmed that it worked as expected.

Native Windows builds used CPython 3.12.16 and Clang/LLD 23.1.5. Two builds from the original Nikon update produced the same 33,061,030-byte EG with SHA-256 `b4c5d8ce38cbda332aa0fa24bfdc5e833ee17bcb2f7fe56be4895d8386e2c006`. The EG CRC residue was zero, and its payload matched the MAIN file byte for byte. The emulator input validator independently rebuilt and accepted the MAIN.

Both PowerShell scripts parsed. All 24 root tests, 23 QEMU Python tests, and 16 firmware tests passed, including the two firmware integration tests using original stock.

The native QEMU 10.2.4 build used MSYS2 UCRT64. The firmware-free QMP smoke test, 292 synthetic renderer checks, and 398 synthetic ISP checks passed. `Run-Z7.ps1` selected the verified V4 MAIN and returned a photo-mode monitor frame after 35.3 seconds. The isolated test guest then stopped through the controller.

The standalone EXE was tested on Windows 11 x64 from a separate folder with the system PATH and a cleared Python and Tcl environment. Both file pickers worked with a destination containing Chinese characters and a space. The app generated a byte-identical `EG161080.BIN` and displayed the full SHA-256. Declining closed the app. Separate checks rejected an invalid input and preserved an existing output.

Emulator validation covers the LCD in photo mode. Isolated ARM execution compares the Z7 line coordinates with stock Z8 AArch64 widget outputs. Z7 QEMU runs the native monitor with synthetic pose, image and battery inputs. The six histogram comparisons against stock Z7 produced zero differing pixels in the histogram region. [Validation summary](../evidence/v4-validation.json) · [Nikon Z8 d17](https://onlinemanual.nikonimglib.com/z8/en/csmd_virtual_horizon_type_247.html)

- [Type A horizon and histogram](../evidence/qemu-type-a-histogram.png)
- [Type A horizon in portrait orientation](../evidence/qemu-type-a-portrait.png)
- [100% battery reading](../evidence/qemu-battery-100.png)
