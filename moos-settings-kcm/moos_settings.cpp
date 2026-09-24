// SPDX-License-Identifier: GPL-2.0-or-later
// Read-only MoOS state inside Plasma's real System Settings host.
#include <KPluginFactory>
#include <KQuickConfigModule>
#include <QDir>
#include <QFile>
#include <QFileSystemWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QStandardPaths>
#include <QStringList>
#include <QTimer>
#include <QVariantMap>

class MoOSSettingsModule final : public KQuickConfigModule {
    Q_OBJECT
    Q_PROPERTY(QVariantMap status READ status NOTIFY statusChanged)
    Q_PROPERTY(bool loading READ loading NOTIFY loadingChanged)
    Q_PROPERTY(QString initialPage READ initialPage CONSTANT)
    Q_PROPERTY(QString requestedPage READ requestedPage NOTIFY requestedPageChanged)
public:
    MoOSSettingsModule(QObject *parent, const KPluginMetaData &data)
        : KQuickConfigModule(parent, data) {
        setButtons(NoAdditionalButton);
        const QString requested = qEnvironmentVariable("MOOS_SETTINGS_SECTION");
        m_initialPage = QStringList{QStringLiteral("update"), QStringLiteral("recovery"),
                                    QStringLiteral("remote"), QStringLiteral("about"),
                                    QStringLiteral("whats-new")}.contains(requested)
                            ? requested : QStringLiteral("overview");
        m_requestedPage = m_initialPage;
        const QString runtime = qEnvironmentVariable("XDG_RUNTIME_DIR");
        if (!runtime.isEmpty()) {
            m_requestDirectory = QDir(runtime).filePath(QStringLiteral("moos-settings"));
            QDir().mkpath(m_requestDirectory);
            m_requestWatcher.addPath(m_requestDirectory);
            connect(&m_requestWatcher, &QFileSystemWatcher::directoryChanged,
                    this, &MoOSSettingsModule::readRequestedPage);
            readRequestedPage();
        }
        m_timer.setInterval(10000);
        connect(&m_timer, &QTimer::timeout, this, &MoOSSettingsModule::refresh);
        connect(&m_reader, qOverload<int, QProcess::ExitStatus>(&QProcess::finished),
                this, [this](int, QProcess::ExitStatus) { readStatus(); });
        connect(&m_reader, &QProcess::errorOccurred, this,
                [this](QProcess::ProcessError) { setLoading(false); });
        m_timer.start();
        QTimer::singleShot(0, this, &MoOSSettingsModule::refresh);
    }

    QVariantMap status() const { return m_status; }
    bool loading() const { return m_loading; }
    QString initialPage() const { return m_initialPage; }
    QString requestedPage() const { return m_requestedPage; }

    Q_INVOKABLE void refresh() {
        if (m_reader.state() != QProcess::NotRunning)
            return;
        setLoading(true);
        m_reader.start(QStringLiteral("/usr/libexec/moos-settings-status"), {});
    }

Q_SIGNALS:
    void statusChanged();
    void loadingChanged();
    void requestedPageChanged();

private:
    void readRequestedPage() {
        QFile file(QDir(m_requestDirectory).filePath(QStringLiteral("request")));
        if (!file.open(QIODevice::ReadOnly)) return;
        const QString requested = QString::fromUtf8(file.readAll()).trimmed();
        if (!QStringList{QStringLiteral("overview"), QStringLiteral("update"),
                         QStringLiteral("recovery"), QStringLiteral("remote"),
                         QStringLiteral("about"), QStringLiteral("whats-new")}.contains(requested)) return;
        if (m_requestedPage == requested) return;
        m_requestedPage = requested;
        Q_EMIT requestedPageChanged();
    }
    void setLoading(bool value) {
        if (m_loading == value) return;
        m_loading = value;
        Q_EMIT loadingChanged();
    }
    void readStatus() {
        const QString runtime = qEnvironmentVariable("XDG_RUNTIME_DIR",
            QStandardPaths::writableLocation(QStandardPaths::CacheLocation));
        QFile file(QDir(runtime).filePath(QStringLiteral("moos-settings/status.json")));
        if (file.open(QIODevice::ReadOnly)) {
            const QJsonDocument document = QJsonDocument::fromJson(file.readAll());
            if (document.isObject()) {
                m_status = document.object().toVariantMap();
                Q_EMIT statusChanged();
            }
        }
        setLoading(false);
    }
    QVariantMap m_status;
    QString m_initialPage;
    QString m_requestedPage;
    QString m_requestDirectory;
    QFileSystemWatcher m_requestWatcher;
    bool m_loading = false;
    QTimer m_timer;
    QProcess m_reader;
};

K_PLUGIN_CLASS_WITH_JSON(MoOSSettingsModule, "kcm_moos.json")
#include "moos_settings.moc"
