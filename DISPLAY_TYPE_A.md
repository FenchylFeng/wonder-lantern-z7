# Z7 Type A monitor experiment

On the original Nikon Z7 C 3.80 photo monitor, d9 offers Off, 4x4, 3x3, and 2x2.
DISP advances from the histogram to the combined histogram and horizon, then
to the horizon-only view and the shooting information page. The fixed cross
stays in monitor coordinates. The pitch strokes rotate with the full roll
angle and move along the upward normal as pitch changes.

## Build from a local official update

Install Python 3.12 and Clang/LLD. Supply your own unmodified
`Z_7_0380.bin` from [Nikon](https://downloadcenter.nikonimglib.com/en/download/fw/558.html).
The tool checks its SHA-256 before extracting the main-engine module locally.
The verified build used Clang and LLD 23.1.5.

```sh
python -m pip install -e "./z7-firmware-extensions[type-a]"
python tools/build_display_type_a.py --source /path/to/Z_7_0380.bin --output .private/build/type-a
```

Use `--llvm-bin` to select an LLVM bin directory. Choose a new output directory
for each build. The EG contains the main-engine payload and its CRC. MAIN is
the corresponding QEMU input. Keep both files and the detailed build manifest
private.

| Output | SHA-256 |
| --- | --- |
| EG | `e91fd4056d303d9e9785b5a149d4df36473d04f222cf73604657f62ceb65c5a8` |
| MAIN | `915d128d63e6a7e20e1822119f87030fbf174022e76536cff05ec0681610bba0` |

The matching image passed 74 isolated ARM checks and 50 QEMU photo-monitor
checks, including both portrait orientation states and the full DISP cycle.
The tests supplied simulated photo, histogram and pose data. Installation and
boot on a physical camera remain unverified for this exact image.

## Sources and licenses

- The grid and composition code builds on
  [tylermcm/WonderLanternZ7](https://github.com/tylermcm/WonderLanternZ7/tree/a99e5da7c41dd5931c35faa7287fa04dcc847ebc)
  and its vendored [Z7 firmware extensions and QEMU revisions](UPSTREAMS.json).
  The [extension license](z7-firmware-extensions/LICENSE) and
  [third-party notices](z7-firmware-extensions/THIRD_PARTY_NOTICES.md)
  describe the source and license of each affected component.
- The GPU row-order change modifies the
  [GPL-licensed QEMU overlay](z7-qemu/NOTICE.md) for QEMU 10.2.4.
  Build it using the existing [QEMU instructions](z7-qemu/docs/build.md).
- [Keystone 0.9.2](https://github.com/keystone-engine/keystone/tree/0.9.2) and
  [Capstone 5.0.7](https://github.com/capstone-engine/capstone/tree/5.0.7) are
  installed as separate Python dependencies.
  [LLVM](https://llvm.org/) Clang and LLD compile and link the ARM renderer locally.
- [Wonder Lantern Z5](https://github.com/WonderLantern/wonder-lantern-z5) and the
  [Nikon Type A manual](https://onlinemanual.nikonimglib.com/z5II/en/csmd_virtual_horizon_type_246.html)
  were feature references.
