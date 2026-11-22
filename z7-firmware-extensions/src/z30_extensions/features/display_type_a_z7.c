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
#define READ_DIRECTION NATIVE(unsigned (*)(void), 0x104070e2u)
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

#define LCD_BUFFER (*(volatile const uint32_t *)0xa1821374u)
#define CPU_BUFFER NATIVE(uint32_t *(*)(uint32_t), 0x101e3ddeu)

enum { WIDTH = 720, HEIGHT = 480, CENTER_X = WIDTH / 2, CENTER_Y = HEIGHT / 2,
       Q12 = 4096, ROLL_HALF_LENGTH = 4156, PITCH_INNER = 18, PITCH_OUTER = 44,
       MASK_LEFT = 300, MASK_TOP = 180, MASK_RIGHT = 420, MASK_BOTTOM = 300,
       PITCH_MAX_DEGREES = 30, PITCH_MAX_OFFSET = 58 };

/* Z8 C 3.12 shooting palette entries 1, 3, 40, 50 and 56. One unit in
   an alpha or color channel identifies the pixels owned by this overlay. */
static const uint32_t shadow_ink = 0x1a000001u;
static const uint32_t guide_ink = 0x66000001u;
static const uint32_t reference_ink = 0x992b2b2au;
static const uint32_t level_ink = 0xfe00ff00u;
static const uint32_t white_ink = 0xfeffffffu;

struct Point {
    int x;
    int y;
};

static uint32_t *canvas(void)
{
    uint32_t handle = LCD_BUFFER;
    uint32_t *pixels = handle ? CPU_BUFFER(handle) : 0;
    return (uintptr_t)pixels & 3 ? 0 : pixels;
}

static int magnitude(int value)
{
    return value < 0 ? -value : value;
}

static int erase_level(uint32_t *pixels)
{
    /* The previous overlay on this canvas supplies the visibility latch. */
    int was_visible = 0;
    for (int i = 0; i < WIDTH * HEIGHT; ++i) {
        uint32_t color = pixels[i];
        if (color == shadow_ink || color == guide_ink || color == reference_ink ||
            color == level_ink || color == white_ink) {
            pixels[i] = 0;
            was_visible = 1;
        }
    }
    return was_visible;
}

static void mark_pixel(uint32_t *pixels, unsigned x, unsigned y, uint32_t color)
{
    if (x < WIDTH && y < HEIGHT) {
        uint32_t *pixel = pixels + y * WIDTH + x;
        if (!(*pixel >> 24))
            *pixel = color;
    }
}

static void draw_reference(uint32_t *pixels)
{
    /* Subtract the native 120x120 clear rectangle from the two fixed strokes. */
    for (unsigned y = 239; y < 241; ++y) {
        for (unsigned x = 258; x < MASK_LEFT; ++x)
            mark_pixel(pixels, x, y, reference_ink);
        for (unsigned x = MASK_RIGHT; x < 462; ++x)
            mark_pixel(pixels, x, y, reference_ink);
    }
    for (unsigned x = 359; x < 361; ++x) {
        for (unsigned y = 138; y < MASK_TOP; ++y)
            mark_pixel(pixels, x, y, reference_ink);
        for (unsigned y = MASK_BOTTOM; y < 342; ++y)
            mark_pixel(pixels, x, y, reference_ink);
    }
}

static int rounded_degrees(int32_t angle)
{
    int result = ((angle + Q16 / 2) >> 16) % 360;
    return result < 0 ? result + 360 : result;
}

static int32_t selected_pitch(const int32_t angles[3], unsigned direction)
{
    int32_t raw = angles[direction == 0 || direction == 3 ? 1 : 2];
    /* The upstream Z8 filter excludes two closed Q16 intervals. */
    if (raw < 0 || raw > 360 * Q16 ||
        (raw >= 60 * Q16 + Q16 / 2 && raw <= 119 * Q16 + Q16 / 2) ||
        (raw >= 240 * Q16 + Q16 / 2 && raw <= 299 * Q16 + Q16 / 2))
        return -1;
    return raw;
}

static int distance_from_axis(int angle, int cycle)
{
    int remainder = angle % cycle;
    return remainder <= cycle / 2 ? remainder : cycle - remainder;
}

static int pitch_offset(int pitch)
{
    int folded = distance_from_axis(pitch, 180);
    if (folded > PITCH_MAX_DEGREES)
        folded = PITCH_MAX_DEGREES;
    int pixels = folded * PITCH_MAX_OFFSET / PITCH_MAX_DEGREES;
    return pitch < 180 ? pixels : -pixels;
}

