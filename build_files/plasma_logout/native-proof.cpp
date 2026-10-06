// SPDX-License-Identifier: MIT
// Runs real vendor/fixed workers on a PRIVATE bus; no host desktop connection.
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusObjectPath>
#include <QDBusPendingCall>
#include <QDBusVariant>
#include <QDBusVirtualObject>
#include <QEventLoop>
#include <QProcess>
#include <QTimer>
#include <cstdio>
#include <sys/prctl.h>

class SessionFixture : public QDBusVirtualObject {
public:
    QString mode;
    int resets = 0;
    bool forceError = false;
    bool cancelWindows = false;
    QString introspect(const QString &) const override {
        return QStringLiteral(
            "<interface name='org.kde.KSMServerInterface'>"
            "<method name='closeSession'><arg type='b' direction='out'/></method>"
            "<method name='resetLogout'/></interface>"
            "<interface name='org.kde.KWin.Session'>"
            "<method name='closeWaylandWindows'><arg type='b' direction='out'/></method></interface>"
            "<interface name='org.freedesktop.systemd1.Manager'>"
            "<method name='GetUnit'><arg type='s' direction='in'/><arg type='o' direction='out'/></method>"
            "<method name='StopUnit'><arg type='s' direction='in'/><arg type='s' direction='in'/><arg type='o' direction='out'/></method></interface>"
            "<interface name='org.freedesktop.DBus.Properties'>"
            "<method name='Get'><arg type='s' direction='in'/><arg type='s' direction='in'/><arg type='v' direction='out'/></method></interface>");
    }
    bool handleMessage(const QDBusMessage &m, const QDBusConnection &bus) override {
        QList<QVariant> result;
        if (m.interface() == QStringLiteral("org.kde.KSMServerInterface")) {
            if (m.member() == QStringLiteral("closeSession")) result << true;
            else if (m.member() == QStringLiteral("resetLogout")) ++resets;
            else return false;
        } else if (m.interface() == QStringLiteral("org.kde.KWin.Session")) {
            if (m.member() != QStringLiteral("closeWaylandWindows")) return false;
            result << !cancelWindows;
        } else if (m.interface() == QStringLiteral("org.freedesktop.systemd1.Manager")) {
            if (m.member() == QStringLiteral("GetUnit")) {
                result << QVariant::fromValue(QDBusObjectPath(QStringLiteral("/fixture/workspace")));
            } else if (m.member() == QStringLiteral("StopUnit")) {
                if (m.arguments().size() != 2 || m.arguments().at(0).toString() != QStringLiteral("graphical-session.target")) return false;
                mode = m.arguments().at(1).toString();
                if (forceError || mode == QStringLiteral("fail")) {
                    bus.send(m.createErrorReply(QStringLiteral("org.freedesktop.systemd1.TransactionIsDestructive"),
                                               QStringLiteral("Private pending startup job")));
                    return true;
                }
                result << QVariant::fromValue(QDBusObjectPath(QStringLiteral("/fixture/job")));
            } else return false;
        } else if (m.interface() == QStringLiteral("org.freedesktop.DBus.Properties") && m.member() == QStringLiteral("Get")) {
            result << QVariant::fromValue(QDBusVariant(QStringLiteral("active")));
        } else return false;
        bus.send(m.createReply(result));
        return true;
    }
};

int main(int argc, char **argv) {
    prctl(PR_SET_DUMPABLE, 0);
    QCoreApplication app(argc, argv);
    if (argc != 3) return 2;
    const QString kind = QString::fromLocal8Bit(argv[2]);
    auto bus = QDBusConnection::sessionBus();
    SessionFixture fixture;
    fixture.forceError = kind == QStringLiteral("rejected");
    fixture.cancelWindows = kind == QStringLiteral("cancelled");
    if (!bus.registerService(QStringLiteral("org.kde.ksmserver")) ||
        !bus.registerService(QStringLiteral("org.kde.KWin")) ||
        !bus.registerService(QStringLiteral("org.freedesktop.systemd1")) ||
        !bus.registerVirtualObject(QStringLiteral("/"), &fixture, QDBusConnection::SubPath)) return 3;
    QProcess worker;
    worker.setChildProcessModifier([] { prctl(PR_SET_DUMPABLE, 0); });
    worker.setProcessChannelMode(QProcess::ForwardedChannels);
    QEventLoop loop;
    bool timedOut = false, requested = false;
    QTimer deadline;
    deadline.setSingleShot(true);
    QObject::connect(&deadline, &QTimer::timeout, &loop, [&] { timedOut = true; worker.kill(); loop.quit(); });
    QObject::connect(&worker, &QProcess::finished, &loop, &QEventLoop::quit);
    QTimer poll;
    QObject::connect(&poll, &QTimer::timeout, &loop, [&] {
        if (!requested && bus.interface()->isServiceRegistered(QStringLiteral("org.kde.Shutdown"))) {
            requested = true;
            const auto call = QDBusMessage::createMethodCall(QStringLiteral("org.kde.Shutdown"),
                QStringLiteral("/Shutdown"), QStringLiteral("org.kde.Shutdown"), QStringLiteral("logout"));
            bus.asyncCall(call);
        }
    });
    worker.start(QString::fromLocal8Bit(argv[1]));
    if (!worker.waitForStarted(3000)) return 4;
    deadline.start(10000);
    poll.start(25);
    loop.exec();
    worker.waitForFinished(3000);
    const QString expectedMode = kind == QStringLiteral("old") ? QStringLiteral("fail") :
                                 kind == QStringLiteral("cancelled") ? QString() : QStringLiteral("replace");
    const int expectedResets = fixture.forceError || fixture.cancelWindows ? 1 : 0;
    if (timedOut || !requested || worker.exitStatus() != QProcess::NormalExit || worker.exitCode() != 0 ||
        fixture.mode != expectedMode || fixture.resets != expectedResets) {
        fprintf(stderr, "FAIL native case=%s mode=%s resets=%d timeout=%d exit=%d\n",
                qPrintable(kind), qPrintable(fixture.mode), fixture.resets, timedOut, worker.exitCode());
        return 1;
    }
    printf("PASS native case=%s mode=%s resets=%d\n", qPrintable(kind), qPrintable(fixture.mode), fixture.resets);
    return 0;
}
