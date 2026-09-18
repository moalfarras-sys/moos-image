pragma ComponentBehavior: Bound

import QtQuick
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

// The clock card: two pages that turn only when asked. Page one is the hour and
// the date (ClockFace); page two is the week the owner is standing in
// (WeekStrip). Nothing rotates on its own — see CardStack for why.
Item {
    id: clockCard

    required property date now
    required property bool motionEnabled
    // MotionMode 2 ("alive"). Passed straight through to the card shell, which
    // owns the only accent this card has: the sheen sweep.
    required property bool accentMotion
    property int entranceDelay: 0
    property bool integrated: false
    // Active MoOS look, e.g. "MIDNIGHT GLASS"; empty falls back to the half.
    property string themeLabel: ""
    // 0 the hour, 1 this week. The wallpaper owns the value; the stack shows it.
    property int page: 0

    GlassCard {
        anchors.fill: parent
        motionEnabled: clockCard.motionEnabled
        accentMotion: clockCard.accentMotion
        entranceDelay: clockCard.entranceDelay
        integrated: clockCard.integrated

        CardStack {
            anchors.fill: parent
            motionEnabled: clockCard.motionEnabled
            page: clockCard.page

            ClockFace {
                now: clockCard.now
                motionEnabled: clockCard.motionEnabled
                themeLabel: clockCard.themeLabel
            }

            WeekStrip {
                now: clockCard.now
            }
        }
    }
}
