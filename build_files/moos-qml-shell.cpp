// moos-qml-shell — the QML host MoOS's pure-QML apps run under.
//
// WHY THIS EXISTS
//
// Mo AI launched as `qml-qt6 /usr/share/moos/apps/moai/main.qml`. Qt derives a
// Wayland window's app_id from QGuiApplication::desktopFileName(), and when that
// is unset it falls back to organizationDomain reversed + the executable's base
// name. For the stock QML runtime that yields:
//
//     org.qt-project.qml-qt6
//
// Plasma matches a window to its launcher by app_id. `org.qt-project.qml-qt6` is
// not `org.moos.moai`, so the task manager could not find org.moos.moai.desktop
// and fell back to the QML runtime's own icon — the generic green Qt diamond the
// user kept seeing instead of the Mo AI orb. The window was Mo AI; the taskbar
// had no way to know.
//
// `qml-qt6 --help` offers no flag for this (checked on the image: -a/--apptype,
// -I, -f, -c, --desktop, --gles, --software … and nothing for the app id). The
// only supported way to set it is QGuiApplication::setDesktopFileName(), which
// means hosting the QML ourselves. That is all this binary does.
//
// StartupWMClass in the .desktop file was the tempting shortcut, and it is wrong
// here: moos-welcome and moos-ui-migrate run under the same runtime, so they all
// share the one app_id and would all collapse onto whichever launcher claimed it.
// Giving each app a real app_id fixes the icon for every one of them at once.
//
// Built in build_files/build.sh section (c4b). Deliberately tiny: it must not
// become a place where app behaviour lives — the apps are still plain QML.

#include <QGuiApplication>
#include <QIcon>
#include <QQmlApplicationEngine>
#include <QString>
#include <QUrl>

#include <cstdio>

namespace {

void usage()
{
    std::fputs(
        "usage: moos-qml-shell --app-id <id> --qml <file> [--icon <name>] [-- <app args>]\n"
        "\n"
        "  --app-id  reverse-DNS desktop file id, e.g. org.moos.moai. Becomes the\n"
        "            Wayland app_id, which is how Plasma finds the launcher icon.\n"
        "  --qml     the QML file to load.\n"
        "  --icon    icon theme name; defaults to the app id.\n",
        stderr);
}

} // namespace

int main(int argc, char *argv[])
{
    QString appId;
    QString qmlPath;
    QString iconName;

    // Parse only our own options, and stop at `--` so everything after it stays
    // in argv for the QML side to read via Qt.application.arguments — that is how
    // `moai --panel device` reaches the app.
    int i = 1;
    for (; i < argc; ++i) {
        const QString arg = QString::fromLocal8Bit(argv[i]);
        if (arg == QLatin1String("--")) {
            break;
        } else if (arg == QLatin1String("--app-id") && i + 1 < argc) {
            appId = QString::fromLocal8Bit(argv[++i]);
        } else if (arg == QLatin1String("--qml") && i + 1 < argc) {
            qmlPath = QString::fromLocal8Bit(argv[++i]);
        } else if (arg == QLatin1String("--icon") && i + 1 < argc) {
            iconName = QString::fromLocal8Bit(argv[++i]);
        } else {
            std::fprintf(stderr, "moos-qml-shell: unknown option: %s\n", argv[i]);
            usage();
            return 2;
        }
    }

    if (appId.isEmpty() || qmlPath.isEmpty()) {
        usage();
        return 2;
    }
    if (iconName.isEmpty()) {
        iconName = appId;
    }

    // Both of these must be set BEFORE the first window is created. The desktop
    // file name is the one that decides the Wayland app_id; the application name
    // is what Qt falls back to, so it is set as well rather than left to chance.
    QGuiApplication::setDesktopFileName(appId);
    QGuiApplication::setApplicationName(appId);
    QGuiApplication::setOrganizationDomain(QString());

    QGuiApplication app(argc, argv);

    // X11/XWayland has no app_id; it matches on the window icon and WM_CLASS.
    // Setting the icon explicitly means the app looks right under either.
    QGuiApplication::setWindowIcon(QIcon::fromTheme(iconName));

    QQmlApplicationEngine engine;
    engine.load(QUrl::fromLocalFile(qmlPath));
    if (engine.rootObjects().isEmpty()) {
        std::fprintf(stderr, "moos-qml-shell: %s produced no root object\n",
                     qPrintable(qmlPath));
        return 1;
    }

    return app.exec();
}
