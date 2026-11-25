"""Add the ISO shortcut switch to the Z7 C 3.80 Custom Settings menu."""

import struct

from ..assembly import assemble, constant, invoke, jump
from . import af_on_af_c_z7 as af
from .grid_z7 import tail
from .iso_double_click_z7 import ON_MARKER, PREFERENCE, STATE


PARENT_PAGE = 0x127
PAGE = 0x1C62
ROW = 45
CONTROL = 0x7A44
ON_CONTROL, OFF_CONTROL = 0x7A45, 0x7A46
LABEL = 0x7A47
F8_BADGE = 0x76E
CONTROLS_BADGE_STYLE = 0x22
PAGE_POINTER = STATE + 16
AF_PAGE, AF_CONTROL, AF_LABEL, AF_BADGE = 0x1C63, 0x7A48, 0x7A4B, 0x76F
AF_CONTROLS = (0x7A49, 0x7A4A)


def _words(*words):
    return struct.pack(f"<{len(words)}I", *words)


def _assemble(plan, source):
    return plan.alloc(assemble(source, plan.address, 384))


def _hook(plan, site, expected, name, source):
    code = _assemble(plan, source)
    plan.edit(site, jump(site, code, len(expected)), name, expected)
    return code


def _events(plan, original, count, replacements):
    events = [plan.image.words(original + i * 16, 4) for i in range(count)]
    if events[-1] != (0x2F2, 0, 0, 0x3A0):
        raise ValueError("Unexpected native menu dispatch terminator")
    if not replacements.keys() <= {event[0] for event in events}:
        raise ValueError("Missing native menu dispatch event")
    return plan.alloc(b"".join(_words(*replacements.get(event[0], event)) for event in events))


def _install_label(plan, af_on):
    # Nikon resolves the resource and language before loading its UTF-16
    # bytes. Leave the style routines on their native fallback resource.
    english = "ISO button double-click".encode("utf-16-le")
    chinese = "连按ISO按钮切换ISO AUTO".encode("utf-16-le")
    en = plan.alloc(english + b"\0\0")
    zh = plan.alloc(chinese + b"\0\0")
    extra_style = ""
    extra_data = ""
    if af_on:
        af_english = "Use AF-C with AF-ON".encode("utf-16-le")
        af_chinese = "AF-ON对焦使用AF-C".encode("utf-16-le")
        af_en = plan.alloc(af_english + b"\0\0")
        af_zh = plan.alloc(af_chinese + b"\0\0")
        extra_data = f"""
        movw r12,#{AF_LABEL}; cmp r1,r12; bne original;
        cmp r0,#8; beq af_simplified;
        {constant('r12', af_en)} str.w r12,[r2]; mov.w r12,#{len(af_english)};
        b length;
        af_simplified:
        {constant('r12', af_zh)} str.w r12,[r2]; mov.w r12,#{len(af_chinese)};
        b length;
        """
        extra_style = f"beq custom_label; movw r3,#{AF_LABEL}; cmp r2,r3;"
    _hook(plan, 0x104BD22C, bytes.fromhex("fa4b4ff0000239b1"),
          "Style the shortcut label with native menu fonts", f"""
        cmp r1,#1; bne original;
        ldr r2,[r0]; movw r3,#{LABEL}; cmp r2,r3; {extra_style} bne original;
        custom_label:
        movw r2,#0x291; str r2,[r0];
        original:
        {constant('r3', 0xA180F1AC)} mov.w r2,#0; cbnz r1,check;
        {tail(0x104BD244)}
        check: {tail(0x104BD234)}
    """)
    _hook(plan, 0x104BD2B6, bytes.fromhex("38b50546d7480121c468"),
          "Keep the shortcut resource for native text lookup", f"""
        ldr r2,[r0]; movw r3,#{LABEL}; cmp r2,r3; {extra_style} bne original;
        custom_label:
        {constant('r0', 0xA180F1AC)} ldr r0,[r0,#12]; bx lr;
        original:
        push {{r3,r4,r5,lr}}; mov r5,r0;
        {constant('r0', 0xA180F1AC)} movs r1,#1; ldr r4,[r0,#12];
        {tail(0x104BD2C0)}
    """)
    return _hook(plan, 0x104BD4FC, bytes.fromhex("2de9ff4101211d46"),
                 "Supply the UTF-16 shortcut label", f"""
        movw r12,#{LABEL}; cmp r1,r12; bne {'other_label' if af_on else 'original'};
        cmp r0,#8; beq simplified;
        {constant('r12', en)} str.w r12,[r2]; mov.w r12,#{len(english)};
        b length;
        simplified:
        {constant('r12', zh)} str.w r12,[r2]; mov.w r12,#{len(chinese)};
        length: str.w r12,[r3]; bx lr;
        {'other_label:' if af_on else ''}
        {extra_data}
        original:
        push.w {{r0-r8,lr}}; movs r1,#1; mov r5,r3;
        {tail(0x104BD4FC + 8)}
    """)


