// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "appearanceprofile.h"
#include "wallpaperintent.h"
#include <QBuffer>
#include <QCryptographicHash>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QDBusVariant>
#include <QFile>
#include <QFont>
#include <QDBusObjectPath>
#include <QGuiApplication>
#include <QIcon>
#include <QImageReader>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QQuickImageProvider>
#include <QRegularExpression>
#include <QTemporaryDir>
#include <QMutex>
#include <QMutexLocker>
#include <QMap>
#include <QDir>
#include <QSharedPointer>
#include <KColorScheme>
#include <KConfig>
#include <KConfigGroup>
#include <KSharedConfig>
#include <KIconTheme>
#include <KIconLoader>
#include <Plasma/Theme>
#include <pwd.h>
#include <unistd.h>
#include <dlfcn.h>

// Image.asynchronous can call the provider on Qt's loading thread. Keep
// immutable frames independent of the GUI QObject's lifetime and retain just
// the current/previous serial, matching palette handoff without unbounded cache.
struct MoOSAppearanceImages {
    QMutex mutex;
    QMap<quint64,QImage> frames;
};

class MoOSSessionAppearance : public QObject {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.moos.LoginAppearance")
    Q_PROPERTY(bool isGreeter READ isGreeter CONSTANT)
    Q_PROPERTY(bool ready READ ready NOTIFY changed)
    Q_PROPERTY(QString look READ look NOTIFY changed)
    Q_PROPERTY(QString wallpaper READ wallpaper NOTIFY changed)
    Q_PROPERTY(QColor canvas READ canvas NOTIFY changed)
    Q_PROPERTY(QColor ink READ ink NOTIFY changed)
    Q_PROPERTY(QColor accent READ accent NOTIFY changed)
public:
    explicit MoOSSessionAppearance(QObject *parent=nullptr):QObject(parent),m_originalPalette(QGuiApplication::palette()),
        m_originalFont(QGuiApplication::font()),m_originalTheme(QIcon::themeName()),m_originalScheme(qApp->property("KDE_COLOR_SCHEME_PATH")) {
        const auto *account=getpwnam("plasmalogin");
        m_greeter=account && account->pw_uid==getuid();
        if (!m_greeter) return;
        preparePlasma();
        auto bus=QDBusConnection::sessionBus();
        bus.connect(service(),path(),iface(),QStringLiteral("SnapshotChanged"),this,SLOT(receiveSnapshot(QString)));
        auto *watcher=new QDBusServiceWatcher(service(),bus,QDBusServiceWatcher::WatchForOwnerChange,this);
        connect(watcher,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](const QString &,const QString &,const QString &owner) {
            if (!m_publisher) { if(owner.isEmpty()) acceptSnapshot({}); else readPublished(); }
        });
        readPublished();
    }
    bool isGreeter() const { return m_greeter; }
    bool ready() const { return m_ready; }
    QString look() const { return m_profile.look; }
    QString wallpaper() const { return m_profile.image.isNull()?QString():QStringLiteral("image://moosappearance/session/%1").arg(m_imageSerial); }
    QSharedPointer<MoOSAppearanceImages> imageStore() const { return m_images; }
    QColor canvas() const { return QGuiApplication::palette().color(QPalette::Window); }
    QColor ink() const { return QGuiApplication::palette().color(QPalette::WindowText); }
    QColor accent() const { return QGuiApplication::palette().color(QPalette::Highlight); }
    Q_INVOKABLE bool observeDesktop() {
        if (m_greeter || QCoreApplication::applicationName()!=QStringLiteral("plasmashell")) return false;
        if (!m_wallpaperIntent) m_wallpaperIntent=new MoOSWallpaperIntent(this);
        return m_wallpaperIntent->start();
    }
    Q_INVOKABLE bool followOwnSession() {
        // Only the native lock/power consumers opt into a private session skin.
        // Never change plasmashell's selected third-party desktop style, and
        // never let an ordinary account choose another account's appearance.
        const auto name=QCoreApplication::applicationName();
        if (m_greeter || (name!=QStringLiteral("ksmserver-logout-greeter")
                          && name!=QStringLiteral("kscreenlocker_greet"))) return false;
        if (m_ownSession) return true;
        m_ownSession=true;preparePlasma();
        const auto generation=++m_generation;
        auto message=QDBusMessage::createMethodCall(accounts(),QStringLiteral("/org/freedesktop/Accounts"),accounts(),QStringLiteral("FindUserById"));
        message << qlonglong(getuid());
        auto *pending=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(message,3000),this);
        connect(pending,&QDBusPendingCallWatcher::finished,this,[this,generation](QDBusPendingCallWatcher *watcher) {
            QDBusPendingReply<QDBusObjectPath> reply=*watcher;watcher->deleteLater();
            if (generation!=m_generation) return;
            if (reply.isError()) { qWarning("MoOS session appearance own-account lookup unavailable");return; }
            const auto object=reply.value().path();
            if (!QRegularExpression(QStringLiteral("^/org/freedesktop/Accounts/User[0-9]+$")).match(object).hasMatch()) return;
            m_accountPath=object;
            QDBusConnection::systemBus().connect(accounts(),object,properties(),QStringLiteral("PropertiesChanged"),this,SLOT(accountChanged(QString,QVariantMap,QStringList)));
            readAccount();
        });
        return true;
    }
    Q_INVOKABLE void followUser(const QString &user) {
        if (!m_greeter || user==m_user) return;
        m_user=user; const auto generation=++m_generation;
        auto session=QDBusConnection::sessionBus();
        if (!m_publisher) {
            if (!session.registerService(service())) { qWarning("MoOS login appearance publisher unavailable");return; }
            if (!session.registerObject(path(),this,QDBusConnection::ExportScriptableSlots|QDBusConnection::ExportScriptableSignals)) {
                session.unregisterService(service());qWarning("MoOS login appearance export unavailable");return;
            }
            m_publisher=true;
        }
        if (!m_accountPath.isEmpty()) QDBusConnection::systemBus().disconnect(accounts(),m_accountPath,properties(),QStringLiteral("PropertiesChanged"),this,SLOT(accountChanged(QString,QVariantMap,QStringList)));
        m_accountPath.clear(); publish({});
        if (user.isEmpty() || user.size()>256 || user.contains(QRegularExpression(QStringLiteral("[\\x00-\\x20/\\x7f]")))) return;
        auto message=QDBusMessage::createMethodCall(accounts(),QStringLiteral("/org/freedesktop/Accounts"),accounts(),QStringLiteral("FindUserByName"));
        message << user;
        auto *pending=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(message,3000),this);
        connect(pending,&QDBusPendingCallWatcher::finished,this,[this,generation](QDBusPendingCallWatcher *watcher) {
            QDBusPendingReply<QDBusObjectPath> reply=*watcher;watcher->deleteLater();
            if (generation!=m_generation) return;
            if (reply.isError()) { qWarning("MoOS login appearance account lookup unavailable");return; }
            const auto object=reply.value().path();
            if (!QRegularExpression(QStringLiteral("^/org/freedesktop/Accounts/User[0-9]+$")).match(object).hasMatch()) return;
            m_accountPath=object;
            QDBusConnection::systemBus().connect(accounts(),object,properties(),QStringLiteral("PropertiesChanged"),this,SLOT(accountChanged(QString,QVariantMap,QStringList)));
            readAccount();
        });
    }
