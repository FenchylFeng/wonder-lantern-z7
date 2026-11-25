"""Run the assembled Thumb gesture with synthetic switch reports and native ABI stubs."""

import importlib.util
import struct
import unittest
from types import SimpleNamespace

from z30_extensions.features import af_on_af_c_z7 as af
from z30_extensions.features.iso_double_click_z7 import (
    HOOK, HOOK_BYTES, ISO_MASK, ON_MARKER, PREFERENCE, STATE, install_gesture,
)


@unittest.skipUnless(all(importlib.util.find_spec(name) for name in ("unicorn", "keystone")),
                     "requires the type-a and verify extras")
class IsoDoubleClickTests(unittest.TestCase):
    def setUp(self):
        from unicorn import Uc, UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_THUMB
        from unicorn import arm_const

        self.arm = arm_const
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        self.stack = 0x20000800
        self.settings = {2: 0x1D, 0x138D: 0, 0x508: 1, 0xB07: 1,
                         af.FOCUS_MODE: af.AF_S, 0xB29: af.AF_S}
        self.permitted = True
        self.menu_depth = 0
        self.clock = 0
        self.writes = []
        self.stock_reports = []
        self.calls = {
            0x1012978C: lambda: int(self.permitted),
            0x10129908: lambda: int(self.permitted),
            0x101F50CC: self.write_clock,
            0x1015BA56: self.read_setting,
            0x10406238: lambda: self.menu_depth,
            0x104065A4: self.read_setting,
            0x104065B0: self.write_setting,
            0x1012C2C2: self.stock_report,
        }
        entry = 0x11FA8000
        pages = {address & ~0xFFF for address in (
            *self.calls, HOOK, entry, STATE, PREFERENCE, self.stack, 0xA1815CED,
        )}
        for page in pages:
            self.uc.mem_map(page, 0x1000)
        self.uc.mem_write(0xA1815CED, b"\x05")
        self.uc.hook_add(UC_HOOK_CODE, self.native_call)
        expected_words = {
            0x100340B0: (0x11F9D440, 0xA1901200, 0x10F7DCC, 0x10020088),
            0x106342A4: (1, 1, 1, ISO_MASK),
            0xA18C2190 + 55 * 12: (0xA24F24F8, 0x9A0, 0),
            0x114D3F4C: (1, 1, PREFERENCE - 2, 0x114DFF7C, 3, 4, PREFERENCE + 2, 0x114DFF80),
            0xA18160FC: (0x00200000, 2, 0x1050),
            0xA1816354: (0x00200000, 2, 0x107D),
            0x10130130: (0x00204400,),
            0x114D3F2C: (8, 0x21, 0xA24F2DAC, 0x114DFF54, 7, 4, 0xA24F2DD0),
            0x114D19AC: (7, 4, 0xA24E33F4, 0),
        }

        def alloc(code):
            self.uc.mem_write(entry, code)
            return entry

        def edit(address, code, _name, _expected):
            if address == HOOK:
                self.uc.mem_write(address, code)

        image = SimpleNamespace(words=lambda a, _n: expected_words[a])
        af_entry = entry + 0x200

        def allocate_af(code):
            self.uc.mem_write(af_entry, code)
            return af_entry

        handler = af.install_input(SimpleNamespace(address=af_entry, image=image,
                                                   alloc=allocate_af, features={}))
        install_gesture(SimpleNamespace(address=entry, image=image, alloc=alloc, edit=edit, features={}),
                        handler)

    def native_call(self, uc, address, _size, _data):
        if address in self.calls:
            result = self.calls[address]()
            uc.reg_write(self.arm.UC_ARM_REG_R0, result)
            uc.reg_write(self.arm.UC_ARM_REG_PC, uc.reg_read(self.arm.UC_ARM_REG_LR))

    def write_clock(self):
        address = self.uc.reg_read(self.arm.UC_ARM_REG_R0)
        self.uc.mem_write(address, struct.pack("<II", 0, self.clock & 0xFFFFFFFF))
        return 0

    def read_setting(self):
        return self.settings[self.uc.reg_read(self.arm.UC_ARM_REG_R0)]

    def write_setting(self):
        key = self.uc.reg_read(self.arm.UC_ARM_REG_R0)
        value = self.uc.reg_read(self.arm.UC_ARM_REG_R1)
        self.settings[key] = value
        self.writes.append((key, value))
        return 1

    def stock_report(self):
        address = self.uc.reg_read(self.arm.UC_ARM_REG_R0)
        self.assertEqual(address, self.stack)
        self.stock_reports.append(bytes(self.uc.mem_read(address, 0x150)))
        return 0

    def report(self, when, held, *, changed=None, other=0, dial=0, mask=ISO_MASK, bank=1):
        self.clock = when
        data = bytearray(0x150)
        if changed is None:
            changed = mask
        struct.pack_into("<5I", data, (0x04, 0x18)[bank], mask if held else 0, 0, changed,
                         changed if held else 0, 0 if held else changed)
        struct.pack_into("<I", data, 0x0C, other | struct.unpack_from("<I", data, 0x0C)[0])
        struct.pack_into("<I", data, 0x54, dial)
        self.uc.mem_write(self.stack, bytes(data))
        self.uc.reg_write(self.arm.UC_ARM_REG_SP, self.stack)
        continuation = HOOK + len(HOOK_BYTES)
        calls_before = len(self.stock_reports)
        self.uc.emu_start(HOOK | 1, continuation, count=500)
        self.assertEqual(self.uc.reg_read(self.arm.UC_ARM_REG_PC), continuation)
        self.assertEqual(self.uc.reg_read(self.arm.UC_ARM_REG_SP), self.stack)
        self.assertEqual(self.uc.reg_read(self.arm.UC_ARM_REG_R7), dial)
        self.assertEqual(self.stock_reports[calls_before:], [data])

    def tap(self, start, hold=60):
        self.report(start, True)
        self.report(start + hold, False)

    def enable(self):
        self.uc.mem_write(PREFERENCE, struct.pack("<H", ON_MARKER))

    def af_on(self, held, *, changed=None):
        self.report(0, held, mask=0x00200000, changed=changed, bank=0)

    def test_af_on_immediate_and_release(self):
        self.af_on(True)
        self.af_on(False)
        self.assertEqual(self.writes, [])
        self.uc.mem_write(af.PREFERENCE, struct.pack("<H", af.ON_MARKER))
        self.report(0, True, mask=0x04000000)
        self.report(0, False, mask=0x04000000)
        self.assertEqual(self.writes, [])
        self.af_on(True)
        self.assertEqual(self.writes, [(af.FOCUS_MODE, af.AF_C)])
        self.af_on(True, changed=0)
        self.af_on(False)
        self.assertEqual(self.writes, [(af.FOCUS_MODE, af.AF_C), (af.FOCUS_MODE, af.AF_S)])

    def test_af_on_does_not_claim_existing_modes(self):
        self.uc.mem_write(af.PREFERENCE, struct.pack("<H", af.ON_MARKER))
        for mode in (0, af.AF_C):
            self.settings[af.FOCUS_MODE] = mode
            self.af_on(True)
            self.af_on(False)
            self.assertEqual(self.settings[af.FOCUS_MODE], mode)
        self.assertEqual(self.writes, [])

    def test_af_on_preserves_explicit_focus_change_while_held(self):
        self.uc.mem_write(af.PREFERENCE, struct.pack("<H", af.ON_MARKER))
        self.af_on(True)
        self.settings[af.FOCUS_MODE] = 0
        self.af_on(False)
        self.assertEqual(self.writes, [(af.FOCUS_MODE, af.AF_C)])

    def test_af_on_restores_its_movie_or_photo_property_on_mode_change(self):
        self.uc.mem_write(af.PREFERENCE, struct.pack("<H", af.ON_MARKER))
        self.settings[0x138D] = 1
        self.af_on(True)
        self.settings[0x138D] = 0
        self.af_on(True, changed=0)
        self.af_on(False)
        self.assertEqual(self.writes, [(0xB29, af.AF_C), (0xB29, af.AF_S)])

    def test_af_on_menu_entry_releases_override_without_rearming(self):
        self.uc.mem_write(af.PREFERENCE, struct.pack("<H", af.ON_MARKER))
        self.af_on(True)
        self.menu_depth = 1
        self.af_on(True, changed=0)
        self.menu_depth = 0
        self.af_on(True, changed=0)
        self.af_on(False)
        self.assertEqual(self.writes, [(af.FOCUS_MODE, af.AF_C), (af.FOCUS_MODE, af.AF_S)])

    def test_missing_unrecognized_or_disabled_preference_ignores_double_clicks(self):
        for marker in (0, 1, 0xFFFF):
            with self.subTest(marker=marker):
                self.uc.mem_write(PREFERENCE, struct.pack("<H", marker))
                self.tap(0)
                self.tap(120)
                self.assertFalse(self.writes)
                self.assertEqual(bytes(self.uc.mem_read(STATE, 16)), bytes(16))

    def test_each_complete_pair_toggles_once(self):
        self.enable()
        self.tap(0)
        self.assertEqual(self.writes, [])
        self.tap(120)
        self.tap(240)
        self.assertEqual(self.writes, [(0x508, 0)])
        self.tap(360)
        self.assertEqual(self.writes, [(0x508, 0), (0x508, 1)])

    def test_thresholds_and_counter_wrap(self):
        self.enable()
        self.tap(0, hold=251)
        self.tap(300)
        self.tap(651)
        self.assertEqual(self.writes, [])
        self.tap(0xFFFFFF00, hold=250)
        self.tap(0x100000000 + 94, hold=0)
        self.assertEqual(self.writes, [(0x508, 0)])

    def test_other_switches_and_dials_cancel(self):
        self.enable()
        self.tap(0)
        self.report(120, True, other=2)
        self.report(180, False)
        self.tap(240)
        self.report(360, True)
        self.report(375, True, changed=0, dial=1)
        self.report(420, False)
        self.assertEqual(self.writes, [])

    def test_movie_manual_uses_its_own_setting(self):
        self.enable()
        self.tap(0)
        self.settings.update({2: 0x20, 0x138D: 1})
        self.tap(120)
        self.assertEqual(self.writes, [])
        self.tap(240)
        self.assertEqual(self.writes, [(0xB07, 0)])
        self.settings[2] = 0x1D
        self.tap(360)
        self.tap(480)
        self.assertEqual(self.writes, [(0xB07, 0)])

    def test_menu_ineligibility_and_invalid_setting_are_ignored(self):
        self.enable()
        self.menu_depth = 2
        self.tap(0)
        self.tap(120)
        self.menu_depth = 0
        self.permitted = False
        self.tap(240)
        self.tap(360)
        self.permitted = True
        self.settings[0x508] = 2
        self.tap(480)
        self.tap(600)
        self.assertEqual(self.writes, [])