/* Truncated Q12 sine at integer degrees, generated from the sine function. */
static int sine_q12(unsigned degrees)
{
    static const uint16_t quarter[] = {
        0, 71, 142, 214, 285, 356, 428, 499, 570, 640,
        711, 781, 851, 921, 990, 1060, 1129, 1197, 1265, 1333,
        1400, 1467, 1534, 1600, 1665, 1731, 1795, 1859, 1922, 1985,
        2048, 2109, 2170, 2230, 2290, 2349, 2407, 2465, 2521, 2577,
        2632, 2687, 2740, 2793, 2845, 2896, 2946, 2995, 3043, 3091,
        3137, 3183, 3227, 3271, 3313, 3355, 3395, 3435, 3473, 3510,
        3547, 3582, 3616, 3649, 3681, 3712, 3741, 3770, 3797, 3823,
        3848, 3872, 3895, 3917, 3937, 3956, 3974, 3991, 4006, 4020,
        4033, 4045, 4056, 4065, 4073, 4080, 4086, 4090, 4093, 4095,
        4096,
    };
    unsigned index = degrees % 90;
    unsigned quadrant = degrees / 90;
    int value = quarter[quadrant & 1 ? 90 - index : index];
    return quadrant >= 2 ? -value : value;
}

static struct Point rotate_point(int x, int shift, int cosine, int sine)
{
    int bias = shift ? Q12 / 2 : 0;
    return (struct Point){CENTER_X + ((x * cosine - shift * sine + bias) >> 12),
                          CENTER_Y + ((x * sine + shift * cosine + bias) >> 12)};
}

static void draw_line(uint32_t *pixels, struct Point p, struct Point q, int width,
                      uint32_t color, int mask_center)
{
    int dx = q.x - p.x, dy = q.y - p.y;
    int horizontal = magnitude(dx) >= magnitude(dy);
    int major = horizontal ? dx : dy;
    int minor = horizontal ? dy : dx;
    int a = horizontal ? p.x : p.y;
    int b = horizontal ? p.y : p.x;
    int first = major > 0 ? a : a + major;
    int last = major > 0 ? a + major : a;
    int extent = horizontal ? WIDTH : HEIGHT;
    if (first < 0)
        first = 0;
    if (last >= extent)
        last = extent - 1;

    int length_squared = dx * dx + dy * dy;
    int64_t stroke_squared = (int64_t)width * width * length_squared;
    for (int axis = first; axis <= last; ++axis) {
        int center = b + (axis - a) * minor / major;
        for (int offset = -width; offset <= width; ++offset) {
            int x = horizontal ? axis : center + offset;
            int y = horizontal ? center + offset : axis;
            if (mask_center && x >= MASK_LEFT && x < MASK_RIGHT && y >= MASK_TOP && y < MASK_BOTTOM)
                continue;
            int rel_x = 2 * (x - p.x) + 1, rel_y = 2 * (y - p.y) + 1;
            int along = rel_x * dx + rel_y * dy;
            int normal = rel_x * dy - rel_y * dx;
            if (along >= 0 && along <= 2 * length_squared &&
                (int64_t)normal * normal <= stroke_squared)
                mark_pixel(pixels, x, y, color);
        }
    }
}

static void draw_pitch(uint32_t *pixels, int shift, int extension, int cosine, int sine,
                       int width, uint32_t color)
{
    int inner = PITCH_INNER + extension, outer = PITCH_OUTER + extension;
    draw_line(pixels, rotate_point(outer, shift, cosine, sine),
              rotate_point(inner, shift, cosine, sine), width, color, 0);
    draw_line(pixels, rotate_point(-outer, shift, cosine, sine),
              rotate_point(-inner, shift, cosine, sine), width, color, 0);
}

