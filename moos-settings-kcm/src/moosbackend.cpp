// SPDX-License-Identifier: GPL-2.0-or-later
#include "moosbackend.h"

#include <QCoreApplication>
#include <QDesktopServices>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJSEngine>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLoggingCategory>
#include <QRegularExpression>

#include <algorithm>

Q_LOGGING_CATEGORY(MOOS_SETTINGS, "moos.settings", QtInfoMsg)

namespace
{
constexpr auto StatusHelper = "/usr/libexec/moos-settings-status";
constexpr auto ThemeTool = "/usr/bin/moos-theme";
constexpr auto SystemdRun = "/usr/bin/systemd-run";
// What a change needs from the session to reach the desktop, passed by name to its unit
// (systemd-run -E NAME copies the value from this process); only the ones that are set.
constexpr const char *SessionEnvironment[] = {
    "WAYLAND_DISPLAY", "DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR",
    "HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME",
    "XDG_CONFIG_DIRS", "XDG_DATA_DIRS", "LANG", "LANGUAGE", "LC_ALL", "PATH",
};
// A change's output files are removed when its page reads them; one a page never read
// (the window closed first) is removed by the next page after this long.
constexpr qint64 StaleJobFileSeconds = 60 * 60;
constexpr auto LogoFile = "/usr/share/moos/moos-logo.png";
// Where the MoOS looks are installed: the same directory moos-theme apply-lnf requires.
constexpr auto LookAndFeelRoot = "/usr/share/plasma/look-and-feel";
constexpr qint64 MaximumMetadataBytes = 64 * 1024;
constexpr qint64 MaximumStatusBytes = 1024 * 1024;
constexpr int MaximumOutputBytes = 64 * 1024;
constexpr int JobTimeoutMs = 180 * 1000;
constexpr int KeptFinishedJobs = 16;
// Mo PC Remote is on exactly while this link exists: `systemctl --user enable` writes it
// into the target the unit's [Install] section names (WantedBy=plasma-workspace.target in
// mo-remote-personal.service; tests/test_moos_settings.py holds the two together).
constexpr auto RemoteEnableLink = "systemd/user/plasma-workspace.target.wants/mo-remote-personal.service";

// ── The status contract ─────────────────────────────────────────────────────
// Only what a page binds is required; a document missing any of it is rejected
// whole, so no page ever presents a default as if it were a measured fact.
struct Field {
    const char *group; // nullptr: a top-level key
    const char *key;
    QJsonValue::Type type;
};
constexpr Field StatusShape[] = {
    {nullptr, "hostname", QJsonValue::String},
    {nullptr, "kernel", QJsonValue::String},
    {nullptr, "kernelLabel", QJsonValue::String},
    {nullptr, "arch", QJsonValue::String},
    {nullptr, "cpu", QJsonValue::String},
    {nullptr, "gpu", QJsonValue::String},
    {nullptr, "session", QJsonValue::String},
    {nullptr, "uptimeSeconds", QJsonValue::Double},
    {"deployment", "known", QJsonValue::Bool},
    {"deployment", "signed", QJsonValue::Bool},
    {"deployment", "staged", QJsonValue::Bool},
    {"deployment", "edition", QJsonValue::String},
    {"deployment", "builtAt", QJsonValue::Double},
    {"deployment", "version", QJsonValue::String},
    {"deployment", "digest", QJsonValue::String},
    {"deployment", "stagedVersion", QJsonValue::String},
    {"deployment", "previousVersion", QJsonValue::String},
    {"deployment", "rollback", QJsonValue::Double},
    {"deployment", "rollbackQueued", QJsonValue::Bool},
    {"deployment", "rollbackTarget", QJsonValue::String},
    {"update", "known", QJsonValue::Bool},
    {"update", "state", QJsonValue::String},
    {"update", "event", QJsonValue::String},
    {"update", "updated", QJsonValue::Double},
    {"update", "latestVersion", QJsonValue::String},
    {"remote", "available", QJsonValue::Bool},
    {"remote", "active", QJsonValue::Bool},
    {"remote", "enabled", QJsonValue::Bool},
    {"remote", "failed", QJsonValue::Bool},
    {"remote", "fast", QJsonValue::Bool},
    {"apps", "known", QJsonValue::Bool},
    {"apps", "state", QJsonValue::String},
    {"apps", "updated", QJsonValue::Double},
    {"apps", "failures", QJsonValue::Array},
    {"memory", "total", QJsonValue::String},
    {"storage", "total", QJsonValue::String},
    {"storage", "free", QJsonValue::String},
    {"whatsNew", "entries", QJsonValue::Array},
    {"whatsNew", "fresh", QJsonValue::Double},
};
// Identity values arrive already normalised, in both languages.
constexpr const char *BilingualLabels[] = {"editionLabel", "archLabel", "sessionLabel"};

// ── The fixed verbs ─────────────────────────────────────────────────────────
// Nothing else can be started from a page. Each argument kind is validated here,
// before a process exists, and moos-theme validates it again.
enum class Argument { None, LookAndFeel, Motion, Clarity, WallpaperToken };
struct Verb {
    const char *id;
    const char *program;
    const char *arguments[2];
    Argument argument;
    // Changes the desktop. moos-theme carries it as a transaction it can roll back only
    // if it is allowed to finish, so it must outlive the page that started it.
    bool mutates;
};
constexpr Verb FixedVerbs[] = {
    {"theme-status", ThemeTool, {nullptr, nullptr}, Argument::None, false},
    {"theme-motion-status", ThemeTool, {"motion", nullptr}, Argument::None, false},
    {"theme-clarity-status", ThemeTool, {"clarity", nullptr}, Argument::None, false},
    {"theme-apply-lnf", ThemeTool, {"apply-lnf", nullptr}, Argument::LookAndFeel, true},
    {"theme-undo", ThemeTool, {"undo", nullptr}, Argument::None, true},
    {"theme-motion", ThemeTool, {"motion", nullptr}, Argument::Motion, true},
    {"theme-clarity", ThemeTool, {"clarity", nullptr}, Argument::Clarity, true},
    {"theme-wallpaper-reset", ThemeTool, {"wallpaper-reset", nullptr}, Argument::None, true},
    {"theme-wallpaper-token", ThemeTool, {"wallpaper-token", nullptr}, Argument::WallpaperToken, true},
};

bool argumentAccepted(Argument kind, const QString &value)
{
    static const QRegularExpression lookAndFeel(QStringLiteral("^org\\.moos\\.ui2[a-z.]*$"));
    static const QRegularExpression token(QStringLiteral("^[A-Za-z0-9_.~%-]{1,4096}$"));
    switch (kind) {
    case Argument::None:
        return value.isEmpty();
    case Argument::LookAndFeel:
        return value.size() <= 64 && lookAndFeel.match(value).hasMatch();
    case Argument::Motion:
        return value == QLatin1String("still") || value == QLatin1String("gentle")
            || value == QLatin1String("alive");
    case Argument::Clarity:
        return value == QLatin1String("clear") || value == QLatin1String("balanced")
            || value == QLatin1String("solid");
    case Argument::WallpaperToken:
        return token.match(value).hasMatch();
    }
    return false;
}

QString runtimeBase()
{
    // The same fallback chain moos-settings-status writes through.
    const QString runtime = qEnvironmentVariable("XDG_RUNTIME_DIR");
    if (!runtime.isEmpty() && QDir::isAbsolutePath(runtime))
        return runtime;
    const QString cache = qEnvironmentVariable("XDG_CACHE_HOME");
    if (!cache.isEmpty() && QDir::isAbsolutePath(cache))
        return cache;
    const QString home = qEnvironmentVariable("HOME");
    return home.isEmpty() ? QString() : QDir(home).filePath(QStringLiteral(".cache"));
}

QDateTime modified(const QString &path)
{
    const QFileInfo info(path);
    return info.exists() ? info.lastModified() : QDateTime();
}

QString readBounded(const QString &path)
{
    QFile file(path);
    if (path.isEmpty() || !file.open(QIODevice::ReadOnly))
        return QString();
    return QString::fromUtf8(file.read(MaximumOutputBytes));
}
} // namespace

