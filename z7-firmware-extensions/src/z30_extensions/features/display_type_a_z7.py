"""Build the original Z7 C 3.80 four-grid and Type A monitor experiment."""

import hashlib
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
from unittest.mock import patch

from ..assembly import assemble, constant, invoke, jump
from ..container import Z7_CONTAINER_SHA256, extract_eg
from ..plan import Plan
from ..platform import z7_380
from . import grid_z7, liveview_dual
from .grid_z7 import tail

FOUR_GRID_MAIN_SHA256 = "574932a48ee213989b8ef57e63b38df2d208ab5d7a40624bbc4fde90dda22498"
HORIZON_SITES = (
    (0x104663A2, "2de9f8437e487d4d2030", "horizon_paint"),
    (0x10465C34, "81487cb504780025", "horizon_clear"),
)


def _append_renderer(plan, clang, lld):
    address = plan.address
    with tempfile.TemporaryDirectory(prefix="z7-type-a-") as directory:
        work = Path(directory)
        layout, obj, image = (work / name for name in ("horizon.ld", "horizon.o", "horizon.bin"))
        layout.write_text(f"""ENTRY(paint_horizon)
SECTIONS {{
 . = {address:#x};
 .entries : {{ LONG(paint_horizon & ~1); LONG(clear_horizon & ~1); }}
 .text : {{ *(.text.paint) . = ALIGN(4); *(.text.clear) *(.text*) }}
 .rodata : {{ *(.rodata*) }}
 /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.ARM.attributes*) }}
}}
""", encoding="ascii")
        subprocess.run([clang, "--target=arm-none-eabi", "-mcpu=cortex-a15", "-mthumb",
                        "-mfloat-abi=soft", "-Os", "-ffreestanding", "-fno-builtin",
                        "-Wall", "-Wextra", "-Werror", "-c",
                        Path(__file__).with_suffix(".c"), "-o", obj], check=True)
        subprocess.run([lld, "-T", layout, "--oformat=binary", obj, "-o", image], check=True)
        binary = image.read_bytes()
    entries = struct.unpack_from("<2I", binary)
    if not all(address + 8 <= entry < address + len(binary) and entry % 4 == 0 for entry in entries):
        raise ValueError("Unexpected virtual-horizon entry offsets")
    plan.alloc(binary)
    return entries


def _install(plan, address, expected, name, code):
    target = plan.alloc(assemble(code, plan.address, 512))
    plan.edit(address, jump(address, target, len(expected)), name, expected)


def _instructions(plan, address, expected):
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

    code = plan.image.read(address, len(expected))
    if code != expected:
        raise ValueError(f"Unexpected source instruction window at {address:#x}")
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    decoder.detail = True
    instructions = list(decoder.disasm(code, address))
    if sum(insn.size for insn in instructions) != len(expected):
        raise ValueError(f"Incomplete source instruction window at {address:#x}")
    return instructions


def _literal(plan, insn):
    from capstone.arm import ARM_OP_MEM, ARM_REG_PC

    if insn.mnemonic == "ldr" and insn.operands[1].type == ARM_OP_MEM:
        operand = insn.operands[1].mem
        if operand.base == ARM_REG_PC:
            return plan.image.words(((insn.address + 4) & ~3) + operand.disp, 1)[0]
    return None


def _replay(plan, instructions, branch=None):
    """Relocate the checked windows from the user's local image."""
    from capstone import CS_GRP_JUMP

    source = []
    for insn in instructions:
        value = _literal(plan, insn)
        if value is not None:
            source.append(constant(insn.reg_name(insn.operands[0].reg), value))
        elif insn.group(CS_GRP_JUMP):
            if branch is None or insn.operands[-1].imm != branch[0]:
                raise ValueError(f"Unexpected branch at {insn.address:#x}")
            prefix = insn.op_str.rsplit(",", 1)[0] + "," if "," in insn.op_str else ""
            source.append(f"{insn.mnemonic} {prefix}{branch[1]};")
        else:
            source.append(".byte " + ",".join(map(str, insn.bytes)) + ";")
    return " ".join(source)


def _histogram(plan):
    spec = liveview_dual.SPECS["z7"]
    if plan.image.words(spec["binding"], 1) != (spec["histogram"],):
        raise ValueError("Unexpected native histogram binding")
    gates = (
        (spec["gate"], spec["gate_expected"], 0x103EBB7A, 0x103EBBA0),
        (spec["widget_gate"], spec["widget_expected"], 0x1036D594, 0x1036D59C),
    )
    for index, (address, expected, yes, no) in enumerate(gates):
        code = liveview_dual.gate_code(plan.address, index == 0, yes, no,
                                       spec["snapshot"], spec["ldrb_cmp"])
        target = plan.alloc(code)
        plan.edit(address, jump(address, target, len(expected)), "Histogram DISP 2 and 3 gate", expected)
    masks = spec["masks_expected"]
    plan.edit(spec["histogram"] + 4, struct.pack("<9I", *(mask | mask << 1 for mask in masks)),
              "Histogram visibility on both DISP pages", struct.pack("<9I", *masks))
    rect, baseline, bounds = 0xA18273DE, 0x102F1670, (475, 269, 675, 370)
    if (plan.image.read(rect, 8) != struct.pack("<4h", *bounds)
            or plan.image.read(baseline, 12) != bytes.fromhex("bdf80a00adf806101044401a")):
        raise ValueError("Unexpected native histogram geometry or bar drawing")
    plan.features["histogram"] = dict(display_states=[2, 3], lcd_bounds=list(bounds),
                                      rect=hex(rect), baseline_site=hex(baseline))


