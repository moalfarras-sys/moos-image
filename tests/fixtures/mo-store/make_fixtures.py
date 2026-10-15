"""Write Mo Store's UI fixtures (tests/test_mo_store_ui_pages.py reads them). Deterministic:

    python3 -I tests/fixtures/mo-store/make_fixtures.py tests/fixtures/mo-store

Every kind (flatpak, webapp, appdrop, windows, android, npm, web, dropped, vendor), installed and
not, every compatibility reason key of docs/MO_STORE.md, updates (an app, a catalogue pin, a
runtime), a permissions document for every row shape and note key, facts, details with local
screenshots, jobs in each state and four machines. The names are invented (example.org); nothing
here names a real publisher. Paths to the fixture's own pictures are written as @FIXTURES@ and the
present moment as @NOW@; the test substitutes both in its private copy.
"""
import json
import re
import struct
import sys
import zlib
from pathlib import Path

OUT = Path(sys.argv[1])
F = "file://@FIXTURES@"
GEN = "2026-10-12T09:30:00Z"

# The index's own search fold (moos-store-index fold_search_text / search_string).
SEARCH_MARKS = re.compile("[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640"
                          "\u200b-\u200f\u202a-\u202e\u2066-\u2069\u061c\ufeff]")
SEARCH_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه",
                             **{chr(0x0660 + d): str(d) for d in range(10)},
                             **{chr(0x06F0 + d): str(d) for d in range(10)}})
SEARCH_SPACE = re.compile(r"[\s_.\-+/()|·]+")


def fold(value):
    text = SEARCH_MARKS.sub("", (value or "").lower()).translate(SEARCH_FOLD)
    return SEARCH_SPACE.sub(" ", text).strip()


def search_string(terms):
    seen = []
    for term in terms:
        folded = fold(term)
        if folded and folded not in seen:
            seen.append(folded)
    return " ".join(seen)


def id_tail(app_id):
    return app_id.rsplit(".", 1)[-1] if "." in app_id else app_id


