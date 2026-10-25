// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QBuffer>
#include <QFile>
#include <QFont>
#include <QImageReader>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>

// Appearance data only. No commands, QML URLs, account setters or authentication
// objects enter this reader. Image decoding runs as the unprivileged greeter.
struct MoOSAppearanceProfile {
    QString look, scheme, style, icons, font;
    QJsonObject colors;
    QImage image;
};

static inline bool moosAppearanceProfile(const QString &raw, MoOSAppearanceProfile &out,
                                 const QString &catalog = QStringLiteral("/usr/share/moos/theme-profiles.tsv"))
{
    if (raw.size() > 1400000) return false;
    const auto doc = QJsonDocument::fromJson(raw.toUtf8());
    if (!doc.isObject()) return false;
    const auto data = doc.object();
    if (data.value("schema") != QJsonValue(1) || !data.value("look").isString()) return false;
    for (const auto &key : data.keys())
        if (!QStringList{"schema","look","image","colors","font"}.contains(key)) return false;
    const QString look = data.value("look").toString();
    QFile profiles(catalog);
    if (!profiles.open(QIODevice::ReadOnly) || profiles.size() > 65536) return false;
    QStringList selected;
    for (const auto &row : profiles.readAll().split('\n')) {
        const auto fields = QString::fromUtf8(row).split('\t');
        if (fields.size() == 17 && fields[0] == look) { selected=fields; break; }
    }
    if (selected.isEmpty()) return false;
    static const QRegularExpression asset(QStringLiteral("^[A-Za-z0-9_-]{1,96}$"));
    if (!asset.match(selected[1]).hasMatch() || !asset.match(selected[2]).hasMatch() || !asset.match(selected[4]).hasMatch()) return false;
    MoOSAppearanceProfile profile;
    profile.look=look; profile.scheme=selected[1]; profile.style=selected[2]; profile.icons=selected[4];
    if (data.contains("font")) {
        if (!data.value("font").isString()) return false;
        profile.font=data.value("font").toString();
        if (profile.font.size() > 512 || profile.font.contains(QRegularExpression("[\\x00-\\x1f\\x7f]"))) return false;
        QFont font;
        if (!profile.font.isEmpty() && !font.fromString(profile.font)) return false;
        if (!profile.font.isEmpty() && (font.pixelSize()!=-1
            ? font.pixelSize()<4 || font.pixelSize()>192
            : font.pointSizeF()<4 || font.pointSizeF()>96)) return false;
    }
    if (data.contains("colors")) {
        if (!data.value("colors").isObject()) return false;
        profile.colors=data.value("colors").toObject();
        const QStringList sets{"Colors:Window","Colors:View","Colors:Button","Colors:Selection","Colors:Tooltip","Colors:Complementary","Colors:Header"};
        const QStringList roles{"BackgroundNormal","BackgroundAlternate","ForegroundNormal","ForegroundInactive","ForegroundActive","ForegroundLink","ForegroundVisited","ForegroundNegative","ForegroundNeutral","ForegroundPositive","DecorationFocus","DecorationHover"};
        static const QRegularExpression rgb("^[0-9]{1,3},[0-9]{1,3},[0-9]{1,3}$");
        for (const auto &set : profile.colors.keys()) {
            if (!sets.contains(set) || !profile.colors.value(set).isObject()) return false;
            const auto entries=profile.colors.value(set).toObject();
            for (const auto &role : entries.keys()) {
                if (!roles.contains(role) || !entries.value(role).isString()) return false;
                const auto value=entries.value(role).toString();
                if (!rgb.match(value).hasMatch()) return false;
                for (const auto &part : value.split(',')) if (part.toInt()>255) return false;
            }
        }
    }
    if (data.contains("image")) {
        if (!data.value("image").isString()) return false;
        const auto encoded=data.value("image").toString().toLatin1();
        if (encoded.isEmpty() || encoded.size()>1048576) return false;
        const auto decoded=QByteArray::fromBase64Encoding(encoded,QByteArray::AbortOnBase64DecodingErrors);
        if (!decoded || decoded.decoded.size()>786432) return false;
        QByteArray bytes=decoded.decoded;
        QBuffer buffer(&bytes); buffer.open(QIODevice::ReadOnly);
        QImageReader reader(&buffer);
        const auto format=reader.format(); const auto size=reader.size();
        if ((format!="png" && format!="jpeg") || size.width()<1 || size.height()<1
            || size.width()>1920 || size.height()>1080 || reader.supportsAnimation()) return false;
        profile.image=reader.read();
        if (profile.image.isNull() || profile.image.size()!=size) return false;
        profile.image=profile.image.convertToFormat(QImage::Format_RGB888);
    }
    out=profile;
    return true;
}

