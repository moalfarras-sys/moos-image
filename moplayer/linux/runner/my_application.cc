#include "my_application.h"

#include <flutter_linux/flutter_linux.h>
#ifdef GDK_WINDOWING_X11
#include <gdk/gdkx.h>
#endif

#include "flutter/generated_plugin_registrant.h"

struct _MyApplication {
  GtkApplication parent_instance;
  char** dart_entrypoint_arguments;
};

G_DEFINE_TYPE(MyApplication, my_application, GTK_TYPE_APPLICATION)

// Called when first Flutter frame received.
static void first_frame_cb(MyApplication* self, FlView *view)
{
  gtk_widget_show(gtk_widget_get_toplevel(GTK_WIDGET(view)));
}

// Implements GApplication::activate.
static void my_application_activate(GApplication* application) {
  MyApplication* self = MY_APPLICATION(application);
  GtkWindow* window =
      GTK_WINDOW(gtk_application_window_new(GTK_APPLICATION(application)));

  // No GTK header bar, and no window manager decoration either.
  //
  // Flutter's template draws a client-side GNOME header bar; that one was always
  // wrong here, because a GNOME-looking title bar inside the OS that ships this
  // app is a foreign object. What replaced it — letting KWin decorate the window
  // — was right for a browser and wrong for a cinema surface: MoPlayer draws its
  // own caption bar (see `lib/app/window_chrome.dart`), which carries the logo,
  // the connected source and the window buttons, and a second, system-drawn bar
  // above it is simply a duplicated header.
  //
  // This is a real trade, and it is paid in full elsewhere: server-side
  // decoration provides the resize borders, the drop shadow and KWin's snapping
  // for free, and going undecorated means the app implements the first two
  // itself (`ResizeEdges`, `WindowCaption`). `MOPLAYER_SSD=1` hands the window
  // back to KWin for anyone debugging a compositor that will not cooperate — and
  // `DesktopService.useSystemDecoration` reads the same variable, so the app's
  // own caption bar steps aside in the same breath.
  //
  // Set here rather than only from Dart: `window_manager` applies the style
  // after the engine is up, which is one frame *after* the compositor has
  // already mapped and decorated the window — long enough to see it flash.
  gtk_window_set_title(window, "MoPlayer");

  const char* ssd = g_getenv("MOPLAYER_SSD");
  if (ssd == nullptr || g_strcmp0(ssd, "1") != 0) {
    // How you actually go frameless on Wayland — and it is *not*
    // `gtk_window_set_decorated(FALSE)`.
    //
    // MoOS is a Wayland session, and on Wayland a GTK3 window with no titlebar
    // widget asks KWin for a *server-side* decoration, which KWin duly draws in
    // MoOS's Aurorae theme. `set_decorated(FALSE)` does not countermand that:
    // GDK's Wayland backend has nothing to apply it to, so the request is
    // dropped and the title bar stays. (On X11 it would have worked, which is
    // exactly why this looked correct until someone ran it.)
    //
    // Setting *any* titlebar widget switches the window to client-side
    // decoration, and KWin then draws nothing at all — the same mechanism
    // Flutter's own template uses when it installs a GtkHeaderBar. So the window
    // takes a titlebar that is empty and zero-height, GTK reports CSD, KWin
    // stands down, and MoPlayer's own caption bar (drawn in Dart) is the only
    // header in the window.
    //
    // GTK keeps drawing the window's shadow and its invisible resize border for
    // us, which is most of what server-side decoration was providing.
    GtkWidget* empty_titlebar = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 0);
    gtk_widget_set_size_request(empty_titlebar, 0, 0);

    // Without this, GTK's theme still paints a header background — a one-pixel
    // strip of the wrong colour across the top of the window, which is the kind
    // of detail that reads as "unfinished" without anyone being able to say why.
    GtkStyleContext* context = gtk_widget_get_style_context(empty_titlebar);
    g_autoptr(GtkCssProvider) css = gtk_css_provider_new();
    gtk_css_provider_load_from_data(
        css,
        "* { background: none; border: none; box-shadow: none; "
        "min-height: 0; padding: 0; margin: 0; }",
        -1, nullptr);
    gtk_style_context_add_provider(context, GTK_STYLE_PROVIDER(css),
                                   GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);

    gtk_widget_show(empty_titlebar);
    gtk_window_set_titlebar(window, empty_titlebar);
  }

  // A first size that suits a cinema surface. window_manager reasserts this from
  // Dart, clamped to what the display can actually show (see
  // DesktopService.initWindow — a 4K panel at 275% scale has a *logical* desktop
  // of 1397x786, and a 1440x900 window does not fit on it). This is what the
  // compositor sees before the engine is up, and it is what stops Plasma from
  // briefly mapping a small default window.
  gtk_window_set_default_size(window, 1280, 800);

  g_autoptr(FlDartProject) project = fl_dart_project_new();
  fl_dart_project_set_dart_entrypoint_arguments(project, self->dart_entrypoint_arguments);

  FlView* view = fl_view_new(project);
  GdkRGBA background_color;
  // The app's canvas (AppColors.surface0). The engine paints this before the
  // first Dart frame; leaving it pure black makes the window flash a different
  // shade of dark than the app it is about to become.
  gdk_rgba_parse(&background_color, "#070809");
  fl_view_set_background_color(view, &background_color);
  gtk_widget_show(GTK_WIDGET(view));
  gtk_container_add(GTK_CONTAINER(window), GTK_WIDGET(view));

  // Show the window when Flutter renders.
  // Requires the view to be realized so we can start rendering.
  g_signal_connect_swapped(view, "first-frame", G_CALLBACK(first_frame_cb), self);
  gtk_widget_realize(GTK_WIDGET(view));

  fl_register_plugins(FL_PLUGIN_REGISTRY(view));

  gtk_widget_grab_focus(GTK_WIDGET(view));
}

