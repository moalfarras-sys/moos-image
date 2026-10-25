// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QObject>
#include <QFileSystemWatcher>
#include <QTimer>
#include <QFile>
#include <QFileInfo>
#include <QSaveFile>
#include <QDir>
#include <QStandardPaths>
#include <QCryptographicHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QUrl>
#include <KConfig>
#include <KConfigGroup>
#include <sys/stat.h>
#include <unistd.h>
#include <cerrno>

// One event-driven observer inside the existing shell. Containment rewrites
// are cheap reads; only changed native image selections wake reconciliation.
// The event file is a hash, never a second wallpaper source or an executor.
class MoOSWallpaperIntent : public QObject {
public:
    explicit MoOSWallpaperIntent(QObject *parent):QObject(parent) {
        m_delay.setSingleShot(true);m_delay.setInterval(150);
        connect(&m_delay,&QTimer::timeout,this,[this] { inspect(); });
        const auto schedule=[this] { if (!m_delay.isActive()) m_delay.start(); };
        connect(&m_watcher,&QFileSystemWatcher::fileChanged,this,schedule);
        connect(&m_watcher,&QFileSystemWatcher::directoryChanged,this,schedule);
    }
    bool start() {
        if (m_started) return true;
        const auto directory=QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation);
        if (!QDir(directory).exists() || !m_watcher.addPath(directory)) return false;
        m_config=directory+QStringLiteral("/plasma-org.kde.plasma.desktop-appletsrc");
        m_pulse=directory+QStringLiteral("/moos-wallpaper-intent.conf");
        m_started=true;m_delay.start();return true;
    }
private:
    QString fingerprint() const {
        QFileInfo file(m_config);
        if (!file.isFile() || file.size()>4194304) return {};
        KConfig config(m_config,KConfig::SimpleConfig);
        const KConfigGroup containments(&config,QStringLiteral("Containments"));
        auto ids=containments.groupList();ids.sort();
        QJsonArray images;
        for (const auto &id:ids) {
            const auto desktop=containments.group(id);
            const auto plugin=desktop.readEntry("plugin",QString());
            if (plugin!="org.kde.plasma.folder" && plugin!="org.kde.desktopcontainment") continue;
            const auto wallpaper=desktop.readEntry("wallpaperplugin",QString());
            if (wallpaper!="org.moos.ui2.wallpaper" && wallpaper!="org.kde.image") return {};
            auto image=desktop.group("Wallpaper").group(wallpaper).group("General").readEntry("Image",QString());
            if (image.startsWith("file://")) {
                const QUrl url(image);if (!url.isLocalFile()) return {};
                image=url.toLocalFile();
            }
            if (!image.startsWith('/') || image.contains(QRegularExpression("[\\x00-\\x1f\\x7f]"))) return {};
            images.append(QJsonArray{id,wallpaper,image});
        }
        if (images.isEmpty()) return {};
        return QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(images).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex());
    }
    bool pulse(const QString &hash) const {
        struct stat state{};
        const auto path=QFile::encodeName(m_pulse);
        if (lstat(path.constData(),&state)==0) {
            if (!S_ISREG(state.st_mode) || state.st_uid!=getuid() || state.st_nlink!=1 || state.st_size>160) return false;
            QFile previous(m_pulse);
            if (!previous.open(QIODevice::ReadOnly) || !QRegularExpression("^\\[Wallpaper\\]\\nFingerprint=[0-9a-f]{64}\\n$").match(QString::fromLatin1(previous.readAll())).hasMatch()) return false;
        } else if (errno!=ENOENT) return false;
        QSaveFile output(m_pulse);
        const auto data=("[Wallpaper]\nFingerprint="+hash+"\n").toUtf8();
        return output.open(QIODevice::WriteOnly) && output.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner)
            && output.write(data)==data.size() && output.commit();
    }
    void inspect() {
        // KConfig replaces the inode atomically. Keep its directory owner and
        // rearm the exact file without a poll or a watcher on every file's data.
        if (!m_watcher.files().contains(m_config) && QFileInfo::exists(m_config)) m_watcher.addPath(m_config);
        const auto value=fingerprint();
        if (value.isEmpty() || value==m_last) return;
        m_last=value;
        if (!pulse(value)) qWarning("MoOS wallpaper intent refused unknown or unavailable destination");
    }
    bool m_started=false;
    QString m_config,m_pulse,m_last;
    QFileSystemWatcher m_watcher;
    QTimer m_delay;
};
