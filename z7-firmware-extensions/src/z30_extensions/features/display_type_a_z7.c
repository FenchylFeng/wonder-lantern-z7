/* Z7 C 3.80 shooting-monitor virtual horizon. Native GUI coordinates are 720x480. */
#include <stdint.h>

#define NATIVE(type, address) ((type)(uintptr_t)((address) | 1u))
#define MODE (*(volatile const uint8_t *)0xa18293e4u)
#define OUTPUT (*(volatile const uint8_t *)0xa18237c6u)
#define DISP (*(volatile const uint8_t *)0xa201d65au)
#define CONTROLLER (*(volatile const uint32_t *)0xa18293e8u)
#define SIZE NATIVE(const uint16_t *(*)(unsigned), 0x103fa36au)
#define SYNC NATIVE(void (*)(void), 0x103fa746u)
#define FLUSH_DRAW_QUEUE NATIVE(void (*)(void), 0x1042eb0eu)
#define PUBLISH NATIVE(void (*)(unsigned), 0x103fcb46u)
#define DIRTY NATIVE(void (*)(uint32_t, unsigned), 0x103fb302u)

#define READ_POSE NATIVE(void (*)(int32_t *), 0x104070deu)
#define ATAN2_Q16 NATIVE(int32_t (*)(int32_t, int32_t), 0x101b35eau)
#define READ_BATTERY NATIVE(void (*)(uint32_t *), 0x10437684u)
enum { HORIZON_ONLY = 5 };

enum { Q16 = 65536 };

static int supported(void)
{
    if (MODE != 1 || OUTPUT != 0)
        return 0;
    const uint16_t *size = SIZE(0);
    return size && size[0] == 720 && size[1] == 480;
}

static int magnitude(int value)
{
    return value < 0 ? -value : value;
}

static int pitch_angle(int32_t raw)
{
    /* 360-degree encoding, with the two valid ranges near 0 and 180. */
    int sign = raw > 180 * Q16 ? -1 : 1;
    if (sign < 0)
        raw = 360 * Q16 - raw;
    return sign * (raw > 90 * Q16 ? 180 * Q16 - raw : raw);
}

static int marker(int32_t angle)
{
    int limit = 15 * Q16;
    if (angle > limit)
        angle = limit;
    if (angle < -limit)
        angle = -limit;
    return angle * 56 / limit;
}

#define LCD_BUFFER (*(volatile const uint32_t *)0xa1821374u)
#define CPU_BUFFER NATIVE(uint32_t *(*)(uint32_t), 0x101e3ddeu)

enum { WIDTH = 720, HEIGHT = 480, CENTER_X = WIDTH / 2, CENTER_Y = HEIGHT / 2,
       CROSS_EXTENT = 100, CROSS_LENGTH = 40, CROSS_WIDTH = 4, WING_GAP = CROSS_EXTENT + 4,
       PITCH_START = 16, PITCH_END = 42 };

/* Private RGBA values with an alpha value distinct from the native indicators. */
static const uint32_t outline_ink = 0xf9000000u;
static const uint32_t white_ink = 0xf9ffffffu;
static const uint32_t level_ink = 0xf924ff43u;

static uint32_t *canvas(void)
{
    uint32_t handle = LCD_BUFFER;
    uint32_t *pixels = handle ? CPU_BUFFER(handle) : 0;
    return (uintptr_t)pixels & 3 ? 0 : pixels;
}

static int screen_y(int y)
{
    return y < 0 ? 0 : y > HEIGHT ? HEIGHT : y;
}

static void erase_span(uint32_t *row, int first, int last)
{
    for (int x = first; x < last; ++x) {
        uint32_t color = row[x];
        if (color == outline_ink || color == white_ink || color == level_ink)
            row[x] = 0;
    }
}

static void erase_level(uint32_t *pixels)
{
    /* With full rotation, any row can contain an old wing. */
    erase_span(pixels, 0, WIDTH * HEIGHT);
}

