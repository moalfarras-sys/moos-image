/* Build-only public-API proof of the actual RPM library's frame cancellation. */
#define _GNU_SOURCE
#include <stdlib.h>
#include <stdio.h>
#include <dlfcn.h>
#include "ply-boot-splash.h"

#ifdef TEST_PLUGIN
static ply_boot_splash_plugin_t *create(ply_key_file_t *key) {
        (void) key;
        return (ply_boot_splash_plugin_t *) calloc(1, 1);
}
static void destroy(ply_boot_splash_plugin_t *plugin) { free(plugin); }
static bool show(ply_boot_splash_plugin_t *plugin, ply_event_loop_t *loop,
                 ply_buffer_t *buffer, ply_boot_splash_mode_t mode) {
        (void) plugin; (void) loop; (void) buffer; (void) mode;
        return true;
}
const ply_boot_splash_plugin_interface_t *ply_boot_splash_plugin_get_interface(void) {
        static const ply_boot_splash_plugin_interface_t api = {
                .create_plugin = create, .destroy_plugin = destroy,
                .show_splash_screen = show,
        };
        return &api;
}
#else
static void *owner;
static ply_event_loop_timeout_handler_t frame;
static int cancellations;

void ply_event_loop_watch_for_timeout(ply_event_loop_t *loop, double seconds,
                                     ply_event_loop_timeout_handler_t handler, void *data) {
        void (*real_watch)(ply_event_loop_t *, double, ply_event_loop_timeout_handler_t, void *)
                = dlsym(RTLD_NEXT, "ply_event_loop_watch_for_timeout");
        if (!real_watch) exit(2);
        if (data == owner) frame = handler;
        real_watch(loop, seconds, handler, data);
}
void ply_event_loop_stop_watching_for_timeout(ply_event_loop_t *loop,
                                            ply_event_loop_timeout_handler_t handler, void *data) {
        void (*real_stop)(ply_event_loop_t *, ply_event_loop_timeout_handler_t, void *)
                = dlsym(RTLD_NEXT, "ply_event_loop_stop_watching_for_timeout");
        if (!real_stop) exit(2);
        if (data == owner && handler == frame) cancellations++;
        real_stop(loop, handler, data);
}
static void finish(void *data, ply_event_loop_t *loop) {
        (void) data;
        ply_event_loop_exit(loop, 0);
}
int main(int argc, char **argv) {
        if (argc != 3) return 2;
        ply_event_loop_t *loop = ply_event_loop_new();
        ply_boot_splash_t *splash = ply_boot_splash_new(argv[1], argv[2], NULL);
        owner = splash;
        if (!ply_boot_splash_load(splash)) return 3;
        ply_boot_splash_attach_to_event_loop(splash, loop);
        if (!ply_boot_splash_show(splash, PLY_BOOT_SPLASH_MODE_BOOT_UP) || !frame) return 4;
        ply_boot_splash_free(splash);
        if (!cancellations) {
                /* Stop before running a freed callback in the unmodified control. */
                ply_event_loop_free(loop);
                return 71;
        }
        ply_event_loop_watch_for_timeout(loop, 0.02, finish, loop);
        int result = ply_event_loop_run(loop);
        ply_event_loop_free(loop);
        printf("Actual package library cancelled its frame before free\n");
        return result;
}
#endif
