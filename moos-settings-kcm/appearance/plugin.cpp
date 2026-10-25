// SPDX-License-Identifier: GPL-2.0-or-later
#include "sessionappearance.h"
#include <QQmlExtensionPlugin>
#include <QQmlEngine>
class MoOSAppearancePlugin : public QQmlExtensionPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID "org.qt-project.Qt.QQmlExtensionInterface/1.0")
public:
    void registerTypes(const char *uri) override {
        qmlRegisterSingletonType<MoOSSessionAppearance>(uri,1,0,"Appearance",[](QQmlEngine *engine,QJSEngine *) -> QObject * {
            auto *appearance = new MoOSSessionAppearance;
            engine->addImageProvider(QStringLiteral("moosappearance"),new MoOSAppearanceImage(appearance->imageStore()));
            return appearance;
        });
    }
};
#include "plugin.moc"
