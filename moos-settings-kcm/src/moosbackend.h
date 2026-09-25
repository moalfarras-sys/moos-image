// SPDX-License-Identifier: GPL-2.0-or-later
// The one C++ backend every MoOS System Settings module shares.
//
// It is deliberately small and closed. It reads ONE private status document that
// /usr/libexec/moos-settings-status publishes, opens moos:// routes (the public
// router decides and confirms), reads three whitelisted environment values, lists
// the installed MoOS looks, and runs a FIXED list of unprivileged verbs declared
// below. It never runs a command a page composed, never escalates, and never
// accepts a path from QML.
// moos-settings-kcm/README.md documents the API for the pages.
#pragma once

#include <KQuickConfigModule>

#include <QDateTime>
#include <QFileSystemWatcher>
#include <QHash>
#include <QJsonObject>
#include <QList>
#include <QPointer>
#include <QProcess>
#include <QString>
#include <QTimer>
#include <QUrl>
#include <QVariantList>
#include <QVariantMap>

class MoOSJob final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString id READ id CONSTANT)
    Q_PROPERTY(QString argument READ argument CONSTANT)
    Q_PROPERTY(bool running READ running NOTIFY finished)
    Q_PROPERTY(bool ok READ ok NOTIFY finished)
    Q_PROPERTY(int exitCode READ exitCode NOTIFY finished)
    Q_PROPERTY(QString output READ output NOTIFY finished)
    Q_PROPERTY(QString errorOutput READ errorOutput NOTIFY finished)

public:
    MoOSJob(const QString &id, const QString &argument, QObject *parent);

    void start(const QString &program, const QStringList &arguments);

    QString id() const { return m_id; }
    QString argument() const { return m_argument; }
    bool running() const { return m_running; }
    bool ok() const { return !m_running && m_exitCode == 0; }
    int exitCode() const { return m_exitCode; }
    QString output() const { return m_output; }
    QString errorOutput() const { return m_errorOutput; }

Q_SIGNALS:
    void finished();

private:
    void complete(int exitCode, const QString &failure = QString());

    QString m_id;
    QString m_argument;
    bool m_running = false;
    int m_exitCode = -1;
    QString m_output;
    QString m_errorOutput;
    QProcess m_process;
    QTimer m_timeout;
};

class MoOSSettingsModule final : public KQuickConfigModule
{
    Q_OBJECT
    // The last ACCEPTED status document (empty while none is).
    Q_PROPERTY(QVariantMap status READ status NOTIFY statusChanged)
    Q_PROPERTY(bool statusValid READ statusValid NOTIFY statusChanged)
    // "" when valid; otherwise one of: no-runtime, unreadable, invalid, stale, helper.
    Q_PROPERTY(QString statusError READ statusError NOTIFY statusChanged)
    Q_PROPERTY(qint64 statusGeneratedAt READ statusGeneratedAt NOTIFY statusChanged)
    Q_PROPERTY(bool loading READ loading NOTIFY loadingChanged)
    // file:///usr/share/moos/moos-logo.png when that file exists, else empty.
    Q_PROPERTY(QUrl logoSource READ logoSource CONSTANT)

public:
    MoOSSettingsModule(QObject *parent, const KPluginMetaData &data);
    ~MoOSSettingsModule() override;

    QVariantMap status() const { return m_status; }
    bool statusValid() const { return m_statusValid; }
    QString statusError() const { return m_statusError; }
    qint64 statusGeneratedAt() const { return m_generatedAt; }
    bool loading() const { return m_loading; }
    QUrl logoSource() const { return m_logoSource; }

    void load() override;

    // Run the status helper now (queued behind a run in progress).
    Q_INVOKABLE void refresh();
    // Run it only when nothing valid and recent is shown; pages call this when shown.
    Q_INVOKABLE void ensureFresh();
    // Open a moos:// route through the desktop's URL handler. Returns whether it could
    // be handed over. Anything that is not a plain moos:// route is refused (false).
    Q_INVOKABLE bool openRoute(const QString &url);
    // MOAI_AGENT_PORT, MOAI_CONTROL_PORT or MOAI_GATEWAY_PORT, only when it is a port
    // number; "" for any other name or value.
    Q_INVOKABLE QString env(const QString &name) const;
    // Start one verb of the fixed list below. Returns the MoOSJob, or null when the id
    // is unknown or the argument fails that verb's validation.
    Q_INVOKABLE QObject *runFixed(const QString &id, const QString &argument = QString());
    // The MoOS looks installed here, read-only, for kcm_moos_appearance: one map per
    // /usr/share/plasma/look-and-feel/org.moos.ui2* package whose id theme-apply-lnf
    // accepts and whose metadata names it: id, name, nameAr, summaryEn, summaryAr,
    // preview (a file URL, or empty), light, family. Takes no argument; runs nothing.
    Q_INVOKABLE QVariantList moosThemes() const;

    // The status contract, as a pure function so it can be read and reasoned about alone.
    static bool acceptStatus(const QJsonObject &document, qint64 now, QString *reason);
    static constexpr qint64 MaximumStatusAge = 45;
    static constexpr qint64 FreshEnough = 15;

Q_SIGNALS:
    void statusChanged();
    void loadingChanged();
    void jobFinished(const QString &id, int exitCode, const QString &output);

private:
    void setLoading(bool value);
    void readerFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void readStatus(bool helperFailed);
    void rejectStatus(const QString &reason);
    void statusDirectoryChanged();
    void sourceDirectoryChanged();
    void watchSources();
    QString statusPath() const;
    QString stateDirectory() const;
    QString configDirectory() const;

    QVariantMap m_status;
    bool m_statusValid = false;
    QString m_statusError;
    qint64 m_generatedAt = 0;
    bool m_loading = false;
    bool m_refreshQueued = false;
    QUrl m_logoSource;
    QString m_statusDirectory;
    QDateTime m_statusModified;
    QHash<QString, QDateTime> m_sourceModified;
    QFileSystemWatcher m_watcher;
    QTimer m_sourceSettle;
    QProcess m_reader;
    QList<QPointer<MoOSJob>> m_jobs;
};
