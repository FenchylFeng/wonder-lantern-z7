# WonderLantern Z7 lab

[简体中文](README.md)

**Experimental firmware may cause data loss, make the camera unresponsive, or
void Nikon warranty coverage. If you choose to use this firmware, the author
accepts no responsibility for any resulting problems. No emergency recovery
procedure has been verified.** [Risk notice](RISK_NOTICE.md)

This independent research fork targets the **original Nikon Z7 C 3.80**.
The project sources and component revisions are listed in the [upstream manifest](UPSTREAMS.json).

## Current version · V1.5

V1.5 includes these features.

- **More framing grids** are available under Custom Setting d9. Choose the
  stock 4×4 grid, 3×3, or 2×2.
- **Updated virtual horizon** offers a Type A display similar to the
  Z8 C 3.12 version.
- **Histogram and horizon together** is one of three views available with
  the DISP button, alongside histogram only and horizon only.
- **Battery percentage** appears inside the battery icon on the shooting
  display. The indicator turns red at 20% or below.
- **Auto ISO shortcut** lets you double-click the ISO button to toggle Auto
  ISO. Enable it under Custom Setting f8.
- **Back-button AF-C** lets you use AF-ON for continuous autofocus while the
  camera is set to AF-S. Enable it under Custom Setting f9.

The author successfully installed V1.5 on a Nikon Z7 and confirmed that it
worked as expected. [Shortcut verification notes](docs/DISPLAY_V4.md#af-on-focus-mode)

## Portable Windows tool

`Z7_FirmwarePatch_V1.5.exe` is a single-file tool for Windows x64. Double-click
the EXE to run it without installing Python or LLVM. You can package the EXE
from source. [GitHub Releases](https://github.com/FenchylFeng/wonder-lantern-z7/releases) · [Usage and packaging](docs/DISPLAY_V4.md#standalone-windows-patcher)

1. Download the original `Z_7_0380.bin` for the Nikon Z7 C 3.80. [Nikon Download Center](https://downloadcenter.nikonimglib.com/en/download/fw/558.html)
2. Open the tool. Click **选择文件 (Choose file)** to select the original
   firmware, then **选择位置 (Choose folder)** to select an output folder.
   If it already contains `EG161080.BIN`, choose another folder.
3. Click **生成V1.5固件 (Generate V1.5 firmware)**, read the risk notice, and
   click **同意并生成固件 (Agree and generate)**. The tool checks the
   original firmware's SHA-256 and saves `EG161080.BIN` after the full EG
   passes its SHA-256 and CRC checks.

## Flashing steps

Flashing experimental firmware can cause data loss or permanently prevent the
camera from starting. An emergency recovery procedure has yet to be verified.
[Risk notice](RISK_NOTICE.md)

1. Confirm that the camera is an original Nikon Z7 running C 3.80 without the
   paid RAW video upgrade.
2. Generate `EG161080.BIN` with the portable tool. If you build from source,
   rename the full EG file `display.emulator.eg.bin` to `EG161080.BIN`.
   Check that its SHA-256 matches the reference below.
3. Back up the camera settings and card contents. Use a compatible card
   formatted in the camera. Copy `EG161080.BIN` to its root directory as the
   only firmware file there. Check the SHA-256 of the copy and safely eject
   the card.
4. Insert the card while the camera is off, then turn it on with a fully
   charged battery. Use a Nikon lens or leave the mount empty. Remove any
   third-party lens or adapter before updating. Open **Setup Menu → Firmware
   version → Update**. The target version remains C 3.80. Stop before confirming
   if **Update** is absent, the camera reports incompatibility, or the
   confirmation screen shows a target version other than 3.80.
5. After confirming the update, maintain power and leave the card inserted
   until the camera reports completion. Follow the on-screen instructions
   to turn it off, remove the card, and restart. [Nikon's stock update instructions](https://downloadcenter.nikonimglib.com/en/download/fw/558.html)
6. After restarting, check the 3×3 and 2×2 grids under Custom Setting d9,
   the horizon and histogram views selected with DISP, and the percentage
   inside the battery icon on the rear monitor in photo mode.

The full V1.5 EG has the following SHA-256. [Reference hashes](evidence/v1.5-reference.json)

```text
322cb50592600b7bee206233d598d48d6c81385fc82e079cac95eae30c06bc71
```

## Build from source

### Build V1.5 on Linux or WSL

Use Python 3.12, Clang, and LLD. Download the original `Z_7_0380.bin` and
replace the firmware path in the command with your local path. [Nikon Download Center](https://downloadcenter.nikonimglib.com/en/download/fw/558.html)

```sh
python -m pip install -e "./z7-firmware-extensions[type-a]"
python tools/build_display_type_a.py --source /path/to/Z_7_0380.bin --output .private/build/display-v4 --af-on-af-c
```

The builder checks the official input's SHA-256, then writes the full EG with
its CRC, the MAIN image for QEMU, and a build manifest to a new local
directory. [Build and verification notes](docs/DISPLAY_V4.md)

### Build V1.5 on native Windows

Use PowerShell on 64-bit Windows. Download the original `Z_7_0380.bin`, then
run the following command from the repository. [Nikon Download Center](https://downloadcenter.nikonimglib.com/en/download/fw/558.html)

```powershell
.\Setup-Z7.ps1 -SourceFirmware 'C:\path\to\Z_7_0380.bin'
```

Setup builds V1.5 with both f8 and f9. It uses Python 3.12+ and prepares Python,
its dependencies, and LLVM 23.1.5 in the private workspace as needed. Use
`-PythonPath` to choose the interpreter for a new virtual environment or
`-LlvmBin` to supply an existing Clang and LLD installation.

The output directory defaults to `.private/builds/display-v1.5-<timestamp>/`.
Use `-BuildDirectory` to choose a new directory. It contains the full EG
(`display.emulator.eg.bin`), MAIN for QEMU (`display.emulator.main.bin`), and
the build manifest (`display.json`). Setup saves the local build configuration
after both on-disk SHA-256 hashes match the V1.5 reference values. [V1.5 reference hashes](evidence/v1.5-reference.json)

To package `Z7_FirmwarePatch_V1.5.exe` from source, complete setup first.
[Standalone packaging instructions](docs/DISPLAY_V4.md#standalone-windows-patcher)

To build the native QEMU emulator, add `-BuildQemu` to the setup command. Then
run `.\Run-Z7.ps1 -OpenBrowser` or open `Start-Z7.cmd`. Use `-Legacy` to
build the archived presets. [Historical QEMU build notes](docs/archive/WINDOWS_BUILD.md)

## Source and licenses

- `z7-firmware-extensions/` contains the firmware builder and Type A drawing code.
- `z7-qemu/` contains the QEMU source overlay, display row-order correction,
  and emulator tools. [QEMU build instructions](z7-qemu/docs/build.md)
- `tools/` contains local build and verification scripts. [Lab handoff](docs/archive/HANDOFF.md)

Source code is distributed under each component's original license. Obtain the
official firmware from Nikon and keep generated EG and MAIN files, firmware
dumps, and camera screenshots local. [Third-party sources and versions](DISPLAY_TYPE_A.md#sources-and-licenses) · [Firmware extensions notices](z7-firmware-extensions/THIRD_PARTY_NOTICES.md) · [QEMU copyright and licenses](z7-qemu/NOTICE.md)

## Upstream archive

The archive covers earlier grid previews, emulator environments, shutter
sound, and other experiments. [Upstream documentation archive](docs/archive/README.md)
