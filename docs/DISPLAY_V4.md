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

## ISO button double-click

In **Custom Settings Menu → f Controls → f8 ISO button double-click**, choose
**On** and press **OK** to enable the shortcut. The first-use default is **Off**.
The camera saves each confirmed choice through its native settings worker and
restores it on the next startup. In the shooting view, two short taps on the
body ISO button then toggle Auto ISO. Each press must be released within
250 ms, with no more than 350 ms between releases. The shortcut uses the
photo setting in P, S, A, and M and the separate movie setting in M. Turning
either command dial cancels a pending double-click. [Nikon ISO button](https://onlinemanual.nikonimglib.com/z7_z6/en/06_shooting_controls_02.html) · [Nikon Controls menu](https://onlinemanual.nikonimglib.com/z7_z6/en/09_menu_guide_05.html)

```sh
python tools/build_display_type_a.py --source /path/to/Z_7_0380.bin \
  --iso-double-click --output .private/build/display-v4-iso
```

The source build generates a separate EG, MAIN and manifest. The QEMU
validator independently rebuilds this profile from the original Nikon update.
The list uses Nikon's purple f8 number bitmap and its translated On and Off
rows. The Simplified Chinese title is `连按ISO按钮切换ISO AUTO`.

The added MAIN code observes native switch reports in the shooting task at
`0x1012C5AC`. The body ISO button is bank 1 bit 29. A completed gesture calls
the same settings service as the On and Off rows of the original shooting
menus for properties `0x508` and `0xB07`. Boot initializes the four gesture
words in volatile RAM at `0xA29F8FD0`. The switch uses an alignment halfword
inside native journal record 55. Only the exact On marker enables the gesture.
The original 89-record schema, startup loader and writer handle storage.

```sh
python tools/audit_iso_double_click_storage.py --source /path/to/Z_7_0380.bin \
  --build .private/build/display-v4-iso --output .private/iso-storage.json
```

The storage audit executes the native worker, journal and startup on ARM
with supplied OS and in-memory flash boundaries. It verifies first-use Off,
both choices across fresh RAM, the original loader's ability to read the
saved journal, and preservation of the last committed choice on a supplied
program failure. Assisted QEMU exercises the menu and the shortcut with
native flash writes disabled in the test fixture. The Z7 QEMU board lacks the
flash command used by the save worker. The body ISO shortcut was also
confirmed on a physical Nikon Z7.

## AF-ON focus mode

The combined build includes the f8 ISO switch and **f9 Use AF-C with AF-ON**
under **Custom Settings Menu → f Controls**. The Simplified Chinese title is
`AF-ON对焦使用AF-C`. f9 defaults to Off on first use. Confirming a choice
requests a save through the native settings worker.

With the setting On and focus mode set to AF-S, the camera applies AF-C
on the AF-ON press edge and restores AF-S on release. The interval is the
time the button is held. AF-C and manual focus stay as selected if already
active at the time of the press. [Nikon AF-ON control](https://onlinemanual.nikonimglib.com/z7_z6/en-nsg/02_getting_to_know_the_camera_02.html)

```sh
python tools/build_display_type_a.py --source /path/to/Z_7_0380.bin \
  --af-on-af-c --output .private/build/display-v4-af-on
```

f9 uses an aligned halfword at `0xA24F2DCE` in native journal record 55.
The storage audit checks both shortcuts in the combined build. The original
photo and movie AF-ON assignments both bind the body switch to bank zero,
bit 21. The stock queue forwards this switch to the shortcut. In assisted
QEMU, the photo AF task read AF-C after the press-edge write.

The corrected combined build passed the user's physical Nikon Z7 C 3.80
check after the AF-ON input mapping was fixed. This report applies to the
combined EG with SHA-256
`322cb50592600b7bee206233d598d48d6c81385fc82e079cac95eae30c06bc71`.