static void mark_rect(uint32_t *pixels, int x, int y, int width, int height, uint32_t color)
{
    int end = screen_y(y + height);
    for (int row = screen_y(y); row < end; ++row) {
        uint32_t *p = pixels + row * WIDTH + x;
        for (int i = 0; i < width; i++) {
            if (!(p[i] >> 24))
                p[i] = color;
        }
    }
}

static void outlined_rect(uint32_t *pixels, int x, int y, int w, int h)
{
    mark_rect(pixels, x, y, w, 1, outline_ink);
    mark_rect(pixels, x, y + h - 1, w, 1, outline_ink);
    mark_rect(pixels, x, y + 1, 1, h - 2, outline_ink);
    mark_rect(pixels, x + w - 1, y + 1, 1, h - 2, outline_ink);
    mark_rect(pixels, x + 1, y + 1, w - 2, h - 2, white_ink);
}

static void draw_reference(uint32_t *pixels)
{
    /* Scale the four separate strokes in the reference to the LCD canvas. */
    int gap = CROSS_EXTENT - CROSS_LENGTH;
    outlined_rect(pixels, CENTER_X - CROSS_EXTENT, CENTER_Y - CROSS_WIDTH / 2,
                  CROSS_LENGTH, CROSS_WIDTH);
    outlined_rect(pixels, CENTER_X + gap, CENTER_Y - CROSS_WIDTH / 2,
                  CROSS_LENGTH, CROSS_WIDTH);
    outlined_rect(pixels, CENTER_X - CROSS_WIDTH / 2, CENTER_Y - CROSS_EXTENT,
                  CROSS_WIDTH, CROSS_LENGTH);
    outlined_rect(pixels, CENTER_X - CROSS_WIDTH / 2, CENTER_Y + gap,
                  CROSS_WIDTH, CROSS_LENGTH);
}

enum { TRIG_UNIT = 4096 };

/* Positive quadrant sine, interpolated in the native Q16-degree domain. */
static int quarter_sine(int32_t angle)
{
    static const uint16_t sine[] = {
        0, 357, 711, 1060, 1401, 1731, 2048, 2349, 2633, 2896,
        3138, 3355, 3547, 3712, 3849, 3956, 4034, 4080, 4096,
    };
    int step = 5 * Q16;
    int index = angle / step;
    if (index == 18)
        return TRIG_UNIT;
    return sine[index] + (sine[index + 1] - sine[index]) * (angle % step) / step;
}

static int32_t corrected_pitch(int32_t first, int32_t second, int cos_roll, int sin_roll)
{
    /* The producer computes the two pitch angles against the two in-plane
       gravity components. Reconstruct the angle against their resultant. */
    int use_first = cos_roll >= sin_roll;
    int32_t raw = use_first ? first : second;
    int projection = use_first ? cos_roll : sin_roll;
    if (raw < 0 || raw > 360 * Q16)
        return -1;
    int32_t angle = pitch_angle(raw);
    int32_t absolute = magnitude(angle);
    int across = quarter_sine(absolute) * projection / TRIG_UNIT;
    int along = quarter_sine(90 * Q16 - absolute);
    int32_t pitch = ATAN2_Q16(along, across);
    return angle < 0 ? -pitch : pitch;
}

static void draw_wings(uint32_t *pixels, int cosine, int sine, uint32_t color)
{
    int horizontal = magnitude(cosine) >= magnitude(sine);
    int major = horizontal ? cosine : sine;
    int minor = horizontal ? sine : cosine;
    int extent = horizontal ? CENTER_X : CENTER_Y;
    int gap = (WING_GAP * magnitude(major) + TRIG_UNIT / 2) / TRIG_UNIT;
    for (int axis = -extent; axis < extent; ++axis) {
        if (magnitude(axis) < gap)
            continue;
        int cross = axis * minor / major;
        uint32_t center = magnitude(axis) == gap ? outline_ink : color;
        if (horizontal) {
            int x = CENTER_X + axis, y = CENTER_Y + cross;
            mark_rect(pixels, x, y - 1, 1, 1, outline_ink);
            mark_rect(pixels, x, y, 1, 1, center);
            mark_rect(pixels, x, y + 1, 1, 1, outline_ink);
        } else {
            int x = CENTER_X + cross, y = CENTER_Y + axis;
            /* A Y-major segment cannot reach either X edge on this canvas. */
            mark_rect(pixels, x - 1, y, 1, 1, outline_ink);
            mark_rect(pixels, x, y, 1, 1, center);
            mark_rect(pixels, x + 1, y, 1, 1, outline_ink);
        }
    }
}

