// SPDX-License-Identifier: GPL-2.0-or-later
#include "appearanceprofile.h"
#include <QGuiApplication>
#include <QPalette>
#include <QIcon>
#include <KIconTheme>
#include <KColorScheme>
#include <KSharedConfig>
#include <QDebug>
#include <QQmlEngine>
#include <QQmlComponent>
#include <QQuickWindow>
#include <QTimer>
#include <plasma_version.h>
#if PLASMA_VERSION >= QT_VERSION_CHECK(6, 8, 0)
#include <PlasmaQuick/PlasmaQuick>
#else
#include <PlasmaQuick/SharedQmlEngine>
#endif
#include <Kirigami/Platform/PlatformTheme>
#include <cstdio>
#include <cstdlib>
#include <sys/prctl.h>
static void require(bool value,const char *message) {
    if (!value) { std::fprintf(stderr,"MoOS appearance contract: %s\n",message); std::exit(1); }
}
int main(int argc,char **argv) {
    prctl(PR_SET_DUMPABLE,0);
    QGuiApplication app(argc,argv);
    if (argc==3 && QString::fromLocal8Bit(argv[1])==QStringLiteral("--desktop-observer")) {
        app.setApplicationName(QStringLiteral("plasmashell"));
        QQmlEngine engine;engine.addImportPath(QString::fromLocal8Bit(argv[2]));
        QQmlComponent component(&engine);
        component.setData(R"(import QtQml
import org.moos.ui as MoUI
QtObject {
 property bool observing: false
 Component.onCompleted: observing = MoUI.SessionAppearance.observeDesktop()
})",QUrl(QStringLiteral("file:///native-desktop-observer.qml")));
        QScopedPointer<QObject> root(component.create());
        require(root && root->property("observing").toBool(),"native ordinary desktop observer failed");
        std::puts("MOOS_NATIVE_DESKTOP_OBSERVER_READY");std::fflush(stdout);
        QTimer::singleShot(6000,&app,&QCoreApplication::quit);
        return app.exec();
    }
    if (argc==4 && QString::fromLocal8Bit(argv[1])==QStringLiteral("--consumer")) {
#if PLASMA_VERSION >= QT_VERSION_CHECK(6, 8, 0)
        auto engine=PlasmaQuick::globalEngine();
        require(engine->property("_kirigamiTheme").toString()==QStringLiteral("KirigamiPlasmaStyle"),"actual native greeter theme engine required");
        const char *engineApi="globalEngine", *paletteOwner="PlasmaTheme";
#else
        // The reviewed 6.7 greeter owns this shared engine. Its startplasma
        // environment selects KDE's platform theme, not the 6.8 Plasma style.
        PlasmaQuick::SharedQmlEngine engineOwner;
        auto engine=engineOwner.engine();
        require(engine->property("_kirigamiTheme").toString().isEmpty(),"legacy greeter engine was replaced");
        const char *engineApi="SharedQmlEngine", *paletteOwner="PlasmaDesktopTheme";
#endif
        engine->addImportPath(QString::fromLocal8Bit(argv[2]));
        QQmlComponent component(engine.get());
        QByteArray body=R"(import QtQuick
import org.kde.kirigami as K
import org.moos.appearance 1.0
import org.moos.ui as MoUI
Window { id: window; width: 320; height: 200; visible: true
 K.Theme.inherit: false
 K.Theme.colorSet: K.Theme.Window
 property bool serviceAccount: Appearance.isGreeter
 property bool ready: MoUI.SessionAppearance.greeterProfile() !== null
 property string selectedLook: MoUI.SessionAppearance.configuredLook()
 property string wallpaper: MoUI.SessionAppearance.greeterWallpaper("")
 property url powerWallpaper: MoUI.SessionAppearance.configuredWallpaper()
 property color surface: K.Theme.backgroundColor
 property color selection: K.Theme.highlightColor
 property color complementary: outside.K.Theme.backgroundColor
 property bool imageReady: picture.status === Image.Ready
 property bool iconValid: mark.valid
 Item { id: outside; width: 1; height: 1; K.Theme.inherit: false; K.Theme.colorSet: K.Theme.Complementary }
 Image { id: picture; anchors.fill: parent; cache: false; asynchronous: true; source: MoUI.SessionAppearance.imageUrl(window.wallpaper) }
 K.Icon { id: mark; x: 8; y: 8; width: 24; height: 24; source: "moos-lock-symbolic"; color: K.Theme.textColor }
 Component.onCompleted: )";
        body += QString::fromLocal8Bit(argv[3])==QStringLiteral("follow") ? "MoUI.SessionAppearance.followUser(\"moosappearance61000\")" : "{}";
        body += "\n}";
        component.setData(body,QUrl(QStringLiteral("file:///native-appearance-consumer.qml")));
        QScopedPointer<QObject> root(component.create());
        if (!root) for (const auto &error:component.errors()) qWarning()<<error;
        require(bool(root),"native plugin import/scene");
        const auto *theme=qmlAttachedPropertiesObject<Kirigami::Platform::PlatformTheme>(root.get(),false);
        require(theme && QByteArray(theme->metaObject()->className())==paletteOwner,"actual version-specific native palette owner required");
        std::fprintf(stderr,"MOOS_NATIVE_GREETER_ENGINE plasma=%s api=%s theme=%s owner=%s\n",PLASMA_VERSION_STRING,engineApi,
            qPrintable(engine->property("_kirigamiTheme").toString()),theme->metaObject()->className());
        auto *window=qobject_cast<QQuickWindow*>(root.get());
        require(window && root->property("serviceAccount").toBool(),"actual greeter service UID required");
        const auto originalSurface=root->property("surface").value<QColor>();
        int phase=0,ticks=0;
        QTimer timer;
        QObject::connect(&timer,&QTimer::timeout,&app,[&] {
            if (++ticks==25) {
                const auto pixels=window->grabWindow();
                const auto pixel=pixels.isNull()?QColor():pixels.pixelColor(pixels.width()/2,pixels.height()/2);
                std::fprintf(stderr,"native appearance state ready=%d look=%s image=%d surface=%s application=%s pixel=%s\n",root->property("ready").toBool(),qPrintable(root->property("selectedLook").toString()),root->property("imageReady").toBool(),qPrintable(root->property("surface").value<QColor>().name()),qPrintable(QGuiApplication::palette().color(QPalette::Window).name()),qPrintable(pixel.name()));
            }
            if (phase<3) {
                const QString expected=phase==0?QStringLiteral("org.moos.ui2.bloom.light"):QStringLiteral("org.moos.ui2.aurora");
                if (!root->property("ready").toBool() || root->property("selectedLook").toString()!=expected || !root->property("imageReady").toBool()) return;
                require(root->property("powerWallpaper").toUrl().toString()==root->property("wallpaper").toString(),"login power scene does not share the selected image");
                const auto bg=root->property("surface").value<QColor>();
                if (bg!=QColor(phase==0?QStringLiteral("#d5d9ee"):phase==1?QStringLiteral("#172236"):QStringLiteral("#193a2e"))) return;
                const auto colors=KSharedConfig::openConfig(QStringLiteral("/usr/share/color-schemes/%1.colors").arg(phase==0?QStringLiteral("MoOSUI2BloomLight"):QStringLiteral("MoOSUI2Aurora")));
                if (root->property("complementary").value<QColor>()!=KColorScheme(QPalette::Active,KColorScheme::Complementary,colors).background().color()) return;
                if (phase==2 && root->property("selection").value<QColor>()!=QColor(QStringLiteral("#e28f33"))) return;
                const QString expectedIcons=phase==0?QStringLiteral("MoOSUI2BloomLight"):QStringLiteral("MoOSUI2Aurora");
                require(QIcon::themeName()==expectedIcons && KIconTheme::current()==expectedIcons,"Qt/KDE icon owners disagree");
                if (!root->property("iconValid").toBool()) return;
                const auto pixels=window->grabWindow();
                if (pixels.isNull()) return;
                const auto actual=pixels.pixelColor(pixels.width()/2,pixels.height()/2);
                const QColor expectedPixel(phase==0?QStringLiteral("#1583b1"):phase==1?QStringLiteral("#b16b15"):QStringLiteral("#156b35"));
                // Publication uses bounded JPEG; allow its measured rounding,
                // while the old image/wrong source is hundreds of levels away.
                if (std::abs(actual.red()-expectedPixel.red())>3 || std::abs(actual.green()-expectedPixel.green())>3 || std::abs(actual.blue()-expectedPixel.blue())>3) return;
                ++phase;std::printf("MOOS_NATIVE_APPEARANCE_PHASE%d\n",phase);std::fflush(stdout);
            } else if (!root->property("ready").toBool() && root->property("wallpaper").toString().isEmpty() && root->property("surface").value<QColor>()==originalSurface) {
                std::puts("MOOS_NATIVE_APPEARANCE_INVALID_REFUSED");std::fflush(stdout);app.exit(0);
            }
        });
        timer.start(80);
        QTimer::singleShot(20000,&app,[&] { std::fprintf(stderr,"native appearance phase %d timed out\n",phase);app.exit(1); });
        return app.exec();
    }
    require(argc==2,"profile catalogue argument required");
    const auto catalog=QString::fromLocal8Bit(argv[1]);
    QFile file(catalog);require(file.open(QIODevice::ReadOnly),"catalogue input");
    int count=0;
    for (const auto &line:file.readAll().split('\n')) {
        auto fields=QString::fromUtf8(line).split(QLatin1Char('\t'));
        if (fields.size()!=17 || fields[0].startsWith(QLatin1Char('#'))) continue;
        QJsonObject data{{QStringLiteral("schema"),1},{QStringLiteral("look"),fields[0]}};
        auto raw=[&] {return QString::fromUtf8(QJsonDocument(data).toJson(QJsonDocument::Compact));};
        MoOSAppearanceProfile result;
        require(moosAppearanceProfile(raw(),result,catalog) && result.scheme==fields[1] && result.style==fields[2] && result.icons==fields[4],"matched native catalogue");
        data[QStringLiteral("look")]=QStringLiteral("../../unknown");require(!moosAppearanceProfile(raw(),result,catalog),"unknown look accepted");data[QStringLiteral("look")]=fields[0];
        data[QStringLiteral("schema")]=1.1;require(!moosAppearanceProfile(raw(),result,catalog),"unknown schema accepted");data[QStringLiteral("schema")]=1;
        data[QStringLiteral("command")]=QStringLiteral("ignored");require(!moosAppearanceProfile(raw(),result,catalog),"unknown instruction accepted");data.remove(QStringLiteral("command"));
        QFont font;font.setPointSizeF(16);data[QStringLiteral("font")]=font.toString();
        require(moosAppearanceProfile(raw(),result,catalog),"bounded native font refused");
        font.setPointSizeF(100000);data[QStringLiteral("font")]=font.toString();
        require(!moosAppearanceProfile(raw(),result,catalog),"unbounded font accepted");data.remove(QStringLiteral("font"));
        data[QStringLiteral("colors")]=QJsonObject{{QStringLiteral("Colors:Window"),QJsonObject{{QStringLiteral("BackgroundNormal"),QStringLiteral("255,0,0")}}}};
        require(moosAppearanceProfile(raw(),result,catalog),"valid bounded native colour");
        data[QStringLiteral("colors")]=QJsonObject{{QStringLiteral("Colors:Window"),QJsonObject{{QStringLiteral("BackgroundNormal"),QStringLiteral("256,0,0")}}}};
        require(!moosAppearanceProfile(raw(),result,catalog),"out of range colour accepted");data.remove(QStringLiteral("colors"));
        data[QStringLiteral("image")]=QStringLiteral("file:///etc/passwd");require(!moosAppearanceProfile(raw(),result,catalog),"file URI accepted");
        QImage image(32,24,QImage::Format_RGB888);image.fill(QColor(QStringLiteral("#1583b1")));
        QByteArray bytes;QBuffer buffer(&bytes);buffer.open(QIODevice::WriteOnly);require(image.save(&buffer,"PNG"),"native image fixture");
        data[QStringLiteral("image")]=QString::fromLatin1(bytes.toBase64());
        require(moosAppearanceProfile(raw(),result,catalog) && result.image.pixelColor(16,12)==QColor(QStringLiteral("#1583b1")),"actual bounded raster decode");
        data[QStringLiteral("image")]=QString(1048577,QLatin1Char('A'));require(!moosAppearanceProfile(raw(),result,catalog),"oversized raster accepted");
        ++count;
    }
    require(count==18,"all shipped profiles required");
    std::printf("MOOS_NATIVE_APPEARANCE_SCHEMA_PASS profiles=%d\n",count);
}
