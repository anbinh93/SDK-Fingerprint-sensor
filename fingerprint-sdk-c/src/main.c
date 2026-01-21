/**
 * USB Fingerprint Reader CLI
 * ==========================
 * Example application using the fingerprint SDK
 *
 * Usage:
 *   sudo ./fingerprint info
 *   sudo ./fingerprint capture [output.raw]
 *   sudo ./fingerprint led <on|off|red|green|blue|white>
 *   sudo ./fingerprint add
 *   sudo ./fingerprint match
 *   sudo ./fingerprint delete <user_id|all>
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <math.h>
#include <zlib.h>
#include "fingerprint.h"

/* ==================== PNG Writer ==================== */

/**
 * Write a grayscale image as PNG file
 * Simple PNG encoder for 8-bit grayscale images
 */
static int write_png(const char *filename, const uint8_t *data, int width, int height) {
    FILE *f = fopen(filename, "wb");
    if (!f) return -1;

    /* PNG signature */
    const uint8_t png_sig[8] = {0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A};
    fwrite(png_sig, 1, 8, f);

    /* Helper to write a PNG chunk */
    #define WRITE_CHUNK(type, data, len) do { \
        uint8_t _len[4] = {(len)>>24, (len)>>16, (len)>>8, (len)}; \
        fwrite(_len, 1, 4, f); \
        fwrite(type, 1, 4, f); \
        if ((len) > 0) fwrite(data, 1, (len), f); \
        uint32_t _crc = crc32(0, (const Bytef*)(type), 4); \
        if ((len) > 0) _crc = crc32(_crc, (const Bytef*)(data), (len)); \
        uint8_t _crcb[4] = {_crc>>24, _crc>>16, _crc>>8, _crc}; \
        fwrite(_crcb, 1, 4, f); \
    } while(0)

    /* IHDR chunk: width, height, bit depth, color type, etc */
    uint8_t ihdr[13] = {
        width >> 24, width >> 16, width >> 8, width,      /* width */
        height >> 24, height >> 16, height >> 8, height,  /* height */
        8,    /* bit depth */
        0,    /* color type: grayscale */
        0,    /* compression method */
        0,    /* filter method */
        0     /* interlace method */
    };
    WRITE_CHUNK("IHDR", ihdr, 13);

    /* Prepare raw data with filter bytes (one filter byte per row) */
    size_t raw_size = (size_t)height * (1 + width);
    uint8_t *raw = (uint8_t*)malloc(raw_size);
    if (!raw) { fclose(f); return -1; }

    for (int y = 0; y < height; y++) {
        raw[y * (1 + width)] = 0;  /* filter type: None */
        memcpy(&raw[y * (1 + width) + 1], &data[y * width], width);
    }

    /* Compress with zlib */
    uLongf compressed_size = compressBound(raw_size);
    uint8_t *compressed = (uint8_t*)malloc(compressed_size);
    if (!compressed) { free(raw); fclose(f); return -1; }

    if (compress2(compressed, &compressed_size, raw, raw_size, Z_BEST_COMPRESSION) != Z_OK) {
        free(raw);
        free(compressed);
        fclose(f);
        return -1;
    }
    free(raw);

    /* IDAT chunk */
    WRITE_CHUNK("IDAT", compressed, (int)compressed_size);
    free(compressed);

    /* IEND chunk */
    WRITE_CHUNK("IEND", NULL, 0);

    #undef WRITE_CHUNK

    fclose(f);
    return 0;
}

/* ==================== Command Handlers ==================== */

static void cmd_info(fp_device_t *dev) {
    printf("Device Information:\n");
    printf("  Registered users: %d\n", fp_get_user_count(dev));
    printf("  Compare level: %d\n", fp_get_compare_level(dev));
}