static void draw_pitch(uint32_t *pixels, int cosine, int sine, int displacement, uint32_t color)
{
    /* Project each pixel onto the horizon tangent and the upward normal. */
    int radius = PITCH_END + 2 + magnitude(displacement);
    int start = PITCH_START * TRIG_UNIT - TRIG_UNIT / 2;
    int end = PITCH_END * TRIG_UNIT + TRIG_UNIT / 2;
    for (int y = -radius; y <= radius; ++y) {
        for (int x = -radius; x <= radius; ++x) {
            int normal = magnitude(x * sine - y * cosine - displacement * TRIG_UNIT);
            if (normal > 2 * TRIG_UNIT + TRIG_UNIT / 2)
                continue;
            int tangent = magnitude(x * cosine + y * sine);
            if (tangent < start || tangent > end)
                continue;
            int border = normal > TRIG_UNIT + TRIG_UNIT / 2 ||
                         tangent < start + TRIG_UNIT || tangent > end - TRIG_UNIT;
            mark_rect(pixels, CENTER_X + x, CENTER_Y + y, 1, 1, border ? outline_ink : color);
        }
    }
}

static void draw_level(uint32_t *pixels, int32_t roll, int32_t first, int32_t second)
{
    roll %= 360 * Q16;
    if (roll > 180 * Q16)
        roll -= 360 * Q16;
    if (roll < -180 * Q16)
        roll += 360 * Q16;
    int32_t absolute = magnitude(roll);
    int32_t quadrant_angle = absolute > 90 * Q16 ? 180 * Q16 - absolute : absolute;
    int sine = quarter_sine(quadrant_angle);
    int cosine = quarter_sine(90 * Q16 - quadrant_angle);
    int32_t pitch = corrected_pitch(first, second, cosine, sine);
    if (pitch == -1)
        return;

    draw_reference(pixels);
    int32_t from_axis = quadrant_angle % (90 * Q16);
    uint32_t roll_color = from_axis <= Q16 / 2 || from_axis >= 90 * Q16 - Q16 / 2
        ? level_ink : white_ink;
    uint32_t pitch_color = magnitude(pitch) <= Q16 / 2 ? level_ink : white_ink;
    sine = roll < 0 ? -sine : sine;
    cosine = absolute > 90 * Q16 ? -cosine : cosine;
    draw_wings(pixels, cosine, sine, roll_color);
    draw_pitch(pixels, cosine, sine, marker(pitch), pitch_color);
}

__attribute__((section(".text.clear")))
int clear_horizon(void)
{
    if (!supported())
        return 0;
    SYNC();
    uint32_t *pixels = canvas();
    if (!pixels)
        return 0;
    erase_level(pixels);
    PUBLISH(0);
    return 1;
}

__attribute__((section(".text.paint")))
int paint_horizon(uint32_t widget)
{
    unsigned page = DISP;
    if (widget != CONTROLLER || (page != 3 && page != HORIZON_ONLY) || !supported())
        return 0;

    int32_t angles[3];
    READ_POSE(angles);
    int32_t roll = angles[0];
    int roll_valid = roll >= -360 * Q16 && roll <= 360 * Q16 && roll != -1;
    SYNC();
    uint32_t *pixels = canvas();
    if (!pixels)
        return 0;
    erase_level(pixels);
    if (roll_valid)
        draw_level(pixels, roll, angles[1], angles[2]);
    PUBLISH(0);
    DIRTY(widget, 0);
    return 1;
}