def _install_page(plan, *, page=PAGE, label_id=LABEL, controls_ids=(ON_CONTROL, OFF_CONTROL),
                  preference=PREFERENCE, on_marker=ON_MARKER, pointer=PAGE_POINTER,
                  clear_gesture=True, defer_getter=False, alternate=None):
    im = plan.image
    obj = list(im.words(0xA1836F8C, 11))
    meta = list(im.words(obj[10], 7))
    callbacks = list(im.words(obj[4], 5))
    if (obj[0] != 0x01530002 or meta[5] != 0x20002
            or callbacks != [0x104EFA6B, 0, 0x1040525F, 0, 0]):
        raise ValueError("Unexpected original On/Off page")

    enter = _assemble(plan, f"""
        push {{r4-r6,lr}}; mov r5,r0;
        {constant('r0', preference)} ldrh r0,[r0]; movw r1,#{on_marker};
        movw r4,#{controls_ids[1]}; cmp r0,r1; bne selected;
        movw r4,#{controls_ids[0]};
        selected:
        {invoke(0x10405F00)} cmp r0,#1; beq mark;
        mov r0,r5; mov r1,r4; {invoke(0x10402BC2)}
        mark: mov r0,r5; mov r1,r4; movs r2,#1;
        pop.w {{r4-r6,lr}}; {tail(0x10404CD8)}
    """)
    controls, dispatch, handlers = [], [], {}
    for index, original in enumerate(im.words(meta[4], 2)):
        label, name, marker = ((0x232, "on", on_marker), (0x233, "off", 0))[index]
        control = controls_ids[index]
        row = list(im.words(meta[3] + 28 * index, 7))
        if row[0] != label or row[6] != 0x1901 + index:
            raise ValueError("Unexpected native On/Off row")
        row[1:3] = [0xFFFF, label_id]
        row[6] = control
        controls.append(_words(*row))
        handler = _assemble(plan, f"""
            {constant('r2', STATE) + ' movs r1,#0; str r1,[r2];' if clear_gesture else ''}
            {constant('r2', preference)} movw r1,#{marker};
            ldrh r3,[r2]; cmp r1,r3; beq unchanged;
            strh r1,[r2]; dmb ish; {tail(0x10117860)}
            unchanged: bx lr;
        """)
        handlers[name] = hex(handler)
        dispatch.append(_events(plan, original, 17, {
            0x239: (0x239, handler | 1, 0, 0x3A1),
            0x25F: (0x25F, handler | 1, 0, 0x3A1),
        }))

    title = list(im.words(meta[2], 12))
    if title[0] != 0x6F9:
        raise ValueError("Unexpected original On/Off title")
    title[0] = label_id
    meta[2] = plan.alloc(_words(*title))
    meta[3] = plan.alloc(b"".join(controls))
    meta[4] = plan.alloc(_words(*dispatch))
    callbacks[0] = enter | 1
    obj[0] = page << 16 | 2
    obj[4] = plan.alloc(_words(*callbacks))
    obj[10] = plan.alloc(_words(*meta))
    template = plan.alloc(_words(*obj))

    info = dict(page=page, page_pointer=hex(pointer), open=hex(enter),
                actions=handlers, control_ids=list(controls_ids))
    if defer_getter:
        return info, template

    # Resolve the custom page separately so the original type-2 page
    # array and its indexes stay in place. The native transition already
    # handles a null result if the UI allocation fails.
    choose_template = constant("r1", template)
    page_check = f"movw r12,#{page}; cmp r1,r12; bne original; {constant('r2', pointer)}"
    if alternate:
        page_check = f"""
        movw r12,#{page}; cmp r1,r12; beq primary;
        movw r12,#{AF_PAGE}; cmp r1,r12; bne original;
        {constant('r2', af.PAGE_POINTER)} b lookup;
        primary: {constant('r2', pointer)}
        lookup:
        """
        choose_template = f"""
        {constant('r1', af.PAGE_POINTER)} cmp r4,r1; bne iso_template;
        {constant('r1', alternate)} b copy;
        iso_template: {constant('r1', template)}
        copy:
        """
    getter = _hook(plan, 0x103FCCC2, bytes.fromhex("072802464ff0000008d24e48"),
                   "Resolve the shortcut settings page", f"""
        cmp r0,#2; bne original;
        {page_check} ldr r0,[r2]; cmp r0,#0; bne done;
        push {{r4,lr}}; mov r4,r2;
        movs r0,#44; movs r1,#0; {invoke(0x1016FE38)}
        cmp r0,#0; beq return_page;
        {choose_template} movs r2,#44;
        loop: subs r2,#4; ldr r3,[r1,r2]; str r3,[r0,r2]; bne loop;
        dmb ish; str r0,[r4];
        return_page: pop {{r4,pc}};
        done: bx lr;
        original: cmp r0,#7; mov r2,r0; mov.w r0,#0; bhs invalid;
        {constant('r0', 0xA200DA5C)} {tail(0x103FCCCE)}
        invalid: bx lr;
    """)
    return info | dict(page_getter=hex(getter))


