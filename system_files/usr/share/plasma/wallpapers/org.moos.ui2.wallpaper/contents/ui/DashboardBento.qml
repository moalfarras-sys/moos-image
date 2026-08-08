// MoOS UI2 Dashboard — one passive, adaptive Tidal Glass bento, rendered as
// part of the WALLPAPER (org.moos.ui2.wallpaper wraps this in a WallpaperItem).
// Living below the Folder View icon grid ended the whole family of "the widget
// sat on top of the Install MoOS icon" collisions: the desktop draws icons,
// windows and everything else ON TOP of this scene, so the bento can never
// cover anything again. Pure QtQuick + Kirigami — no Plasmoid API — so the
// build's QML smoke harness can load it directly.
// It uses the active Kirigami palette and keeps all artwork local to the package.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Item {
    id: root

    readonly property var design: MoUI.Tokens
    implicitWidth: Math.round(Kirigami.Units.gridUnit
                              * design.desktopHubColumns)
    implicitHeight: Math.round(Kirigami.Units.gridUnit
                               * design.desktopHubRows)

    property date now: new Date()
    property real latitude: NaN
    property real longitude: NaN
    property string city: ""
    property var forecastData: null
    // Display name of the active MoOS look, for the clock card's badge.
    property string themeLabel: ""

    // The plugin's MotionMode config key, resolved by main.qml and threaded down:
    // 0 still / 1 gentle / 2 alive. The name carries the key on purpose — a
    // consumer that says which setting it obeys cannot quietly stop obeying it,
    // which is exactly what happened here.
    //
    // A plain property with a default, NOT a `required` one: build.sh loads this
    // file directly in a bare Loader for the QML smoke gate, and a required
    // property that nobody sets is a load error there — the gate would fail on a
    // perfectly good file. 1 is the shipped default, so the smoke still exercises
    // the ordinary path.
    property int resolvedMotionMode: 1

    // The single on/off seam every decorative movement in the package hangs off.
    // TWO things can switch it off and both must be able to:
    //
    //   * the user's own policy — `moos-theme motion still`, or the Motion
    //     control on this wallpaper's Desktop Settings page. This file used to
    //     INVENT its own gate here and never read the plugin's configuration at
    //     all, so "still" stopped the wallpaper's ambient washes and left every
    //     card in the bento animating, forever, with nothing able to stop it.
    //
    //   * Plasma's global "disable animations". Plasma expresses that by
    //     collapsing its durations — but Kirigami FLOORS longDuration at 1 and
    //     never returns 0, so the `> 0` this used to test could not be false and
    //     the gate was dead in both files. KDE's own BusyIndicator.qml, all three
    //     of them, test `> 1`.
    //
    // The policy is named FIRST, before `visible`, deliberately. It is the term
    // that was missing, it is what a reader should see first — and
    // tests/verify_user_experience.py reads only the first line of this
    // expression when it checks that the gate consults the plugin's own key, so
    // burying the key on a continuation line reads to that gate exactly like the
    // bug it is there to catch.
    readonly property bool motionEnabled:
        root.resolvedMotionMode > 0 && root.visible
        && Kirigami.Units.longDuration > 1

    // Which of the two LIVE levels this is. Deliberately NOT conjoined with
    // motionEnabled: every consumer writes `motionEnabled && accentMotion`, which
    // keeps "may anything move at all" and "which moving level is this" two
    // separate, individually readable questions, and makes it impossible for an
    // accent to start while motion is off.
    readonly property bool accentMotion: root.resolvedMotionMode >= 2

    readonly property bool weatherReady: forecastData !== null
                                                 && !isNaN(latitude)
                                                 && !isNaN(longitude)
    readonly property var arabicLocale: Qt.locale("ar")

    // Setting `now` is the WHOLE job. The timer's interval is a binding on `now`,
    // so re-aligning to the next minute boundary happens by itself.
    //
    // This function also assigned minuteTimer.interval, which looked like a
    // harmless restatement of that binding and was not: an imperative write to a
    // bound property DESTROYS the binding. From the very first tick the interval
    // stopped tracking `now` and kept whatever offset that one moment produced,
    // so the clock drifted off the minute boundary and stayed off for the rest of
    // the session — the digits changed a little later every hour.
    function refreshClock() {
        root.now = new Date()
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

    // Horizon Hub: time, weather and system health are one desktop instrument,
    // not three unrelated floating cards. One glass shell owns depth, entrance
    // and sheen; the sections below contribute content and quiet dividers only.
    GlassCard {
        anchors.fill: parent
        motionEnabled: root.motionEnabled
        accentMotion: root.accentMotion
        entranceDelay: 0

        RowLayout {
            anchors.fill: parent
            spacing: 0

            ClockCard {
                Layout.preferredWidth: Math.round(Kirigami.Units.gridUnit
                    * root.design.desktopHubClockColumns)
                Layout.fillHeight: true
                now: root.now
                motionEnabled: root.motionEnabled
                accentMotion: root.accentMotion
                integrated: true
                themeLabel: root.themeLabel
            }

            Rectangle {
                Layout.preferredWidth: root.design.borderHairline
                Layout.fillHeight: true
                Layout.topMargin: root.design.space3
                Layout.bottomMargin: root.design.space3
                color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                               Kirigami.Theme.highlightColor.g,
                               Kirigami.Theme.highlightColor.b,
                               root.design.glassBorderOpacity)
            }

            WeatherCard {
                Layout.preferredWidth: Math.round(Kirigami.Units.gridUnit
                    * root.design.desktopHubWeatherColumns)
                Layout.fillHeight: true
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
                accentMotion: root.accentMotion
                integrated: true
            }

            Rectangle {
                Layout.preferredWidth: root.design.borderHairline
                Layout.fillHeight: true
                Layout.topMargin: root.design.space3
                Layout.bottomMargin: root.design.space3
                color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                               Kirigami.Theme.highlightColor.g,
                               Kirigami.Theme.highlightColor.b,
                               root.design.glassBorderOpacity)
            }

            SystemCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                motionEnabled: root.motionEnabled
                accentMotion: root.accentMotion
                integrated: true
            }
        }
    }
}
