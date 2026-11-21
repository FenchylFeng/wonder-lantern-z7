/* Z7 C 3.80 shooting-monitor virtual horizon. Native GUI coordinates are 720x480. */
#include <stdint.h>

#define NATIVE(type, address) ((type)(uintptr_t)((address) | 1u))
#define MODE (*(volatile const uint8_t *)0xa18293e4u)
#define OUTPUT (*(volatile const uint8_t *)0xa18237c6u)
#define DISP (*(volatile const uint8_t *)0xa201d65au)
#define CONTROLLER (*(volatile const uint32_t *)0xa18293e8u)
#define SIZE NATIVE(const uint16_t *(*)(unsigned), 0x103fa36au)
#define SYNC NATIVE(void (*)(void), 0x103fa746u)
#define PUBLISH NATIVE(void (*)(unsigned), 0x103fcb46u)
#define DIRTY NATIVE(void (*)(uint32_t, unsigned), 0x103fb302u)

#define READ_POSE NATIVE(void (*)(int32_t *), 0x104070deu)
#define ATAN2_Q16 NATIVE(int32_t (*)(int32_t, int32_t), 0x101b35eau)
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
       CROSS_EXTENT = 100, CROSS_LENGTH = 40, CROSS_WIDTH = 4, WING_GAP = CROSS_EXTENT + 4 };

/* Private RGBA values with an alpha value distinct from the native indicators. */
static const uint32_t roll_ink = 0xf9e8ae00u;
static const uint32_t pitch_ink = 0xf923d7fcu;
static const uint32_t level_ink = 0xf924ff43u;
static const uint32_t reference_ink = 0xf9a0a0a0u;

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
        if (color >> 24 == 0xf9 &&
            (color == roll_ink || color == pitch_ink || color == level_ink || color == reference_ink))
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

static inline __attribute__((always_inline)) void draw_reference(uint32_t *pixels)
{
    /* Scale the four separate strokes in the reference to the LCD canvas. */
    int gap = CROSS_EXTENT - CROSS_LENGTH;
    mark_rect(pixels, CENTER_X - CROSS_EXTENT, CENTER_Y - CROSS_WIDTH / 2,
              CROSS_LENGTH, CROSS_WIDTH, reference_ink);
    mark_rect(pixels, CENTER_X + gap, CENTER_Y - CROSS_WIDTH / 2,
              CROSS_LENGTH, CROSS_WIDTH, reference_ink);
    mark_rect(pixels, CENTER_X - CROSS_WIDTH / 2, CENTER_Y - CROSS_EXTENT,
              CROSS_WIDTH, CROSS_LENGTH, reference_ink);
    mark_rect(pixels, CENTER_X - CROSS_WIDTH / 2, CENTER_Y + gap,
              CROSS_WIDTH, CROSS_LENGTH, reference_ink);
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
        if (horizontal) {
            mark_rect(pixels, CENTER_X + axis, CENTER_Y + cross - 1, 1, 3, color);
        } else {
            int x = CENTER_X + cross;
            /* A Y-major segment cannot reach either X edge on this canvas. */
            mark_rect(pixels, x - 1, CENTER_Y + axis, 3, 1, color);
        }
    }
}

static void draw_pitch(uint32_t *pixels, int cosine, int sine, int displacement, uint32_t color)
{
    /* Project each pixel onto the horizon tangent and the upward normal. */
    int radius = 32 + magnitude(displacement);
    for (int y = -radius; y <= radius; ++y) {
        for (int x = -radius; x <= radius; ++x) {
            int normal = x * sine - y * cosine - displacement * TRIG_UNIT;
            if (magnitude(normal) > 2 * TRIG_UNIT + TRIG_UNIT / 2)
                continue;
            int tangent = magnitude(x * cosine + y * sine);
            if (tangent >= 14 * TRIG_UNIT - TRIG_UNIT / 2 &&
                tangent <= 30 * TRIG_UNIT + TRIG_UNIT / 2)
                mark_rect(pixels, CENTER_X + x, CENTER_Y + y, 1, 1, color);
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
        ? level_ink : roll_ink;
    uint32_t pitch_color = magnitude(pitch) <= Q16 / 2 ? level_ink : pitch_ink;
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
