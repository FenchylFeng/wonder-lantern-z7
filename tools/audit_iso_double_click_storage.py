"""Replay Z7 f8 choices, the original save worker and fresh settings startup."""

import argparse
import gc
import json
from pathlib import Path
import struct
import sys

from audit_grid_native_value import NativeValueGrid, WORKER_STATE
from audit_splash_image import MEM, STACK, STOP
from unicorn.arm_const import UC_ARM_REG_SP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "z7-qemu/tools"))
sys.path.insert(0, str(ROOT / "z7-firmware-extensions/src"))
from firmware_input import validate_firmware
from z30_extensions.container import extract_eg
from z30_extensions.features.iso_double_click_z7 import STATE
from z30_extensions.features.iso_double_click_menu_z7 import AF_LABEL, LABEL


class IsoSettings(NativeValueGrid):
    def __init__(self, image, journal=None, failure=None):
        super().__init__(image, journal=journal, failure=failure)
        self.initialize()

    def startup(self):
        self.call(0x10117594)

    def run_queued_save(self):
        self.u.mem_write(WORKER_STATE + 4, struct.pack("<I", 0x10117851))
        self.u.mem_write(WORKER_STATE + 12, struct.pack("<I", 1))
        self.worker = True
        self.u.reg_write(UC_ARM_REG_SP, STACK)
        self.u.emu_start(0x1011774D, STOP, timeout=10000000, count=10000000)
        return self.worker_finished and self.word(WORKER_STATE + 12) == 0

    def marker(self, address):
        return struct.unpack("<H", self.u.mem_read(address, 2))[0]

    def select(self, action):
        self.u.mem_write(STATE, struct.pack("<I", 2))
        self.call(action)
        return self.word(STATE) == 0