public Q_SLOTS:
    Q_SCRIPTABLE QString GetSnapshot() const { return m_raw; }
Q_SIGNALS:
    void changed();
    Q_SCRIPTABLE void SnapshotChanged(const QString &snapshot);
private Q_SLOTS:
    void receiveSnapshot(const QString &snapshot) { ++m_receivedSerial; if (!m_publisher) acceptSnapshot(snapshot); }
    void accountChanged(const QString &interface,const QVariantMap &,const QStringList &) {
        if (interface==accountInterface()) readAccount();
    }
private:
    void preparePlasma() {
        if (m_plasmaTheme) return;
        m_plasmaTheme=new Plasma::Theme(this);
        m_originalGlobal=m_plasmaTheme->useGlobalSettings();
        m_originalDataDirs=qgetenv("XDG_DATA_DIRS");
        m_hadDataDirs=qEnvironmentVariableIsSet("XDG_DATA_DIRS");
    }
    static QString service() { return QStringLiteral("org.moos.LoginAppearance"); }
    static QString path() { return QStringLiteral("/Appearance"); }
    static QString iface() { return QStringLiteral("org.moos.LoginAppearance"); }
    static QString accounts() { return QStringLiteral("org.freedesktop.Accounts"); }
    static QString properties() { return QStringLiteral("org.freedesktop.DBus.Properties"); }
    static QString accountInterface() { return QStringLiteral("org.moos.Accounts.Appearance"); }
    void readPublished() {
        const auto serial=++m_receivedSerial;
        auto message=QDBusMessage::createMethodCall(service(),path(),iface(),QStringLiteral("GetSnapshot"));
        auto *pending=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(message,3000),this);
        connect(pending,&QDBusPendingCallWatcher::finished,this,[this,serial](QDBusPendingCallWatcher *watcher) {
            QDBusPendingReply<QString> reply=*watcher;watcher->deleteLater();
            if (!m_publisher && serial==m_receivedSerial && !reply.isError()) acceptSnapshot(reply.value());
        });
    }
    void readAccount() {
        if (m_accountPath.isEmpty()) return;
        const auto generation=m_generation;
        const auto serial=++m_accountReadSerial;
        auto message=QDBusMessage::createMethodCall(accounts(),m_accountPath,properties(),QStringLiteral("Get"));
        message << accountInterface() << QStringLiteral("Appearance");
        auto *pending=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(message,3000),this);
        connect(pending,&QDBusPendingCallWatcher::finished,this,[this,generation,serial](QDBusPendingCallWatcher *watcher) {
            QDBusPendingReply<QDBusVariant> reply=*watcher;watcher->deleteLater();
            if (generation!=m_generation || serial!=m_accountReadSerial) return;
            if (reply.isError()) { qWarning("MoOS login appearance account metadata unavailable");return; }
            const auto value=reply.value().variant();
            if (value.metaType().id()==QMetaType::QString) publish(value.toString());
        });
    }
    void publish(const QString &raw) { acceptSnapshot(raw);Q_EMIT SnapshotChanged(m_raw); }
    void acceptSnapshot(const QString &raw) {
        if (raw==m_raw && (m_ready || raw.isEmpty())) return;
        MoOSAppearanceProfile profile;
        if (!raw.isEmpty() && moosAppearanceProfile(raw,profile) && applyPalette(profile)) {
            m_profile=profile;m_raw=raw;m_ready=true;
            Dl_info loaded{};
            if (dladdr(metaObject(),&loaded) && loaded.dli_fname)
                qInfo("MOOS_LOGIN_APPEARANCE_READY look=%s icons=%s module=%s",qPrintable(profile.look),qPrintable(profile.icons),loaded.dli_fname);
        } else {
            if (!raw.isEmpty()) qWarning("MoOS login appearance payload or palette refused");
            m_profile={};m_raw.clear();m_ready=false;
            restorePlasma();
            qApp->setProperty("KDE_COLOR_SCHEME_PATH",m_originalScheme);
            QGuiApplication::setPalette(m_originalPalette);QGuiApplication::setFont(m_originalFont);applyIcons(m_originalTheme);
        }
        ++m_imageSerial;
        {
            QMutexLocker guard(&m_images->mutex);
            m_images->frames.insert(m_imageSerial,m_profile.image);
            while (m_images->frames.size()>2) m_images->frames.erase(m_images->frames.begin());
        }
        Q_EMIT changed();
    }
    bool applyPalette(const MoOSAppearanceProfile &profile) {
        if (!m_temporary.isValid()) return false;
        QFile base(QStringLiteral("/usr/share/color-schemes/%1.colors").arg(profile.scheme));
        if (!base.open(QIODevice::ReadOnly) || base.size()>65536) return false;
        const auto bytes=base.readAll();
        // KDE caches the scheme by path. Rewriting one path can leave its
        // existing Kirigami owners on the previous user's colours even though
        // QGuiApplication already reports the new palette. Give each palette
        // a content identity; retain only its current and previous private file.
        QByteArray paletteIdentity=bytes;
        paletteIdentity.append(QJsonDocument(profile.colors).toJson(QJsonDocument::Compact));
        const auto digest=QCryptographicHash::hash(paletteIdentity,QCryptographicHash::Sha256).toHex();
        const auto file=m_temporary.filePath(QString::fromLatin1(digest)+QStringLiteral(".colors"));
        QFile target(file);
        if (!target.open(QIODevice::WriteOnly|QIODevice::Truncate)) return false;
        if (target.write(bytes)!=bytes.size()) return false;
        target.close();
        auto config=KSharedConfig::openConfig(file,KConfig::SimpleConfig);
        config->reparseConfiguration();
        for (const auto &set : profile.colors.keys()) {
            KConfigGroup group(config,set);
            const auto entries=profile.colors.value(set).toObject();
            for (const auto &role : entries.keys()) group.writeEntry(role,entries.value(role).toString());
        }
        if (!config->sync()) return false;
        if (!applyPlasma(profile,file)) return false;
        qApp->setProperty("KDE_COLOR_SCHEME_PATH",file);
        QGuiApplication::setPalette(KColorScheme::createApplicationPalette(config));
        applyIcons(profile.icons);
        QFont font=m_originalFont;
        if (!profile.font.isEmpty()) font.fromString(profile.font);
        QGuiApplication::setFont(font);
        m_recentPalettes.removeAll(file);m_recentPalettes.append(file);
        while (m_recentPalettes.size()>2) QFile::remove(m_recentPalettes.takeFirst());
        return true;
    }
    bool applyPlasma(const MoOSAppearanceProfile &profile,const QString &paletteFile) {
        // KirigamiPlasmaStyle reads Plasma::Theme, not just QGuiApplication's
        // palette. Reuse that shared native owner with a private data-only skin.
        // Its SVG fallback is the immutable catalogue style; no account QML or
        // persistent greeter configuration is copied, executed or overwritten.
        if (!m_plasmaTheme || QCoreApplication::applicationName().isEmpty()) return false;
        const auto config=KSharedConfig::openConfig(QStringLiteral("plasmarc"));
        if (m_originalGlobal && KConfigGroup(config,QStringLiteral("Theme")).isEntryImmutable(QStringLiteral("name"))) return false;
        const QString name=QStringLiteral("MoOSSession-")+profile.style;
        const auto data=m_temporary.filePath(QStringLiteral("data"));
        const QString skin=data+QStringLiteral("/plasma/desktoptheme/")+name;
        if (!QDir().mkpath(skin)) return false;
        QFile palette(paletteFile);
        if (!palette.open(QIODevice::ReadOnly)) return false;
        const auto write=[](const QString &path,const QByteArray &bytes) {
            QFile file(path);
            return file.open(QIODevice::WriteOnly|QIODevice::Truncate) && file.write(bytes)==bytes.size();
        };
        const QJsonObject metadata{{QStringLiteral("KPlugin"),QJsonObject{{QStringLiteral("Id"),name},{QStringLiteral("Name"),QStringLiteral("MoOS Session")},{QStringLiteral("Version"),QStringLiteral("1")},{QStringLiteral("License"),QStringLiteral("GPL-2.0-or-later")}}},{QStringLiteral("X-Plasma-API"),QStringLiteral("5.0")}};
        if (!write(skin+QStringLiteral("/metadata.json"),QJsonDocument(metadata).toJson(QJsonDocument::Compact)) ||
            !write(skin+QStringLiteral("/colors"),palette.readAll()) ||
            !write(skin+QStringLiteral("/plasmarc"),(QStringLiteral("[Settings]\nFallbackTheme=")+profile.style+QStringLiteral("\n")).toUtf8())) return false;
        KSharedConfig::openConfig(skin+QStringLiteral("/colors"))->reparseConfiguration();
        const auto source=m_temporary.filePath(QStringLiteral("session-plasmarc"));
        if (!write(source,(QStringLiteral("[Theme-")+QCoreApplication::applicationName()+QStringLiteral("]\nname=")+name+QStringLiteral("\n")).toUtf8())) return false;
        if (!m_plasmaSourceAdded) { config->addConfigSources({source});m_plasmaSourceAdded=true; }
        else config->reparseConfiguration();
        QByteArray dataDirectories=data.toUtf8();dataDirectories.append(':');
        dataDirectories.append(m_hadDataDirs?m_originalDataDirs:QByteArray("/usr/local/share:/usr/share"));
        qputenv("XDG_DATA_DIRS",dataDirectories);
        // This public read-only reload path invokes settingsChanged(false-write)
        // internally. setThemeName() would persist a temporary skin name.
        m_plasmaTheme->setUseGlobalSettings(true);
        m_plasmaTheme->setUseGlobalSettings(false);
        return m_plasmaTheme->themeName()==name;
    }
    void restorePlasma() {
        if (!m_plasmaTheme || !m_plasmaSourceAdded) return;
        if (m_hadDataDirs) qputenv("XDG_DATA_DIRS",m_originalDataDirs);else qunsetenv("XDG_DATA_DIRS");
        // An empty private source removes our defaults; administrator/main
        // sources retain their native precedence throughout.
        QFile file(m_temporary.filePath(QStringLiteral("session-plasmarc")));
        if (file.open(QIODevice::WriteOnly|QIODevice::Truncate)) file.close();
        KSharedConfig::openConfig(QStringLiteral("plasmarc"))->reparseConfiguration();
        m_plasmaTheme->setUseGlobalSettings(!m_originalGlobal);
        m_plasmaTheme->setUseGlobalSettings(m_originalGlobal);
    }
    void applyIcons(const QString &theme) {
        if (QIcon::themeName()==theme && KIconTheme::current()==theme) return;
        QIcon::setThemeName(theme);
        // Qt's override alone leaves KDE's already-created icon owner on its
        // cached first theme. Retain the native loader and invalidate it using
        // its public reconfiguration API; never force a testing theme.
        KIconTheme::reconfigure();
        KIconLoader::global()->reconfigure(QString());
    }
    bool m_greeter=false,m_publisher=false,m_ready=false,m_ownSession=false;
    Plasma::Theme *m_plasmaTheme=nullptr;
    MoOSWallpaperIntent *m_wallpaperIntent=nullptr;
    bool m_originalGlobal=true,m_hadDataDirs=false,m_plasmaSourceAdded=false;
    QByteArray m_originalDataDirs;
    quint64 m_generation=0,m_imageSerial=0,m_receivedSerial=0,m_accountReadSerial=0;
    QString m_user,m_accountPath,m_raw;
    QStringList m_recentPalettes;
    MoOSAppearanceProfile m_profile;
    QPalette m_originalPalette;QFont m_originalFont;QString m_originalTheme;QVariant m_originalScheme;
    QTemporaryDir m_temporary;
    QSharedPointer<MoOSAppearanceImages> m_images=QSharedPointer<MoOSAppearanceImages>::create();
};

class MoOSAppearanceImage : public QQuickImageProvider {
public:
    explicit MoOSAppearanceImage(QSharedPointer<MoOSAppearanceImages> images):QQuickImageProvider(QQuickImageProvider::Image),m_images(std::move(images)) {}
    QImage requestImage(const QString &id,QSize *size,const QSize &) override {
        bool valid=false;const auto serial=id.section(QLatin1Char('/'),-1).toULongLong(&valid);
        QMutexLocker guard(&m_images->mutex);
        const auto image=valid?m_images->frames.value(serial):QImage();
        if (size) *size=image.size();
        return image;
    }
private:
    QSharedPointer<MoOSAppearanceImages> m_images;
};
