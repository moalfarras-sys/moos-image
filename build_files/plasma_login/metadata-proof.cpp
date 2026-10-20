// SPDX-License-Identifier: LGPL-2.0-or-later
#include "fingerprintmetadata.h"
#include <QCoreApplication>
#include <QTemporaryDir>
#include <cstdio>

int main(int argc, char **argv)
{
    QCoreApplication application(argc, argv);
    if (::geteuid() != 0) return 2; // A private rootless SDK, never the host.
    QTemporaryDir directory;
    if (!directory.isValid()) return 3;
    const QString path = directory.filePath(QStringLiteral("capabilities.json"));
    const QByteArray native = QFile::encodeName(path);
    QFile boot(QStringLiteral("/proc/sys/kernel/random/boot_id"));
    if (!boot.open(QIODevice::ReadOnly)) return 4;
    QJsonObject object{{QStringLiteral("schema"), 1},
                       {QStringLiteral("boot_id"), QString::fromUtf8(boot.readAll().trimmed())},
                       {QStringLiteral("users"), QJsonArray{QStringLiteral("synthetic-owner")}}};
    auto write = [&](const QJsonObject &value) {
        QFile file(path);
        if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) return false;
        const QByteArray bytes = QJsonDocument(value).toJson();
        return file.write(bytes) == bytes.size() && ::chmod(native.constData(), 0600) == 0;
    };
    if (!write(object) || !moosFingerprintUsers(path).contains(QStringLiteral("synthetic-owner"))) return 10;
    if (::chmod(native.constData(), 0666) || !moosFingerprintUsers(path).isEmpty()) return 11;
    if (::chmod(native.constData(), 0600) || ::chown(native.constData(), 1234, 1234)
        || !moosFingerprintUsers(path).isEmpty() || ::chown(native.constData(), 0, 0)) return 12;
    auto stale = object;
    stale.insert(QStringLiteral("boot_id"), QStringLiteral("previous-boot"));
    if (!write(stale) || !moosFingerprintUsers(path).isEmpty()) return 13;
    auto invalid = object;
    invalid.insert(QStringLiteral("users"), QJsonArray{QStringLiteral("synthetic-owner"), 42});
    if (!write(invalid) || !moosFingerprintUsers(path).isEmpty()) return 14;
    invalid = object;
    invalid.insert(QStringLiteral("schema"), 2);
    if (!write(invalid) || !moosFingerprintUsers(path).isEmpty()) return 15;
    if (!write(object)) return 16;
    const QString link = directory.filePath(QStringLiteral("link.json"));
    if (::symlink(native.constData(), QFile::encodeName(link).constData())
        || !moosFingerprintUsers(link).isEmpty()) return 17;
    if (!QFile::remove(path) || ::mkfifo(native.constData(), 0600)
        || !moosFingerprintUsers(path).isEmpty()) return 18;
    if (!QFile::remove(path) || !moosFingerprintUsers(path).isEmpty()) return 19;
    std::puts("MOOS_FINGERPRINT_METADATA_NATIVE_OK");
    return 0;
}
