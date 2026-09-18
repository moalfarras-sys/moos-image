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
    // The cards this desktop asked for (desktop right-click menu or wallpaper page).
    // Hidden cards take no width and keep no divider, and the hub shrinks around
    // what is left instead of leaving a hole in the composition.
    property bool showClock: true
    // Which face the clock card shows; owned by the wallpaper's HubClockPage key.
    property int clockPage: 0
    // Which face the weather card shows; owned by HubWeatherPage.
    property int weatherPage: 0
    // Which face the device card shows; owned by HubSystemPage.
    property int systemPage: 0
    property bool showWeather: true
    property bool showSystem: true
    readonly property int visibleCards: (showClock ? 1 : 0) + (showWeather ? 1 : 0)
                                        + (showSystem ? 1 : 0)
    // With every card shown the hub keeps its designed 46-column width exactly; the
    // system card absorbs the remainder, as it always has.
    implicitWidth: Math.round(Kirigami.Units.gridUnit * (visibleCards === 3
        ? design.desktopHubColumns
        : (showClock ? design.desktopHubClockColumns : 0)
          + (showWeather ? design.desktopHubWeatherColumns : 0)
          + (showSystem ? design.desktopHubSystemColumns : 0)
          + Math.max(0, visibleCards - 1) * 0.5))
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
                // The card's second face answers "what about later today": the next
                // hours, from the SAME request the card already makes. One more
                // parameter, no second service, no extra poll.
                + "&hourly=temperature_2m,weather_code&forecast_hours=12"
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
                // The hourly block is a courtesy, not a requirement: a provider that
                // omits it leaves the second face empty rather than failing the card.
                const hourly = payload.hourly
                const hours = []
                if (hourly && hourly.time && hourly.temperature_2m) {
                    const nowStamp = new Date()
                    for (let i = 0; i < hourly.time.length && hours.length < 6; ++i) {
                        const when = new Date(hourly.time[i])
                        if (isNaN(when.getTime()) || when.getTime() < nowStamp.getTime() - 3600000) {
                            continue
                        }
                        const value = hourly.temperature_2m[i]
                        if (typeof value !== "number" || !isFinite(value)) { continue }
                        hours.push({
                            hour: Qt.formatTime(when, "HH:mm"),
                            temperature: Math.round(value),
                            code: (hourly.weather_code && typeof hourly.weather_code[i] === "number")
                                ? hourly.weather_code[i] : current.weather_code
                        })
                    }
                }
                root.forecastData = {
                    temperature: Math.round(current.temperature_2m),
                    feelsLike: Math.round(current.apparent_temperature),
                    code: current.weather_code,
                    daylight: current.is_day === 1,
                    high: Math.round(daily.temperature_2m_max[0]),
                    low: Math.round(daily.temperature_2m_min[0]),
                    hours: hours
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

    // Weather condition in the SESSION language. This was Arabic-only, so an English or German
    // desktop showed "أمطار" under an English city name.
    function conditionName(code) {
        const L = MoUI.Locale
        if (code === 0) return L.local("سماء صافية", "Clear sky")
        if (code === 1) return L.local("صحو غالباً", "Mostly clear")
        if (code === 2) return L.local("غائم جزئياً", "Partly cloudy")
        if (code === 3) return L.local("غائم", "Overcast")
        if (code === 45 || code === 48) return L.local("ضباب هادئ", "Fog")
        if (code >= 95) return L.local("عاصفة رعدية", "Thunderstorm")
        if ((code >= 71 && code <= 77) || code === 85 || code === 86) return L.local("تساقط ثلجي", "Snow")
        if (code >= 80 && code <= 82) return L.local("زخّات مطر", "Showers")
        if (code >= 61 && code <= 67) return L.local("أمطار", "Rain")
        if (code >= 51 && code <= 57) return L.local("رذاذ", "Drizzle")
        return L.local("غائم", "Cloudy")
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

    // Horizon Hub: time, weather and system health float directly in the
    // wallpaper composition. There is deliberately no outer card, border,
    // shadow, scrim or blur layer here: the wallpaper remains visible through
    // the complete instrument. The two hairline dividers are the only material
    // marks outside the content and keep the three readings legible on both
    // bright and dark parts of the wallpaper.
    RowLayout {
        anchors.fill: parent
        spacing: 0

        ClockCard {
            page: root.clockPage
            visible: root.showClock
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
            // Between the clock and whatever follows it.
            visible: root.showClock && (root.showWeather || root.showSystem)
            Layout.preferredWidth: root.design.borderHairline
            Layout.fillHeight: true
            Layout.topMargin: root.design.space3
            Layout.bottomMargin: root.design.space3
            color: Qt.rgba(Kirigami.Theme.textColor.r,
                           Kirigami.Theme.textColor.g,
                           Kirigami.Theme.textColor.b, 0.22)
        }

        WeatherCard {
            page: root.weatherPage
            hours: root.weatherReady && root.forecastData.hours !== undefined
                ? root.forecastData.hours : []
            // One code, one picture, on both faces.
            kindForCode: function (code) {
                return root.weatherKind(code, root.weatherReady ? root.forecastData.daylight : true)
            }
            visible: root.showWeather
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
                    ? root.conditionName(root.forecastData.code)
                    : ""
            motionEnabled: root.motionEnabled
            accentMotion: root.accentMotion
            integrated: true
        }

        Rectangle {
            // Between the weather and the system card.
            visible: root.showWeather && root.showSystem
            Layout.preferredWidth: root.design.borderHairline
            Layout.fillHeight: true
            Layout.topMargin: root.design.space3
            Layout.bottomMargin: root.design.space3
            color: Qt.rgba(Kirigami.Theme.textColor.r,
                           Kirigami.Theme.textColor.g,
                           Kirigami.Theme.textColor.b, 0.22)
        }

        SystemCard {
            page: root.systemPage
            visible: root.showSystem
            Layout.fillWidth: true
            Layout.fillHeight: true
            motionEnabled: root.motionEnabled
            accentMotion: root.accentMotion
            integrated: true
        }
    }
}
