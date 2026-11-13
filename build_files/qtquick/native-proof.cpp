// SPDX-License-Identifier: MIT
// QQuickView owner for Qt's QTBUG-150769 regression fixture; never a greeter.
#include <QGuiApplication>
#include <QQuickView>
#include <QQuickItem>
#include <QTimer>
#include <QUrl>
#include <cstdio>
#include <cstring>
#include <link.h>

int main(int argc, char **argv)
{
    if (argc != 2)
        return 2;
    QGuiApplication app(argc, argv);
    app.setQuitOnLastWindowClosed(false);
    dl_iterate_phdr([](dl_phdr_info *info, size_t, void *) {
        if (std::strstr(info->dlpi_name, "/libQt6Quick.so.")
            || std::strstr(info->dlpi_name, "/libQt6Core.so.")
            || std::strstr(info->dlpi_name, "/libQt6Qml.so."))
            std::fprintf(stderr, "MOOS_QT_LIBRARY %s\n", info->dlpi_name);
        return 0;
    }, nullptr);
    QQuickView view;
    view.setSource(QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1])));
    if (view.status() != QQuickView::Ready || !view.rootObject())
        return 3;
    QTimer::singleShot(1000, &app, [&] {
        const bool done = view.rootObject()
            && view.rootObject()->property("viewDestroyed").toBool();
        std::fprintf(stderr, "MOOS_QT_TEARDOWN_NATIVE_EXECUTED %s\n", done ? "true" : "false");
        app.exit(done ? 0 : 7);
    });
    return app.exec();
}
