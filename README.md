# WonderLantern Z7 lab

[简体中文](README.zh-CN.md)

**Experimental firmware may cause data loss, make the camera unresponsive,
or affect Nikon warranty coverage. An emergency recovery procedure has yet
to be verified.** [Risk notice](RISK_NOTICE.md)

This independent research fork targets the **original Nikon Z7 C 3.80**.
See [UPSTREAMS.json](UPSTREAMS.json) for project sources and component revisions.

## Current version · V4 monitor

V4 includes the following monitor features.

- **More framing grids** are available under Custom Setting d9, including the
  standard 4×4 grid and the added 3×3 and 2×2 grids.
- **Type A virtual horizon** reproduces the Z8 C 3.12 monitor geometry,
  degree rounding and pitch limits. Roll and pitch turn green independently.
- **Histogram and horizon together** is one of three views available with the
  DISP button, alongside histogram only and horizon only.
- **Battery percentage** appears in antialiased numerals inside the shooting
  monitor's battery icon. The icon uses red at 20% or below.

The author reported hardware results for V3. [V3 build and validation notes](DISPLAY_TYPE_A.md)

### Build V4 on Linux or WSL

Use Python 3.12, Clang and LLD. Obtain the original `Z_7_0380.bin` from
[Nikon](https://downloadcenter.nikonimglib.com/en/download/fw/558.html).

```sh
python -m pip install -e "./z7-firmware-extensions[type-a]"
python tools/build_display_type_a.py --source /path/to/Z_7_0380.bin --output .private/build/display-v4
```

The builder first checks the official input's SHA-256, then writes the full EG
with its CRC, the QEMU MAIN image, and a build manifest to a new local directory.
See the [V4 notes](docs/DISPLAY_V4.md) for build and validation details.

### Native Windows build · Pending

Validation of the V4 patcher on native Windows is pending. The repository's
`Setup-Z7.ps1` and `Start-Z7.cmd` belong to the upstream workflow.
[Upstream Windows emulator notes](docs/archive/WINDOWS_BUILD.md)

## Documentation

- [V4 battery and Type A changes](docs/DISPLAY_V4.md)
- [V3 build and validation notes](DISPLAY_TYPE_A.md)
- [Upstream research archive](docs/archive/README.md) for earlier grids, emulator setup, and other lab experiments

## Inputs and distribution

No Nikon firmware, modified firmware binary, dump, key, camera screenshot,
private media, virtual environment or compiled QEMU binary is included. These
stay in ignored local directories. Generated CMOS color bars are recreated from
source. No camera-installable update package or flash writer is supplied.

See `z7-qemu/NOTICE.md`, `z7-qemu/COPYING`, and the license/notices inside
`z7-firmware-extensions/`. Their respective licenses apply to their components;
no license here grants rights over Nikon firmware.
