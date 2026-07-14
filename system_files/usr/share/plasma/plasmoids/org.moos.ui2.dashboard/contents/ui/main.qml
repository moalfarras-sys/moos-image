// MoOS UI2 Dashboard — one passive, adaptive Tidal Glass bento for the desktop.
// It uses the active Kirigami palette and keeps all artwork local to the package.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasmoid

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    property date now: new Date()
    property real latitude: NaN
    property real longitude: NaN
    property string city: ""
    property var forecastData: null

    // Plasma sets animation durations to zero when global animation speed is off.
    // Every decorative movement in the package is gated by this single value.
    readonly property bool motionEnabled: root.visible
                                          && Kirigami.Units.longDuration > 0
    readonly property bool weatherReady: forecastData !== null
                                                 && !isNaN(latitude)
                                                 && !isNaN(longitude)
    readonly property var arabicLocale: Qt.locale("ar")

    function refreshClock() {
        root.now = new Date()
        minuteTimer.interval = 60000
                - (root.now.getSeconds() * 1000 + root.now.getMilliseconds())
    }

    Timer {
        id: minuteTimer
        interval: 60000
                - (root.now.getSeconds() * 1000 + root.now.getMilliseconds())
        running: true
        repeat: true
        onTriggered: root.refreshClock()
    }

    // City-level geolocation and weather are intentionally keyless and stateless.
    // Location refreshes every six hours, weather every fifteen minutes, and failed
    // requests wait two minutes before retrying — exactly the proven UI1 cadence.
    function locate() {
        const request = new XMLHttpRequest()
        request.open("GET", "https://ipwho.is/")
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE) {
                return
            }
            if (request.status !== 200) {
                retryTimer.restart()
                return
            }
            try {
                const payload = JSON.parse(request.responseText)
                if (payload.success === false
                        || typeof payload.latitude !== "number"
                        || typeof payload.longitude !== "number") {
                    throw new Error("Location response has no coordinates")
                }
                root.latitude = payload.latitude
                root.longitude = payload.longitude
                root.city = payload.city || payload.region || ""
                root.refreshForecast()
            } catch (error) {
                retryTimer.restart()
            }
        }
        request.send()
    }

    function refreshForecast() {
        if (isNaN(root.latitude) || isNaN(root.longitude)) {
            return
        }
        const endpoint = "https://api.open-meteo.com/v1/forecast"
                + "?latitude=" + root.latitude
                + "&longitude=" + root.longitude
                + "&current=temperature_2m,apparent_temperature,weather_code,is_day"
                + "&daily=temperature_2m_max,temperature_2m_min"
                + "&forecast_days=1&timezone=auto"
        const request = new XMLHttpRequest()
        request.open("GET", endpoint)
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE) {
                return
            }
            if (request.status !== 200) {
                retryTimer.restart()
                return
            }
            try {
                const payload = JSON.parse(request.responseText)
                const current = payload.current
                const daily = payload.daily
                if (!current || !daily
                        || typeof current.temperature_2m !== "number"
                        || !isFinite(current.temperature_2m)
                        || typeof current.apparent_temperature !== "number"
                        || !isFinite(current.apparent_temperature)
                        || typeof current.weather_code !== "number"
                        || !isFinite(current.weather_code)
                        || !daily.temperature_2m_max
                        || daily.temperature_2m_max.length < 1
                        || typeof daily.temperature_2m_max[0] !== "number"
                        || !isFinite(daily.temperature_2m_max[0])
                        || !daily.temperature_2m_min
                        || daily.temperature_2m_min.length < 1
                        || typeof daily.temperature_2m_min[0] !== "number"
                        || !isFinite(daily.temperature_2m_min[0])) {
                    throw new Error("Forecast response is incomplete")
                }
                root.forecastData = {
                    temperature: Math.round(current.temperature_2m),
                    feelsLike: Math.round(current.apparent_temperature),
                    code: current.weather_code,
                    daylight: current.is_day === 1,
                    high: Math.round(daily.temperature_2m_max[0]),
                    low: Math.round(daily.temperature_2m_min[0])
                }
            } catch (error) {
                retryTimer.restart()
            }
        }
        request.send()
    }

    function weatherKind(code, daylight) {
        if (code === 0 || code === 1) {
            return daylight ? "clear-day" : "clear-night"
        }
        if (code === 2) {
            return daylight ? "partly-day" : "partly-night"
        }
        if (code === 3) {
            return "cloudy"
        }
        if (code === 45 || code === 48) {
            return "fog"
        }
        if (code >= 95) {
            return "storm"
        }
        if ((code >= 71 && code <= 77) || code === 85 || code === 86) {
            return "snow"
        }
        if ((code >= 51 && code <= 67) || (code >= 80 && code <= 82)) {
            return "rain"
        }
        return "cloudy"
    }

    function conditionNameArabic(code) {
        if (code === 0) {
            return "سماء صافية"
        }
        if (code === 1) {
            return "صحو غالباً"
        }
        if (code === 2) {
            return "غائم جزئياً"
        }
        if (code === 3) {
            return "غائم"
        }
        if (code === 45 || code === 48) {
            return "ضباب هادئ"
        }
        if (code >= 95) {
            return "عاصفة رعدية"
        }
        if ((code >= 71 && code <= 77) || code === 85 || code === 86) {
            return "تساقط ثلجي"
        }
        if (code >= 80 && code <= 82) {
            return "زخّات مطر"
        }
        if (code >= 61 && code <= 67) {
            return "أمطار"
        }
        if (code >= 51 && code <= 57) {
            return "رذاذ"
        }
        return "غائم"
    }

    Component.onCompleted: root.locate()

    Timer {
        interval: 15 * 60000
        running: true
        repeat: true
        onTriggered: root.refreshForecast()
    }

    Timer {
        interval: 6 * 3600000
        running: true
        repeat: true
        onTriggered: root.locate()
    }

    Timer {
        id: retryTimer
        interval: 2 * 60000
        running: false
        repeat: false
        onTriggered: isNaN(root.latitude) ? root.locate() : root.refreshForecast()
    }

    fullRepresentation: Item {
        id: dashboard

        implicitWidth: Math.round(Kirigami.Units.gridUnit * 31)
        implicitHeight: Math.round(Kirigami.Units.gridUnit * 12)
        Layout.minimumWidth: implicitWidth
        Layout.minimumHeight: implicitHeight
        Layout.preferredWidth: implicitWidth
        Layout.preferredHeight: implicitHeight

        RowLayout {
            anchors.fill: parent
            spacing: Math.round(Kirigami.Units.gridUnit * 0.65)

            ClockCard {
                Layout.preferredWidth: Math.round(Kirigami.Units.gridUnit * 12.45)
                Layout.fillHeight: true
                now: root.now
                motionEnabled: root.motionEnabled
                entranceDelay: 0
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: Math.round(Kirigami.Units.gridUnit * 0.65)

                WeatherCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.round(Kirigami.Units.gridUnit * 7.05)
                    weatherReady: root.weatherReady
                    city: root.city
                    temperature: root.weatherReady ? root.forecastData.temperature : 0
                    feelsLike: root.weatherReady ? root.forecastData.feelsLike : 0
                    high: root.weatherReady ? root.forecastData.high : 0
                    low: root.weatherReady ? root.forecastData.low : 0
                    kind: root.weatherReady
                            ? root.weatherKind(root.forecastData.code,
                                               root.forecastData.daylight)
                            : "cloudy"
                    condition: root.weatherReady
                            ? root.conditionNameArabic(root.forecastData.code)
                            : ""
                    motionEnabled: root.motionEnabled
                    entranceDelay: 70
                }

                SystemCard {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    motionEnabled: root.motionEnabled
                    entranceDelay: 140
                }
            }
        }
    }
}