// ── MoOSJob ─────────────────────────────────────────────────────────────────

MoOSJob::MoOSJob(const QString &id, const QString &argument, bool ceiling, QObject *parent)
    : QObject(parent)
    , m_id(id)
    , m_argument(argument)
{
    m_process.setProcessChannelMode(QProcess::SeparateChannels);
    m_process.setWorkingDirectory(QDir::homePath());
    m_timeout.setSingleShot(true);
    m_timeout.setInterval(JobTimeoutMs);
    if (ceiling) {
        connect(&m_timeout, &QTimer::timeout, this, [this] {
            m_process.kill();
            complete(-1, QStringLiteral("timed out"));
        });
    }
    connect(&m_process, &QProcess::finished, this, [this](int exitCode, QProcess::ExitStatus status) {
        complete(status == QProcess::NormalExit ? exitCode : -1);
    });
    connect(&m_process, &QProcess::errorOccurred, this, [this](QProcess::ProcessError error) {
        if (error == QProcess::FailedToStart)
            complete(-1, QStringLiteral("could not start"));
    });
}

MoOSJob::~MoOSJob()
{
    if (!m_running)
        return;
    // Ended here, explicitly, before ~QProcess would: its finished() must not reach a job
    // that is being destroyed. A query (or a change with no user manager) is this
    // process's own child and stops with it; a change in its own unit keeps running, and
    // only its waiting client ends — its output is no one's to read any more.
    m_process.disconnect(this);
    m_timeout.stop();
    m_process.kill();
    m_process.waitForFinished(1000);
    if (!m_outputFile.isEmpty()) {
        QFile::remove(m_outputFile);
        QFile::remove(m_errorFile);
    }
}