def _horizon_page(plan):
    address, expected = 0x1037062A, bytes.fromhex("90f88a01083d2c5c022c")
    ops = _instructions(plan, address, expected)
    _install(plan, address, expected, "Insert LCD horizon-only DISP state", f"""
        {_replay(plan, ops[:2])}
        cmp r0,#5; beq info;
        {_replay(plan, ops[2:3])} cmp r0,#3; bne next;
        {constant('r2', 0xA18237C6)} ldrb r2,[r2]; cbnz r2,next;
        {constant('r2', 0xA18293E4)} ldrb r2,[r2]; cmp r2,#1; bne next;
        movs r4,#5; b next;
        info: movs r4,#4;
        next: {_replay(plan, ops[3:])} {tail(address + len(expected))}
    """)

    # Page 5 shares the native horizon widgets. Histogram gates see state 5.
    readers = (
        (0x102F289C, "1a4890f88a0140b1", 2, 0x102F28B6),
        (0x102F2994, "e84890f88a0160b1", 2, 0x102F29B6),
        (0x102F2700, "92f88a21dcb1032c", 1, 0x102F273E),
        (0x102F28EE, "90f88a01012b0ad0012a", 1, 0x102F290C),
        (0x102F2940, "90f88a0158b10128", 1, 0x102F295E),
        (0x102F5AC8, "90f88a11032973d1", 1, 0x102F5BB8),
        (0x1033778C, "90f88a01032803d1", 1, 0x1033779C),
        (0x1036831C, "96f88a01032808d1", 1, 0x10368336),
        (0x1036DCA8, "95f88a0103285ed1", 1, 0x1036DD6E),
        (0x1036E01C, "95f88a21012a1bd0", 1, 0x1036E05C),
        (0x1036E8B2, "90f88a0148b1012807d0", 1, 0x1036E8CC),
        (0x1036E9E8, "92f88a215ab1012a", 1, 0x1036EA06),
    )
    for address, window, prefix, alternate in readers:
        expected = bytes.fromhex(window)
        ops = _instructions(plan, address, expected)
        load = ops[prefix - 1]
        register = load.reg_name(load.operands[0].reg)
        name = "Use horizon visibility mask on DISP 5" if prefix == 2 else "Reuse native horizon widgets on DISP 5"
        _install(plan, address, expected, name, f"""
            {_replay(plan, ops[:prefix])} cmp {register},#5; it eq; moveq {register},#3;
            {_replay(plan, ops[prefix:], (alternate, 'alternate'))}
            {tail(address + len(expected))}
            alternate: {tail(alternate)}
        """)

    address, expected = 0x1036913C, bytes.fromhex("032923d110bb0c20")
    ops = _instructions(plan, address, expected)
    skip = 0x10369188
    _install(plan, address, expected, "Invalidate native horizon on DISP 5 entry", f"""
        cmp r1,#5; beq is_horizon; {_replay(plan, ops[:2], (skip, 'skip'))}
        is_horizon: {_replay(plan, ops[2:], (skip, 'skip'))} {tail(address + len(expected))}
        skip: {tail(skip)}
    """)


def _horizon(plan, clang, lld):
    entries = _append_renderer(plan, clang, lld)
    for (address, window, name), entry in zip(HORIZON_SITES, entries, strict=True):
        expected = bytes.fromhex(window)
        ops = _instructions(plan, address, expected)
        if name == "horizon_paint":
            if _literal(plan, ops[1]) != _literal(plan, ops[2]):
                raise ValueError("Unexpected native horizon controller references")
            stock = _replay(plan, ops[:2]) + " mov r5,r0; " + _replay(plan, ops[3:])
        else:
            stock = _replay(plan, ops)
        _install(plan, address, expected, name + " Type A LCD", f"""
            push.w {{r0-r5,r12,lr}}; {invoke(entry)} cbz r0,original;
            add sp,#4; pop.w {{r1-r5,r12,pc}};
            original: pop.w {{r0-r5,r12,lr}}; {stock}
            {tail(address + len(expected))}
        """)
    _horizon_page(plan)
    plan.features["horizon"] = dict(style="Type A-inspired central axes", output="shooting LCD 720x480",
                                    paint=hex(entries[0]), clear=hex(entries[1]),
                                    display_states=[3, 5], roll_degrees=360, cycle=[0, 1, 2, 3, 5, 4])


def build(container, llvm_bin=None):
    if hashlib.sha256(container).hexdigest() != Z7_CONTAINER_SHA256:
        raise ValueError("Requires the exact original Nikon Z7 C 3.80 update file")
    clang, lld = (shutil.which(name, path=str(llvm_bin) if llvm_bin is not None else None)
                  for name in ("clang", "ld.lld"))
    if not clang or not lld:
        raise ValueError("Install Clang and LLD, or supply their bin directory")
    stock = extract_eg(container)
    grid, _ = grid_z7.build(stock, native_choice=True, four_grids=True)
    if hashlib.sha256(grid[:-2]).hexdigest() != FOUR_GRID_MAIN_SHA256:
        raise ValueError("Unexpected four-grid baseline")

    class DisplayPlan(Plan):
        def finish(self):
            _histogram(self)
            _horizon(self, clang, lld)
            return super().finish()

    with patch.object(grid_z7, "Plan", DisplayPlan):
        eg, report = grid_z7.build(stock, native_choice=True, four_grids=True)
    heap = grid_z7.HEAP_SITE - z7_380.BASE
    if eg[heap:heap + len(grid_z7.HEAP_EXPECTED)] != grid_z7.HEAP_EXPECTED:
        raise ValueError("Native heap initialization changed")
    report.update(preset="z7-inline-type-a-portrait-emulator-only", profile="type-a-portrait",
                  main_payload_sha256=hashlib.sha256(eg[:-2]).hexdigest())
    return eg, report
