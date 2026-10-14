pragma ComponentBehavior: Bound

import QtQuick
import org.moos.ui as MoUI

// A control that has keyboard focus must SHOW it. WCAG 2.4.7, and plain courtesy.
//
// Mo Store is the one MoOS app that supports Tab at all — five component types declare
// activeFocusOnTab. Measured, exactly ONE of them drew anything when focused: the search
// field, whose border thickens (StoreHeader.qml). The other four moved an invisible cursor,
// so a keyboard user could tab through the whole storefront with no idea where they were.
//
// This is a component rather than five copies of a Rectangle because the next focusable
// thing anyone adds should be one line away from being correct.
//
// It is NOT a QtQuick.Controls style. There is no MoOS style module to put it in — Mo Store,
// Welcome and the Installer all run QT_QUICK_CONTROLS_STYLE=Basic — and a Controls style
// could not reach these anyway: every focusable here is a bare Rectangle with hand-rolled
// TapHandler/Keys handlers, which no Controls style ever touches.
//
// Drawn OUTSIDE the shape (negative margins) so it never covers content or fights the
// control's own border, and it follows the parent's own radius so a pill stays a pill and a
// card stays a card. No animation: a focus ring must appear the instant focus lands, and
// Liquid Glass surfaces already gate their motion on `motionEnabled`.
MoUI.FocusRing {
    id: ring
    required property var win
    accentColor: win.accent
}