void MoOSJob::start(const QString &program, const QStringList &arguments, const QString &outputFile,
                    const QString &errorFile)
{
    m_running = true;
    m_outputFile = outputFile;
    m_errorFile = errorFile;
    m_timeout.start(); // stops the process only for a job built with a ceiling
    m_process.start(program, arguments);
}

void MoOSJob::complete(int exitCode, const QString &failure)
{
    if (!m_running)
        return;
    m_running = false;
    m_timeout.stop();
    m_exitCode = exitCode;
    if (m_outputFile.isEmpty()) {
        m_output = QString::fromUtf8(m_process.readAllStandardOutput().left(MaximumOutputBytes));
        m_errorOutput = failure.isEmpty()
            ? QString::fromUtf8(m_process.readAllStandardError().left(MaximumOutputBytes))
            : failure;
    } else {
        // The change wrote into its unit's files; systemd-run's own words (when it could
        // not start the unit at all) are on its stderr.
        m_output = readBounded(m_outputFile);
        const QString client = QString::fromUtf8(m_process.readAllStandardError().left(MaximumOutputBytes));
        const QString change = readBounded(m_errorFile);
        m_errorOutput = !failure.isEmpty() ? failure : (change.isEmpty() ? client : change);
        QFile::remove(m_outputFile);
        QFile::remove(m_errorFile);
    }
    Q_EMIT finished();
}

// ── MoOSSettingsModule ──────────────────────────────────────────────────────

