# Z7 V4 photo-monitor display

V4 adds remaining charge inside the battery icon on the original Nikon Z7 C 3.80 photo monitor. The display uses the native BatteryCheckService reading and draws 11×19 glyphs with four coverage levels. At 20% and below, the numerals and battery frame are red. The camera draws its original icon when the active battery reading is unavailable.

The Type A horizon uses white fills and one-pixel black outlines. The roll and pitch strokes are both five pixels wide, and each fill turns green at its own level position. Each pitch stroke is 27 pixels long with a 31-pixel center gap on the 720×480 monitor canvas. The pitch strokes move about 25 pixels at 10° and reach roughly 37 pixels from center at 15°.

Use the [local build procedure](../README.md#build-v4-on-linux-or-wsl) with a new output directory. V3's source remains on `main` at `f779db4`. Its hashes and hardware report are in the [V3 notes](../DISPLAY_TYPE_A.md).

V4 changes the MAIN engine's monitor drawing code. The battery feature handles the native LCD battery icon submission at `0x10430256` and reads the active slot from the camera's battery service. The horizon shares the existing paint and clear entry points.

Validation covers the LCD in photo mode. Isolated ARM execution checks the exact stroke widths, fill colors, invalid-read fallback, and both battery slots. QEMU runs the native monitor and uses synthetic battery samples. Camera hardware validation is pending.

The battery feature follows the approach documented in the Z5 project. The Z7 drawing and battery-service integration are implemented against the Z7 interfaces. [Z5 battery implementation](https://github.com/WonderLantern/wonder-lantern-z5/blob/cfa33e7d1f67439bf443606db321f67f8f2bf7bf/src/card_module/vui_card.inc#L1524-L1580)