static void cmd_led(fp_device_t *dev, const char *state) {
    fp_led_color_t color;

    if (strcasecmp(state, "on") == 0 || strcasecmp(state, "white") == 0) {
        color = FP_LED_WHITE;
    } else if (strcasecmp(state, "off") == 0) {
        color = FP_LED_OFF;
    } else if (strcasecmp(state, "red") == 0) {
        color = FP_LED_RED;
    } else if (strcasecmp(state, "green") == 0) {
        color = FP_LED_GREEN;
    } else if (strcasecmp(state, "blue") == 0) {
        color = FP_LED_BLUE;
    } else {
        printf("Unknown LED state: %s\n", state);
        printf("Valid: on, off, red, green, blue, white\n");
        return;
    }

    int ret = fp_led_on(dev, color);
    if (ret == FP_OK) {
        printf("LED: %s\n", state);
    } else {
        printf("Failed to set LED: %s\n", fp_error_string(ret));
    }
}

static void cmd_capture(fp_device_t *dev, const char *output) {
    uint8_t image[FP_IMAGE_SIZE];
    size_t image_size;
    int ret;

    printf("Place your finger on the sensor...\n");
    fp_led_on(dev, FP_LED_WHITE);

    /* Wait for valid fingerprint */
    printf("Waiting for finger...");
    fflush(stdout);

    int found = 0;
    for (int i = 0; i < 50; i++) {  /* 5 seconds timeout */
        ret = fp_capture_image(dev, image, &image_size);
        if (ret == FP_OK && fp_has_fingerprint(image, image_size)) {
            found = 1;
            break;
        }
        printf(".");
        fflush(stdout);
        usleep(100000);  /* 100ms */
    }
    printf("\n");

    if (!found) {
        printf("No finger detected (empty sensor)\n");
        fp_led_off(dev);
        return;
    }

    printf("Fingerprint captured!\n");
    fp_beep(dev, 50);
    fp_led_off(dev);

    printf("Image size: %zu bytes\n", image_size);

    /* Calculate quality metrics */
    double sum = 0;
    for (size_t i = 0; i < image_size; i++) {
        sum += image[i];
    }
    double avg = sum / image_size;

    double variance = 0;
    for (size_t i = 0; i < image_size; i++) {
        double diff = image[i] - avg;
        variance += diff * diff;
    }
    variance /= image_size;

    double std_dev = sqrt(variance);

    printf("Image quality: StdDev=%.1f (higher is better)\n", std_dev);

    /* Save raw image */
    FILE *f = fopen(output, "wb");
    if (f) {
        fwrite(image, 1, image_size, f);
        fclose(f);
        printf("Saved raw image: %s (192x192 grayscale, 8-bit)\n", output);
    } else {
        printf("Failed to save image\n");
        return;
    }

    /* Generate PNG filename and save */
    char png_filename[256];
    size_t len = strlen(output);

    /* If output ends with .raw, replace with .png; otherwise append .png */
    if (len > 4 && strcmp(output + len - 4, ".raw") == 0) {
        strncpy(png_filename, output, len - 4);
        png_filename[len - 4] = '\0';
        strcat(png_filename, ".png");
    } else {
        snprintf(png_filename, sizeof(png_filename), "%s.png", output);
    }

    if (write_png(png_filename, image, FP_IMAGE_WIDTH, FP_IMAGE_HEIGHT) == 0) {
        printf("Saved PNG image: %s\n", png_filename);
    } else {
        printf("Failed to save PNG image\n");
    }
}

static void cmd_add(fp_device_t *dev) {
    uint8_t image[FP_IMAGE_SIZE];
    size_t image_size;
    int ret;

    printf("Place your finger on the sensor...\n");
    fp_led_on(dev, FP_LED_GREEN);

    /* Wait for valid fingerprint */
    printf("Waiting for finger...");
    fflush(stdout);

    int found = 0;
    for (int i = 0; i < 50; i++) {
        ret = fp_capture_image(dev, image, &image_size);
        if (ret == FP_OK && fp_has_fingerprint(image, image_size)) {
            found = 1;
            break;
        }
        printf(".");
        fflush(stdout);
        usleep(100000);
    }
    printf("\n");

    if (!found) {
        printf("No finger detected\n");
        fp_led_off(dev);
        return;
    }

    printf("Adding fingerprint...\n");
    int assigned_id;
    ret = fp_add_user(dev, 0, &assigned_id);
    fp_led_off(dev);

    if (ret == FP_OK) {
        fp_beep(dev, 100);
        printf("Added user #%d\n", assigned_id);
    } else {
        printf("Failed to add fingerprint: %s\n", fp_error_string(ret));
    }
}

