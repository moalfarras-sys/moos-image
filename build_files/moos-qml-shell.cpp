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
#include <QQmlContext>
#include <QObject>
#include <QString>
#include <QUrl>
#include <QWindow>
#include <QDir>
#include <QFile>
#include <QFileDevice>
#include <QProcess>
#include <QRegularExpression>
#include <QVariantList>

#include <KDBusService>
#include <KWindowSystem>

#include <cstdio>
#include <cstdlib>

// InstallerBridge — the ONE way the (unprivileged, pure-QML) MoOS installer hands
// the user's answers to the privileged install helper WITHOUT putting a password
// in a moos:// URL (which xdg-open/journald could log). QML calls
// MoosInstaller.writeRecipe(json); we write it to a FIXED path (the installer's own
// cache dir) with 0600 perms. The path is computed here from the environment, not
// taken from QML, so a hosted app cannot aim the write anywhere else. The helper
// reads it, hashes the password, plants the answers on the target, and wipes it.
class InstallerBridge : public QObject
{
    Q_OBJECT
public:
    using QObject::QObject;

    Q_INVOKABLE bool writeRecipe(const QString &json)
    {
        const char *xdg = std::getenv("XDG_CACHE_HOME");
        const char *home = std::getenv("HOME");
        QString base;
        if (xdg && *xdg) {
            base = QString::fromLocal8Bit(xdg);
        } else if (home && *home) {
            base = QString::fromLocal8Bit(home) + QLatin1String("/.cache");
        } else {
            return false;
        }
        const QString dir = base + QLatin1String("/moos-installer");
        QDir().mkpath(dir);
        const QString path = dir + QLatin1String("/recipe.json");
        QFile f(path);
        if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
            return false;
        }
        f.write(json.toUtf8());
        f.close();
        QFile::setPermissions(path, QFileDevice::ReadOwner | QFileDevice::WriteOwner);
        return true;
    }
};

// StoreBridge — a narrow process boundary for Mo Store and the Welcome.
//
// A `moos:` URL is a public desktop URL scheme: any web page can ask the
// desktop to open one.  It therefore must never be the authority that installs,
// updates or removes software.  The old Store fired
// `moos://store/install/<id>` and the URL handler performed the install; that
// made a browser tab capable of starting a catalogue install.
//
// This bridge is exposed only to the two trusted QML files loaded from the
// read-only image (org.moos.store and org.moos.welcome).  It starts one fixed
// backend with an argv list — never a shell — and that backend validates every
// identifier again, owns the Flatpak transaction and publishes job state.  The
// bridge deliberately contains no package-manager behaviour itself.
class StoreBridge : public QObject
{
    Q_OBJECT
public:
    explicit StoreBridge(bool enabled, QObject *parent = nullptr)
        : QObject(parent), m_enabled(enabled)
    {
    }

    Q_INVOKABLE bool installApps(const QVariantList &values)
    {
        if (!m_enabled || values.isEmpty() || values.size() > 64) {
            return false;
        }
        QStringList args{QStringLiteral("install")};
        for (const QVariant &value : values) {
            const QString id = value.toString();
            if (!validId(id)) {
                return false;
            }
            args.append(id);
        }
        return start(args);
    }

    Q_INVOKABLE bool removeApp(const QString &id)
    {
        return m_enabled && validId(id)
            && start({QStringLiteral("remove"), id});
    }

    Q_INVOKABLE bool runApp(const QString &id)
    {
        return m_enabled && validId(id)
            && start({QStringLiteral("run"), id});
    }

    Q_INVOKABLE bool updateApps()
    {
        return m_enabled && start({QStringLiteral("update")});
    }

    Q_INVOKABLE bool checkUpdates()
    {
        // Read-only counterpart of updateApps(): the backend reports what an
        // update would act on and writes updates.json.  It takes no lock, so
        // the Store can answer "what is pending?" while a job is running.
        return m_enabled && start({QStringLiteral("check-updates")});
    }

    Q_INVOKABLE bool refreshIndex()
    {
        return m_enabled && start({QStringLiteral("refresh-index")});
    }

    Q_INVOKABLE bool cancelJob()
    {
        return m_enabled && start({QStringLiteral("cancel")});
    }

    Q_INVOKABLE bool openEngine(const QString &name)
    {
        static const QStringList allowed{
            QStringLiteral("bazaar"),
            QStringLiteral("discover"),
            QStringLiteral("firmware"),
            QStringLiteral("permissions")
        };
        return m_enabled && allowed.contains(name)
            && start({QStringLiteral("open-engine"), name});
    }

    Q_INVOKABLE bool openSystemUpdater()
    {
        // The updater is a fixed, signed MoOS application.  It owns its own
        // confirmation and privilege boundary; no identifier or command comes
        // from QML.
        return m_enabled
            && QProcess::startDetached(QStringLiteral("/usr/bin/moos-update"),
                                       QStringList{});
    }

private:
    bool m_enabled = false;

    static bool validId(const QString &id)
    {
        // Flatpak reverse-DNS ids and the small, signed MoOS catalogue both fit
        // this character set.  The backend applies the stricter source-specific
        // schema; this first gate keeps control chars, paths and option-looking
        // values out of argv before a process is even created.
        static const QRegularExpression pattern(
            QStringLiteral("^[A-Za-z0-9][A-Za-z0-9._-]{1,254}$"));
        return pattern.match(id).hasMatch()
            && !id.contains(QStringLiteral(".."))
            && !id.startsWith(QLatin1Char('-'))
            && !id.endsWith(QLatin1Char('.'));
    }

    static bool start(const QStringList &args)
    {
        return QProcess::startDetached(QStringLiteral("/usr/bin/moos-storectl"),
                                       args);
    }
};

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
    // The installer's secure answers channel (see InstallerBridge). Harmless for
    // the other MoOS apps that never call it.
    InstallerBridge installerBridge;
    engine.rootContext()->setContextProperty(QStringLiteral("MoosInstaller"),
                                             &installerBridge);
    const bool storeBridgeEnabled =
        appId == QLatin1String("org.moos.store")
        || appId == QLatin1String("org.moos.welcome");
    StoreBridge storeBridge(storeBridgeEnabled);
    if (storeBridgeEnabled) {
        engine.rootContext()->setContextProperty(QStringLiteral("MoosStore"),
                                                 &storeBridge);
    }
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

// InstallerBridge uses Q_OBJECT/Q_INVOKABLE, so this .cpp is moc'd and the
// generated meta-object is included here (build.sh runs moc before g++).
#include "moos-qml-shell.moc"
