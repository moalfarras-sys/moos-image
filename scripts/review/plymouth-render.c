/* SDK-only native Plymouth script/renderer review; private X server, no host seat. */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/resource.h>
#include <ply-boot-splash.h>
#include <ply-pixel-display.h>
#include <ply-renderer.h>
#include <ply-list.h>
static ply_renderer_t *renderer;
static ply_renderer_head_t *head;
static const char *output;
static void capture(void *data, ply_event_loop_t *loop) {
    (void)data;
    ply_pixel_buffer_t *buffer = ply_renderer_get_buffer_for_head(renderer, head);
    unsigned long w = ply_pixel_buffer_get_width(buffer), h = ply_pixel_buffer_get_height(buffer);
    uint32_t *pixels = ply_pixel_buffer_get_argb32_data(buffer);
    FILE *file = fopen(output, "wb");
    if (!file) exit(5);
    fprintf(file, "P6\n%lu %lu\n255\n", w, h);
    for (unsigned long i = 0; i < w * h; i++) {
        unsigned char rgb[] = {pixels[i] >> 16, pixels[i] >> 8, pixels[i]};
        if (fwrite(rgb, 1, 3, file) != 3) exit(5);
    }
    if (fclose(file)) exit(5);
    struct rusage usage;
    if (getrusage(RUSAGE_SELF, &usage)) exit(5);
    printf("native %lux%lu peak_rss_kib=%ld user_cpu_s=%.6f system_cpu_s=%.6f\n",
           w, h, usage.ru_maxrss,
           usage.ru_utime.tv_sec + usage.ru_utime.tv_usec / 1000000.0,
           usage.ru_stime.tv_sec + usage.ru_stime.tv_usec / 1000000.0);
    ply_event_loop_exit(loop, 0);
}
int main(int argc, char **argv) {
    struct rlimit limit = {0, 0};
    if (setrlimit(RLIMIT_CORE, &limit)) return 2;
    if (argc < 4 || argc > 5) return 2;
    output = argv[3];
    ply_event_loop_t *loop = ply_event_loop_get_default();
    renderer = ply_renderer_new(PLY_RENDERER_TYPE_X11, NULL, NULL, NULL);
    if (!ply_renderer_open(renderer, true)) return 3;
    head = ply_list_node_get_data(ply_list_get_first_node(ply_renderer_get_heads(renderer)));
    if (!head) return 3;
    ply_pixel_display_t *display = ply_pixel_display_new(renderer, head);
    ply_boot_splash_t *splash = ply_boot_splash_new(argv[1], argv[2], NULL);
    if (!ply_boot_splash_load(splash)) return 4;
    ply_boot_splash_attach_to_event_loop(splash, loop);
    ply_boot_splash_add_pixel_display(splash, display);
    ply_renderer_activate(renderer);
    if (!ply_boot_splash_show(splash, PLY_BOOT_SPLASH_MODE_BOOT_UP)) return 4;
    if (argc == 5) ply_boot_splash_display_password(splash, argv[4], 4);
    ply_event_loop_watch_for_timeout(loop, 1.2, capture, NULL);
    int result = ply_event_loop_run(loop);
    ply_boot_splash_hide(splash);
    ply_boot_splash_free(splash);
    ply_pixel_display_free(display);
    ply_renderer_free(renderer);
    return result;
}
