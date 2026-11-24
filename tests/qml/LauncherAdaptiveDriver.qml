// Private Plasma-host input driver. Injected only into a temporary package copy.
// No shortcuts, settings, authentication or owner-session input are modified.
import QtQuick
import QtQuick.Window
import org.kde.kirigami as Kirigami
import QtTest as Test

Item {
    id: driver
    required property var surface
    required property var field
    required property var appGrid
    required property var homeGrid
    required property var homeScroll
    required property var canvas
    required property var pages
    required property var navigation
    required property var categories
    required property var placesList
    required property var powerButton
    required property var powerMenu
    required property var actionMenu
    required property string reviewDirectory
    required property var runnerFavorites
    required property string firstSearchRunner
    property bool captureFinished: false
    function captureSurface(name) {
        captureFinished = false;
        driver.verify(surface.grabToImage(result => {
            captureFinished = result.saveToFile(reviewDirectory + "-" + name + ".png");
        }), "native surface capture started");
        driver.waitVerified(() => captureFinished, 1500, "native source surface captured: " + name);
    }

    function textItem(item, value) {
        if (item.text === value) return item;
        for (const child of item.children || []) {
            const found = textItem(child, value);
            if (found) return found;
        }
        return null;
    }
    function verify(value, message) {
        if (!value) console.error("MOOS_ADAPTIVE_ASSERT " + message);
        check.verify(value, message);
    }
    function compare(actual, expected, message) {
        if (actual !== expected) console.error("MOOS_ADAPTIVE_ASSERT " + message
            + " actual=" + actual + " expected=" + expected);
        check.compare(actual, expected, message);
    }
    function waitVerified(predicate, timeout, message) {
        try { check.tryVerify(predicate, timeout, message); }
        catch (error) { console.error("MOOS_ADAPTIVE_ASSERT " + message); throw error; }
    }
    Test.TestCase { id: check; when: false; name: "MoOSAdaptiveLauncher" }
    Timer {
        interval: 1200
        running: true
        repeat: false
        onTriggered: {
            try {
                console.info("MOOS_ADAPTIVE_STAGE begin");
                const v = driver.surface;
                const l = v.launcher;
                const nativeTheme=v.nativeThemeProbe;
                const initialPalette={owner:String(nativeTheme),background:String(nativeTheme.backgroundColor),text:String(nativeTheme.textColor),accent:String(nativeTheme.highlightColor)};
                driver.verify(initialPalette.owner.startsWith("PlasmaTheme("),"actual source view uses native Plasma theme owner");
                driver.Window.window.title = "MoOS Adaptive Input Gate";
                // Windowed hosts lack plasmashell's inherited RTL parent.
                v.LayoutMirroring.enabled = v.rtl;
                v.LayoutMirroring.childrenInherit = true;
                check.wait(100);
                driver.verify(v.width > 0 && v.height > 0, "real full representation");
                driver.verify(driver.canvas.x >= 0 && driver.canvas.y >= 0,
                             "canvas starts inside surface");
                driver.verify(driver.canvas.x + driver.canvas.width <= v.width + 1
                    && driver.canvas.y + driver.canvas.height <= v.height + 1,
                    "canvas fits surface");
                for (let p = 0; p < 4; ++p) {
                    const nav = v.navForPage(p);
                    driver.verify(nav.width >= 44 && nav.height >= 44, "44px navigation");
                }
                driver.verify(driver.appGrid.cellWidth >= 100, "readable application cells");
                driver.verify(driver.appGrid.columns >= 1 && driver.appGrid.columns <= 8,
                             "one through eight columns");
                const originalSearchPins = JSON.stringify(l.favoriteSearchIds);
                driver.compare(JSON.stringify(v.searchModel.favoriteIds), JSON.stringify(driver.runnerFavorites),
                    "Milou preserves native default or personal provider priority");
                l.searchQuery = "true";
                function searchRows() {
                    const rows = [];
                    for (let row = 0; row < v.searchModel.rowCount(); ++row) {
                        const index = v.searchModel.index(row, 0);
                        const urls = v.searchModel.data(index, 265) || [];
                        rows.push({ id: String(v.searchModel.data(index, 257)),
                            urls: Array.from(urls, url => String(url)) });
                    }
                    return rows;
                }
                function fixtureResult(row) { return row.urls.some(url => url.endsWith("/mova-provider-fixture.desktop")); }
                function commandResult(row) { return row.id === "exec:///usr/bin/true"; }
                driver.waitVerified(() => !v.searchModel.querying && searchRows().some(fixtureResult)
                    && searchRows().some(commandResult), 5000, "native search providers produce competing results");
                console.info("MOOS_ADAPTIVE_STAGE search-ready");
                const nativeSearchRows = searchRows();
                driver.verify(nativeSearchRows.some(fixtureResult),
                    "native services provider finds the private application");
                driver.verify(nativeSearchRows.some(commandResult),
                    "native shell provider supplies its own executable result");
                driver.verify(driver.firstSearchRunner === "krunner_services"
                    ? fixtureResult(nativeSearchRows[0]) : commandResult(nativeSearchRows[0]),
                    "native result ranking follows configured provider priority: " + JSON.stringify(nativeSearchRows));
                l.searchQuery = "";
                check.wait(60);
                driver.compare(JSON.stringify(l.favoriteSearchIds), originalSearchPins,
                    "native provider ranking leaves application pins unchanged");
                l.activePage = 1;
                check.tryCompare(driver.pages, "pageAnimating", false, 1500,
                    "application page settles before category pointer input");
                driver.verify(check.waitForPolish(driver.categories), "native category layout polished");
                driver.verify(check.waitForPolish(driver.appGrid), "visible native app layout polished");
                const fullRows=Math.floor((driver.appGrid.height+.01)/driver.appGrid.cellHeight);
                driver.verify(fullRows>=1 && driver.appGrid.height-fullRows*driver.appGrid.cellHeight<3,
                    "library settles on complete readable rows: height="+driver.appGrid.height+" cell="+driver.appGrid.cellHeight+" rows="+fullRows);

                const allApps = driver.appGrid.count;
                driver.verify(l.appRootModel.count > 2, "native app categories are present");
                driver.categories.positionViewAtIndex(2, ListView.Contain);
                driver.verify(check.waitForPolish(driver.categories), "scrolled category layout polished");
                const category = driver.categories.itemAtIndex(2);
                driver.verify(category && category.visible && category.height >= 44,
                    "native category is a visible touch target");
                check.mouseClick(category);
                check.wait(80);
                driver.compare(l.appsModelRow, 2, "pointer selects native category");
                driver.verify(driver.appGrid.model === l.appRootModel.modelForRow(2),
                    "grid consumes the actual selected Kicker model");
                driver.verify(driver.appGrid.count > 0 && driver.appGrid.count <= allApps,
                    "category has actual application entries");
                check.keyClick(v.rtl ? Qt.Key_Left : Qt.Key_Right);
                check.wait(80);
                driver.compare(l.appsModelRow, Math.min(3, l.appRootModel.count - 1),
                    "logical arrow changes category");
                v.focusCategory(1);
                check.wait(80);
                driver.compare(driver.appGrid.count, allApps, "All restores complete catalogue");
                // Follow the actual nested KService menu produced in private XDG.
                let nativeFolder = null;
                for (let categoryRow = 2; categoryRow < l.appRootModel.count; ++categoryRow) {
                    const model = l.appRootModel.modelForRow(categoryRow);
                    if (!model) continue;
                    for (let row = 0; row < model.count; ++row) {
                        const child = model.modelForRow(row);
                        if (child) {nativeFolder={category:categoryRow,row:row,parent:model,child:child};break;}
                    }
                    if (nativeFolder) break;
                }
                driver.verify(nativeFolder !== null,"real nested KService group exists");
                l.appsModelRow = nativeFolder.category;
                driver.verify(l.enterAppFolder(nativeFolder.row,"Native folder"),"enter native child folder");
                driver.verify(l.appsModel === nativeFolder.child && l.appFolderPath.length === 1,
                    "folder grid uses the exact native child model");
                driver.verify(!l.enterAppFolder(-1,"invalid"),"invalid folder row is refused");
                driver.verify(l.leaveAppFolder() && l.appsModel === nativeFolder.parent,
                    "folder back restores the exact native parent");
                driver.verify(!l.leaveAppFolder(),"folder root cannot underflow");
                v.selectCategory(1);check.wait(50);
                // One level per row and a name that stays with its icon: the
                // layout once spread spare cell height between them, and a
                // wrapped name lifted only its own icon.
                const rowIcons=[];
                for(let i=0;i<Math.min(driver.appGrid.columns,driver.appGrid.count);++i){
                    const t=driver.appGrid.itemAtIndex(i);if(!t)continue;
                    const icon=named(t,"movaAppIcon"),label=named(t,"movaAppName");
                    driver.verify(icon&&label,"tile exposes its icon and name");
                    const iy=icon.mapToItem(driver.appGrid,0,0).y,ly=label.mapToItem(driver.appGrid,0,0).y;
                    rowIcons.push(iy);
                    driver.verify(ly-(iy+icon.height)<=v.space2+1,"name sits with its icon: gap="+(ly-(iy+icon.height)));
                    driver.verify(label.mapToItem(t,0,0).y+label.paintedHeight<=t.height+1,"name ink inside its card");
                }
                driver.verify(rowIcons.length>0&&Math.max(...rowIcons)-Math.min(...rowIcons)<=1,
                    "first library row keeps one icon level: "+JSON.stringify(rowIcons));
                driver.captureSurface("library");
                const densityButton=driver.textItem(v,v.local("عرض مضغوط","Compact view"));
                driver.verify(densityButton!==null,"native compact preference control is reachable");
                const normalRow=driver.appGrid.cellHeight;
                check.mouseClick(densityButton);check.wait(50);
                driver.compare(densityButton.text,v.local("عرض مريح","Comfortable view"),"compact choice rereads its native preference");
                driver.verify(driver.appGrid.cellHeight<=normalRow,"compact choice preserves or increases visible rows");
                const compactTile=driver.appGrid.itemAtIndex(0);
                const compactName=named(compactTile,"movaAppName");
                compactName.text=v.local("مُحَرِّرُ المُسْتَنَدَاتِ وَمَلَفَّاتُ العَمَلِ","Long application name for documents and workspace");
                check.wait(40);
                driver.verify(compactName.height+1>=compactName.paintedHeight,"compact card reserves actual two-line ink");
                compactName.text=Qt.binding(()=>String(compactTile.model.compactName||compactTile.model.display||""));
                driver.captureSurface("library-compact");
                check.mouseClick(densityButton);check.wait(50);
                driver.compare(densityButton.text,v.local("عرض مضغوط","Compact view"),"density test restores exact original preference");

                // The same menu and native favorite client used by the real applet.
                const originalPins = JSON.stringify(l.favoriteSearchIds);
                let actionTile = null;
                for (let row = 0; row < driver.appGrid.count; ++row) {
                    driver.appGrid.positionViewAtIndex(row, GridView.Contain);
                    check.wait(20);
                    const candidate = driver.appGrid.itemAtIndex(row);
                    if (candidate && candidate.favoriteId && !l.favoriteModel.isFavorite(candidate.favoriteId)) {
                        actionTile = candidate; break;
                    }
                }
                driver.verify(actionTile !== null, "real unpinned application for native menu");
                check.mouseClick(actionTile, actionTile.width/2, actionTile.height/2, Qt.RightButton);
                check.tryCompare(driver.actionMenu, "opened", true, 1500, "right click opens native menu");
                const entries = driver.actionMenu.__menu.content;
                let favoriteAction = null;
                for (const entry of entries) {
                    if (entry.actionItem && entry.actionItem.actionId === "_kicker_favorite_add") favoriteAction = entry;
                }
                driver.verify(favoriteAction !== null, "native Kicker favorite action exists");
                const pinnedId = actionTile.favoriteId;
                driver.actionMenu.favoriteIdentity = "not-the-selected-application";
                favoriteAction.action.trigger();check.wait(50);
                driver.verify(!l.favoriteModel.isFavorite(pinnedId),"retired menu identity cannot affect another application");
                driver.actionMenu.favoriteIdentity = pinnedId;
                favoriteAction.action.trigger();
                driver.waitVerified(() => l.favoriteModel.isFavorite(pinnedId), 1500, "native QAction pins application");
                driver.actionMenu.__menu.close();
                l.favoriteModel.removeFavorite(pinnedId);
                driver.waitVerified(() => JSON.stringify(l.favoriteSearchIds) === originalPins, 1500,
                    "native pin test restores exact favorite identity/order");
                driver.appGrid.positionViewAtBeginning();
                driver.Window.window.requestActivate();
                check.tryCompare(driver.Window.window, "active", true);
                v.focusSearch();
                check.keyClick(Qt.Key_Down);
                driver.verify(driver.appGrid.activeFocus, "Down enters real app catalogue");
                check.keyClick(Qt.Key_Backtab, Qt.ShiftModifier);
                driver.verify(v.navForPage(1).activeFocus, "Backtab returns to current navigation");
                if (v.compact) {
                    check.keyClick(v.rtl ? Qt.Key_Right : Qt.Key_Left);
                    driver.verify(v.navForPage(0).activeFocus, "logical previous compact tab");
                } else {
                    check.keyClick(Qt.Key_Up);
                    driver.verify(v.navForPage(0).activeFocus, "previous wide navigation");
                }
                check.keyClick(Qt.Key_Return);
                driver.compare(l.activePage, 0, "keyboard changes page");
                // Qt touch input uses the actual ItemDelegate and native Kicker state.
                const apps = v.navForPage(1);
                const touch = check.touchEvent(apps);
                touch.press(0, apps, apps.width/2, apps.height/2).commit();
                touch.release(0, apps, apps.width/2, apps.height/2).commit();
                check.wait(80);
                driver.compare(l.activePage, 1, "touch changes page");
                driver.verify(apps.activeFocus, "touch focus follows selected page");
                v.focusSearch();
                for (const letter of "moos-adaptive-test") check.keyClick(letter);
                driver.compare(l.searchQuery, "moos-adaptive-test", "native text editing");
                check.keyClick(Qt.Key_Escape);
                driver.compare(l.searchQuery, "", "Escape clears query");
                if (v.compact) {
                    check.mouseClick(driver.powerButton);
                    check.wait(100);
                    driver.verify(driver.powerMenu.visible && driver.powerMenu.count > 0,
                                 "real session actions remain reachable");
                    check.keyClick(Qt.Key_Escape);
                    check.tryCompare(driver.powerMenu, "visible", false, 1000,
                                     "Escape dismisses power menu after its finite transition");
                }
                // Visit every real page; no program or session action is executed.
                for (let p = 0; p < 4; ++p) {
                    check.mouseClick(v.navForPage(p));
                    check.wait(30);
                    driver.compare(l.activePage, p, "all pages remain selectable");
                    driver.verify(v.navForPage(p).activeFocus, "pointer focus follows selected page");
                }
                l.activePage = 0;
                check.wait(100);
                function named(item, name) {
                    if (item.objectName === name) return item;
                    for (const child of item.children || []) {
                        const found = named(child, name);
                        if (found) return found;
                    }
                    return null;
                }
                for (const name of ["moosHomeOverview", "moosHomeArrangement", "moosHomeSettings", "moosHomeMira"]) {
                    const action = named(v, name);
                    driver.verify(action && action.width >= 44 && action.height >= 44,
                        "Home action keeps its input target: " + name);
                    for (const caption of [action.title, action.eyebrow]) {
                        const label = driver.textItem(action.contentItem, caption);
                        driver.verify(!!label, "Home command has a native label: " + caption);
                        const top = label.mapToItem(action, 0, 0).y;
                        driver.verify(top >= action.topPadding - 1
                            && top + label.implicitHeight <= action.height - action.bottomPadding + 1,
                            "Home command reserves its full label and padding: " + caption
                            + " top=" + top + " line=" + label.implicitHeight + " card=" + action.height);
                    }
                    action.forceActiveFocus();check.wait(20);
                    const visiblePosition=action.mapToItem(driver.homeScroll,0,0);
                    driver.verify(visiblePosition.y>=-1 && visiblePosition.y+action.height<=driver.homeScroll.height+1,
                        "focused Home action stays inside visible viewport");
                    const position = action.mapToItem(driver.homeScroll, 0, 0);
                    driver.verify(position.x >= -1 && position.x + action.width <= driver.homeScroll.width + 1,
                        "Home action fits horizontally: " + name);
                }
                const pinnedHeading=named(v,"launcherPinnedHeading"),firstPinned=driver.homeGrid.itemAtIndex(0);
                if(pinnedHeading&&firstPinned){
                    const gap=firstPinned.mapToItem(driver.homeScroll,0,0).y-(pinnedHeading.mapToItem(driver.homeScroll,0,0).y+pinnedHeading.height);
                    driver.verify(gap<=v.space3*2+v.space1+1,"first pinned row follows its heading: gap="+gap);
                }
                const edge=named(driver.homeScroll,"movaScrollEdge");
                driver.verify(edge&&edge.parent===driver.homeScroll,"scroll edge belongs to the viewport, not the scrolled content");
                driver.homeScroll.contentY=0;check.wait(v.motionFast+60);
                const overflow=driver.homeScroll.contentHeight-driver.homeScroll.height>1;
                driver.compare(edge.more,overflow,"scroll edge appears exactly when Home continues below");
                if(overflow){
                    driver.homeScroll.contentY=driver.homeScroll.contentHeight-driver.homeScroll.height;
                    check.wait(v.motionFast+60);
                    driver.verify(!edge.more&&!edge.visible,"scroll edge leaves at the end of Home");
                    driver.homeScroll.contentY=0;
                }
                const horizon=named(v,"movaHorizon");
                driver.verify(horizon&&horizon.gradient.stops[0].color.a===0&&horizon.gradient.orientation===Gradient.Vertical,
                    "horizon rises from the rim with no top edge");
                l.activePage = 2;
                check.tryCompare(driver.pages, "pageAnimating", false, 1500, "Places settles");
                v.focusActivePageContent();
                driver.verify(driver.placesList.activeFocus && driver.placesList.currentSection.length > 0,
                    "Places keeps native row focus and publishes its native group");
                check.keyClick(Qt.Key_Backtab, Qt.ShiftModifier);
                check.keyClick(Qt.Key_Backtab, Qt.ShiftModifier);
                const split = named(v, "movaSplitFiles");
                driver.verify(split && split.activeFocus && split.height >= 44
                    && split.width >= split.implicitWidth - 1,
                    "Split Files is a readable keyboard-reachable touch target");
                driver.captureSurface("places");
                l.activePage=3;check.tryCompare(driver.pages,"pageAnimating",false,1500,"customize settles");
                const switches=[];
                (function collect(item){if(item.objectName==="movaSettingSwitch")switches.push(item);for(const c of item.children||[])collect(c);})(v);
                driver.verify(switches.length>=2,"customize toggles are native switches");
                for(const sw of switches){
                    const track=named(sw,"movaSettingSwitchTrack");
                    driver.verify(track&&track.visible===!sw.checked,"off switch shows a visible track");
                    driver.verify(Math.abs(track.width-sw.indicator.width)<1&&Math.abs(track.height-sw.indicator.height)<1
                        &&Math.abs(track.x-sw.indicator.x)<1&&Math.abs(track.y-sw.indicator.y)<1,"track matches native indicator");
                }
                l.activePage=0;check.wait(v.motionMedium+60);
                const store = named(v, "launcherStore");
                driver.verify(store && store.width >= 44 && store.height >= 44,
                    "Store remains a real application-library destination");
                const orbitTitle = driver.textItem(v, v.local("تطبيقاتك المفضّلة", "Pinned applications"));
                driver.verify(orbitTitle !== null, "real Home section title exists");
                driver.compare(orbitTitle.effectiveHorizontalAlignment,
                    v.rtl ? Text.AlignRight : Text.AlignLeft,
                    "section text follows the logical leading edge once");
                // Real Qt pointer drag through production DragHandler/DropArea,
                // committing to the native KAStats owner only on accepted drop.
                l.expanded = true;
                l.activePage = 0; l.editMode = false;
                check.wait(100);
                driver.homeScroll.contentY = 0;
                driver.homeGrid.positionViewAtBeginning();
                driver.verify(check.waitForPolish(driver.homeGrid), "favorite layout polished");
                check.tryCompare(driver.pages,"pageAnimating",false,1500,"Home settles before review");
                driver.captureSurface("home");
                l.editMode = true;
                check.wait(100);
                console.info("MOOS_ADAPTIVE_STAGE before-native-drag");
                function settledFavoriteRows() {
                    driver.homeGrid.forceLayout();
                    driver.verify(check.waitForPolish(driver.homeGrid), "moved favorite layout polished");
                    const owner = v.Window.window;
                    driver.verify(owner && owner.visible, "favorite layout has a visible native window");
                    owner.update();
                    driver.verify(check.waitForRendering(driver.homeGrid,1500), "favorite rows reach a native frame");
                    driver.waitVerified(() => [0,1].every(row => {
                        const tile = driver.homeGrid.itemAtIndex(row);
                        return tile && tile.index === row
                            && tile.favoriteId === l.favoriteSearchIds[row]
                            && tile.Window.window === owner;
                    }),1500,"favorite delegates match the current native row identities");
                }
                settledFavoriteRows();
                const pinOrder = JSON.stringify(l.favoriteSearchIds);
                const firstPin = l.favoriteSearchIds[0];
                const secondPin = l.favoriteSearchIds[1];
                const firstTile = driver.homeGrid.itemAtIndex(0);
                const secondTile = driver.homeGrid.itemAtIndex(1);
                driver.verify(firstTile && secondTile, "real favorite delegates for reordering");
                const name = named(firstTile, "movaAppName");
                const menuButton = named(firstTile, "movaAppActionsButton");
                driver.verify(name && name.height + 1 >= name.paintedHeight,
                    "application name ink fits its actual two-line item");
                const originalName = name.text;
                name.text = v.local("مُحَرِّرُ المُسْتَنَدَاتِ وَمَلَفَّاتُ العَمَلِ", "Long application name for documents and workspace");
                check.wait(40);
                driver.verify(name.lineCount <= 2 && name.height + 1 >= name.paintedHeight,
                    "long source-font label retains its natural two-line ink bounds");
                name.text = Qt.binding(() => String(firstTile.model.compactName || firstTile.model.display || ""));
                menuButton.forceActiveFocus();check.wait(20);
                driver.verify(menuButton.visible && menuButton.activeFocus,"native actions retain their keyboard focus");
                driver.verify(menuButton && menuButton.width >= 44 && menuButton.height >= 44
                    && menuButton.x >= 0 && menuButton.x + menuButton.width <= firstTile.width + 1,
                    "single action target fits narrow favorite card");
                check.mousePress(firstTile, firstTile.width/2, firstTile.height/2, Qt.LeftButton);
                check.mouseMove(firstTile, firstTile.width/2 + 16, firstTile.height/2, 30);
                check.mouseMove(secondTile, secondTile.width/2, secondTile.height/2, 60);
                check.wait(80);
                driver.compare(JSON.stringify(l.favoriteSearchIds), pinOrder,
                    "drag hover never changes persistent favorite order");
                check.mouseRelease(secondTile, secondTile.width/2, secondTile.height/2, Qt.LeftButton);
                check.wait(100);
                driver.waitVerified(() => l.favoriteSearchIds[0] === secondPin && l.favoriteSearchIds[1] === firstPin,
                    1500, "accepted Qt drop reorders the native favorites model");
                l.moveFavorite(1, 0);
                driver.waitVerified(() => JSON.stringify(l.favoriteSearchIds) === pinOrder, 1500,
                    "private drag test restores native order");
                settledFavoriteRows();
                // Closing during a held drag is cancellation, never accepted drop.
                const favoriteWindowOwner = v.Window.window;
                const cancelledSource = driver.homeGrid.itemAtIndex(0);
                const cancelledTarget = driver.homeGrid.itemAtIndex(1);
                check.mouseMove(cancelledSource,cancelledSource.width/2,cancelledSource.height/2,30);
                check.mousePress(cancelledSource, cancelledSource.width/2, cancelledSource.height/2, Qt.LeftButton);
                check.mouseMove(cancelledSource, cancelledSource.width/2 + 16, cancelledSource.height/2, 30);
                check.mouseMove(cancelledTarget, cancelledTarget.width/2, cancelledTarget.height/2, 60);
                driver.waitVerified(() => named(cancelledTarget,"movaFavoriteDrop").containsDrag,1000,
                    "cancel control reaches the actual accepted drop target");
                l.expanded = false;
                check.mouseRelease(cancelledTarget, cancelledTarget.width/2, cancelledTarget.height/2, Qt.LeftButton);
                check.wait(100);
                driver.compare(JSON.stringify(l.favoriteSearchIds), pinOrder,
                    "closed launcher refuses a held drop without changing native order");
                l.expanded = true; l.activePage = 0; l.editMode = true;
                driver.waitVerified(() => v.Window.window === favoriteWindowOwner
                    && favoriteWindowOwner.visible,1500,
                    "reopened content retains the actual native window owner");
                settledFavoriteRows();
                const touchSource = driver.homeGrid.itemAtIndex(0);
                const touchTarget = driver.homeGrid.itemAtIndex(1);
                const touchInput = favoriteWindowOwner.contentItem;
                const reorderTouch = check.touchEvent(touchInput);
                let touchHeld = false;
                let touchPosition = touchSource.mapToItem(touchInput,touchSource.width/2,touchSource.height/2);
                function verifyTouchOwner() {
                    driver.verify(v.Window.window === favoriteWindowOwner
                        && touchSource.Window.window === favoriteWindowOwner
                        && touchTarget.Window.window === favoriteWindowOwner
                        && favoriteWindowOwner.visible,"touch stays on the qualified native window");
                }
                function touchFrame() {
                    verifyTouchOwner();
                    favoriteWindowOwner.update();
                    driver.verify(check.waitForRendering(touchSource,1500),
                        "touch motion reaches a native rendered frame");
                    verifyTouchOwner();
                }
                try {
                    verifyTouchOwner();
                    touchHeld = true;
                    reorderTouch.press(0,touchInput,touchPosition.x,touchPosition.y).commit();
                    touchFrame();
                    touchPosition = touchSource.mapToItem(touchInput,touchSource.width/2+24,touchSource.height/2);
                    reorderTouch.move(0,touchInput,touchPosition.x,touchPosition.y).commit();
                    touchFrame();
                    driver.waitVerified(() => named(touchSource,"movaFavoriteDragProxy").Drag.active,
                        1500,"touch move activates the native favorite drag");
                    touchPosition = touchTarget.mapToItem(touchInput,touchTarget.width/2,touchTarget.height/2);
                    reorderTouch.move(0,touchInput,touchPosition.x,touchPosition.y).commit();
                    touchFrame();
                    driver.waitVerified(() => named(touchTarget,"movaFavoriteDrop").containsDrag,
                        1500,"touch move reaches the native favorite drop target");
                    driver.compare(JSON.stringify(l.favoriteSearchIds), pinOrder,"touch drag hover preserves order");
                    verifyTouchOwner();
                    reorderTouch.release(0,touchInput,touchPosition.x,touchPosition.y).commit();
                    touchHeld = false;
                    driver.waitVerified(() => l.favoriteSearchIds[0] === secondPin && l.favoriteSearchIds[1] === firstPin,
                        1500,"Qt touch drop reorders native favorites in edit mode");
                } finally {
                    if (touchHeld) {
                        // Cancel before release, using the original window's stable
                        // input item even if the surface has been reparented.
                        l.expanded = false;
                        try { reorderTouch.release(0,touchInput,touchPosition.x,touchPosition.y).commit(); }
                        catch (cleanupError) { console.error("MOOS_TOUCH_CLEANUP " + String(cleanupError)); }
                    }
                }
                l.moveFavorite(1,0);
                driver.waitVerified(() => JSON.stringify(l.favoriteSearchIds) === pinOrder,1500,"touch test restores native order");
                l.editMode = false;
                // Rapid page changes use one finite driver. Input remains
                // available throughout, hidden pages settle immediately, and
                // Reduced Motion never starts a translation.
                l.expanded = true;
                v.entranceReady = true;
                l.activePage = 2;
                check.wait(20);
                l.activePage = 1;
                check.wait(20);
                l.activePage = 3;
                check.wait(20);
                if (v.motionMedium === 0) {
                    driver.compare(driver.pages.pageAnimating, false, "reduced page motion is off");
                    driver.compare(driver.pages.pageTranslation, 0, "reduced page translation is zero");
                }
                check.wait(v.motionMedium + 80);
                driver.compare(driver.pages.pageAnimating, false, "page transition reaches rest");
                driver.compare(driver.pages.opacity, 1, "page returns to full ink");
                driver.compare(driver.pages.pageTranslation, 0, "page returns to its input geometry");
                l.activePage = 2;
                v.visible = false;
                check.wait(20);
                driver.compare(driver.pages.pageAnimating, false, "hidden page transition stops");
                driver.compare(driver.pages.pageTranslation, 0, "hidden page geometry settles");
                v.visible = true;
                driver.compare(JSON.stringify(v.searchModel.favoriteIds), JSON.stringify(driver.runnerFavorites),
                    "native pin actions preserve the provider preference");
                console.info("MOOS_ADAPTIVE_INPUT_PASS " + JSON.stringify({
                    width: v.width, height: v.height, rtl: v.rtl,
                    compact: v.compact, columns: driver.appGrid.columns, motion: v.motionMedium,
                    homeContent: driver.homeScroll.contentHeight,
                    homeViewport: driver.homeScroll.height,
                    touch: true, keyboard: true, sessionMenu: v.compact,
                    nativeCategories: l.appRootModel.count - 1, categoryBrowsing: true,
                    pageMotionSettled: true, nativeMenu: true, nativeFavoriteAction: true,
                    nativeFavoriteDrop: true, nativeTouchDrop: true, cancelledDropRefused: true,
                    nativeWindowReopen: true, touchFrameDelivery: true,
                    nativeFolderNavigation: true, applicationInkFits: true, requestedFont: v.uiFontFamily,
                    nativeProviderPreference: true, runnerFavorites: v.searchModel.favoriteIds,
                    nativeSearchRows: nativeSearchRows,
                    initialPalette: initialPalette,
                    palette: { owner: String(nativeTheme), background: String(nativeTheme.backgroundColor),
                               text: String(nativeTheme.textColor),
                               accent: String(nativeTheme.highlightColor) }
                }));
            } catch (error) {
                console.error("MOOS_ADAPTIVE_INPUT_FAIL " + String(error));
            }
        }
    }
}
