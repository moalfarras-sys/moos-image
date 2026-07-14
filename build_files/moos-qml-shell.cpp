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

// SECOND LAUNCH, SAME WINDOW
//
// This host had no single-instance guard, and EVERY pure-QML MoOS app runs under it — so
// clicking Mo AI twice gave you two Mo AIs, and the Store the same. Measured on the maintainer's
// machine: `moai` three times produced three processes, each with its own QML engine and its own
// GPU surface, on a card the local brain already holds ~6 GB of. It is the same bug MoPlayer had
// (Flutter's G_APPLICATION_NON_UNIQUE) arriving by a different road, and it is worse here because
// one fix or one omission lands on every MoOS app at once.
//
// KDBusService(Unique) is the KDE answer rather than a lock file, and the reason is the raise. On
// Wayland a process may not simply pull its window to the front — it needs an XDG activation
// token, and only the launching shell can mint one. KDBusService carries that token across the
// D-Bus call (Plasma puts it in the environment; the second instance forwards it in platform_data)
// and KWindowSystem::activateWindow spends it. A lock file would have prevented the duplicate and
// left the user staring at a desktop where nothing appeared to happen.

#include <QGuiApplication>
#include <QIcon>
#include <QQmlApplicationEngine>
#include <QObject>
#include <QString>
#include <QUrl>
#include <QWindow>

#include <KDBusService>
#include <KWindowSystem>

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

    // One instance per app id. The service name is derived from applicationName, which is the
    // app id above — so Mo AI and the Store are unique against THEMSELVES and not against each
    // other, even though they are the same binary.
    //
    // Constructed before the engine on purpose: in Unique mode, a second launch hands its
    // arguments and its activation token to the running instance and exits from inside this
    // constructor. Building the QML engine first would mean paying for a window we are about to
    // throw away — which on this hardware means allocating a GPU surface we cannot spare.
    // NoExitOnFailure is about the BUS, not about the second instance: without it, a shell that
    // cannot reach a session bus at all refuses to start — which is exactly what happened in the
    // image build, where the QML smoke-test runs with no bus and every MoOS QML app came back
    // exit=1 instead of staying up. A missing bus must cost the guard, never the app.
    // The "somebody else already owns this app id" path is separate: it hands off and exits below,
    // and this flag does not touch it. Both halves are tested live, because guessing which one a
    // flag governs is how an app ships that either opens twice or does not open at all.
    KDBusService service(KDBusService::Unique | KDBusService::NoExitOnFailure);

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

    // Somebody launched us again — show them the window they already have. Without this the
    // second launch is silently swallowed and the app looks like it failed to start.
    QObject::connect(&service, &KDBusService::activateRequested, &app,
                     [&engine](const QStringList &, const QString &) {
        const QList<QObject *> roots = engine.rootObjects();
        if (roots.isEmpty()) {
            return;
        }
        if (auto *window = qobject_cast<QWindow *>(roots.first())) {
            window->show();
            window->raise();
            // Spends the XDG activation token KDBusService just installed. requestActivate()
            // alone is not enough on Wayland: with no token KWin refuses the focus steal and
            // merely blinks the task, which is not what "open the app" means.
            KWindowSystem::activateWindow(window);
        }
    });

    return app.exec();
}
