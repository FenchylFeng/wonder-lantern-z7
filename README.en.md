# WonderLantern Z7 lab

[简体中文](README.md)

**Experimental firmware may cause data loss, make the camera unresponsive, or
void Nikon warranty coverage. If you choose to use this firmware, the author
accepts no responsibility for any resulting problems. No emergency recovery
procedure has been verified.** [Risk notice](RISK_NOTICE.md)

This independent research fork targets the **original Nikon Z7 C 3.80**.
The project sources and component revisions are listed in the [upstream manifest](UPSTREAMS.json).

## Current version · V4 monitor

V4 includes these monitor features.

- **More framing grids** are available under Custom Setting d9. Choose the
  stock 4×4 grid, 3×3, or 2×2.
- **Updated virtual horizon** offers a Type A display similar to the
  Z8 C 3.12 version.
- **Histogram and horizon together** is one of three views available with
  the DISP button, alongside histogram only and horizon only.
- **Battery percentage** appears inside the battery icon on the shooting
  display. The indicator turns red at 20% or below.

The author successfully installed V4 on a Nikon Z7 and confirmed that it worked
as expected. [V4 verification notes](docs/DISPLAY_V4.md#verification)

## Portable Windows tool

`Z7_FirmwarePatch_V4.exe` is a single-file tool for Windows x64. Double-click
the EXE to run it without installing Python or LLVM. You can package the EXE
from source. [GitHub Releases](https://github.com/FenchylFeng/wonder-lantern-z7/releases) · [Usage and packaging](docs/DISPLAY_V4.md#standalone-windows-patcher)

1. Download the original `Z_7_0380.bin` for the Nikon Z7 C 3.80. [Nikon Download Center](https://downloadcenter.nikonimglib.com/en/download/fw/558.html)
2. Open the tool. Click **选择文件 (Choose file)** to select the original
   firmware, then **选择位置 (Choose folder)** to select an output folder.
   If it already contains `EG161080.BIN`, choose another folder.
3. Click **生成V4固件 (Generate V4 firmware)**, read the risk notice, and
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
   charged battery. Open **Setup Menu → Firmware version → Update**. The
   camera may still show C 3.80 after the update. Stop before confirming
   if **Update** is absent, the camera reports incompatibility, or the
   confirmation screen shows a target version other than 3.80.
5. After confirming the update, maintain power and leave the card inserted
   until the camera reports completion. Follow the on-screen instructions
   to turn it off, remove the card, and restart. [Nikon's stock update instructions](https://downloadcenter.nikonimglib.com/en/download/fw/558.html)
6. After restarting, check the 3×3 and 2×2 grids under Custom Setting d9,
   the horizon and histogram views selected with DISP, and the percentage
   inside the battery icon on the rear monitor in photo mode.

The full V4 EG has the following SHA-256. [Reference hashes](evidence/v4-validation.json)

```text
b4c5d8ce38cbda332aa0fa24bfdc5e833ee17bcb2f7fe56be4895d8386e2c006
```

## Build from source

### Build V4 on Linux or WSL

Use Python 3.12, Clang, and LLD. Download the original `Z_7_0380.bin` and
replace the firmware path in the command with your local path. [Nikon Download Center](https://downloadcenter.nikonimglib.com/en/download/fw/558.html)

```sh
python -m pip install -e "./z7-firmware-extensions[type-a]"
python tools/build_display_type_a.py --source /path/to/Z_7_0380.bin --output .private/build/display-v4
```

The builder checks the official input's SHA-256, then writes the full EG with
its CRC, the MAIN image for QEMU, and a build manifest to a new local
directory. [V4 build and verification notes](docs/DISPLAY_V4.md)

QEMU verification covered the rear monitor in photo mode. [Verification summary and QEMU screenshots](docs/DISPLAY_V4.md#verification)

### Build V4 on native Windows

Use PowerShell on 64-bit Windows. Download the original `Z_7_0380.bin`, then
run the following command from the repository. [Nikon Download Center](https://downloadcenter.nikonimglib.com/en/download/fw/558.html)

```powershell
.\Setup-Z7.ps1 -SourceFirmware 'C:\path\to\Z_7_0380.bin'
```

Setup uses Python 3.12+ and installs the V4 Python dependencies and LLVM 23.1.5
in the private workspace as needed. Use `-PythonPath` or `-LlvmBin` to supply
your own tools. Outputs go to a new directory under `.private/builds/` by
default. Setup reads the EG and MAIN from disk and saves the build configuration
after both SHA-256 hashes match the V4 reference values. [Reference hashes](evidence/v4-validation.json)

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