def _install_list_rendering(plan, callbacks, af_on):
    # C 3.80 includes a stock f8 bitmap. Use its own number widget and the
    # same palette as the other f rows. The title and value have separate slots.
    def row(control, badge, preference, marker, skip, show_value):
        return f"""
        mov r0,r4; movw r1,#{control}; {invoke(0x10402B96)}
        cmp r0,#0; blt {skip}; mov r5,r0;
        ldr r0,[r4,#36]; mov r1,r5; movs r2,#3; {invoke(0x103FCF5C)}
        cbz r0,{show_value}; mov r7,r0; movw r1,#{badge}; {invoke(0x103FB344)}
        movs r0,#{CONTROLS_BADGE_STYLE}; str r0,[r7,#0x38];
        {show_value}:
        ldr r0,[r4,#36]; mov r1,r5; movs r2,#0; {invoke(0x103FCF5C)}
        {constant('r1', preference)} ldrh r1,[r1]; movw r2,#{marker};
        cmp r1,r2; mov.w r1,#0xd1; it eq; moveq r1,#0xd2;
        {invoke(0x103FB344)}
        """

    render = _assemble(plan, f"""
        push {{r4-r8,lr}}; mov r4,r0; {invoke(0x104ECF14)} mov r6,r0;
        {row(CONTROL, F8_BADGE, PREFERENCE, ON_MARKER, 'next_row' if af_on else 'done', 'iso_value')}
        next_row:
        {row(AF_CONTROL, AF_BADGE, af.PREFERENCE, af.ON_MARKER, 'done', 'af_value') if af_on else ''}
        done: mov r0,r6; pop {{r4-r8,pc}};
    """)
    plan.edit(callbacks + 16, _words(render | 1), "Draw the f8 label and saved On/Off value",
              _words(0x104ECF15))