MoOSSettingsModule::MoOSSettingsModule(QObject *parent, const KPluginMetaData &data)
    : KQuickConfigModule(parent, data)
{
    setButtons(NoAdditionalButton);
    if (QFileInfo::exists(QString::fromLatin1(LogoFile)))
        m_logoSource = QUrl::fromLocalFile(QString::fromLatin1(LogoFile));

    const QString base = runtimeBase();
    if (!base.isEmpty()) {
        m_statusDirectory = QDir(base).filePath(QStringLiteral("moos-settings"));
        if (QDir().mkpath(m_statusDirectory)) {
            QFile::setPermissions(m_statusDirectory,
                                  QFileDevice::ReadOwner | QFileDevice::WriteOwner | QFileDevice::ExeOwner);
            m_watcher.addPath(m_statusDirectory);
        }
    }
    connect(&m_watcher, &QFileSystemWatcher::directoryChanged, this, [this](const QString &path) {
        if (path == m_statusDirectory)
            statusDirectoryChanged();
        else
            sourceDirectoryChanged();
    });
    watchSources();

    // A source record changed (an update was staged, an app update finished, Fast
    // Remote flipped, Mo PC Remote was turned on or off): gather once after the writes
    // settle, not once per write.
    m_sourceSettle.setSingleShot(true);
    m_sourceSettle.setInterval(1500);
    connect(&m_sourceSettle, &QTimer::timeout, this, &MoOSSettingsModule::refresh);

    connect(&m_reader, &QProcess::finished, this, &MoOSSettingsModule::readerFinished);
    connect(&m_reader, &QProcess::errorOccurred, this, [this](QProcess::ProcessError error) {
        if (error == QProcess::FailedToStart)
            readerFinished(-1, QProcess::CrashExit);
    });
    // systemsettings forwards a second `systemsettings <this module>` to the running
    // window as an activation: that is the page being shown again.
    connect(this, &KAbstractConfigModule::activationRequested, this, &MoOSSettingsModule::ensureFresh);
    // One line when the page really loaded: the image build's load gate requires it, so a
    // page that failed to construct cannot pass because it printed nothing wrong.
    connect(this, &KQuickConfigModule::mainUiReady, this, [this] {
        qCInfo(MOOS_SETTINGS, "MOOS_KCM_READY %s", qPrintable(metaData().pluginId()));
    });

    // A change outlives this page only through the user's service manager, which owns its
    // unit; without one (no private socket) it stays a child of this module.
    static const QRegularExpression plainPath(QStringLiteral("^/[A-Za-z0-9_./-]+$"));
    const QString runtime = qEnvironmentVariable("XDG_RUNTIME_DIR");
    const QString jobs = QDir(runtime).filePath(QStringLiteral("moos-settings/jobs"));
    if (plainPath.match(runtime).hasMatch() && QFileInfo(QString::fromLatin1(SystemdRun)).isExecutable()
        && QFileInfo::exists(QDir(runtime).filePath(QStringLiteral("systemd/private"))) && QDir().mkpath(jobs)
        && QFile::setPermissions(jobs, QFileDevice::ReadOwner | QFileDevice::WriteOwner | QFileDevice::ExeOwner)) {
        m_jobDirectory = jobs;
        m_changesOutlivePage = true;
        const QDateTime stale = QDateTime::currentDateTime().addSecs(-StaleJobFileSeconds);
        for (const QFileInfo &old : QDir(jobs).entryInfoList(QDir::Files)) {
            if (old.lastModified() < stale)
                QFile::remove(old.filePath());
        }
    }
    QTimer::singleShot(0, this, &MoOSSettingsModule::refresh);
}

MoOSSettingsModule::~MoOSSettingsModule()
{
    // A change still running in its own unit keeps running whatever happens here; its
    // waiting client moves to the application so it still reads and removes the output
    // (and says nothing about a process destroyed while running) when the page is gone.
    for (const QPointer<MoOSJob> &job : std::as_const(m_jobs)) {
        if (job && job->running() && job->property("outlivesPage").toBool()) {
            job->setParent(QCoreApplication::instance());
            connect(job, &MoOSJob::finished, job, &QObject::deleteLater);
        }
    }
    // The helper is read-only and publishes atomically; stopping it loses nothing.
    if (m_reader.state() != QProcess::NotRunning) {
        m_reader.kill();
        m_reader.waitForFinished(1000);
    }
}