static void cmd_match(fp_device_t *dev) {
    printf("Place your finger on the sensor...\n");
    fp_led_on(dev, FP_LED_BLUE);

    fp_match_result_t result;
    int ret = fp_match(dev, 10.0f, &result);
    fp_led_off(dev);

    if (ret == FP_OK && result.matched) {
        fp_beep(dev, 100);
        printf("Matched: User #%d\n", result.user_id);
    } else if (ret == FP_OK) {
        printf("No match found\n");
    } else {
        printf("Match error: %s\n", fp_error_string(ret));
    }
}

static void cmd_delete(fp_device_t *dev, const char *target) {
    int ret;

    if (strcasecmp(target, "all") == 0) {
        ret = fp_delete_all(dev);
        if (ret == FP_OK) {
            printf("Deleted all fingerprints\n");
        } else {
            printf("Delete failed: %s\n", fp_error_string(ret));
        }
    } else {
        char *endptr;
        long user_id = strtol(target, &endptr, 10);

        if (*endptr != '\0' || user_id < 1 || user_id > FP_MAX_USERS) {
            printf("Invalid user ID: %s\n", target);
            return;
        }

        ret = fp_delete_user(dev, (int)user_id);
        if (ret == FP_OK) {
            printf("Deleted user #%ld\n", user_id);
        } else {
            printf("Delete failed: %s\n", fp_error_string(ret));
        }
    }
}

static void print_usage(const char *prog) {
    printf("USB Fingerprint Reader CLI\n\n");
    printf("Usage:\n");
    printf("  %s info                    Show device information\n", prog);
    printf("  %s capture [output.raw]    Capture fingerprint image\n", prog);
    printf("  %s led <state>             Control LED (on/off/red/green/blue/white)\n", prog);
    printf("  %s add                     Add new fingerprint\n", prog);
    printf("  %s match                   Match fingerprint\n", prog);
    printf("  %s delete <id|all>         Delete fingerprint(s)\n", prog);
    printf("\nExamples:\n");
    printf("  sudo %s info\n", prog);
    printf("  sudo %s capture fingerprint.raw\n", prog);
    printf("  sudo %s led red\n", prog);
    printf("  sudo %s add\n", prog);
    printf("  sudo %s match\n", prog);
    printf("  sudo %s delete all\n", prog);
}

/* ==================== Main ==================== */

int main(int argc, char *argv[]) {
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }

    const char *cmd = argv[1];

    /* Initialize library */
    int ret = fp_init();
    if (ret != 0) {
        printf("ERROR: Failed to initialize libusb\n");
        return 1;
    }

    /* Open device */
    fp_device_t dev;
    ret = fp_open(&dev);
    if (ret != FP_OK) {
        printf("ERROR: %s\n", fp_error_string(ret));
        printf("Make sure device is connected and you have permissions (sudo)\n");
        fp_exit();
        return 1;
    }

    /* Execute command */
    if (strcmp(cmd, "info") == 0) {
        cmd_info(&dev);
    } else if (strcmp(cmd, "capture") == 0) {
        const char *output = (argc >= 3) ? argv[2] : "fingerprint.raw";
        cmd_capture(&dev, output);
    } else if (strcmp(cmd, "led") == 0) {
        if (argc < 3) {
            printf("Usage: %s led <on|off|red|green|blue|white>\n", argv[0]);
        } else {
            cmd_led(&dev, argv[2]);
        }
    } else if (strcmp(cmd, "add") == 0) {
        cmd_add(&dev);
    } else if (strcmp(cmd, "match") == 0) {
        cmd_match(&dev);
    } else if (strcmp(cmd, "delete") == 0) {
        if (argc < 3) {
            printf("Usage: %s delete <user_id|all>\n", argv[0]);
        } else {
            cmd_delete(&dev, argv[2]);
        }
    } else {
        printf("Unknown command: %s\n", cmd);
        print_usage(argv[0]);
    }

    /* Cleanup */
    fp_close(&dev);
    fp_exit();

    return 0;
}