/* BatteryCheckService returns the same 56-byte report used by Battery info. */
static int battery_percent(void)
{
    uint32_t report[14];
    READ_BATTERY(report);
    const uint8_t *state = (const uint8_t *)report;
    if (!report[0] || state[7] > 1 || state[4] == 0 || state[4] == 3 ||
        state[4] == 4 || state[4] == 5 || state[4] > 6)
        return -1;
    unsigned slot = state[7] * 6;
    if (state[9 + slot * 4] != 1 || report[6 + slot] > 100)
        return -1;
    return (int)report[6 + slot];
}

#define GLYPH(a,b,c,d,e) ((a) << 12 | (b) << 9 | (c) << 6 | (d) << 3 | (e))

static void draw_battery(uint32_t *pixels, int x, int y, unsigned percent)
{
    static const uint16_t glyphs[] = {
        GLYPH(7,5,5,5,7), GLYPH(2,6,2,2,7), GLYPH(7,1,7,4,7),
        GLYPH(7,1,7,1,7), GLYPH(5,5,7,1,1), GLYPH(7,4,7,1,7),
        GLYPH(7,4,7,5,7), GLYPH(7,1,2,2,2), GLYPH(7,5,7,5,7),
        GLYPH(7,5,7,1,7), GLYPH(5,1,2,4,5),
    };
    enum { BODY_WIDTH = 56, ICON_WIDTH = 60, ICON_HEIGHT = 32, SCALE = 3 };
    uint8_t digits[4];
    unsigned count = 0;
    if (percent == 100)
        digits[count++] = 1;
    if (percent >= 10)
        digits[count++] = (percent / 10) % 10;
    digits[count++] = percent % 10;
    digits[count++] = 10;

    uint32_t ink = percent <= 20 ? 0xff3939f5u : 0xfff8f8f8u;
    for (int dy = 0; dy < ICON_HEIGHT; ++dy) {
        uint32_t *row = pixels + (y + dy) * WIDTH + x;
        for (int dx = 0; dx < ICON_WIDTH; ++dx) {
            uint32_t color = 0;
            if (dx < BODY_WIDTH && dy >= 2 && dy < 30) {
                color = dx < 2 || dx >= BODY_WIDTH - 2 || dy < 4 || dy >= 28
                    ? ink : 0xc0000000u;
            } else if (dx >= BODY_WIDTH && dy >= 11 && dy < 21) {
                color = ink;
            }
            row[dx] = color;
        }
    }

    int left = x + (BODY_WIDTH - (int)(count * 4 * SCALE - SCALE)) / 2;
    for (unsigned i = 0; i < count; ++i) {
        unsigned bits = glyphs[digits[i]];
        for (int row = 0; row < 5; ++row) {
            for (int col = 0; col < 3; ++col) {
                if (!(bits & (1u << (14 - 3 * row - col))))
                    continue;
                for (int dy = 0; dy < SCALE; ++dy)
                    for (int dx = 0; dx < SCALE; ++dx)
                        pixels[(y + 8 + row * SCALE + dy) * WIDTH + left + col * SCALE + dx] = ink;
            }
        }
        left += 4 * SCALE;
    }
}

__attribute__((section(".text.battery")))
int paint_battery(const uint32_t *image)
{
    /* The native monitor submits a shadow and a foreground for the same
       60x32 battery widget on the shooting HUD. Leave other jobs to Nikon. */
    unsigned page = DISP;
    if (OUTPUT != 0 || (page > 3 && page != HORIZON_ONLY) ||
        image[0] != 1 || image[1] != 7 ||
        image[5] != (32u << 16 | 60u) ||
        image[6] != (396u << 16 | 2u) || image[7] != (428u << 16 | 62u))
        return 0;
    uint32_t pass = image[8];
    if ((pass & 0xff) != 0xff)
        return 0;
    int percent = battery_percent();
    if (percent < 0)
        return 0;
    const uint16_t *size = SIZE(0);
    if (!size || size[0] != WIDTH || size[1] != HEIGHT)
        return 0;
    uint32_t *pixels = canvas();
    if (!pixels)
        return 0;
    if (pass != 0x000000ffu) {
        /* The submitting renderer already holds the graphics lock. */
        FLUSH_DRAW_QUEUE();
        draw_battery(pixels, 2, 396, (unsigned)percent);
        PUBLISH(0);
    }
    return 1;
}