def install_menu(plan, *, af_on=False):
    im = plan.image
    meta_address = 0xA18719E8
    meta = list(im.words(meta_address, 7))
    obj = im.words(0xA18367FC, 11)
    if obj[10] != meta_address or meta[5] != 0x00080033:
        raise ValueError("Unexpected Custom Settings list")
    count = meta[5] & 0xFFFF
    rows = [im.words(meta[3] + index * 28, 7) for index in range(count)]
    dispatch = list(im.words(meta[4], count))
    if rows[ROW - 1][6] != 0x1979 or rows[ROW][6] != 0x1A69:
        raise ValueError("Unexpected f7 or g1 control")
    # The generic event dispatcher constrains type-2 page IDs below 0x3A0.
    # Open this separately resolved page through the native transition API.
    settings = [(PAGE, LABEL, CONTROL)]
    if af_on:
        settings.append((AF_PAGE, AF_LABEL, AF_CONTROL))
    for index, (page, label_id, control) in enumerate(settings, ROW):
        rows.insert(index, (label_id, 0xFFFF, label_id, 1, 0x1805, 0, control))
        open_page = _assemble(plan, f"""
            movs r0,#2; movw r1,#{page}; {tail(0x10404C42)}
        """)
        dispatch.insert(index, _events(plan, dispatch[ROW - 1], 32, {
            0x239: (0x239, open_page | 1, 0, 0x3A0),
            0x252: (0x252, open_page | 1, 0x10405009, 0x3A0),
            0x25F: (0x25F, open_page | 1, 0, 0x3A0),
        }))
    rows_addr = plan.alloc(b"".join(_words(*row) for row in rows))
    events_addr = plan.alloc(_words(*dispatch))
    plan.edit(meta_address + 12, _words(rows_addr, events_addr, meta[5] + len(settings)),
              "Insert f8 after Reverse indicators", _words(meta[3], meta[4], meta[5]))

    # Group 6 in the lookup table is the f Controls category.
    group_table = 0x10658F00
    original = im.read(group_table, 52 * 16)
    original += _words(CONTROL << 16 | 0xFFFF, 6, F8_BADGE, CONTROLS_BADGE_STYLE)
    if af_on:
        original += _words(AF_CONTROL << 16 | AF_CONTROL, 6, AF_BADGE, CONTROLS_BADGE_STYLE)
    groups = plan.alloc(original)
    for site in (0x104ECB0C, 0x104F7954):
        plan.edit(site, _words(groups), "Classify f8 with f Controls", _words(group_table))
    group_count = 52 + len(settings)
    plan.edit(0x104EC8C4, bytes((group_count, 0x21)), "Include shortcuts in Custom Settings group lookup",
              bytes.fromhex("3421"))
    plan.edit(0x104F7578, bytes((group_count, 0x29)), "Classify shortcuts in the secondary group lookup",
              bytes.fromhex("3429"))
    plan.edit(0x104F7614, bytes((group_count, 0x29)), "Resolve native shortcut numbers in the group table",
              bytes.fromhex("3429"))
    _install_list_rendering(plan, obj[4], af_on)
    label = _install_label(plan, af_on)
    common = dict(parent_page=PARENT_PAGE, default="off", label_lookup=hex(label),
                  journal_record=55, journal_schema_records=89, save_request="0x10117860")
    alternate = None
    if af_on:
        info, alternate = _install_page(
            plan, page=AF_PAGE, label_id=AF_LABEL, controls_ids=AF_CONTROLS,
            preference=af.PREFERENCE, on_marker=af.ON_MARKER, pointer=af.PAGE_POINTER,
            clear_gesture=False, defer_getter=True,
        )
        plan.features["af_on_af_c"]["menu"] = common | info | dict(
            row=ROW + 1, control=AF_CONTROL, preference=hex(af.PREFERENCE), on_marker=hex(af.ON_MARKER),
        )
    info = _install_page(plan, alternate=alternate)
    plan.features["iso_double_click"]["menu"] = common | info | dict(
        row=ROW, control=CONTROL, preference=hex(PREFERENCE), on_marker=hex(ON_MARKER),
    )