static void draw_level(uint32_t *pixels, int roll, int pitch)
{
    int sine = sine_q12(roll);
    int cosine = sine_q12((roll + 90) % 360);
    int shift = pitch_offset(pitch);
    uint32_t roll_color = roll % 90 == 0 ? level_ink : white_ink;
    uint32_t pitch_color = pitch % 90 == 0 ? level_ink : white_ink;
    struct Point start = rotate_point(-ROLL_HALF_LENGTH, 0, cosine, sine);
    struct Point end = rotate_point(ROLL_HALF_LENGTH, 0, cosine, sine);

    /* Paint the foreground first; the existing camera HUD always has priority. */
    draw_pitch(pixels, shift, 0, cosine, sine, 2, pitch_color);
    draw_pitch(pixels, shift, 1, cosine, sine, 4, shadow_ink);
    draw_pitch(pixels, 0, 0, cosine, sine, 2, guide_ink);
    draw_line(pixels, start, end, 2, roll_color, 1);
    draw_line(pixels, start, end, 4, shadow_ink, 1);
    draw_reference(pixels);
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
    int32_t pitch = selected_pitch(angles, READ_DIRECTION());
    int32_t roll = angles[0];
    int roll_valid = roll >= -360 * Q16 && roll <= 360 * Q16 && roll != -1;
    SYNC();
    uint32_t *pixels = canvas();
    if (!pixels)
        return 0;
    int was_visible = erase_level(pixels);
    if (roll_valid && pitch >= 0) {
        int folded = distance_from_axis(pitch, 180 * Q16);
        if (folded < 55 * Q16 || (was_visible && folded <= 60 * Q16))
            draw_level(pixels, rounded_degrees(roll), rounded_degrees(pitch));
    }
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

static void draw_battery(uint32_t *pixels, int x, int y, unsigned percent)
{
    enum { BODY_WIDTH = 56, ICON_WIDTH = 60, ICON_HEIGHT = 32,
           GLYPH_WIDTH = 11, GLYPH_HEIGHT = 19, GLYPH_GAP = 2 };
    /* Four coverage levels, from transparent space to full ink. */
    static const uint8_t coverage[] = { ['.'] = 1, ['+'] = 2, ['#'] = 3 };
    static const char glyphs[][GLYPH_HEIGHT][GLYPH_WIDTH + 1] = {
        { /* 0 */
            "           ",
            "   .###.   ",
            "  .#####.  ",
            "  ##+ +##  ",
            " .##   ##+ ",
            " +#+   +#+ ",
            " ##.   .## ",
            " ##     ##.",
            ".##     ##.",
            ".##     ##.",
            ".##     ##.",
            " ##     ##.",
            " ##.   .## ",
            " +#+   .## ",
            " .##   ##+ ",
            "  ##+ +##  ",
            "  .#####.  ",
            "   .###.   ",
            "     .     ",
        },
        { /* 1, with the short flag and no foot of the stock shooting readout. */
            "           ",
            "    +#+    ",
            "   +###    ",
            "  +####    ",
            " .##+##    ",
            "  ...##    ",
            "    .##    ",
            "    .##    ",
            "    .##    ",
            "    .##    ",
            "    .##    ",
            "    .##    ",
            "    .##    ",
            "    .##    ",
            "    .##    ",
            "    .##    ",
            "    .##    ",
            "    .##    ",
            "    .++    ",
        },
        { /* 2 */
            "    ...    ",
            "  .#####.  ",
            " .#######. ",
            " ##+   +## ",
            " ##.    ## ",
            " ++     ## ",
            "       +## ",
            "      .##. ",
            "      ##+  ",
            "     ###   ",
            "    +##.   ",
            "   +##.    ",
            "  .##+     ",
            "  +#+      ",
            " .##.      ",
            " +#+       ",
            " ######### ",
            " ######### ",
            "  .......  ",
        },
        { /* 3 */
            "    ...    ",
            "  .#####.  ",
            " +#######. ",
            " ##+   +#+ ",
            "       .## ",
            "       .## ",
            "       +#+ ",
            "    ..+##. ",
            "   .####+  ",
            "   .#####. ",
            "      .##+ ",
            "       .## ",
            "        ##.",
            "        ##.",
            "       .## ",
            " ##+  .##+ ",
            " +#######  ",
            "  .####+   ",
            "     .     ",
        },
        { /* 4 */
            "           ",
            "      +#.  ",
            "      ##+  ",
            "     +##+  ",
            "    .###+  ",
            "    +###+  ",
            "   .####+  ",
            "   ##++#+  ",
            "  +## +#+  ",
            "  ##+ +#+  ",
            " +##  +#+  ",
            ".#########.",
            ".#########.",
            " .....+#+. ",
            "      +#+  ",
            "      +#+  ",
            "      +#+  ",
            "      +#.  ",
            "       .   ",
        },
        { /* 5 */
            "           ",
            " .#######+ ",
            " .#######+ ",
            " .#+       ",
            " +#+       ",
            " +#+       ",
            " +#+ .     ",
            " +#####+   ",
            " +#######  ",
            " .#+  .##+ ",
            "       .## ",
            "        ## ",
            "        ##.",
            "       .## ",
            "       .## ",
            " ##+. .##+ ",
            " +#######  ",
            "  .+###+   ",
            "           ",
        },
        { /* 6 */
            "     ..    ",
            "   .####+  ",
            "  .######+ ",
            "  +##  .+. ",
            " .##.      ",
            " +#+       ",
            " +#+       ",
            " ##+###+   ",
            " ########. ",
            " ###. .##+ ",
            " ##.   .## ",
            " ##     ##.",
            " ##.    ##.",
            " ##.    ##.",
            " +#+   .## ",
            " .##.  +#+ ",
            "  +##+###. ",
            "   +####.  ",
            "    ...    ",
        },
        { /* 7 */
            "           ",
            " ######### ",
            " ######### ",
            "  .....##+ ",
            "      .##. ",
            "      +#+  ",
            "      ##.  ",
            "     .##   ",
            "     +#+   ",
            "     ##.   ",
            "    .##    ",
            "    +#+    ",
            "    +#.    ",
            "    ##.    ",
            "   .##     ",
            "   .##     ",
            "   +#+     ",
            "   +#.     ",
            "    .      ",
        },
        { /* 8 */
            "     .     ",
            "   +###+   ",
            "  #######  ",
            " +##. .##+ ",
            " ##+   .## ",
            " ##.   .## ",
            " +#+   +## ",
            " .##+..##. ",
            "  +#####+  ",
            "  #######. ",
            " +##. .##+ ",
            " ##.   .##.",
            ".##     ##.",
            ".##     ##.",
            " ##.   .##.",
            " +##.  +#+ ",
            " .#######. ",
            "  .+####.  ",
            "    ...    ",
        },
        { /* 9 */
            "    ..     ",
            "  .+###+   ",
            "  ######+  ",
            " +##  .##. ",
            " ##.   +#+ ",
            ".##    .## ",
            ".##     ## ",
            ".##     ##.",
            " ##.   .##.",
            " +##. .### ",
            " .######## ",
            "  .+###### ",
            "     . +#+ ",
            "       ##+ ",
            "      .##. ",
            "  .   ##+  ",
            " +##+###   ",
            " .#####.   ",
            "   ...     ",
        },
        { /* % */
            "           ",
            "           ",
            " .##.   .. ",
            " ####  .#+ ",
            ".#..#. +#  ",
            ".#..#..#+  ",
            " #### +#   ",
            " .++..#+   ",
            "     +#    ",
            "    .#.    ",
            "    ##     ",
            "   .#..++. ",
            "   ## #### ",
            "  .#..#..#.",
            "  #+ .#..#.",
            " +#.  #### ",
            " .+   .##. ",
            "           ",
            "           ",
        },
    };
    uint8_t digits[4];
    unsigned count = 0;
    if (percent == 100)
        digits[count++] = 1;
    if (percent >= 10)
        digits[count++] = (percent / 10) % 10;
    digits[count++] = percent % 10;
    digits[count++] = 10;

    uint32_t ink = percent <= 20 ? 0xff3939f5u : 0xfff8f8f8u;
    const uint32_t background = 0xc0000000u;
    for (int dy = 0; dy < ICON_HEIGHT; ++dy) {
        uint32_t *row = pixels + (y + dy) * WIDTH + x;
        for (int dx = 0; dx < ICON_WIDTH; ++dx) {
            uint32_t color = 0;
            if (dx < BODY_WIDTH && dy >= 2 && dy < 30) {
                color = dx < 2 || dx >= BODY_WIDTH - 2 || dy < 4 || dy >= 28
                    ? ink : background;
            } else if (dx >= BODY_WIDTH && dy >= 11 && dy < 21) {
                color = ink;
            }
            row[dx] = color;
        }
    }

    /* Composite the glyph coverage over the translucent black body. */
    uint32_t shades[4] = {background, 0, 0, ink};
    for (unsigned shade = 1; shade < 3; ++shade) {
        unsigned opacity = 85 * shade;
        unsigned alpha = 192 + 21 * shade;
        uint32_t mixed = alpha << 24;
        for (unsigned shift = 0; shift < 24; shift += 8) {
            unsigned channel = (ink >> shift) & 0xff;
            mixed |= ((channel * opacity + alpha / 2) / alpha) << shift;
        }
        shades[shade] = mixed;
    }

    int text_width = (int)count * (GLYPH_WIDTH + GLYPH_GAP) - GLYPH_GAP;
    int left = x + (BODY_WIDTH - text_width) / 2;
    int top = y + (ICON_HEIGHT - GLYPH_HEIGHT) / 2;
    for (unsigned i = 0; i < count; ++i) {
        for (int row = 0; row < GLYPH_HEIGHT; ++row) {
            uint32_t *dest = pixels + (top + row) * WIDTH + left;
            for (int col = 0; col < GLYPH_WIDTH; ++col)
                dest[col] = shades[coverage[(unsigned char)glyphs[digits[i]][row][col]]];
        }
        left += GLYPH_WIDTH + GLYPH_GAP;
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