// Implements GApplication::local_command_line.
static gboolean my_application_local_command_line(GApplication* application, gchar*** arguments, int* exit_status) {
  MyApplication* self = MY_APPLICATION(application);
  // Strip out the first argument as it is the binary name.
  self->dart_entrypoint_arguments = g_strdupv(*arguments + 1);

  g_autoptr(GError) error = nullptr;
  if (!g_application_register(application, nullptr, &error)) {
     g_warning("Failed to register: %s", error->message);
     *exit_status = 1;
     return TRUE;
  }

  g_application_activate(application);
  *exit_status = 0;

  return TRUE;
}

// Implements GApplication::startup.
static void my_application_startup(GApplication* application) {
  //MyApplication* self = MY_APPLICATION(object);

  // Perform any actions required at application startup.

  G_APPLICATION_CLASS(my_application_parent_class)->startup(application);
}

// Implements GApplication::shutdown.
static void my_application_shutdown(GApplication* application) {
  //MyApplication* self = MY_APPLICATION(object);

  // Perform any actions required at application shutdown.

  G_APPLICATION_CLASS(my_application_parent_class)->shutdown(application);
}

// Implements GObject::dispose.
static void my_application_dispose(GObject* object) {
  MyApplication* self = MY_APPLICATION(object);
  g_clear_pointer(&self->dart_entrypoint_arguments, g_strfreev);
  G_OBJECT_CLASS(my_application_parent_class)->dispose(object);
}

static void my_application_class_init(MyApplicationClass* klass) {
  G_APPLICATION_CLASS(klass)->activate = my_application_activate;
  G_APPLICATION_CLASS(klass)->local_command_line = my_application_local_command_line;
  G_APPLICATION_CLASS(klass)->startup = my_application_startup;
  G_APPLICATION_CLASS(klass)->shutdown = my_application_shutdown;
  G_OBJECT_CLASS(klass)->dispose = my_application_dispose;
}

static void my_application_init(MyApplication* self) {}

MyApplication* my_application_new() {
  // Set the program name to the application ID, which helps various systems
  // like GTK and desktop environments map this running application to its
  // corresponding .desktop file. This ensures better integration by allowing
  // the application to be recognized beyond its binary name.
  g_set_prgname(APPLICATION_ID);

  return MY_APPLICATION(g_object_new(my_application_get_type(),
                                     "application-id", APPLICATION_ID,
                                     "flags", G_APPLICATION_NON_UNIQUE,
                                     nullptr));
}
