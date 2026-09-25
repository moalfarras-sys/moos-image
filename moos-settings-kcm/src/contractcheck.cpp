// SPDX-License-Identifier: GPL-2.0-or-later
// Developer check, not installed: does the backend's status contract accept a document?
//   moos-settings-contract-check <status.json>   prints "accepted" (exit 0) or the reason (exit 1)
// Built only with -DMOOS_KCM_CONTRACT_CHECK=ON; see README.md.
#include "moosbackend.h"

#include <QCoreApplication>
#include <QDateTime>
#include <QFile>
#include <QJsonDocument>

#include <cstdio>

int main(int argc, char **argv)
{
    QCoreApplication application(argc, argv);
    if (argc != 2) {
        std::fputs("usage: moos-settings-contract-check <status.json>\n", stderr);
        return 2;
    }
    QFile file(QString::fromLocal8Bit(argv[1]));
    if (!file.open(QIODevice::ReadOnly)) {
        std::puts("unreadable");
        return 1;
    }
    const QJsonDocument document = QJsonDocument::fromJson(file.readAll());
    QString reason;
    const bool accepted = document.isObject()
        && MoOSSettingsModule::acceptStatus(document.object(), QDateTime::currentSecsSinceEpoch(), &reason);
    std::printf("%s\n", accepted ? "accepted" : qPrintable(reason.isEmpty() ? QStringLiteral("invalid") : reason));
    return accepted ? 0 : 1;
}