void MoOSSettingsModule::load()
{
    KQuickConfigModule::load();
    ensureFresh();
}

QString MoOSSettingsModule::statusPath() const
{
    return m_statusDirectory.isEmpty() ? QString()
                                       : QDir(m_statusDirectory).filePath(QStringLiteral("status.json"));
}

QString MoOSSettingsModule::stateDirectory() const
{
    const QString state = qEnvironmentVariable("XDG_STATE_HOME");
    const QString base = !state.isEmpty() && QDir::isAbsolutePath(state)
        ? state
        : QDir(QDir::homePath()).filePath(QStringLiteral(".local/state"));
    return QDir(base).filePath(QStringLiteral("moos"));
}

QString MoOSSettingsModule::configDirectory() const
{
    const QString config = qEnvironmentVariable("XDG_CONFIG_HOME");
    return !config.isEmpty() && QDir::isAbsolutePath(config)
        ? config
        : QDir(QDir::homePath()).filePath(QStringLiteral(".config"));
}

void MoOSSettingsModule::watchSources()
{
    // Directories, not files: every owner publishes by atomic rename, which a file
    // watch loses after the first replacement. The Remote unit's enable link can
    // appear in a directory that does not exist yet: every level of it that exists is
    // watched, a level created below a watched one is added when it appears, and a
    // refresh adds whatever exists by then.
    const QString remoteLink = QDir(configDirectory()).filePath(QString::fromLatin1(RemoteEnableLink));
    const QString wants = QFileInfo(remoteLink).path();
    const QString userUnits = QFileInfo(wants).path();
    for (const QString &directory : {QStringLiteral("/run/moos"), stateDirectory(), QFileInfo(userUnits).path(),
                                     userUnits, wants}) {
        if (QFileInfo(directory).isDir() && !m_watcher.directories().contains(directory))
            m_watcher.addPath(directory);
    }
    for (const QString &source : {QStringLiteral("/run/moos/update-state.json"),
                                  QDir(stateDirectory()).filePath(QStringLiteral("app-updates.json")),
                                  QDir(stateDirectory()).filePath(QStringLiteral("fast-remote.on")),
                                  remoteLink}) {
        if (!m_sourceModified.contains(source))
            m_sourceModified.insert(source, modified(source));
    }
}

void MoOSSettingsModule::sourceDirectoryChanged()
{
    watchSources();
    bool changed = false;
    for (auto it = m_sourceModified.begin(); it != m_sourceModified.end(); ++it) {
        const QDateTime now = modified(it.key());
        if (now != it.value()) {
            it.value() = now;
            changed = true;
        }
    }
    if (changed)
        m_sourceSettle.start();
}

void MoOSSettingsModule::statusDirectoryChanged()
{
    // Our own run is read when it finishes; a temporary file appearing mid-run must
    // not make the page read the previous document.
    if (m_reader.state() != QProcess::NotRunning)
        return;
    const QDateTime now = modified(statusPath());
    if (now.isValid() && now != m_statusModified)
        readStatus(false);
}

void MoOSSettingsModule::setLoading(bool value)
{
    if (m_loading == value)
        return;
    m_loading = value;
    Q_EMIT loadingChanged();
}

void MoOSSettingsModule::refresh()
{
    if (m_reader.state() != QProcess::NotRunning) {
        m_refreshQueued = true;
        return;
    }
    if (m_statusDirectory.isEmpty()) {
        rejectStatus(QStringLiteral("no-runtime"));
        return;
    }
    watchSources();
    setLoading(true);
    m_reader.start(QString::fromLatin1(StatusHelper), {});
}