def audit(stock, candidate, menu, *, af_on=False):
    checks = []

    def check(name, result):
        checks.append(dict(name=name, passed=bool(result)))

    on, off = (int(menu["actions"][name], 16) for name in ("on", "off"))
    enter = int(menu["open"], 16)
    record_index = menu["journal_record"]
    preference = int(menu["preference"], 16)
    marker = int(menu["on_marker"], 16)
    on_control, off_control = menu["control_ids"]
    offset = preference - 0xA24F24F8
    resource = AF_LABEL if af_on else LABEL
    titles = ("Use AF-C with AF-ON", "AF-ON对焦使用AF-C") if af_on else (
        "ISO button double-click", "连按ISO按钮切换ISO AUTO")

    # Start from an original journal that has never seen f8.
    fixture = IsoSettings(stock)
    fixture.save_worker()
    stock_banks = fixture.journal()
    original_records = fixture.payloads()
    del fixture
    gc.collect()

    fixture = IsoSettings(candidate, stock_banks)
    fixture.startup()
    check("stock-journal-first-use-defaults-to-off", fixture.marker(preference) == 0 and not fixture.operations)
    fixture.call(enter, MEM)
    check("menu-marks-off", fixture.marks == [(off_control, 1)])
    text_out = MEM + 0x30
    for language, expected in zip((1, 8), titles):
        fixture.u.mem_write(0xA180F1B8, struct.pack("<I", language))
        fixture.u.mem_write(text_out, struct.pack("<I", resource))
        resolved = fixture.call(0x104BD2B6, text_out)
        fixture.call(0x104BD4FC, resolved, fixture.word(text_out), text_out + 4, text_out + 8)
        actual = bytes(fixture.u.mem_read(fixture.word(text_out + 4),
                                          fixture.word(text_out + 8))).decode("utf-16-le")
        check(f"native-menu-text-{language}-{resource:x}", resolved == language and actual == expected)

    # Original group 0x11's neighbors write only their declared payloads.
    before = bytes(fixture.u.mem_read(preference - 2, 8))
    check("on-action-owns-only-its-gesture-state", fixture.select(on) == (not af_on))
    after = bytes(fixture.u.mem_read(preference - 2, 8))
    check("on-action-changes-only-padding", fixture.marker(preference) == marker
          and after[:2] == before[:2] and after[4:] == before[4:])
    if not af_on:
        original_byte = before[0]
        for value in (0x5A, original_byte):
            fixture.call(0x100704FA, 0x1185, value, MEM)
            check(f"native-one-byte-write-preserves-preference-{value}", fixture.marker(preference) == marker
                  and fixture.u.mem_read(preference - 2, 1)[0] == value)
    check("on-posts-one-native-save-request", fixture.events == [0x1000] and not fixture.operations)
    fixture.select(on)
    check("reselecting-on-does-not-post-a-second-request", fixture.events == [0x1000])
    check("native-worker-commits-queued-on", fixture.run_queued_save() and fixture.operations)
    on_banks = fixture.journal()
    on_records = fixture.payloads()
    expected_on = original_records.copy()
    record = expected_on[record_index]
    expected_on[record_index] = record[:offset] + struct.pack("<H", marker) + record[offset + 2:]
    check("on-changes-only-two-bytes-across-original-89-records", on_records == expected_on)
    del fixture
    gc.collect()

    for label, image in (("modified", candidate), ("stock", stock)):
        fixture = IsoSettings(image, on_banks)
        fixture.startup()
        check(f"{label}-fresh-startup-restores-all-89-records",
              fixture.marker(preference) == marker and fixture.payloads() == expected_on
              and fixture.word(WORKER_STATE) == 1 and not fixture.operations)
        if label == "modified":
            fixture.call(enter, MEM)
            check("reopened-menu-marks-on", fixture.marks == [(on_control, 1)])
            check("off-action-owns-only-its-gesture-state", fixture.select(off) == (not af_on))
            check("off-posts-one-native-save-request", fixture.marker(preference) == 0 and fixture.events == [0x1000])
            check("native-worker-commits-queued-off", fixture.run_queued_save() and fixture.operations)
            off_banks = fixture.journal()
        del fixture
        gc.collect()

    fixture = IsoSettings(candidate, off_banks)
    fixture.startup()
    check("fresh-startup-restores-off-and-all-original-records",
          fixture.payloads() == original_records and not fixture.operations)
    fixture.call(enter, MEM)
    check("reopened-menu-marks-off", fixture.marks == [(off_control, 1)])
    del fixture
    gc.collect()

    fixture = IsoSettings(candidate, on_banks, failure="program")
    fixture.startup()
    fixture.select(off)
    fixture.run_queued_save()
    failed_banks = fixture.journal()
    del fixture
    gc.collect()
    fixture = IsoSettings(candidate, failed_banks)
    fixture.startup()
    check("failed-program-preserves-last-committed-choice",
          fixture.marker(preference) == marker and fixture.payloads() == expected_on)
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.resolve().relative_to((ROOT / ".private").resolve())
    manifest = args.build / "display.json"
    main_payload = args.build / "display.emulator.main.bin"
    validate_firmware(main_payload, manifest, args.source)
    report = json.loads(manifest.read_text(encoding="utf-8"))
    stock = extract_eg(args.source.read_bytes())[:-2]
    payload = main_payload.read_bytes()
    checks = audit(stock, payload, report["features"]["iso_double_click"]["menu"])
    if "af_on_af_c" in report["features"]:
        checks = [dict(check, setting="f8") for check in checks]
        checks += [dict(check, setting="f9") for check in
                   audit(stock, payload, report["features"]["af_on_af_c"]["menu"], af_on=True)]
    result = dict(main_payload_sha256=report["main_payload_sha256"],
                  scope="Native ARM startup, journal and worker with supplied in-memory flash and OS boundaries",
                  checks=checks, passed=all(check["passed"] for check in checks))
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(f"{sum(check['passed'] for check in checks)}/{len(checks)} shortcut preference checks passed")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
