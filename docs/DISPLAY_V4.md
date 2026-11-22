# Z7 V4 photo-monitor display

V4 adds remaining charge inside the battery icon on the original Nikon Z7 C 3.80 photo monitor. The display uses the native BatteryCheckService reading and draws 11×19 glyphs with four coverage levels. The digit 1 follows the stock shooting readout's short flag and unfooted stem. At 20% and below, the numerals and battery frame are red. The camera draws its original icon when the active battery reading is unavailable.

The Type A horizon follows the 720×480 Z8 C 3.12 monitor profile. The fixed guides and roll stroke have a 120×120 center cutout. The pitch segments rotate with the roll angle and use the pitch channel selected by the camera's orientation. The foreground is two pixels wide over a four-pixel translucent backing. Each axis turns green independently after rounding to whole degrees. Pitch travel reaches 58 pixels at 30°. The display becomes visible below 55° and stays visible through 60°.

Use the [local build procedure](../README.md#build-v4-on-linux-or-wsl) with a new output directory. The source for V3 is available at commit `f779db4`. Its hashes and hardware report are in the [V3 notes](../DISPLAY_TYPE_A.md).

V4 changes the MAIN engine's monitor drawing code. The battery feature handles the native LCD battery icon submission at `0x10430256` and reads the active slot from the camera's battery service. The horizon shares the existing paint and clear entry points.

The battery feature follows the approach documented in the Z5 project. The Z7 drawing and battery-service integration are implemented against the Z7 interfaces. [Z5 battery implementation](https://github.com/WonderLantern/wonder-lantern-z5/blob/cfa33e7d1f67439bf443606db321f67f8f2bf7bf/src/card_module/vui_card.inc#L1524-L1580)

## Verification

On 2026-11-23, the author reported successfully installing V4 on a Nikon Z7 and confirmed that it worked as expected.

Emulator validation covers the LCD in photo mode. Isolated ARM execution compares the Z7 line coordinates with stock Z8 AArch64 widget outputs. Z7 QEMU runs the native monitor with synthetic pose, image and battery inputs. The six histogram comparisons against stock Z7 produced zero differing pixels in the histogram region. [Validation summary](../evidence/v4-validation.json) · [Nikon Z8 d17](https://onlinemanual.nikonimglib.com/z8/en/csmd_virtual_horizon_type_247.html)

- [Type A horizon and histogram](../evidence/qemu-type-a-histogram.png)
- [Type A horizon in portrait orientation](../evidence/qemu-type-a-portrait.png)
- [100% battery reading](../evidence/qemu-battery-100.png)