def png(path: Path, width: int, height: int, stops, bands=()) -> None:
    """A small RGB PNG: a vertical gradient between colour stops, with horizontal bands."""
    rows = []
    for y in range(height):
        t = y / max(1, height - 1)
        seg = min(len(stops) - 2, int(t * (len(stops) - 1)))
        local = t * (len(stops) - 1) - seg
        a, b = stops[seg], stops[seg + 1]
        base = tuple(int(a[i] + (b[i] - a[i]) * local) for i in range(3))
        row = bytearray()
        for x in range(width):
            colour = base
            for (x0, y0, x1, y1, c) in bands:
                if x0 <= x / width <= x1 and y0 <= t <= y1:
                    colour = c
            row += bytes(colour)
        rows.append(b"\x00" + bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


def compat(verdict="ok", *reasons):
    return {"verdict": verdict, "reasons": list(reasons)}


def flatpak(app_id, name, summary, *, ar=None, cat="util", developer="", verified=True, installed=False,
            scopes=None, branding=None, rating="all", details=False, version="1.0", icon=None,
            listed=True, compat_=None, eol=False, installed_version=None):
    entry = {
        "id": app_id, "source": "flatpak", "kind": "flatpak", "origin": "flathub",
        "scope": "system" if scopes == ["system"] else "user", "installable": True, "listed": listed,
        "flatpak_ref": f"app/{app_id}/x86_64/stable", "arch": "x86_64", "branch": "stable",
        "name": ar or name, "name_en": name, "summary": summary, "description": summary + " " + summary,
        "developer": developer, "license": "GPL-3.0-or-later", "category": "utilities", "categories": [],
        "icon": icon, "screenshot": None, "verified": verified, "installed": installed,
        "version": version, "curated": False, "branding": branding, "content_rating": rating,
        "details": f"details/{app_id}.json" if details else None, "cat": cat,
        "update_available": False, "installed_version": installed_version, "eol": eol,
        "compat": compat_ or compat(),
    }
    if scopes:
        entry["installed_scopes"] = scopes
        entry["installed_scope"] = scopes[0]
    entry["search"] = search_string([ar or name, name, developer, id_tail(app_id)])
    return entry


def curated(app_id, kind, en, ar, desc_en, desc_ar, *, cat, install, developer="", installed=False,
            accent=None, compat_=None, listed=True, version="", installed_version=None, engine=None, source="moos"):
    entry = {
        "id": app_id, "source": source, "kind": kind, "origin": source, "scope": "user", "installable": True,
        "listed": listed, "flatpak_ref": None, "name": ar, "name_en": en, "en": en, "ar": ar,
        "summary": desc_ar, "description": desc_ar, "desc_en": desc_en, "desc_ar": desc_ar,
        "developer": developer, "license": "", "category": "other", "categories": [], "icon": None,
        "screenshot": None, "verified": False, "installed": installed, "version": version,
        "curated": source == "moos", "branding": None, "content_rating": None, "details": None, "cat": cat,
        "install": install, "update_available": False, "installed_version": installed_version, "eol": False,
        "compat": compat_ or compat(), "search": search_string([ar, en, developer, id_tail(app_id)]),
    }
    if accent:
        entry["accent"] = accent
    if engine:
        entry["engine"] = engine
    return entry


def build() -> None:
    (OUT / "details").mkdir(parents=True, exist_ok=True)
    (OUT / "media").mkdir(parents=True, exist_ok=True)
    (OUT / "permissions").mkdir(parents=True, exist_ok=True)

    png(OUT / "media/shot-1.png", 320, 180, [(36, 52, 88), (18, 24, 44)],
        [(0.06, 0.08, 0.3, 0.92, (60, 84, 140)), (0.34, 0.08, 0.94, 0.2, (232, 236, 248)), (0.34, 0.3, 0.8, 0.86, (90, 140, 220))])
    png(OUT / "media/shot-2.png", 320, 200, [(246, 240, 230), (226, 214, 196)],
        [(0.1, 0.1, 0.9, 0.18, (120, 92, 60)), (0.1, 0.28, 0.6, 0.9, (255, 255, 255)), (0.64, 0.28, 0.9, 0.9, (196, 120, 70))])
    png(OUT / "media/shot-3.png", 240, 180, [(20, 90, 70), (8, 40, 34)],
        [(0.12, 0.2, 0.88, 0.8, (60, 180, 140))])
    png(OUT / "media/icon-paint.png", 64, 64, [(250, 180, 60), (220, 90, 50)], [(0.25, 0.25, 0.75, 0.75, (255, 246, 230))])
    png(OUT / "media/icon-office.png", 64, 64, [(70, 160, 90), (30, 110, 60)], [(0.28, 0.2, 0.72, 0.8, (255, 255, 255))])

    apps = [
        flatpak("org.example.Paint", "Paint Studio", "Draw, paint and edit photos with layers", ar="استوديو الرسم",
                cat="art", developer="Example Arts", installed=True, scopes=["user"],
                branding={"light": "#f2c28a", "dark": "#7a3b12"}, details=True, version="4.2",
                installed_version="4.1", icon=f"{F}/media/icon-paint.png"),
        flatpak("org.example.Office", "Office Suite", "Documents, spreadsheets and slides", ar="حزمة المكتب",
                cat="work", developer="Example Foundation", branding={"light": "#9ad0a4", "dark": "#1b5e30"},
                details=True, version="26.8", icon=f"{F}/media/icon-office.png"),
        flatpak("org.example.Retro", "Retro Arcade", "Classic games from old consoles", cat="fun",
                developer="Retro Team", verified=False,
                compat_=compat("warn", "small_screen", "x11_only_scaled", "not_verified"), rating="teen"),
        flatpak("org.example.Old", "Old Viewer", "A viewer nobody updates any more", cat="util",
                developer="Gone Inc.", installed=True, scopes=["user"], listed=False, eol=True,
                compat_=compat("warn", "eol"), installed_version="0.9"),
        flatpak("org.example.Shared", "Shared Tool", "Installed for everyone on this computer", cat="util",
                developer="Admins", installed=True, scopes=["system"]),
        flatpak("org.example.ArmOnly", "Arm Only", "Built for another kind of computer", cat="dev",
                developer="Elsewhere", compat_=compat("blocked", "arch")),
        flatpak("org.example.Files", "Files Everywhere", "Reaches every file on the computer", cat="util",
                developer="Wide Access", compat_=compat("warn", "broad_permissions"), rating="mature"),
        flatpak("org.example.Big", "Big Game", "A huge open world", cat="fun", developer="Large Studio",
                branding={"light": "#b9c8ff", "dark": "#20306a"}, compat_=compat("warn", "low_disk", "low_memory")),
        flatpak("org.example.Kart", "Kart Racer", "Race with friends", ar="سباق الكارت", cat="fun",
                developer="Kart Team", branding={"light": "#ffd27a", "dark": "#6b3d00"}),
        flatpak("org.example.Chess", "Chess", "Play chess against the computer", ar="شطرنج", cat="fun",
                developer="Board Games"),
        flatpak("org.example.Browser", "Web Browser", "A fast, private web browser", ar="متصفح الويب", cat="ess",
                developer="Open Web", installed=True, scopes=["user"], branding={"light": "#a8c8ff", "dark": "#123a7a"}),
        flatpak("org.example.Mail", "Mail", "Email for every account", ar="البريد", cat="comm", developer="Mail Co."),
        flatpak("org.example.Music", "Music Player", "Your music, beautifully", ar="مشغل الموسيقى", cat="media",
                developer="Sound Lab", installed=True, scopes=["user"]),
        flatpak("org.example.Code", "Code Editor", "Write code with a smart editor", ar="محرر الشيفرة", cat="dev",
                developer="Example Foundation"),
        flatpak("org.example.Learn", "Flashcards", "Remember anything with spaced repetition", ar="بطاقات المراجعة",
                cat="edu", developer="Learning Lab"),
        curated("chat-web", "webapp", "Chat Assistant", "مساعد المحادثة", "An assistant in a window of its own.",
                "مساعد في نافذته الخاصة.", cat="ai", developer="Assist Labs", installed=True, accent="#c15f3c",
                install={"kind": "webapp", "url": "https://chat.example.org/", "hosts": ["chat.example.org"],
                         "identity": ["google", "microsoft"], "permissions": ["notifications", "microphone", "camera"],
                         "accent": "#c15f3c", "risk": "web-app", "requires_review": True},
                compat_=compat("warn", "needs_internet")),
        curated("mail-web", "webapp", "Web Mail", "البريد على الويب", "Your mail on the web, in its own window.",
                "بريدك على الويب في نافذته الخاصة.", cat="comm", developer="Mail Co.", accent="#0f6cbd",
                install={"kind": "webapp", "url": "https://mail.example.org/", "hosts": ["mail.example.org"],
                         "identity": ["microsoft"], "permissions": ["notifications", "clipboard"], "accent": "#0f6cbd",
                         "risk": "web-app", "requires_review": True},
                compat_=compat("warn", "needs_internet")),
        curated("vendor-site", "web", "Studio Download", "تنزيل الاستوديو", "Opens the publisher's download page.",
                "يفتح صفحة التنزيل لدى الناشر.", cat="dev", developer="Studio Inc.",
                install={"kind": "web", "url": "https://studio.example.org/download", "risk": "external-download",
                         "requires_review": True, "external": True}),
        curated("photo-tool", "appdrop", "Photo Tool", "أداة الصور", "Edit photos and layered files.",
                "حرّر الصور والملفات ذات الطبقات.", cat="art", developer="Photo Project", installed=True,
                accent="#5b3fd9", version="2.4.0", installed_version="2.3.1",
                install={"kind": "appdrop", "artifact": "appimage", "version": "2.4.0",
                         "downloads": {"x86_64": {"url": "https://example.org/photo.AppImage", "sha256": "0" * 64,
                                                  "size": 98000000}},
                         "risk": "downloaded-executable", "requires_review": True, "external": True}),
        curated("editor-x", "appdrop", "Editor X", "المحرر إكس", "A code editor from its publisher.",
                "محرر شيفرة من ناشره.", cat="dev", developer="X Corp", accent="#2b4acb",
                install={"kind": "appdrop", "artifact": "archive", "version": "1.9",
                         "downloads": {"x86_64": {"url": "https://example.org/x.tar.gz", "sha256": "1" * 64,
                                                  "size": 240000000}},
                         "risk": "downloaded-executable", "requires_review": True, "external": True}),
        curated("notes-win", "windows", "Notes Plus", "نوتس بلس", "A fast text editor for Windows.",
                "محرر نصوص سريع لويندوز.", cat="win", developer="Notes Dev", installed=True, engine="windows",
                version="8.9", install={"kind": "windows-portable", "version": "8.9", "exe": "notes.exe",
                                         "downloads": {"x86_64": {"url": "https://example.org/notes.zip",
                                                                  "sha256": "2" * 64, "size": 8300000}},
                                         "risk": "downloaded-executable", "requires_review": True, "external": True}),
        curated("tool-win", "windows", "Disk Tool", "أداة الأقراص", "Inspect disks and files.",
                "افحص الأقراص والملفات.", cat="win", developer="Disk Dev", engine="windows",
                install={"kind": "windows-portable", "version": "3.1", "exe": "disk.exe",
                         "downloads": {"x86_64": {"url": "https://example.org/disk.zip", "sha256": "3" * 64,
                                                  "size": 4100000}},
                         "risk": "downloaded-executable", "requires_review": True, "external": True},
                compat_=compat("blocked", "engine_missing")),
        curated("org.example.reader", "android", "Reader", "القارئ", "Read books and articles offline.",
                "اقرأ الكتب والمقالات دون إنترنت.", cat="droid", developer="Reader Team", installed=True,
                engine="android", install={"kind": "android", "url": "https://example.org/reader.apk",
                                           "package": "org.example.reader", "sha256": "4" * 64,
                                           "risk": "external-download", "requires_review": True, "external": True},
                compat_=compat("warn", "android_software_graphics")),
        curated("org.example.podcasts", "android", "Podcasts", "البودكاست", "Subscribe and listen offline.",
                "اشترك واستمع دون إنترنت.", cat="droid", developer="Pod Team", engine="android",
                install={"kind": "android", "url": "https://example.org/pod.apk", "package": "org.example.podcasts",
                         "sha256": "5" * 64, "risk": "external-download", "requires_review": True, "external": True},
                compat_=compat("warn", "android_setup")),
        curated("cli-agent", "npm", "Code Agent", "وكيل البرمجة", "A coding agent in the terminal.",
                "وكيل برمجة في الطرفية.", cat="ai", developer="Agents Inc.", installed=True,
                install={"kind": "npm", "pkg": "@example/agent", "bin": "agent", "risk": "runs-package-scripts",
                         "requires_review": True}),
        curated("cli-two", "npm", "Shell Helper", "مساعد الطرفية", "Explain any command.",
                "اشرح أي أمر.", cat="dev", developer="Shell Co.",
                install={"kind": "npm", "pkg": "@example/helper", "bin": "helper", "risk": "runs-package-scripts",
                         "requires_review": True}),
        curated("desktop-vendor", "vendor", "Desktop Assistant", "المساعد المكتبي",
                "The publisher's own desktop app, signed by them.", "تطبيق الناشر نفسه لسطح المكتب، موقّع منه.",
                cat="ai", developer="Vendor Labs", accent="#0b6e55",
                install={"kind": "vendor-rpm", "repo": "https://packages.example.org/rpm/$basearch",
                         "package": "desktop-assistant", "key_fingerprint": "0" * 40,
                         "install_root": "opt/DesktopAssistant", "exec": "opt/DesktopAssistant/assistant",
                         "desktop": "desktop-assistant.desktop", "wm_class": "DesktopAssistant",
                         "risk": "downloaded-executable", "requires_review": True, "external": True},
                compat_=compat("warn", "vendor_download")),
    ]
    dropped = {
        "id": "my-tool", "slug": "my-tool", "source": "local", "kind": "dropped", "origin": "local", "scope": "user",
        "installable": False, "listed": False, "flatpak_ref": None, "name": "My Tool", "name_en": "My Tool",
        "summary": "Added from a file", "description": "Added from a file", "developer": "", "license": "",
        "category": "utilities", "categories": [], "icon": None, "screenshot": None, "verified": False,
        "installed": True, "version": "", "curated": False, "branding": None, "content_rating": None,
        "details": None, "catalog_id": None, "installed_version": None, "update_available": False, "eol": False,
        "cat": "util", "search": search_string(["My Tool", "my-tool"]), "compat": compat(),
    }
    apps.append(dropped)

    categories = [
        {"id": "ess", "en": "Essentials", "ar": "الأساسيات", "glyph": "compass"},
        {"id": "comm", "en": "Communication", "ar": "التواصل", "glyph": "chat"},
        {"id": "work", "en": "Office & study", "ar": "المكتب والدراسة", "glyph": "briefcase"},
        {"id": "art", "en": "Graphics & photo", "ar": "التصميم والصور", "glyph": "pen"},
        {"id": "media", "en": "Watch & listen", "ar": "شاهد واستمع", "glyph": "play"},
        {"id": "fun", "en": "Games", "ar": "الألعاب", "glyph": "gaming"},
        {"id": "dev", "en": "Development", "ar": "البرمجة", "glyph": "code"},
        {"id": "ai", "en": "AI", "ar": "الذكاء الاصطناعي", "glyph": "ai"},
        {"id": "edu", "en": "Education", "ar": "التعليم", "glyph": "bulb"},
        {"id": "util", "en": "Utilities & security", "ar": "الأدوات والأمان", "glyph": "shield"},
        {"id": "droid", "en": "Android apps", "ar": "تطبيقات أندرويد", "glyph": "android-apps"},
        {"id": "win", "en": "Windows programs", "ar": "برامج ويندوز", "glyph": "grid"},
    ]
    collections = [
        {"id": "new-pc", "en": "Essentials for a new PC", "ar": "أساسيات لكل جهاز جديد", "glyph": "star",
         "desc_en": "The apps most people install first.", "desc_ar": "التطبيقات التي يثبّتها معظم الناس أولًا.",
         "apps": ["org.example.Browser", "org.example.Office", "org.example.Mail", "org.example.Music", "chat-web"]},
        {"id": "create", "en": "Create and design", "ar": "صمّم وأبدع", "glyph": "pen",
         "desc_en": "Edit photos, draw and design.", "desc_ar": "حرّر الصور وارسم وصمّم.",
         "apps": ["org.example.Paint", "photo-tool", "org.example.Files", "editor-x"]},
        {"id": "play", "en": "Play", "ar": "العب", "glyph": "gaming", "desc_en": "Games for everyone.",
         "desc_ar": "ألعاب للجميع.", "apps": ["org.example.Kart", "org.example.Chess", "org.example.Big", "org.example.Retro"]},
        {"id": "windows-programs", "en": "Windows programs that run here", "ar": "برامج ويندوز تعمل هنا",
         "glyph": "grid", "desc_en": "Well-known Windows tools.", "desc_ar": "أدوات ويندوز معروفة.",
         "apps": ["notes-win", "tool-win", "editor-x"]},
    ]
    featured = [
        {"app": "photo-tool", "title_en": "Photo Tool", "title_ar": "أداة الصور",
         "tagline_en": "Edit photos and layered files, free and fast.", "tagline_ar": "حرّر الصور والملفات ذات الطبقات، مجانًا وبسرعة.",
         "accent": "#4f35c2"},
        {"app": "chat-web", "title_en": "Chat Assistant", "title_ar": "مساعد المحادثة",
         "tagline_en": "Think, write and analyse in a window of its own.", "tagline_ar": "فكّر واكتب وحلّل في نافذة خاصة.",
         "accent": "#a8502f"},
        {"app": "org.example.Office", "title_en": "Office Suite", "title_ar": "حزمة المكتب",
         "tagline_en": "Documents with full Arabic support.", "tagline_ar": "مستندات بدعم كامل للعربية.", "accent": "#1b6e2e"},
        {"app": "org.example.ArmOnly", "title_en": "Never shown", "title_ar": "لا يظهر", "tagline_en": "", "tagline_ar": ""},
    ]
    bundles = [
        {"id": "office-starter", "en": "Office Starter", "ar": "حزمة المكتب", "glyph": "briefcase",
         "desc_en": "Documents, email and meetings.", "desc_ar": "مستندات وبريد واجتماعات.",
         "apps": ["org.example.Office", "org.example.Mail", "mail-web"]},
        {"id": "game-starter", "en": "Gaming Starter", "ar": "حزمة الألعاب", "glyph": "gamepad",
         "desc_en": "Play from one place.", "desc_ar": "العب من مكان واحد.",
         "apps": ["org.example.Kart", "org.example.Chess", "org.example.Big"]},
    ]
    index = {
        "schema_version": 1, "generation": {"id": "fixture-1", "generated_at": GEN},
        "sources": [{"kind": "flatpak-appstream", "path": "/var/lib/flatpak/appstream/flathub/x86_64/active"}],
        "stats": {"total_apps": len(apps), "appstream_components": 15, "verified_apps": 11},
        "engines": ["android", "linux", "windows"], "categories": categories, "bundles": bundles,
        "collections": collections, "featured": featured, "apps": apps,
    }
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    office = {"schema": 1, "id": "org.example.Office",
              "screenshots": [
                  {"thumb": f"{F}/media/shot-1.png", "full": f"{F}/media/shot-1.png", "caption": "Writer with a long document",
                   "width": 1280, "height": 720},
                  {"thumb": f"{F}/media/shot-2.png", "full": f"{F}/media/shot-2.png", "caption": "Spreadsheets", "width": 1280,
                   "height": 800},
                  {"thumb": f"{F}/media/shot-3.png", "full": f"{F}/media/shot-3.png", "width": 960, "height": 720}],
              "releases": [{"version": "26.8", "date": "2026-09-24", "notes": "Faster start.\n\n• Better Arabic shaping in tables\n• New templates"},
                           {"version": "26.2", "date": "2026-03-02", "notes": ""},
                           {"version": "25.8", "date": "2025-08-20", "notes": ""}],
              "urls": {"homepage": "https://office.example.org/", "help": "http://office.example.org/help",
                       "donation": "https://office.example.org/donate", "bugtracker": "https://bugs.example.org/"},
              "keywords": ["office", "مكتب"], "languages": {"ar": 92}, "requires": {"controls": []},
              "verification": {"method": "website", "website": "example.org"}, "license": "MPL-2.0",
              "developer": "Example Foundation"}
    paint = {"schema": 1, "id": "org.example.Paint",
             "screenshots": [{"thumb": f"{F}/media/shot-2.png", "full": f"{F}/media/shot-2.png",
                              "caption": "Layers and brushes", "width": 1280, "height": 800}],
             "releases": [{"version": "4.2", "date": "2026-10-01", "notes": ""}],
             "urls": {"homepage": "https://paint.example.org/"}, "keywords": [], "languages": {"ar": 30},
             "requires": {"controls": []}, "verification": {}, "license": "LicenseRef-proprietary",
             "developer": "Example Arts"}
    for doc in (office, paint):
        (OUT / "details" / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    machines = {
        "machine-station.json": {"arch": "x86_64", "engines": ["android", "linux", "windows"], "memory_bytes": 16576327680,
                                 "swap_bytes": 8589930496, "cpu_cores": 16,
                                 "gpu": {"vendor": "nvidia", "name": "Example GPU", "discrete": True}, "session": "wayland",
                                 "free_bytes": {"apps": 145545641984},
                                 "android": {"ready": True, "initialized": True, "graphics": "software"},
                                 "windows": {"ready": True, "x86_32": False},
                                 "screen": {"width": 3840, "height": 2160, "scale": 2.5}},
        "machine-fresh.json": {"arch": "x86_64", "engines": ["android", "linux", "windows"], "memory_bytes": 4000000000,
                               "swap_bytes": 0, "cpu_cores": 4, "gpu": {"vendor": "intel", "name": None, "discrete": False},
                               "session": "wayland", "free_bytes": {"apps": 6000000000},
                               "android": {"ready": False, "initialized": False, "graphics": "hardware"},
                               "windows": {"ready": False, "x86_32": False},
                               "screen": {"width": 1366, "height": 768, "scale": 1}},
        "machine-arm.json": {"arch": "aarch64", "engines": ["linux"], "memory_bytes": 25000000000, "swap_bytes": 0,
                             "cpu_cores": 4, "gpu": {"vendor": None, "name": None, "discrete": False}, "session": "wayland",
                             "free_bytes": {"apps": 40000000000}, "android": None, "windows": None, "screen": None},
        "machine-old.json": {"arch": "x86_64", "engines": ["android", "linux", "windows"]},
    }
    for name, doc in machines.items():
        (OUT / name).write_text(json.dumps(doc, indent=1), encoding="utf-8")

    updates_known = {"schema": 1, "action": "check-updates", "state": "success", "checked_at": "@NOW@",
                     "count": 3, "app_count": 2, "auto_updates": True, "message": "",
                     "items": [{"id": "org.example.Paint", "ref": "app/org.example.Paint/x86_64/stable", "kind": "app",
                                "name": "Paint Studio", "version": "4.1", "origin": "flathub"},
                               {"id": "photo-tool", "kind": "pin", "name": "Photo Tool", "version": "2.4.0",
                                "installed_version": "2.3.1"},
                               {"id": "org.freedesktop.Platform", "ref": "runtime/org.freedesktop.Platform/x86_64/25.08",
                                "kind": "runtime", "name": "Platform", "version": "25.08.3"}]}
    updates_none = {"schema": 1, "action": "check-updates", "state": "success", "checked_at": "@NOW@", "count": 0,
                    "app_count": 0, "auto_updates": False, "message": "Apps are up to date", "items": []}
    updates_failed = {"schema": 1, "action": "check-updates", "state": "failed", "checked_at": "@NOW@", "count": 0,
                      "app_count": 0, "message": "Could not resolve updates", "items": []}
    for name, doc in (("updates-known.json", updates_known), ("updates-none.json", updates_none),
                      ("updates-failed.json", updates_failed)):
        (OUT / name).write_text(json.dumps(doc, indent=1), encoding="utf-8")

    facts = {"schema": 1, "generated_at": GEN, "state": "success", "apps": {
        "org.example.Paint": {"download": 128000000, "installed": 402000000, "eol": None, "eol_rebase": None,
                              "permissions": ["network", "files-home", "sound"], "x11_only": False, "extra_data": False},
        "org.example.Office": {"download": 288000000, "installed": 812000000, "eol": None, "eol_rebase": None,
                               "permissions": ["network", "downloads", "sound"], "x11_only": False, "extra_data": False},
        "org.example.Files": {"download": 12000000, "installed": 40000000, "eol": None, "eol_rebase": None,
                              "permissions": ["files-all", "host-commands", "devices"], "x11_only": True, "extra_data": False},
        "org.example.Big": {"download": 18000000000, "installed": 42000000000, "eol": None, "eol_rebase": None,
                            "permissions": ["network", "sound", "devices"], "x11_only": False, "extra_data": True},
    }}
    (OUT / "facts.json").write_text(json.dumps(facts, indent=1), encoding="utf-8")
    (OUT / "settings.json").write_text(json.dumps({"schema": 1, "auto_updates": True}), encoding="utf-8")
    (OUT / "settings-off.json").write_text(json.dumps({"schema": 1, "auto_updates": False}), encoding="utf-8")

    permissions = {
        "org.example.Paint": {"schema": 1, "id": "org.example.Paint", "kind": "flatpak", "generated_at": "@NOW@",
                              "sandboxed": True, "installed": True,
                              "rows": [{"key": "network", "state": "allow", "changeable": True},
                                       {"key": "files-home", "state": "allow", "changeable": True},
                                       {"key": "files-all", "state": "deny", "changeable": True},
                                       {"key": "downloads", "state": "allow", "changeable": False},
                                       {"key": "devices", "state": "deny", "changeable": True},
                                       {"key": "sound", "state": "allow", "changeable": True},
                                       {"key": "bluetooth", "state": "deny", "changeable": True},
                                       {"key": "background", "state": "allow", "changeable": True}]},
        "chat-web": {"schema": 1, "id": "chat-web", "kind": "webapp", "generated_at": "@NOW@", "sandboxed": True,
                     "installed": True,
                     "rows": [{"key": "notifications", "state": "allow", "changeable": True, "ask": False},
                              {"key": "microphone", "state": "deny", "changeable": True, "ask": True},
                              {"key": "camera", "state": "deny", "changeable": True, "ask": False}]},
        "notes-win": {"schema": 1, "id": "notes-win", "kind": "unsandboxed", "generated_at": "@NOW@",
                      "sandboxed": False, "rows": [], "note_key": "full_access"},
        "org.example.reader": {"schema": 1, "id": "org.example.reader", "kind": "android", "generated_at": "@NOW@",
                               "sandboxed": True, "rows": [], "note_key": "android_managed"},
        "org.example.Music": {"schema": 1, "id": "org.example.Music", "kind": "flatpak", "generated_at": "@NOW@",
                              "sandboxed": True, "installed": False, "rows": [], "note_key": "not_installed"},
    }
    for app_id, doc in permissions.items():
        (OUT / "permissions" / f"{app_id}.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")

    jobs = {
        "job-running.json": {"schema": 1, "job_id": "fixture-running", "action": "install", "state": "running",
                             "progress": 42, "current_id": "org.example.Office", "message": "Downloading",
                             "message_key": "downloading_file", "started_at": "@NOW@", "updated_at": "@NOW@",
                             "items": [{"id": "org.example.Office", "state": "running", "progress": 42}]},
        "job-indeterminate.json": {"schema": 1, "job_id": "fixture-indeterminate", "action": "install", "state": "running",
                                   "progress": None, "current_id": "chat-web", "message": "Preparing",
                                   "message_key": "integrating_app", "started_at": "@NOW@", "updated_at": "@NOW@",
                                   "items": [{"id": "chat-web", "state": "running", "progress": None},
                                             {"id": "org.example.Mail", "state": "queued", "progress": None}]},
        "job-failed.json": {"schema": 1, "job_id": "fixture-failed", "action": "install", "state": "failed",
                            "progress": None, "current_id": None, "message": "The download did not match its fingerprint",
                            "message_key": None, "started_at": "@NOW@", "updated_at": "@NOW@",
                            "items": [{"id": "editor-x", "state": "failed", "progress": None}]},
        "job-success.json": {"schema": 1, "job_id": "fixture-success", "action": "install", "state": "success",
                             "progress": 100, "current_id": None, "message": "Installed", "message_key": "all_ready",
                             "started_at": "@NOW@", "updated_at": "@NOW@",
                             "items": [{"id": "org.example.Office", "state": "done", "progress": 100,
                                        "message_key": "installed"}]},
    }
    for name, doc in jobs.items():
        (OUT / name).write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print("fixtures in", OUT)


build()
