"""Recognize two short body ISO presses in the Z7 C 3.80 shooting task."""

import re
import struct

from ..assembly import assemble, constant, invoke, jump
from .grid_z7 import tail


PRESET = "z7-inline-display-v4-iso-double-click"
PROFILE = "display-v4-iso-double-click"
HOOK = 0x1012C5AC
HOOK_BYTES = bytes.fromhex("6846fff788fedde91571")
STATE = 0xA29F8FD0
# Record 55 covers this aligned halfword between the one-byte property
# 0x1185 and the four-byte property 0x1186. Nikon's journal saves the gap.
PREFERENCE = 0xA24F2DD6
ON_MARKER = 0xB75A
TAP_MS = 250
PAIR_MS = 350
ISO_MASK = 0x20000000


def install_gesture(plan, af_on_handler=None):
    # Extend the existing boot zero-fill into the padding at the end of this
    # page. Four volatile gesture words precede the menu page pointer.
    scatter = 0x100340B0
    source, destination, length, zero_fill = (0x11F9D440, 0xA1901200, 0x10F7DCC, 0x10020088)
    if (plan.image.words(scatter, 4) != (source, destination, length, zero_fill)
            or destination + length != STATE - 4
            or plan.image.words(0x106342A4, 4) != (1, 1, 1, ISO_MASK)):
        raise ValueError("Unexpected Z7 boot zero-fill or ISO switch mapping")
    if (plan.image.words(0xA18C2190 + 55 * 12, 3)[:2] != (0xA24F24F8, 0x9A0)
            or plan.image.words(0x114D3F4C, 8)[:7]
            != (1, 1, PREFERENCE - 2, 0x114DFF7C, 3, 4, PREFERENCE + 2)):
        raise ValueError("Unexpected native journal padding for the ISO shortcut preference")
    state_size = 28 if af_on_handler else 20
    plan.edit(scatter + 8, struct.pack("<I", STATE + state_size - destination),
              "Initialize ISO gesture state and menu page pointer", struct.pack("<I", length))

    code = f"""
        /* The original report is on the shooting task's stack. */
        mov r0,sp;
        push.w {{r4-r8,lr}};
        sub sp,#8;
        mov r4,r0;
        {invoke(af_on_handler) if af_on_handler else ""}
        {constant('r5', STATE)}
        {constant('r0', PREFERENCE)} ldrh r0,[r0];
        movw r1,#{ON_MARKER}; cmp r0,r1; bne stock;

        /* A turn of either command dial or another switch change ends a pair. */
        ldr r0,[r4,#0x54]; ldr r1,[r4,#0x58]; orrs r0,r1;
        ldr r1,[r4,#0x5c]; orrs r0,r1; ldr r1,[r4,#0x60]; orrs r0,r1;
        ldr r1,[r4,#0x0c]; orrs r0,r1; ldr r1,[r4,#0x34]; orrs r0,r1;
        ldr r1,[r4,#0x48]; orrs r0,r1;
        ldr r1,[r4,#0x68]; orrs r0,r1; ldr r1,[r4,#0x70]; orrs r0,r1;
        ldr r1,[r4,#0x78]; orrs r0,r1; ldr r1,[r4,#0x80]; orrs r0,r1;
        ldr r1,[r4,#0x20]; bic r2,r1,#{ISO_MASK}; orrs r0,r2;
        bne cancel;
        tst r1,#{ISO_MASK}; beq stock;
        ldr r0,[r4,#0x24]; ldr r1,[r4,#0x28]; tst r0,r1;
        bne cancel;

        /* Require the shooting view and the stock dial worker's eligibility. */
        {invoke(0x10406238)} cmp r0,#0; bne cancel;
        movs r0,#5; movs r1,#0; {invoke(0x1012978C)}
        cmp r0,#0; beq cancel;
        movs r0,#5; {invoke(0x10129908)}
        cmp r0,#0; beq cancel;
        movs r0,#2; {invoke(0x1015BA56)} mov r6,r0;
        subs r0,#0x1d; cmp r0,#3; bhi cancel;
        movw r0,#0x138d; {invoke(0x1015BA56)}
        cmp r0,#1; bhi cancel; bne mode_ready;
        cmp r6,#0x20; bne cancel;
        orr r6,r6,#0x100;

        mode_ready:
        mov r0,sp; {invoke(0x101F50CC)}
        ldr.w r8,[sp,#4];
        ldr r7,[r5];
        ldr r0,[r4,#0x18]; tst r0,#{ISO_MASK}; beq release;

        /* Phase 1 is the first press, 2 waits for the second, 3 is the second press. */
        movs r0,#1;
        cmp r7,#2; bne press;
        ldr r1,[r5,#12]; cmp r1,r6; bne press;
        ldr r1,[r5,#8]; sub.w r1,r8,r1; cmp r1,#{PAIR_MS}; bhi press;
        movs r0,#3;
        press:
        str r0,[r5]; str.w r8,[r5,#4]; str r6,[r5,#12];
        b stock;

        release:
        cmp r7,#1; beq check_tap;
        cmp r7,#3; bne stock;
        check_tap:
        ldr r1,[r5,#12]; cmp r1,r6; bne cancel;
        ldr r1,[r5,#4]; sub.w r1,r8,r1; cmp r1,#{TAP_MS}; bhi cancel;
        {constant('r0', 0xA1815CED)} ldrb r0,[r0]; cmp r0,#5; bne cancel;
        cmp r7,#3; bne first_release;
        ldr r1,[r5,#8]; sub.w r1,r8,r1; cmp r1,#{PAIR_MS}; bhi first_release;

        /* Use the same settings service as the stock On and Off menu rows. */
        movs r0,#0; str r0,[r5];
        movw r7,#0x508; tst r6,#0x100; beq read_auto_iso;
        movw r7,#0xb07;
        read_auto_iso:
        mov r0,r7; {invoke(0x104065A4)} cmp r0,#1; bhi stock;
        eor r1,r0,#1; mov r0,r7; {invoke(0x104065B0)}
        b stock;

        first_release:
        movs r0,#2; str r0,[r5]; str.w r8,[r5,#8];
        b stock;
        cancel:
        movs r0,#0; str r0,[r5];
        stock:
        add sp,#8;
        pop.w {{r4-r8,lr}};
        mov r0,sp; {invoke(0x1012C2C2)}
        ldrd r7,r1,[sp,#0x54];
        {tail(HOOK + len(HOOK_BYTES))}
    """
    target = plan.alloc(assemble(re.sub(r"/\*.*?\*/", "", code, flags=re.S), plan.address, 512))
    plan.edit(HOOK, jump(HOOK, target, len(HOOK_BYTES)), "Recognize a double click of the body ISO button", HOOK_BYTES)
    plan.features["iso_double_click"] = dict(
        input_hook=hex(HOOK), handler=hex(target), volatile_state=hex(STATE),
        tap_ms=TAP_MS, pair_ms=PAIR_MS,
        setting_ids={"photo": "0x508", "movie_m": "0xb07"},
        settings_writer="0x104065b0")


def install(plan, af_on=False):
    from .af_on_af_c_z7 import install_input
    from .iso_double_click_menu_z7 import install_menu

    install_gesture(plan, install_input(plan) if af_on else None)
    install_menu(plan, af_on=af_on)
