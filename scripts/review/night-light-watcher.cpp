// SPDX-License-Identifier: GPL-3.0-or-later
// Private protocol fixture: run only with an isolated HOME and session bus.
// Build using the existing native development toolbox, then run against the
// host's actual KConfig library. This is not a compositor or a colour-output test.
#include <KConfigGroup>
#include <KConfigWatcher>
#include <KSharedConfig>
#include <QCoreApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTextStream>
#include <QTimer>

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    const auto config = KSharedConfig::openConfig(QStringLiteral("kwinrc"), KConfig::NoGlobals);
    const auto watcher = KConfigWatcher::create(config);
    const auto report = [](const QString &event, const KConfigGroup &group, const QByteArrayList &keys) {
        QJsonArray names;
        for (const auto &key : keys) {
            names.append(QString::fromUtf8(key));
        }
        const QJsonObject result{{QStringLiteral("event"), event},
                                 {QStringLiteral("group"), group.name()},
                                 {QStringLiteral("keys"), names},
                                 {QStringLiteral("active"), group.readEntry("Active", false)},
                                 {QStringLiteral("mode"), group.readEntry("Mode", QString())}};
        QTextStream(stdout) << QJsonDocument(result).toJson(QJsonDocument::Compact) << Qt::endl;
    };
    QObject::connect(watcher.data(), &KConfigWatcher::configChanged, &app,
                     [&](const KConfigGroup &group, const QByteArrayList &keys) {
                         report(QStringLiteral("changed"), group, keys);
                     });
    report(QStringLiteral("ready"), config->group(QStringLiteral("NightColor")), {});
    QTimer::singleShot(10000, &app, &QCoreApplication::quit);
    return app.exec();
}
