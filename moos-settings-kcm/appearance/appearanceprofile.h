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
    if (data.value(QStringLiteral("schema")) != QJsonValue(1) || !data.value(QStringLiteral("look")).isString()) return false;
    for (const auto &key : data.keys())
        if (!QStringList{QStringLiteral("schema"),QStringLiteral("look"),QStringLiteral("image"),QStringLiteral("colors"),QStringLiteral("font")}.contains(key)) return false;
    const QString look = data.value(QStringLiteral("look")).toString();
    QFile profiles(catalog);
    if (!profiles.open(QIODevice::ReadOnly) || profiles.size() > 65536) return false;
    QStringList selected;
    for (const auto &row : profiles.readAll().split('\n')) {
        const auto fields = QString::fromUtf8(row).split(QLatin1Char('\t'));
        if (fields.size() == 17 && fields[0] == look) { selected=fields; break; }
    }
    if (selected.isEmpty()) return false;
    static const QRegularExpression asset(QStringLiteral("^[A-Za-z0-9_-]{1,96}$"));
    if (!asset.match(selected[1]).hasMatch() || !asset.match(selected[2]).hasMatch() || !asset.match(selected[4]).hasMatch()) return false;
    MoOSAppearanceProfile profile;
    profile.look=look; profile.scheme=selected[1]; profile.style=selected[2]; profile.icons=selected[4];
    if (data.contains(QStringLiteral("font"))) {
        if (!data.value(QStringLiteral("font")).isString()) return false;
        profile.font=data.value(QStringLiteral("font")).toString();
        if (profile.font.size() > 512 || profile.font.contains(QRegularExpression(QStringLiteral("[\\x00-\\x1f\\x7f]")))) return false;
        QFont font;
        if (!profile.font.isEmpty() && !font.fromString(profile.font)) return false;
        if (!profile.font.isEmpty() && (font.pixelSize()!=-1
            ? font.pixelSize()<4 || font.pixelSize()>192
            : font.pointSizeF()<4 || font.pointSizeF()>96)) return false;
    }
    if (data.contains(QStringLiteral("colors"))) {
        if (!data.value(QStringLiteral("colors")).isObject()) return false;
        profile.colors=data.value(QStringLiteral("colors")).toObject();
        const QStringList sets{QStringLiteral("Colors:Window"),QStringLiteral("Colors:View"),QStringLiteral("Colors:Button"),QStringLiteral("Colors:Selection"),QStringLiteral("Colors:Tooltip"),QStringLiteral("Colors:Complementary"),QStringLiteral("Colors:Header")};
        const QStringList roles{QStringLiteral("BackgroundNormal"),QStringLiteral("BackgroundAlternate"),QStringLiteral("ForegroundNormal"),QStringLiteral("ForegroundInactive"),QStringLiteral("ForegroundActive"),QStringLiteral("ForegroundLink"),QStringLiteral("ForegroundVisited"),QStringLiteral("ForegroundNegative"),QStringLiteral("ForegroundNeutral"),QStringLiteral("ForegroundPositive"),QStringLiteral("DecorationFocus"),QStringLiteral("DecorationHover")};
        static const QRegularExpression rgb(QStringLiteral("^[0-9]{1,3},[0-9]{1,3},[0-9]{1,3}$"));
        for (const auto &set : profile.colors.keys()) {
            if (!sets.contains(set) || !profile.colors.value(set).isObject()) return false;
            const auto entries=profile.colors.value(set).toObject();
            for (const auto &role : entries.keys()) {
                if (!roles.contains(role) || !entries.value(role).isString()) return false;
                const auto value=entries.value(role).toString();
                if (!rgb.match(value).hasMatch()) return false;
                for (const auto &part : value.split(QLatin1Char(','))) if (part.toInt()>255) return false;
            }
        }
    }
    if (data.contains(QStringLiteral("image"))) {
        if (!data.value(QStringLiteral("image")).isString()) return false;
        const auto encoded=data.value(QStringLiteral("image")).toString().toLatin1();
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