void MoOSSettingsModule::ensureFresh()
{
    if (m_reader.state() != QProcess::NotRunning)
        return;
    const qint64 age = QDateTime::currentSecsSinceEpoch() - m_generatedAt;
    if (!m_statusValid || age < -5 || age > FreshEnough)
        refresh();
}

void MoOSSettingsModule::readerFinished(int exitCode, QProcess::ExitStatus exitStatus)
{
    readStatus(exitStatus != QProcess::NormalExit || exitCode != 0);
    setLoading(false);
    if (m_refreshQueued) {
        m_refreshQueued = false;
        QTimer::singleShot(0, this, &MoOSSettingsModule::refresh);
    }
}

void MoOSSettingsModule::rejectStatus(const QString &reason)
{
    m_status.clear();
    m_statusValid = false;
    m_statusError = reason;
    m_generatedAt = 0;
    Q_EMIT statusChanged();
}

void MoOSSettingsModule::readStatus(bool helperFailed)
{
    const QString path = statusPath();
    QFile file(path);
    m_statusModified = modified(path);
    if (path.isEmpty() || !file.open(QIODevice::ReadOnly)) {
        rejectStatus(helperFailed ? QStringLiteral("helper") : QStringLiteral("unreadable"));
        return;
    }
    if (file.size() > MaximumStatusBytes) {
        rejectStatus(QStringLiteral("invalid"));
        return;
    }
    QJsonParseError error;
    const QJsonDocument document = QJsonDocument::fromJson(file.readAll(), &error);
    if (error.error != QJsonParseError::NoError || !document.isObject()) {
        rejectStatus(QStringLiteral("invalid"));
        return;
    }
    QString reason;
    if (!acceptStatus(document.object(), QDateTime::currentSecsSinceEpoch(), &reason)) {
        // A helper that failed leaves the previous document behind; say which it was.
        rejectStatus(helperFailed && reason == QLatin1String("stale") ? QStringLiteral("helper") : reason);
        return;
    }
    m_status = document.object().toVariantMap();
    m_statusValid = true;
    m_statusError.clear();
    m_generatedAt = document.object().value(QStringLiteral("generatedAt")).toInteger();
    Q_EMIT statusChanged();
}

bool MoOSSettingsModule::acceptStatus(const QJsonObject &document, qint64 now, QString *reason)
{
    const auto fail = [reason](const char *why) {
        if (reason)
            *reason = QString::fromLatin1(why);
        return false;
    };
    const QJsonValue schema = document.value(QStringLiteral("schema"));
    if (!schema.isDouble() || schema.toDouble() != 1.0)
        return fail("invalid");
    if (document.value(QStringLiteral("product")).toString() != QLatin1String("MoOS"))
        return fail("invalid");
    const QJsonValue generated = document.value(QStringLiteral("generatedAt"));
    if (!generated.isDouble())
        return fail("invalid");
    const qint64 age = now - generated.toInteger();
    if (age < -5 || age > MaximumStatusAge)
        return fail("stale");

    for (const Field &field : StatusShape) {
        QJsonValue value;
        if (field.group) {
            const QJsonValue group = document.value(QLatin1String(field.group));
            if (!group.isObject())
                return fail("invalid");
            value = group.toObject().value(QLatin1String(field.key));
        } else {
            value = document.value(QLatin1String(field.key));
        }
        if (value.type() != field.type)
            return fail("invalid");
    }
    for (const char *label : BilingualLabels) {
        const QJsonObject texts = document.value(QLatin1String(label)).toObject();
        if (!texts.value(QStringLiteral("ar")).isString() || !texts.value(QStringLiteral("en")).isString())
            return fail("invalid");
    }
    const QJsonValue destinations = document.value(QStringLiteral("destinations"));
    if (!destinations.isObject())
        return fail("invalid");
    const QJsonObject routes = destinations.toObject();
    for (auto it = routes.begin(); it != routes.end(); ++it) {
        if (!it.value().isBool())
            return fail("invalid");
    }
    if (reason)
        reason->clear();
    return true;
}

