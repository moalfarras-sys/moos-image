/*
    SPDX-FileCopyrightText: 2014 David Edmundson <davidedmundson@kde.org>
    SPDX-FileCopyrightText: 2026 Moalfarras — MoOS identity

    SPDX-License-Identifier: LGPL-2.0-or-later
*/

// MoOS: Plasma's own list of accounts, standing as a row when it can.
//
// Upstream's list is a carousel: whoever is selected is pulled to the centre and
// everyone else trails off to one side. On a home machine with three accounts
// that meant an island with its owner in the middle, one neighbour beside them,
// an empty place on the other side and a third account out of frame. When the
// accounts FIT — up to five, and the screen is wide enough — they stand in one
// centred row instead, nobody moves, and the selection is shown where the face
// is: the ring lights and the bloom comes up (UserDelegate). More accounts than
// that, or a narrow screen, and it is upstream's carousel again, unchanged.
//
// Everything else is upstream's, verbatim: the model contract, the delegate's
// bindings and its names, the signal and the keys. It carries no authentication.
pragma ComponentBehavior: Bound

import QtQuick

import org.kde.kirigami as Kirigami

/*
 * A model with a list of users to show in the view.
 * There are different implementations in sddm greeter (UserModel) and
 * KScreenLocker (SessionsModel), so some roles will be missing.
 *
 * type: {
 *  name: string,
 *  realName: string,
 *  homeDir: string,
 *  icon: string,
 *  iconName?: string,
 *  needsPassword?: bool,
 *  displayNumber?: string,
 *  vtNumber?: int,
 *  session?: string
 *  isTty?: bool,
 * }
 */
ListView {
    id: view
    readonly property string selectedUser: currentItem ? (currentItem as UserDelegate).userName : ""
    readonly property int userItemWidth: Kirigami.Units.gridUnit * 8
    readonly property int userItemHeight: Kirigami.Units.gridUnit * 9
    readonly property bool constrainText: count > 1
    property real fontSize: Kirigami.Theme.defaultFont.pointSize + 2

    implicitHeight: userItemHeight

    activeFocusOnTab: true

    /*
     * Signals that a user was explicitly selected
     */
    signal userSelected()

    // MoOS: the accounts stand as one centred row when all of them fit.
    readonly property int rowLimit: 5
    readonly property bool showsEveryone: count > 1 && count <= rowLimit
                                          && count * userItemWidth <= width

    orientation: ListView.Horizontal
    highlightRangeMode: showsEveryone ? ListView.NoHighlightRange
                                      : ListView.StrictlyEnforceRange

    //centre align selected item (which implicitly centre aligns the rest
    preferredHighlightBegin: width/2 - userItemWidth/2
    preferredHighlightEnd: preferredHighlightBegin

    leftMargin: showsEveryone ? Math.round((width - count * userItemWidth) / 2) : 0
    rightMargin: leftMargin

    // Disable flicking if we only have on user (like on the lockscreen)
    interactive: count > 1 && !showsEveryone

    delegate: UserDelegate {
        id: userDelegate
        required property int index
        required property string icon
        required property string realName
        required property var model
        avatarPath: icon || ""
        iconSource: model.iconName || "user-identity"
        fontSize: view.fontSize
        needsPassword: model.needsPassword !== undefined ? model.needsPassword : true

        name: {
            const displayName = realName || model.name

            if (model.vtNumber === undefined || model.vtNumber < 0) {
                return displayName
            }

            if (!model.session) {
                return i18ndc("plasma_lookandfeel_org.kde.lookandfeel", "Nobody logged in on that session", "Unused")
            }


            let location = undefined
            if (model.isTty) {
                location = i18ndc("plasma_lookandfeel_org.kde.lookandfeel", "User logged in on console number", "TTY %1", model.vtNumber)
            } else if (model.displayNumber) {
                location = i18ndc("plasma_lookandfeel_org.kde.lookandfeel", "User logged in on console (X display number)", "on TTY %1 (Display %2)", model.vtNumber, model.displayNumber)
            }

            if (location !== undefined) {
                return i18ndc("plasma_lookandfeel_org.kde.lookandfeel", "Username (location)", "%1 (%2)", displayName, location)
            }

            return displayName
        }

        userName: model.name

        width: view.userItemWidth
        height: view.userItemHeight

        //if we only have one delegate, we don't need to clip the text as it won't be overlapping with anything
        constrainText: view.constrainText

        isCurrent: ListView.isCurrentItem

        onClicked: {
            view.currentIndex = index;
            view.userSelected();
        }
    }

    Keys.onEscapePressed: view.userSelected()
    Keys.onEnterPressed: view.userSelected()
    Keys.onReturnPressed: view.userSelected()
}
