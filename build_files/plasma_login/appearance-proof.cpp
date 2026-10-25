// SPDX-FileCopyrightText: 2026 Moalfarras
// SPDX-License-Identifier: GPL-2.0-or-later
#include "moosappearancesettings.h"
#include <QCoreApplication>
#include <QStandardPaths>
#include <QTemporaryDir>
#include <cstdio>
#include <cstdlib>

static void require(bool ok, const char *message)
{
    if (!ok) {
        std::fprintf(stderr, "appearance proof: %s\n", message);
        std::exit(1);
    }
}
static void write(const QString &path, const QString &contents)
{
    QFile file(path);
    require(file.open(QIODevice::WriteOnly), "fixture open");
    const auto bytes = contents.toUtf8();
    require(file.write(bytes) == bytes.size(), "fixture write");
}
static QString read(const QString &path)
{
    QFile file(path);
    require(file.open(QIODevice::ReadOnly), "readback open");
    return QString::fromUtf8(file.readAll());
}
int main(int argc, char **argv)
{
    QTemporaryDir root;
    require(root.isValid(), "private root");
    const QString config = root.path() + QStringLiteral("/config");
    const QString defaults = root.path() + QStringLiteral("/defaults");
    require(QDir().mkpath(config) && QDir().mkpath(defaults), "private config directories");
    qputenv("HOME", root.path().toUtf8());
    qputenv("XDG_CONFIG_HOME", config.toUtf8());
    qputenv("XDG_CONFIG_DIRS", defaults.toUtf8());
    QCoreApplication app(argc, argv);
    for (const auto &name : {"save", "sync", "reset"}) {
        KAuth::Action action(QStringLiteral("org.kde.kcontrol.kcmplasmalogin.") + QLatin1String(name));
        require(action.timeout() == -1, "native old default timeout");
        moosLoginAppearanceTimeout(action);
        require(action.timeout() == 300000, "finite native administrator wait");
    }
    std::puts("MOOS_LOGIN_APPEARANCE_FINITE_WAIT_PASS");
    const QString userPath = config + QStringLiteral("/kdeglobals");
    const QString defaultsPath = defaults + QStringLiteral("/kdeglobals");
    const QString out = root.path() + QStringLiteral("/exported");
    const QString inherited = QStringLiteral("[General]\nColorScheme=MoOSUI2BloomLight\n[Icons]\nTheme=MoOSUI2BloomLight\n");
    const QString partial = QStringLiteral("[General]\nfont=Owner Font,13\n[OwnerOnly]\nKeep=unchanged\n[Colors:Window]\nBackgroundNormal=11,22,33\n");
    write(userPath, partial);
    write(defaultsPath, inherited);
    // Execute the original locate/read export with real KConfig inputs. The
    // first file is a partial override; its inherited selectors disappear.
    const QString located = QStandardPaths::locate(QStandardPaths::GenericConfigLocation, QStringLiteral("kdeglobals"));
    require(located == userPath, "native original input");
    write(out, read(located));
    {
        KConfig old(out, KConfig::SimpleConfig);
        require(KConfigGroup(&old, "General").readEntry("ColorScheme", QString()).isEmpty(), "old scheme omission");
        require(KConfigGroup(&old, "Icons").readEntry("Theme", QString()).isEmpty(), "old icon omission");
    }
    std::puts("MOOS_LOGIN_APPEARANCE_OLD_OMISSION");
    for (bool custom : {false, true}) {
        const QString original = partial + (custom ? QStringLiteral("\n[General]\nColorScheme=OwnerScheme\n[Icons]\nTheme=OwnerIcons\n") : QString());
        write(userPath, original);
        const auto snapshot = moosLoginAppearanceSnapshot(original, root.path());
        require(snapshot.has_value(), "effective appearance export");
        write(out, *snapshot);
        KConfig actual(out, KConfig::SimpleConfig);
        require(KConfigGroup(&actual, "General").readEntry("ColorScheme", QString()) == (custom ? QStringLiteral("OwnerScheme") : QStringLiteral("MoOSUI2BloomLight")), "effective scheme/owner precedence");
        require(KConfigGroup(&actual, "Icons").readEntry("Theme", QString()) == (custom ? QStringLiteral("OwnerIcons") : QStringLiteral("MoOSUI2BloomLight")), "effective icons/owner precedence");
        require(KConfigGroup(&actual, "General").readEntry("font", QString()) == QStringLiteral("Owner Font,13"), "font preserved");
        require(KConfigGroup(&actual, "OwnerOnly").readEntry("Keep", QString()) == QStringLiteral("unchanged"), "owner key preserved");
        require(KConfigGroup(&actual, "Colors:Window").readEntry("BackgroundNormal", QString()) == QStringLiteral("11,22,33"), "palette preserved");
        require(read(userPath) == original && read(defaultsPath) == inherited, "snapshot modified native inputs");
    }
    const QString blocked = root.path() + QStringLiteral("/not-a-directory");
    write(blocked, QStringLiteral("preserve this unknown file"));
    require(!moosLoginAppearanceSnapshot(partial, blocked).has_value(), "storage refusal");
    require(read(blocked) == QStringLiteral("preserve this unknown file"), "storage refusal destroyed existing bytes");
    std::puts("MOOS_LOGIN_APPEARANCE_SNAPSHOT_PASS");
}