bool MoOSSettingsModule::openRoute(const QString &url)
{
    // A route is a fixed case in moos-open; the page may only name one.
    static const QRegularExpression route(QStringLiteral("^moos://[a-z0-9][a-z0-9._-]*(?:/[a-z0-9][a-z0-9._-]*){0,3}$"));
    if (url.size() > 160 || !route.match(url).hasMatch() || url.contains(QLatin1String("..")))
        return false;
    const bool opened = QDesktopServices::openUrl(QUrl(url));
    if (opened && (url.startsWith(QLatin1String("moos://remote/")) || url.startsWith(QLatin1String("moos://do/")))) {
        // An action's effect lands in a unit or a record a moment later; look twice, then stop.
        QTimer::singleShot(3000, this, &MoOSSettingsModule::refresh);
        QTimer::singleShot(10000, this, &MoOSSettingsModule::refresh);
    }
    return opened;
}

QString MoOSSettingsModule::env(const QString &name) const
{
    static const QRegularExpression port(QStringLiteral("^[0-9]{1,5}$"));
    if (name != QLatin1String("MOAI_AGENT_PORT") && name != QLatin1String("MOAI_CONTROL_PORT")
        && name != QLatin1String("MOAI_GATEWAY_PORT"))
        return QString();
    const QString value = qEnvironmentVariable(name.toLatin1().constData());
    return port.match(value).hasMatch() ? value : QString();
}

QObject *MoOSSettingsModule::runFixed(const QString &id, const QString &argument)
{
    const Verb *verb = nullptr;
    for (const Verb &candidate : FixedVerbs) {
        if (id == QLatin1String(candidate.id)) {
            verb = &candidate;
            break;
        }
    }
    if (!verb || !argumentAccepted(verb->argument, argument))
        return nullptr;

    QStringList arguments;
    for (const char *fixed : verb->arguments) {
        if (fixed)
            arguments << QString::fromLatin1(fixed);
    }
    if (verb->argument != Argument::None)
        arguments << argument;

    // Keep a bounded history of finished jobs; a running one is never dropped.
    int finished = 0;
    for (int index = m_jobs.size() - 1; index >= 0; --index) {
        MoOSJob *job = m_jobs.at(index);
        if (!job) {
            m_jobs.removeAt(index);
        } else if (!job->running() && ++finished > KeptFinishedJobs) {
            job->deleteLater();
            m_jobs.removeAt(index);
        }
    }

    const bool outlives = verb->mutates && m_changesOutlivePage;
    auto *job = new MoOSJob(id, argument, !outlives, this);
    QJSEngine::setObjectOwnership(job, QJSEngine::CppOwnership);
    connect(job, &MoOSJob::finished, this, [this, job] {
        Q_EMIT jobFinished(job->id(), job->exitCode(), job->output());
    });
    m_jobs.append(job);
    if (!outlives) {
        job->start(QString::fromLatin1(verb->program), arguments);
        return job;
    }
    // systemd-run --wait returns the change's own exit status (systemd-run(1), EXIT
    // STATUS); stdin is /dev/null and the output goes to files this job reads when it ends.
    job->setProperty("outlivesPage", true);
    const QString name = QStringLiteral("moos-settings-%1-%2-%3")
                             .arg(id)
                             .arg(QCoreApplication::applicationPid())
                             .arg(++m_jobCounter);
    const QString output = QDir(m_jobDirectory).filePath(name + QStringLiteral(".out"));
    const QString error = QDir(m_jobDirectory).filePath(name + QStringLiteral(".err"));
    QStringList run{QStringLiteral("--user"), QStringLiteral("--quiet"), QStringLiteral("--collect"),
                    QStringLiteral("--wait"), QStringLiteral("--service-type=exec"),
                    QStringLiteral("--unit=") + name,
                    QStringLiteral("--property=StandardOutput=truncate:") + output,
                    QStringLiteral("--property=StandardError=truncate:") + error};
    for (const char *variable : SessionEnvironment) {
        if (qEnvironmentVariableIsSet(variable))
            run << QStringLiteral("--setenv=") + QString::fromLatin1(variable);
    }
    run << QStringLiteral("--") << QString::fromLatin1(verb->program) << arguments;
    job->start(QString::fromLatin1(SystemdRun), run, output, error);
    return job;
}

