// SDK-only grammar proof against the actual rebuilt script plugin. No devices.
#include <dlfcn.h>
#include <stdio.h>
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    void *lib = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!lib) { fprintf(stderr, "%s\n", dlerror()); return 2; }
    void *(*parse)(const char *) = dlsym(lib, "script_parse_file");
    void (*destroy)(void *) = dlsym(lib, "script_parse_op_free");
    if (!parse || !destroy) return 2;
    void *op = parse(argv[2]);
    if (!op) return 71;
    destroy(op);
    dlclose(lib);
    return 0;
}
