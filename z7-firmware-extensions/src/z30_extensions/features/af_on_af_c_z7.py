"""Apply AF-C while the body AF-ON button is held on the Z7 C 3.80."""

from ..assembly import assemble, constant, invoke, jump
from .iso_double_click_z7 import STATE as ISO_STATE

PRESET = "z7-inline-display-v4-af-on-af-c"
PROFILE = "display-v4-af-on-af-c"
STATE = ISO_STATE + 24
PAGE_POINTER = ISO_STATE + 20
PREFERENCE = 0xA24F2DCE
ON_MARKER = 0xC76D
AF_ON_MASK = 0x00200000
AF_ON_HELD = 0x04
AF_ON_PRESSED = 0x10
FOCUS_MODE = 0x567
AF_S, AF_C = 1, 2


def install_input(plan):
    # The f2 and g2 AF-ON assignment properties select the native action
    # for this bank-zero button. The stock queue already forwards its edges.
    if (plan.image.words(0xA18160FC, 3) != (AF_ON_MASK, 2, 0x1050)
            or plan.image.words(0xA1816354, 3) != (AF_ON_MASK, 2, 0x107D)
            or not plan.image.words(0x10130130, 1)[0] & AF_ON_MASK
            or plan.image.words(0x114D3F2C, 7)
            != (8, 0x21, 0xA24F2DAC, 0x114DFF54, 7, 4, 0xA24F2DD0)
            or plan.image.words(0x114D19AC, 4)[:3] != (7, 4, 0xA24E33F4)):
        raise ValueError("Unexpected Z7 AF-ON switch, focus mode or settings padding")

    # The shooting task owns this state. Keep ownership until the original
    # settings service confirms the transition back to AF-S.
    code = f"""
        push {{r4-r6,lr}};
        mov r6,r0;
        {constant('r4', STATE)}
        ldr r5,[r4];
        ldr r0,[r6,#{AF_ON_HELD}]; tst r0,#{AF_ON_MASK}; beq restore;
        {constant('r0', PREFERENCE)} ldrh r0,[r0];
        movw r1,#{ON_MARKER}; cmp r0,r1; bne restore;
        {invoke(0x10406238)} cmp r0,#0; bne restore;
        movw r0,#0x138d; {invoke(0x1015BA56)} cmp r0,#1; bne photo;
        movw r0,#0xb29; b mode_ready;
        photo: cmp r0,#0; bne restore; movw r0,#{FOCUS_MODE};
        mode_ready:
        cmp r5,#0; bne held;
        ldr r1,[r6,#{AF_ON_PRESSED}]; tst r1,#{AF_ON_MASK}; beq done;
        mov r5,r0; {invoke(0x104065A4)} cmp r0,#{AF_S}; bne done;
        mov r0,r5; movs r1,#{AF_C}; {invoke(0x104065B0)}
        cmp r0,#1; bne done; str r5,[r4]; b done;
        held: cmp r5,r0; beq done;
        restore:
        cmp r5,#0; beq done;
        mov r0,r5; {invoke(0x104065A4)} cmp r0,#{AF_C}; bne clear;
        mov r0,r5; movs r1,#{AF_S}; {invoke(0x104065B0)}
        cmp r0,#1; bne done;
        clear: movs r0,#0; str r0,[r4];
        done: pop {{r4-r6,pc}};
    """
    handler = plan.alloc(assemble(code, plan.address, 256))
    plan.features["af_on_af_c"] = dict(
        handler=hex(handler), state=hex(STATE), switch_bank=0, switch_mask=hex(AF_ON_MASK),
        focus_mode={"photo": hex(FOCUS_MODE), "movie": "0xb29", "af_s": AF_S, "af_c": AF_C},
    )
    return handler
