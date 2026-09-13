import QtQuick
import org.kde.kirigami as Kirigami

// Finite, retargetable physical feedback for SCALE only. Layout/hit targets
// never move. No timers or render layers; idle springs do no work.
QtObject {
    id: feedback
    property bool motionEnabled: Kirigami.Units.longDuration > 1
    property bool active: true
    property real targetScale: 1
    property real value: 1
    property bool initialized: false
    readonly property bool settling: spring.running

    function retarget() {
        if (motionEnabled && active) {
            spring.to = targetScale
            spring.restart()
        }
        else {
            spring.stop()
            value = targetScale
        }
    }
    onTargetScaleChanged: { if (initialized) retarget() }
    Component.onCompleted: {
        value = targetScale
        initialized = true
    }
    // A Behavior owns its animation and ignores public stop/complete calls.
    // Keep the spring on this private value instead: reduced motion can stop
    // it synchronously without replacing the consumer's scale binding.
    onMotionEnabledChanged: {
        if (initialized && !motionEnabled) retarget()
    }
    onActiveChanged: { if (initialized && !active) retarget() }

    property SpringAnimation animation: SpringAnimation {
        id: spring
        target: feedback
        property: "value"
        spring: Tokens.springStiffness
        damping: Tokens.springDamping
        epsilon: Tokens.springEpsilon
        mass: 1
    }
}