QVariantList MoOSSettingsModule::moosThemes() const
{
    // Read-only and closed: one fixed directory, names this backend would pass to
    // theme-apply-lnf, and each package's own metadata. Nothing from QML reaches it.
    struct Look {
        QString family;
        bool light;
        QVariantMap entry;
    };
    QList<Look> looks;
    const QDir root(QString::fromLatin1(LookAndFeelRoot));
    const QStringList ids = root.entryList({QStringLiteral("org.moos.ui2*")}, QDir::Dirs | QDir::NoDotAndDotDot,
                                           QDir::Name);
    for (const QString &id : ids) {
        // Every look offered is one the apply verb accepts, so no card can fail validation.
        if (!argumentAccepted(Argument::LookAndFeel, id))
            continue;
        const QDir package(root.filePath(id));
        QFile metadata(package.filePath(QStringLiteral("metadata.json")));
        if (metadata.size() > MaximumMetadataBytes || !metadata.open(QIODevice::ReadOnly))
            continue;
        const QJsonObject plugin =
            QJsonDocument::fromJson(metadata.readAll()).object().value(QStringLiteral("KPlugin")).toObject();
        const QString name = plugin.value(QStringLiteral("Name")).toString().trimmed();
        if (plugin.value(QStringLiteral("Id")).toString() != id || name.isEmpty())
            continue;
        const QString nameAr = plugin.value(QStringLiteral("Name[ar]")).toString().trimmed();
        // A MoOS package describes itself "Arabic | English"; a Description[ar] wins.
        const QString description = plugin.value(QStringLiteral("Description")).toString().trimmed();
        const qsizetype bar = description.indexOf(QLatin1String(" | "));
        const QString summaryEn = bar >= 0 ? description.mid(bar + 3).trimmed() : description;
        QString summaryAr = plugin.value(QStringLiteral("Description[ar]")).toString().trimmed();
        if (summaryAr.isEmpty())
            summaryAr = bar >= 0 ? description.left(bar).trimmed() : description;
        QUrl preview;
        for (const char *candidate : {"contents/previews/preview.png", "contents/previews/fullscreenpreview.jpg"}) {
            const QString path = package.filePath(QLatin1String(candidate));
            if (QFileInfo(path).isFile()) {
                preview = QUrl::fromLocalFile(path);
                break;
            }
        }
        // Every MoOS light look is its dark sibling's id + ".light" (moos-theme's own rule).
        const bool light = id.endsWith(QLatin1String(".light"));
        const QString family = light ? id.chopped(6) : id;
        looks.append({family,
                      light,
                      {{QStringLiteral("id"), id},
                       {QStringLiteral("name"), name},
                       {QStringLiteral("nameAr"), nameAr.isEmpty() ? name : nameAr},
                       {QStringLiteral("summaryEn"), summaryEn},
                       {QStringLiteral("summaryAr"), summaryAr},
                       {QStringLiteral("preview"), preview},
                       {QStringLiteral("light"), light},
                       {QStringLiteral("family"), family}}});
    }
    // Families together, the base family first, each dark look before its light sibling.
    const QString base = QStringLiteral("org.moos.ui2");
    std::stable_sort(looks.begin(), looks.end(), [&base](const Look &one, const Look &other) {
        if ((one.family == base) != (other.family == base))
            return one.family == base;
        if (one.family != other.family)
            return one.family < other.family;
        return !one.light && other.light;
    });
    QVariantList result;
    for (const Look &look : looks)
        result.append(look.entry);
    return result;
}
