"""
Mira Neural OS — High-Fidelity Futuristic Assistant Application
Pixel-perfect implementation of the reference design for MoOS.
"""
import sys
import os
import json
import math
import html
import threading
import queue
import subprocess
import time
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

from PySide6.QtCore import (
    Qt, QObject, Signal, QTimer, QSize, QVariantAnimation,
    QSettings, QPointF, QRectF
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QPlainTextEdit, QComboBox, QBoxLayout,
    QSlider, QCheckBox, QScrollArea, QSplitter, QTabWidget, QGridLayout,
    QListWidget, QListWidgetItem, QFileDialog, QMenu, QFrame, QButtonGroup
)
from PySide6.QtGui import (
    QPainter, QPixmap, QIcon, QFont, QColor, QPen,
    QRadialGradient, QLinearGradient
)

ROOT = Path(__file__).parent
IP = os.environ.get('MIRA_ECHO_HOST', '192.168.3.83')
KEY = Path.home() / '.config/mo-dot/device.key'

# ─── Custom Futuristic Modules ──────────────────────────────────────
from theme import build_stylesheet, MiraColors, MiraFonts
from orb_widget import Orb, NeuralCanvas, DockWave, Gauge
from widgets import (
    GlassCard, WeatherClockCard, DeviceItemCard, QuickPill,
    FloatingTag, CenterVoiceBar, DockTabButton, ChatTVCard, ChatWeatherCard
)


# ─── Embedded Tone & Model Server ───────────────────────────────────
class ToneServer(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.client_address[0] != IP:
            self.send_error(403); return
        if self.path == '/tone.wav':
            import wave, struct
            buf = struct.pack('<' + 'h' * 48000, *[int(16000 * math.sin(2 * math.pi * 440 * i / 48000)) for i in range(48000)])
            self.send_response(200); self.send_header('Content-Type', 'audio/wav'); self.end_headers()
            w = wave.open(self.wfile, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(buf); w.close()
        elif self.path in ('/hey_mira.json', '/hey_mira.tflite'):
            data = (ROOT / self.path.lstrip('/')).read_bytes()
            self.send_response(200); self.send_header('Content-Type', 'application/octet-stream'); self.end_headers(); self.wfile.write(data)
        else:
            self.send_error(404)


# The tested encrypted Echo transport is shared with this visual shell.
from mira_bridge import Bridge


# ─── Worker Bridges ─────────────────────────────────────────────────
class ChatBridge(QObject):
    reply = Signal(str)
    error = Signal(str)

    def ask(self, text, provider='Mo AI'):
        def work():
            try:
                if provider == 'Mo AI':
                    from moai_link import ask
                    answer = ask(text)
                else:
                    from inference import ask
                    answer, _ = ask(text)
                self.reply.emit(answer)
            except Exception as e:
                self.error.emit(str(e) if isinstance(e, (ValueError, RuntimeError)) else 'تعذّر الاتصال بالوكيل: ' + type(e).__name__)
        threading.Thread(target=work, daemon=True).start()


class PcBridge(QObject):
    result = Signal(object)

    def run(self, name, args):
        def worker():
            try:
                from moai_link import execute
                result=execute(name, args)
                if name in ('set_volume','set_brightness') and result.get('status')=='ok':
                    observed=execute('get_system_status',{})
                    key='volume' if name=='set_volume' else 'brightness'
                    try:
                        value=json.loads(observed.get('output') or '{}')[key]
                        if observed.get('status')!='ok' or round(float(value))!=int(args['value']):
                            result={'status':'pending','error':'أُرسل الأمر، لكن قراءة الكمبيوتر لا تؤكد القيمة المطلوبة'}
                        else:
                            result={'status':'ok','output':f'{key}: {round(float(value))}%', 'verified_value':value}
                    except (ValueError,TypeError,KeyError,OverflowError):
                        result={'status':'pending','error':'أُرسل الأمر، لكن تعذّرت قراءة القيمة الجديدة'}
                self.result.emit({'tool':name,**result})
            except Exception:
                self.result.emit({'tool':name,'status': 'error'})
        threading.Thread(target=worker, daemon=True).start()


class CommandBridge(QObject):
    result = Signal(object)

    def run(self, text):
        def worker():
            try:
                from command_router import dispatch
                self.result.emit({'dispatch': dispatch(text), 'text': text})
            except Exception as e:
                self.result.emit({'error': str(e) if isinstance(e, (ValueError, RuntimeError)) else 'تعذّر تنفيذ الأمر', 'text': text})
        threading.Thread(target=worker, daemon=True).start()


class HomeBridge(QObject):
    result = Signal(object)

    def __init__(self):
        super().__init__()
        self.jobs=queue.Queue()
        threading.Thread(target=self._worker,daemon=True).start()

    def run(self, action='refresh', entity_id=None, value=None, color=None):
        self.jobs.put((action,entity_id,value,color))

    def _worker(self):
        while True:
            action,entity_id,value,color=self.jobs.get()
            try:
                from home_link import entities, control, control_all_lights
                if action == 'refresh':
                    payload = {'kind':'devices', 'devices':entities()}
                elif action in ('all_on','all_off'):
                    outcome = control_all_lights('turn_on' if action=='all_on' else 'turn_off')
                    payload = {'kind':'action','outcome':outcome}
                else:
                    outcome = control(entity_id, action, value=value, color=color)
                    payload = {'kind':'action','outcome':outcome}
                self.result.emit(payload)
            except Exception as exc:
                self.result.emit({'kind':'error','error':str(exc) if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__})
            finally:
                self.jobs.task_done()


# ─── Main Window ────────────────────────────────────────────────────
class Window(QMainWindow):
    weather_updated = Signal(float, str, str, str, str)
    weather_failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Mira Neural OS · ميرا')
        self.resize(1440, 900)
        self.setMinimumSize(480, 680)
        self.setWindowIcon(QIcon(str(ROOT / 'mira-icon-v2.png')))

        # Settings
        self.settings = QSettings('MoOS', 'Mira')
        self.lang = self.settings.value('language', 'ar')
        self.lang = self.lang if self.lang in ('ar','en') else 'ar'
        self.setLayoutDirection(Qt.RightToLeft if self.lang=='ar' else Qt.LeftToRight)
        self.face_style = self.settings.value('face_style', 'rose')
        self.voice_name = self.settings.value('voice_name', 'Aoede')
        self.local_wake_enabled = self.settings.value('local_wake_enabled', True, type=bool)
        self.local_wake_process = None
        if self.face_style not in ('rose', 'holo'): self.face_style = 'rose'
        if self.voice_name not in ('Aoede', 'Kore', 'Leda'): self.voice_name = 'Aoede'

        # Backend
        self.bridge = Bridge(self.voice_name)
        self.bykey = {}
        self.controls = {}
        self.states = {}
        self.voice_phase = 'off'
        self.wake_request_seq = 0
        self.chat_bridge = ChatBridge()
        self.command_bridge = CommandBridge()
        self.command_bridge.result.connect(self.dock_result)

        self._build_ui()
        self._restore_chat()
        self._connect_signals()
        self.apply_responsive_layout()
        self.bridge.start()

        self.weather_updated.connect(self._on_weather_updated)
        self.weather_failed.connect(self._on_weather_failed)
        QTimer.singleShot(1000, self.update_weather_async)
        self.weather_timer = QTimer(self)
        self.weather_timer.setInterval(300000)
        self.weather_timer.timeout.connect(self.update_weather_async)
        self.weather_timer.start()

    def _build_ui(self):
        root = QWidget()
        root.setObjectName('shell')
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(10)

        # 1. Top Bar
        self._build_top_bar(outer)

        # Mira, Home, Conversation, Computer and Device are real workspaces.
        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()
        outer.addWidget(self.tabs, 1)

        self._build_main_cockpit()
        self._build_devices_page()
        self._build_conversation_page()
        self._build_computer_page()
        self._build_settings_page()

        # 3. Bottom Dock
        self._build_bottom_dock(outer)

    def _build_top_bar(self, parent_layout):
        bar = QFrame()
        bar.setObjectName('miraTopBar')
        bar.setLayoutDirection(Qt.LeftToRight)
        bar.setFixedHeight(56)
        bar.setStyleSheet("""
            QFrame#miraTopBar {
                background: rgba(11, 16, 38, 0.85);
                border: 1px solid rgba(66, 120, 240, 0.22);
                border-radius: 18px;
            }
        """)
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(16, 4, 16, 4)
        hl.setSpacing(12)

        # Left: Brand Logo & Title
        brand_box = QHBoxLayout()
        brand_box.setSpacing(10)
        self.brand_icon = QLabel()
        self.brand_icon.setPixmap(QPixmap(str(ROOT / 'mira-icon-v2.png')).scaled(34,34,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        brand_box.addWidget(self.brand_icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_lbl = QLabel("M I R A")
        title_lbl.setFont(QFont("Noto Sans Arabic", 13, QFont.Bold))
        title_lbl.setStyleSheet("color:#FFF; letter-spacing: 2px;")
        sub_lbl = QLabel("Neural OS")
        sub_lbl.setFont(QFont("Noto Sans Arabic", 8))
        sub_lbl.setStyleSheet("color:#A855F7; letter-spacing: 1px;")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        brand_box.addLayout(title_col)
        hl.addLayout(brand_box)

        hl.addStretch(1)

        # Center: Navigation Route Pills
        self.nav_group = QButtonGroup(self)
        nav_routes = [
            ("🏠 الرئيسية", 0),
            ("📱 الأجهزة", 1),
            ("💬 المحادثة", 2),
            ("▣ الكمبيوتر", 3),
            ("⚙ الإعدادات", 4)
        ]
        self.top_nav_buttons=[]
        for label, idx in nav_routes:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #8E9BB5;
                    border: 1px solid transparent;
                    border-radius: 12px;
                    padding: 0 16px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    color: #FFF;
                    background: rgba(0, 229, 255, 0.08);
                }
                QPushButton:checked {
                    color: #FFF;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #00E5FF);
                    border: 1px solid rgba(0, 229, 255, 0.6);
                    font-weight: bold;
                }
            """)
            btn.clicked.connect(lambda checked=False, i=idx: self.tabs.setCurrentIndex(i))
            self.nav_group.addButton(btn)
            self.top_nav_buttons.append((idx,btn))
            hl.addWidget(btn)
            if idx == 0 and label.startswith("🏠"):
                btn.setChecked(True)

        hl.addStretch(1)

        # Right: Tools & Profile
        right_box = QHBoxLayout()
        right_box.setSpacing(10)

        search_btn = QPushButton("🔍")
        search_btn.setFixedSize(36, 36)
        search_btn.setStyleSheet("""
            QPushButton {
                background: rgba(20, 28, 60, 0.7);
                color: #8E9BB5;
                border: 1px solid rgba(66, 120, 240, 0.3);
                border-radius: 18px;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #00E5FF;
                background: rgba(0, 229, 255, 0.15);
                border-color: rgba(0, 229, 255, 0.6);
            }
        """)
        search_btn.setToolTip('اكتب سؤالاً أو أمراً لميرا')
        search_btn.clicked.connect(lambda: self.chat_input.setFocus())
        right_box.addWidget(search_btn)

        theme_btn = QPushButton("🎭")
        theme_btn.setFixedSize(36, 36)
        theme_btn.setStyleSheet("""
            QPushButton {
                background: rgba(20, 28, 60, 0.7);
                color: #8E9BB5;
                border: 1px solid rgba(66, 120, 240, 0.3);
                border-radius: 18px;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #FFB800;
                background: rgba(255, 184, 0, 0.15);
                border-color: rgba(255, 184, 0, 0.5);
            }
        """)
        theme_btn.setToolTip('اختيار وجه ميرا من الإعدادات')
        theme_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(4))
        right_box.addWidget(theme_btn)

        lang_btn = QPushButton("🌐 العربية ▾")
        lang_btn.setFixedHeight(36)
        lang_btn.setStyleSheet("background:rgba(20,28,60,0.6); color:#C5D2E8; border:1px solid rgba(66,120,240,0.25); border-radius:12px; padding:0 10px; font-size:11px;")
        lang_btn.setToolTip('إعدادات اللغة والوجه والصوت')
        lang_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(4))
        right_box.addWidget(lang_btn)

        self.mobile_menu_button = QPushButton('القائمة ▾')
        self.mobile_menu_button.setToolTip('مساحات ميرا')
        self.mobile_menu_button.setFixedSize(68, 36)
        menu = QMenu(self.mobile_menu_button)
        for title, index in [('ميرا', 0), ('البيت', 1), ('المحادثة', 2),
                             ('الكمبيوتر', 3), ('الإعدادات', 4)]:
            action = menu.addAction(title)
            action.triggered.connect(lambda checked=False, i=index: self.tabs.setCurrentIndex(i))
        self.mobile_menu_button.setMenu(menu)
        right_box.addWidget(self.mobile_menu_button)

        # User profile chip
        chip = QFrame()
        self.profile_chip=chip
        chip.setFixedHeight(38)
        chip.setStyleSheet("background:rgba(18,26,58,0.9); border:1px solid rgba(0,229,255,0.3); border-radius:19px; padding:2px 10px;")
        chip_l = QHBoxLayout(chip)
        chip_l.setContentsMargins(6, 2, 8, 2)
        chip_l.setSpacing(8)
        mira_mini = QLabel()
        mira_mini.setPixmap(QPixmap(str(ROOT / 'mira-icon-v2.png')).scaled(25,25,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        chip_l.addWidget(mira_mini)
        name_l = QLabel("Mira AI")
        name_l.setFont(QFont("Noto Sans Arabic", 10, QFont.Bold))
        name_l.setStyleSheet("color:#FFF;")
        chip_l.addWidget(name_l)
        dot_l = QLabel("○ جارٍ الاتصال")
        self.connection_dot = dot_l
        dot_l.setFont(QFont("Noto Sans Arabic", 9))
        dot_l.setStyleSheet("color:#00FF88;")
        chip_l.addWidget(dot_l)
        right_box.addWidget(chip)

        hl.addLayout(right_box)
        parent_layout.addWidget(bar)

    # ─── Main Neural Cockpit (3 Columns) ────────────────────────────
    def _build_main_cockpit(self):
        canvas = NeuralCanvas()
        canvas.setLayoutDirection(Qt.LeftToRight)
        cl = QBoxLayout(QBoxLayout.LeftToRight,canvas)
        self.stage_layout=cl
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(14)

        # ─── Column 1: Left Context Panel (Width 300px) ─────
        left_panel = GlassCard(radius=20)
        self.context_panel = left_panel
        left_panel.setFixedWidth(290)
        ll = QVBoxLayout(left_panel)
        ll.setContentsMargins(14, 14, 14, 14)
        ll.setSpacing(10)

        # Weather & Live Clock Card
        self.weather_clock = WeatherClockCard()
        ll.addWidget(self.weather_clock)

        live_heading = QLabel('الأجهزة المتصلة الآن')
        live_heading.setStyleSheet('color:#BCAAE5;font-size:12px;font-weight:600;margin-top:2px;')
        ll.addWidget(live_heading)

        # Device status items with direct interactive toggles
        self.dev_home = DeviceItemCard("🏠", "المنزل", "جارٍ قراءة Home Assistant", QColor(100, 116, 139))
        self.dev_home.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        self.dev_home.set_toggle_enabled(False)
        ll.addWidget(self.dev_home)

        self.dev_tv = DeviceItemCard("📺", "التلفزيون", "تظهر حالته بعد الربط", QColor(100, 116, 139))
        self.dev_tv.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        self.dev_tv.set_toggle_enabled(False)
        self.dev_tv.toggle_requested.connect(self.toggle_tv)
        ll.addWidget(self.dev_tv)

        self.dev_lights = DeviceItemCard("💡", "الإضاءة", "جارٍ قراءة الأضواء", QColor(100, 116, 139))
        self.dev_lights.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        self.dev_lights.toggle_requested.connect(lambda on: self.run_home_action('all_on' if on else 'all_off'))
        ll.addWidget(self.dev_lights)

        # Quick Suggestions Section
        sugg_header = QLabel("مقترحات سريعة ✨")
        sugg_header.setFont(QFont("Noto Sans Arabic", 10, QFont.Bold))
        sugg_header.setStyleSheet("color:#A855F7; margin-top:4px;")
        ll.addWidget(sugg_header)

        for icon, text in [
            ("💡", "تشغيل كل الأضواء"),
            ("💡", "إطفاء كل الأضواء"),
            ("🏠", "حالة المنزل"),
            ("💻", "افحصي حالة الكمبيوتر"),
        ]:
            pill = QuickPill(icon, text)
            pill.clicked.connect(lambda checked=False, t=text: self.submit_suggestion(f"ميرا، {t}"))
            ll.addWidget(pill)

        ll.addStretch()
        cl.addWidget(left_panel)

        # ─── Column 2: Center Hero Mira Core ────────────────
        center_stage = QWidget()
        self.center_stage = center_stage
        stage_l = QVBoxLayout(center_stage)
        stage_l.setContentsMargins(10, 8, 10, 8)
        stage_l.setSpacing(6)

        # Face with surrounding floating action tags
        face_row = QHBoxLayout()
        face_row.setContentsMargins(4, 0, 4, 0)
        face_row.setSpacing(0)

        # Left floating action tags (4 tags)
        left_tags = QVBoxLayout()
        left_tags.setSpacing(12)
        left_tags.addStretch(1)

        tag_think = FloatingTag("🧠", "اسأل ميرا")
        tag_think.clicked.connect(lambda: self.chat_input.setFocus())
        left_tags.addWidget(tag_think)

        tag_listen = FloatingTag("〰️", "استمع...")
        tag_listen.clicked.connect(self.tap_to_talk)
        left_tags.addWidget(tag_listen)

        tag_speak = FloatingTag("💬", "أتحدث...")
        tag_speak.clicked.connect(lambda: self.tabs.setCurrentIndex(2))
        left_tags.addWidget(tag_speak)

        tag_exec = FloatingTag("⚙️", "أنفذ الأمر...")
        tag_exec.clicked.connect(lambda: self.tabs.setCurrentIndex(3))
        left_tags.addWidget(tag_exec)
        left_tags.addStretch(1)
        face_row.addLayout(left_tags)

        # Central Avatar
        self.orb = Orb()
        self.orb.setToolTip('اضغط لبدء محادثة صوتية أو انقر نقراً مزدوجاً للتبديل')
        self.orb.activated.connect(self.tap_to_talk)
        self.orb.face_toggle_requested.connect(self._toggle_face_style)
        self.orb.set_face_style(self.face_style)
        face_row.addWidget(self.orb, 1)

        # Right floating domain tags (5 tags)
        right_tags = QVBoxLayout()
        right_tags.setSpacing(10)
        right_tags.addStretch(1)

        tag_web = FloatingTag("🌐", "افتح المتصفح", is_right=True)
        tag_web.clicked.connect(self.open_browser)
        right_tags.addWidget(tag_web)

        tag_apps = FloatingTag("</>", "التطبيقات", is_right=True)
        tag_apps.clicked.connect(lambda: self.tabs.setCurrentIndex(3))
        right_tags.addWidget(tag_apps)

        tag_devs = FloatingTag("🏠", "الأجهزة", is_right=True)
        tag_devs.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        right_tags.addWidget(tag_devs)

        tag_mem = FloatingTag("📖", "المعرفة", is_right=True)
        tag_mem.clicked.connect(lambda: self.tabs.setCurrentIndex(4))
        right_tags.addWidget(tag_mem)

        tag_sett = FloatingTag("🔧", "الأدوات", is_right=True)
        tag_sett.clicked.connect(lambda: self.tabs.setCurrentIndex(4))
        right_tags.addWidget(tag_sett)
        right_tags.addStretch(1)
        face_row.addLayout(right_tags)

        self.stage_routes = [
            tag_think, tag_listen, tag_speak, tag_exec,
            tag_web, tag_apps, tag_devs, tag_mem, tag_sett
        ]

        stage_l.addLayout(face_row, 1)

        # Center Title & Subtitle
        mira_title = QLabel("M I R A")
        mira_title.setFont(QFont("Noto Sans Arabic", 26, QFont.Bold))
        mira_title.setAlignment(Qt.AlignCenter)
        mira_title.setStyleSheet("color:#FFF; letter-spacing: 6px;")
        stage_l.addWidget(mira_title)

        mira_sub = QLabel("YOUR AI ASSISTANT")
        mira_sub.setFont(QFont("Noto Sans Arabic", 9, QFont.DemiBold))
        mira_sub.setAlignment(Qt.AlignCenter)
        mira_sub.setStyleSheet("color:#A855F7; letter-spacing: 3px;")
        stage_l.addWidget(mira_sub)

        # Quick interactive switcher row: Hologram / Rose Face toggle + Neural Mode
        switch_row = QHBoxLayout()
        switch_row.setAlignment(Qt.AlignCenter)
        switch_row.setSpacing(10)

        self.face_toggle_btn = QPushButton(f"🎭 المظهر: {'هولو 🔮' if self.face_style == 'holo' else 'وردي 🌸'}")
        self.face_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.face_toggle_btn.setFixedHeight(28)
        self.face_toggle_btn.setStyleSheet("""
            QPushButton {
                background: rgba(18, 25, 55, 0.8);
                color: #C5D2E8;
                border: 1px solid rgba(168, 85, 247, 0.45);
                border-radius: 14px;
                padding: 0 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(168, 85, 247, 0.25);
                border-color: #A855F7;
                color: #FFFFFF;
            }
        """)
        self.face_toggle_btn.clicked.connect(self._toggle_face_style)
        switch_row.addWidget(self.face_toggle_btn)

        mode_chip = QLabel("⚡ MIRA // ECHO")
        mode_chip.setFont(QFont("Noto Sans Mono", 8))
        mode_chip.setStyleSheet("color: #00E5FF; background: rgba(0, 229, 255, 0.08); border: 1px solid rgba(0, 229, 255, 0.25); border-radius: 14px; padding: 4px 12px; letter-spacing: 1px;")
        switch_row.addWidget(mode_chip)

        stage_l.addLayout(switch_row)

        # Voice Bar
        self.voice_bar = CenterVoiceBar()
        stage_l.addWidget(self.voice_bar)

        cl.addWidget(center_stage, 1)

        # ─── Column 3: Right Conversation Panel (Width 360px)
        right_panel = GlassCard(radius=20)
        self.conversation_panel=right_panel
        right_panel.setFixedWidth(350)
        rl = QVBoxLayout(right_panel)
        rl.setContentsMargins(14, 14, 14, 14)
        rl.setSpacing(10)

        # Real conversation feed; no example messages or invented weather.
        tab_header = QHBoxLayout()
        chat_title = QLabel('المحادثة والإجراءات')
        chat_title.setStyleSheet('color:#F6F1FF;font-size:13px;font-weight:600;')
        tab_header.addWidget(chat_title)
        tab_header.addStretch(1)
        rl.addLayout(tab_header)

        # Scrollable Chat Area
        chat_scroll = QScrollArea()
        chat_scroll.setWidgetResizable(True)
        chat_scroll.setStyleSheet("background:transparent; border:none;")
        chat_scroll.viewport().setStyleSheet("background:transparent;")

        self.chat_host = QWidget()
        self.chat_host.setStyleSheet("background:transparent;")
        self.chat_layout = QVBoxLayout(self.chat_host)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(10)

        self.empty_chat = QLabel('اسأل ميرا أو اختر أمراً حقيقياً. سيظهر هنا ما نُفّذ وما لم يتأكد.')
        self.empty_chat.setWordWrap(True)
        self.empty_chat.setAlignment(Qt.AlignCenter)
        self.empty_chat.setStyleSheet('color:#A8B5CF;padding:40px 12px;')
        self.chat_layout.addWidget(self.empty_chat)
        self.chat_layout.addStretch()
        chat_scroll.setWidget(self.chat_host)
        rl.addWidget(chat_scroll, 1)

        # Chat Input Box
        input_frame = QFrame()
        input_frame.setObjectName('conversationComposer')
        input_frame.setFixedHeight(44)
        input_frame.setStyleSheet("""
            QFrame#conversationComposer {
                background: rgba(14, 22, 50, 0.9);
                border: 1px solid rgba(66, 120, 240, 0.3);
                border-radius: 22px;
            }
        """)
        ifl = QHBoxLayout(input_frame)
        ifl.setContentsMargins(10, 4, 6, 4)
        ifl.setSpacing(6)

        clip_btn = QPushButton("📎")
        clip_btn.setFixedSize(28, 28)
        clip_btn.setStyleSheet("background:transparent; color:#8E9BB5; border:none; font-size:14px;")
        clip_btn.setToolTip('إرفاق ملف نصي صغير')
        clip_btn.clicked.connect(self.attach_text)
        ifl.addWidget(clip_btn)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("اكتب رسالتك هنا...")
        self.chat_input.setStyleSheet("background:transparent; color:#FFF; border:none; font-size:12px;")
        self.chat_input.returnPressed.connect(self._handle_chat_input)
        ifl.addWidget(self.chat_input, 1)

        send_btn = QPushButton("↗")
        send_btn.setFixedSize(32, 32)
        send_btn.setToolTip('إرسال الرسالة')
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #8B5CF6, stop:1 #00E5FF);
                color: #FFF;
                border-radius: 16px;
                border: none;
                font-size: 14px;
            }
        """)
        send_btn.clicked.connect(self._handle_chat_input)
        ifl.addWidget(send_btn)
        self.conversation_composer = input_frame
        # The single composer lives in the command dock, so chat never has a second input.

        cl.addWidget(right_panel)
        self.tabs.addTab(canvas, "الرئيسية")

    def _add_chat_msg(self, role, text, timestamp="", persist=True):
        self.empty_chat.hide()
        row = QWidget()
        row.setStyleSheet("background:transparent;")
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        bubble = QLabel()
        bubble.setTextFormat(Qt.RichText)
        bubble.setWordWrap(True)
        stamp = timestamp or datetime.now().strftime("%H:%M")

        if role == 'user':
            bubble.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(20, 48, 86, 0.88), stop:1 rgba(12, 28, 56, 0.88));
                color: #EDF9FC;
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 14px;
                padding: 10px 14px;
                font-size: 12px;
            """)
            badge = '<div style="color:#00E5FF;font-size:8px;font-weight:bold;letter-spacing:1px;margin-bottom:3px;">USER // INPUT</div>'
            hl.addStretch(1)
            hl.addWidget(bubble)
        else:
            if role == 'action':
                bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(16, 50, 42, 0.88), stop:1 rgba(10, 32, 28, 0.88))"
                border = "rgba(0, 255, 136, 0.4)"
                badge = '<div style="color:#00FF88;font-size:8px;font-weight:bold;letter-spacing:1px;margin-bottom:3px;">SYS // EXECUTION</div>'
            elif role == 'error':
                bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(60, 20, 35, 0.88), stop:1 rgba(38, 12, 22, 0.88))"
                border = "rgba(239, 68, 68, 0.4)"
                badge = '<div style="color:#EF4444;font-size:8px;font-weight:bold;letter-spacing:1px;margin-bottom:3px;">SYS // ALERT</div>'
            else:
                bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(32, 24, 68, 0.88), stop:1 rgba(20, 15, 45, 0.88))"
                border = "rgba(168, 85, 247, 0.35)"
                badge = '<div style="color:#A855F7;font-size:8px;font-weight:bold;letter-spacing:1px;margin-bottom:3px;">MIRA // NEURAL AI</div>'

            bubble.setStyleSheet(f"""
                background: {bg};
                color: #F4F0FF;
                border: 1px solid {border};
                border-radius: 14px;
                padding: 10px 14px;
                font-size: 12px;
            """)
            hl.addWidget(bubble)
            hl.addStretch(1)

        bubble.setText(f'{badge}<div style="line-height:130%;">{html.escape(text)}</div><div style="color:#8E9BB5;font-size:9px;margin-top:4px;text-align:right;">{stamp}</div>')
        self.chat_layout.insertWidget(self.chat_layout.count()-1,row)
        if hasattr(self,'conversation_log'):
            self.conversation_log.appendPlainText(f'{stamp} · {role}: {text}')
        if persist:
            from mira_memory import add_message
            add_message(role,text)

    def _toggle_face_style(self):
        new_style = 'holo' if self.face_style == 'rose' else 'rose'
        self.select_face(new_style)
        if hasattr(self, 'face_toggle_btn'):
            self.face_toggle_btn.setText(f"🎭 المظهر: {'هولو 🔮' if new_style == 'holo' else 'وردي 🌸'}")

    def _on_weather_updated(self, temp_c, condition_ar, city, humidity, wind):
        if hasattr(self, 'weather_clock'):
            self.weather_clock.set_weather(temp_c, condition_ar, city=city, humidity=humidity, wind=wind)

    def _on_weather_failed(self, message):
        if hasattr(self, 'weather_clock'):
            self.weather_clock.set_weather_error(message)

    def update_weather_async(self):
        city = str(self.settings.value('weather_city', '')).strip()
        if not city:
            return
        def worker():
            try:
                import weather_link
                res = weather_link.current(city)
                if res.get('status') == 'ok':
                    hum = f"{res.get('humidity_percent')}%" if res.get('humidity_percent') is not None else ''
                    wind = f"{round(res['wind_kmh'])} km/h" if res.get('wind_kmh') is not None else ''
                    self.weather_updated.emit(res['temperature_c'], res['condition_ar'], res['city'], hum, wind)
            except (OSError, RuntimeError, ValueError):
                self.weather_failed.emit('الطقس غير متاح الآن')
        threading.Thread(target=worker, daemon=True).start()

    def _restore_chat(self):
        from mira_memory import recent_messages
        messages = recent_messages(50)
        merged = []
        for msg in messages:
            if merged and merged[-1]['role'] == msg['role']:
                t1_str = merged[-1].get('time', '')
                t2_str = msg.get('time', '')
                try:
                    from datetime import datetime
                    t1 = datetime.fromisoformat(t1_str)
                    t2 = datetime.fromisoformat(t2_str)
                    diff = abs((t2 - t1).total_seconds())
                except Exception:
                    diff = 0
                if diff < 5.0 or len(msg.get('text', '')) < 25:
                    sep = ' ' if not merged[-1]['text'].endswith(' ') and not msg['text'].startswith(' ') else ''
                    merged[-1]['text'] = (merged[-1]['text'] + sep + msg['text']).strip()
                    continue
            merged.append(dict(msg))

        for message in merged[-8:]:
            self._add_chat_msg(message['role'], message['text'],
                               message.get('time','')[11:16], persist=False)

    def _handle_chat_input(self):
        txt = self.chat_input.text().strip()
        if not txt: return
        self.chat_input.clear()
        self._send_command(txt)

    def _build_devices_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 16)
        header = QBoxLayout(QBoxLayout.LeftToRight)
        self.home_header_layout=header
        header.addWidget(QLabel('البيت · أجهزة Home Assistant'))
        header.addStretch()
        refresh = QPushButton('↻ تحديث الحالة')
        refresh.clicked.connect(lambda: self.home_jobs.run())
        header.addWidget(refresh)
        open_ha = QPushButton('↗ Home Assistant')
        open_ha.clicked.connect(self.open_home_assistant)
        header.addWidget(open_ha)
        layout.addLayout(header)

        self.home_status = QLabel('جارٍ قراءة الأجهزة الفعلية…')
        self.home_status.setWordWrap(True)
        layout.addWidget(self.home_status)

        pairing = QHBoxLayout()
        self.ha_token = QLineEdit()
        self.ha_token.setEchoMode(QLineEdit.Password)
        self.ha_token.setPlaceholderText('رمز Home Assistant المحلي، إن لم يكن الربط موجوداً')
        pairing.addWidget(self.ha_token, 1)
        save = QPushButton('حفظ الربط')
        save.clicked.connect(self.save_home_token)
        pairing.addWidget(save)
        layout.addLayout(pairing)
        self.ha_token.setVisible(not (Path.home()/'.config/mo-dot/home.json').exists())
        save.setVisible(self.ha_token.isVisible())
        self.ha_save_button = save

        bulk = QBoxLayout(QBoxLayout.LeftToRight)
        self.home_bulk_layout=bulk
        bulk.addWidget(QLabel('جميع المصابيح الفردية المتاحة'))
        for label, action in [('تشغيل كل الأضواء','all_on'),('إطفاء كل الأضواء','all_off')]:
            button = QPushButton(label)
            button.setObjectName('routeAction')
            button.clicked.connect(lambda checked=False, a=action: self.run_home_action(a))
            bulk.addWidget(button)
        bulk.addStretch()
        layout.addLayout(bulk)

        panes = QSplitter(Qt.Horizontal)
        self.home_panes=panes
        layout.addWidget(panes, 1)
        self.home_list = QListWidget()
        self.home_list.setObjectName('homeList')
        self.home_list.currentItemChanged.connect(lambda *_: self.update_home_selection())
        panes.addWidget(self.home_list)
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        self.home_name = QLabel('اختر جهازاً من القائمة')
        self.home_name.setStyleSheet('font-size:20px;font-weight:600;')
        detail_layout.addWidget(self.home_name)
        self.home_observed = QLabel('تظهر حالة الجهاز وقدراته هنا.')
        self.home_observed.setWordWrap(True)
        detail_layout.addWidget(self.home_observed)
        power = QHBoxLayout()
        self.home_on = QPushButton('تشغيل')
        self.home_off = QPushButton('إطفاء')
        self.home_on.clicked.connect(lambda: self.run_home_action('turn_on'))
        self.home_off.clicked.connect(lambda: self.run_home_action('turn_off'))
        power.addWidget(self.home_on)
        power.addWidget(self.home_off)
        detail_layout.addLayout(power)
        self.home_color = QComboBox()
        for label, color in [('وردي','pink'),('بنفسجي','purple'),('أزرق','blue'),('أخضر','green'),
                             ('أصفر','yellow'),('برتقالي','orange'),('أحمر','red')]:
            self.home_color.addItem(label, color)
        detail_layout.addWidget(self.home_color)
        self.home_color_button = QPushButton('تغيير لون الإضاءة')
        self.home_color_button.clicked.connect(lambda: self.run_home_action('color', color=self.home_color.currentData()))
        detail_layout.addWidget(self.home_color_button)
        self.home_brightness_label = QLabel('سطوع الإضاءة')
        detail_layout.addWidget(self.home_brightness_label)
        self.home_brightness = QSlider(Qt.Horizontal)
        self.home_brightness.setRange(1,100)
        self.home_brightness.sliderReleased.connect(lambda: self.run_home_action('brightness', value=self.home_brightness.value()))
        detail_layout.addWidget(self.home_brightness)
        self.home_volume_label = QLabel('صوت التلفزيون')
        detail_layout.addWidget(self.home_volume_label)
        self.home_volume = QSlider(Qt.Horizontal)
        self.home_volume.setRange(0,100)
        self.home_volume.sliderReleased.connect(lambda: self.run_home_action('volume', value=self.home_volume.value()))
        detail_layout.addWidget(self.home_volume)
        media = QHBoxLayout()
        self.home_play = QPushButton('▶ تشغيل الوسائط')
        self.home_pause = QPushButton('Ⅱ إيقاف مؤقت')
        self.home_play.clicked.connect(lambda: self.run_home_action('media_play'))
        self.home_pause.clicked.connect(lambda: self.run_home_action('media_pause'))
        media.addWidget(self.home_play)
        media.addWidget(self.home_pause)
        detail_layout.addLayout(media)
        detail_layout.addStretch()
        panes.addWidget(detail)
        panes.setSizes([400,700])
        self.home_entries = {}
        self.home_jobs = HomeBridge()
        self.home_jobs.result.connect(self.home_result)
        self.update_home_selection()
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(page)
        self.tabs.addTab(scroll, 'البيت')
        if os.environ.get('MIRA_TEST_MODE')!='1':
            QTimer.singleShot(1500, lambda: self.home_jobs.run())

    def open_home_assistant(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl('http://127.0.0.1:8123'))

    def open_browser(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        if not QDesktopServices.openUrl(QUrl('https://www.google.com/')):
            self._add_chat_msg('error', 'لم أتمكن من فتح المتصفح')

    def toggle_tv(self, on):
        entity_id = getattr(self, 'tv_entity_id', None)
        if not entity_id:
            self._add_chat_msg('error', 'لا يوجد تلفزيون قابل للتحكم في البيت')
            return
        self.home_status.setText('أتحقق من حالة التلفزيون…')
        self.home_jobs.run('turn_on' if on else 'turn_off', entity_id)

    def save_home_token(self):
        from home_link import save_token
        try:
            save_token(self.ha_token.text())
            self.ha_token.clear()
            self.ha_token.hide()
            self.ha_save_button.hide()
            self.home_jobs.run()
        except ValueError as exc:
            self.home_status.setText(str(exc))

    def selected_home_id(self):
        item = self.home_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def update_home_selection(self):
        item = self.home_entries.get(self.selected_home_id())
        if not item:
            self.home_name.setText('اختر جهازاً من القائمة')
            self.home_observed.setText('تظهر حالة الجهاز وقدراته هنا.')
            for button in (self.home_on,self.home_off,self.home_color_button,self.home_play,self.home_pause):
                button.setEnabled(False)
            return
        domain = item['entity_id'].split('.')[0]
        features = item.get('supported_features') or 0
        available = item['state'] not in ('unavailable','unknown')
        self.home_name.setText(item['name'])
        self.home_observed.setText('الحالة المقروءة: '+item['state'] + (' · غير متاح حالياً' if not available else ''))
        self.home_on.setEnabled(available and (domain!='media_player' or bool(features&128)))
        self.home_off.setEnabled(available and (domain!='media_player' or bool(features&256)))
        is_light = domain=='light'
        color = is_light and any(m in (item.get('supported_color_modes') or []) for m in ('hs','xy','rgb','rgbw','rgbww'))
        self.home_color.setVisible(color)
        self.home_color_button.setVisible(color)
        self.home_color_button.setEnabled(available and color)
        self.home_brightness_label.setVisible(is_light)
        self.home_brightness.setVisible(is_light)
        self.home_brightness.setEnabled(available and is_light)
        if item.get('brightness') is not None:
            self.home_brightness.setValue(max(1,round(item['brightness']*100/255)))
        volume = domain=='media_player' and bool(features&4)
        self.home_volume_label.setVisible(volume)
        self.home_volume.setVisible(volume)
        self.home_volume.setEnabled(available and volume and item.get('volume_level') is not None)
        if item.get('volume_level') is not None:
            self.home_volume.setValue(round(item['volume_level']*100))
        for button, bit in ((self.home_play,16384),(self.home_pause,1)):
            button.setVisible(domain=='media_player' and bool(features&bit))
            button.setEnabled(available and bool(features&bit))

    def run_home_action(self, action, value=None, color=None):
        entity_id = None if action in ('all_on','all_off') else self.selected_home_id()
        if not entity_id and action not in ('all_on','all_off'):
            self.home_status.setText('اختر جهازاً أولاً')
            return
        self.home_status.setText('أتحقق من نتيجة الأمر على الجهاز…')
        self.home_jobs.run(action, entity_id, value, color)

    def home_result(self, payload):
        if payload['kind']=='devices':
            devices = payload['devices']
            selected = self.selected_home_id()
            self.home_entries = {item['entity_id']:item for item in devices}
            self.home_list.blockSignals(True)
            self.home_list.clear()
            for item in devices:
                label = ('● ' if item['state'] not in ('unavailable','unknown') else '○ ') + item['name'] + ' · ' + item['state']
                row = QListWidgetItem(label)
                row.setData(Qt.UserRole,item['entity_id'])
                self.home_list.addItem(row)
            self.home_list.blockSignals(False)
            for index in range(self.home_list.count()):
                if self.home_list.item(index).data(Qt.UserRole)==selected:
                    self.home_list.setCurrentRow(index)
                    break
            if self.home_list.currentRow()<0 and self.home_list.count():
                self.home_list.setCurrentRow(0)
            self.update_home_selection()
            online = [item for item in devices if item['state'] not in ('unavailable','unknown')]
            lights = [item for item in devices if item['entity_id'].startswith('light.') and item['state']=='on' and not item.get('is_hue_group')]
            tv = next((item for item in devices if item['entity_id'].startswith('media_player.') and item['state'] not in ('unavailable','unknown')),None)
            self.tv_entity_id = tv['entity_id'] if tv else None
            self.dev_home.set_state(str(len(online))+' أجهزة متاحة',QColor(0,255,136) if online else QColor(100,116,139))
            self.dev_lights.set_state(str(len(lights))+' مصابيح مضاءة',QColor(0,255,136) if lights else QColor(100,116,139), bool(lights))
            self.dev_lights.set_toggle_enabled(any(item['entity_id'].startswith('light.') and item['state'] not in ('unavailable','unknown') and not item.get('is_hue_group') for item in devices))
            self.dev_tv.set_state((tv['name']+' · '+tv['state']) if tv else 'غير متاح',QColor(0,229,255) if tv else QColor(100,116,139), bool(tv and tv['state'] in ('on','playing','paused','idle')))
            self.dev_tv.set_toggle_enabled(bool(tv and (tv.get('supported_features',0) & (256 if self.dev_tv.is_on else 128))))
            self.home_status.setText(str(len(online))+' أجهزة متاحة · '+str(len(devices)-len(online))+' غير متاحة')
        elif payload['kind']=='action':
            result=payload['outcome']
            if 'confirmed' in result:
                message=f"تأكدت من {result['confirmed']}/{result['total']} أضواء؛ " + ('كلها استجابت' if result['status']=='ok' else 'بعضها غير متاح أو لم يؤكد التنفيذ')
            else:
                message=('تأكدت من التنفيذ' if result['status']=='ok' else 'أُرسل الأمر لكن لم أتأكد من النتيجة')+' · '+result['entity_id']
            self.home_status.setText(message)
            self._add_chat_msg('action' if result['status']=='ok' else 'error',message)
            self.home_jobs.run()
        else:
            self.home_status.setText(payload['error'])
            self._add_chat_msg('error',payload['error'])

    def _build_conversation_page(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(24,20,24,16)
        layout.addWidget(QLabel('المحادثة الحية والإجراءات المؤكدة'))
        self.conversation_log=QPlainTextEdit();self.conversation_log.setReadOnly(True)
        layout.addWidget(self.conversation_log,1)
        button=QPushButton('العودة إلى ميرا')
        button.clicked.connect(lambda:self.tabs.setCurrentIndex(0))
        layout.addWidget(button)
        self.tabs.addTab(page,'المحادثة')

    def _build_computer_page(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(24,20,24,16)
        layout.addWidget(QLabel('الكمبيوتر · أدوات Mo AI الفعلية'))
        layout.addWidget(QLabel('الفحص يقرأ الحالة؛ أوامر التغيير تمر عبر منفذ Mo AI وقواعد تأكيده.'))
        row=QGridLayout()
        self.pc_grid=row
        self.pc_buttons=[]
        for name,label in [('get_system_status','حالة الكمبيوتر'),('memory_status','الذاكرة'),
                           ('disk_status','التخزين'),('network_status','الشبكة'),
                           ('top_processes','العمليات'),('list_failed_units','الخدمات المتعثرة'),
                           ('list_installed_apps','التطبيقات المثبتة')]:
            button=QPushButton(label)
            button.clicked.connect(lambda checked=False,n=name:self.run_pc_tool(n))
            self.pc_buttons.append(button)
            row.addWidget(button,0,len(self.pc_buttons)-1)
        layout.addLayout(row)
        controls=QHBoxLayout()
        volume_box=QVBoxLayout()
        volume_box.addWidget(QLabel('صوت الكمبيوتر'))
        self.pc_volume=QSlider(Qt.Horizontal)
        self.pc_volume.setRange(0,100)
        self.pc_volume.setEnabled(False)
        self.pc_volume.sliderReleased.connect(lambda:self.run_pc_tool('set_volume',{'value':str(self.pc_volume.value())}))
        volume_box.addWidget(self.pc_volume)
        controls.addLayout(volume_box,1)
        brightness_box=QVBoxLayout()
        brightness_box.addWidget(QLabel('سطوع الشاشة'))
        self.pc_brightness=QSlider(Qt.Horizontal)
        self.pc_brightness.setRange(5,100)
        self.pc_brightness.setEnabled(False)
        self.pc_brightness.sliderReleased.connect(lambda:self.run_pc_tool('set_brightness',{'value':str(self.pc_brightness.value())}))
        brightness_box.addWidget(self.pc_brightness)
        controls.addLayout(brightness_box,1)
        layout.addLayout(controls)
        self.pc_status=QLabel('اختر فحصاً لقراءة نتيجة حقيقية')
        layout.addWidget(self.pc_status)
        self.pc_output=QPlainTextEdit();self.pc_output.setReadOnly(True)
        layout.addWidget(self.pc_output,1)
        self.pc_jobs=PcBridge();self.pc_jobs.result.connect(self.pc_result)
        self.tabs.addTab(page,'الكمبيوتر')
        if os.environ.get('MIRA_TEST_MODE')!='1':
            QTimer.singleShot(1800,lambda:self.run_pc_tool('get_system_status'))

    def run_pc_tool(self,name,args=None):
        self.pc_status.setText('جارٍ فحص الكمبيوتر…')
        self.pc_jobs.run(name,args or {})

    def pc_result(self,result):
        self.pc_status.setText('تأكدت من النتيجة' if result.get('status')=='ok' and result.get('tool') in ('set_volume','set_brightness')
                               else 'تمت القراءة من Mo AI' if result.get('status')=='ok'
                               else 'أُرسل الأمر ولم أتأكد من النتيجة' if result.get('status')=='pending'
                               else 'تعذّر فحص الكمبيوتر')
        self.pc_output.setPlainText(str(result.get('output') or result.get('error') or 'لا توجد نتيجة'))
        if result.get('tool')=='get_system_status' and result.get('status')=='ok':
            try:
                values=json.loads(result.get('output') or '{}')
                for key,slider in (('volume',self.pc_volume),('brightness',self.pc_brightness)):
                    if isinstance(values.get(key),(int,float)):
                        slider.setValue(round(values[key]))
                        slider.setEnabled(True)
            except (ValueError,TypeError):
                pass
        elif result.get('tool') in ('set_volume','set_brightness'):
            self._add_chat_msg('action' if result.get('status')=='ok' else 'error',
                               str(result.get('output') or result.get('error') or 'لم أتأكد من التغيير'))

    def _build_settings_page(self):
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        page.viewport().setStyleSheet('background:#0B1028;')
        body = QWidget()
        body.setStyleSheet('''
            QWidget { background:#0B1028; color:#E9EEFA; }
            QLabel { background:transparent; color:#CAD5EA; font-size:13px; }
            QPushButton, QComboBox {
                background:#161E3C; color:#F2F4FF;
                border:1px solid rgba(112,145,208,0.28);
                border-radius:12px; padding:9px 13px;
            }
            QPushButton:hover { background:#202C53; }
            QPlainTextEdit, QLineEdit {
                background:#101935; color:#F2F4FF;
                border:1px solid rgba(112,145,208,0.28);
                border-radius:12px; padding:10px;
            }
            QCheckBox { color:#E9EEFA; spacing:9px; background:transparent; }
        ''')
        page.setWidget(body)
        pl = QVBoxLayout(body)
        pl.setContentsMargins(24, 20, 24, 16)
        pl.setSpacing(12)
        pl.addWidget(QLabel('الجهاز · الوجه والصوت'))
        pl.addWidget(QLabel('الوجهان الأصليان محفوظان. اختر أحدهما؛ التغيير يظهر فوراً ويُحفظ.'))
        faces=QHBoxLayout();self.face_choices={}
        for style,label in [('rose','الوجه الوردي'),('holo','الوجه الهولوغرافي')]:
            button=QPushButton(label)
            button.setCheckable(True)
            button.setIcon(QIcon(self.orb.frames_by_style[style][0]))
            button.setIconSize(QSize(80,80))
            button.setMinimumHeight(100)
            button.setChecked(style==self.face_style)
            button.clicked.connect(lambda checked=False,s=style:self.select_face(s))
            faces.addWidget(button)
            self.face_choices[style]=button
        pl.addLayout(faces)
        pl.addWidget(QLabel('صوت ميرا'))
        self.voice_picker=QComboBox()
        for label,name in [('Aoede · دافئ','Aoede'),('Kore · واضح','Kore'),('Leda · هادئ','Leda')]:
            self.voice_picker.addItem(label,name)
        self.voice_picker.setCurrentIndex(self.voice_picker.findData(self.voice_name))
        self.voice_picker.currentIndexChanged.connect(self.select_voice)
        pl.addWidget(self.voice_picker)
        self.device_voice_toggle=QPushButton('تشغيل المحادثة الصوتية')
        self.device_voice_toggle.clicked.connect(lambda:self.bridge.set_voice(self.voice_phase in ('off','error')))
        pl.addWidget(self.device_voice_toggle)
        self.local_wake_toggle=QCheckBox('تفعيل «ميرا / يا ميرا / هاي ميرا» من ميكروفون الكمبيوتر')
        self.local_wake_toggle.setChecked(self.local_wake_enabled)
        self.local_wake_toggle.toggled.connect(self.set_local_wake)
        pl.addWidget(self.local_wake_toggle)
        pl.addWidget(QLabel('ميكروفون نداء ميرا على الكمبيوتر'))
        self.mic_source_picker=QComboBox()
        for source in self.available_microphones():
            self.mic_source_picker.addItem(source,source)
        saved_source=str(self.settings.value('local_wake_source',''))
        index=self.mic_source_picker.findData(saved_source)
        if index>=0:self.mic_source_picker.setCurrentIndex(index)
        self.mic_source_picker.currentIndexChanged.connect(self.select_mic_source)
        pl.addWidget(self.mic_source_picker)
        self.local_wake_state=QLabel('النداء المحلي: جارٍ التحقق من الميكروفون')
        pl.addWidget(self.local_wake_state)
        pl.addWidget(QLabel('قل الاسم أولاً، ثم اسأل بعد إشارة Echo. السؤال والرد عبر Echo.'))
        self.device_state=QLabel('جارٍ قراءة جهاز Mira…')
        pl.addWidget(self.device_state)
        pl.addWidget(QLabel('صوت سماعة Echo'))
        self.speaker_volume=QSlider(Qt.Horizontal);self.speaker_volume.setRange(0,100)
        self.speaker_volume.setEnabled(False)
        self.speaker_volume.sliderReleased.connect(lambda:self.bridge.command('volume','speaker',self.speaker_volume.value()/100))
        pl.addWidget(self.speaker_volume)
        pl.addWidget(QLabel('حساسية النموذج الحالي «Hey Mira»'))
        self.wake_threshold=QSlider(Qt.Horizontal);self.wake_threshold.setRange(50,99)
        self.wake_threshold.setEnabled(False)
        self.wake_threshold.sliderReleased.connect(lambda:self.bridge.command('number','wake_threshold_1',self.wake_threshold.value()/100))
        pl.addWidget(self.wake_threshold)
        pl.addWidget(QLabel('نموذج Echo الأصلي للإنجليزية؛ النداء العربي المحلي يحتاج ميكروفون الكمبيوتر.'))
        pl.addWidget(QLabel('مدينة الطقس'))
        self.weather_city_input=QLineEdit()
        self.weather_city_input.setPlaceholderText('اكتب المدينة والبلد؛ لا يُعرض طقس افتراضي')
        self.weather_city_input.setText(str(self.settings.value('weather_city','')))
        pl.addWidget(self.weather_city_input)
        weather_save=QPushButton('حفظ المدينة وتحديث الطقس')
        weather_save.clicked.connect(self.save_weather_city)
        pl.addWidget(weather_save)
        pl.addWidget(QLabel('روح ميرا · معلوماتك ومشاريعك التي تريدها أن تتذكرها'))
        from mira_memory import profile_text
        self.profile_editor=QPlainTextEdit()
        self.profile_editor.setPlaceholderText('اسمي… · طوّرت ميرا… · مشاريعي… · تفضيلاتي…')
        self.profile_editor.setPlainText(profile_text())
        self.profile_editor.setMinimumHeight(120)
        pl.addWidget(self.profile_editor)
        self.profile_save=QPushButton('حفظ روح ميرا محلياً')
        self.profile_save.clicked.connect(self.save_mira_profile)
        pl.addWidget(self.profile_save)
        pl.addWidget(QLabel('يُستخدم الملف كمعرفة للمحادثة؛ لا يضيف صلاحيات أو أدوات تلقائياً.'))
        pl.addStretch()
        self.tabs.addTab(page,'الإعدادات')

    def save_mira_profile(self):
        from mira_memory import save_profile
        try:
            save_profile(self.profile_editor.toPlainText())
            self._add_chat_msg('action','حُفظ ملف ميرا على الكمبيوتر؛ ستقرأه في المحادثة القادمة.')
        except (OSError,ValueError) as exc:
            self._add_chat_msg('error',str(exc))

    def save_weather_city(self):
        city=self.weather_city_input.text().strip()
        if city:
            import re
            if not re.fullmatch(r'[\w\s\-،,.]{2,80}',city,re.UNICODE):
                self._add_chat_msg('error','اسم المدينة غير صالح')
                return
        self.settings.setValue('weather_city',city)
        if city:
            self.update_weather_async()
        else:
            self.weather_clock.set_weather_error('حدّد المدينة من الإعدادات')

    def select_face(self,style):
        if style not in ('rose','holo'):
            return
        self.face_style=style
        self.settings.setValue('face_style',style)
        self.orb.set_face_style(style)
        for name,button in self.face_choices.items():
            button.setChecked(name==style)

    def select_voice(self):
        name=self.voice_picker.currentData()
        if name not in ('Aoede','Kore','Leda'):
            return
        self.voice_name=name
        self.settings.setValue('voice_name',name)
        self.bridge.voice_name=name
        if self.bridge.voice:
            self.bridge.voice.voice_name=name

    # ─── Bottom Command Dock ────────────────────────────────────────
    def _build_bottom_dock(self, parent_layout):
        dock = QFrame()
        dock.setObjectName('miraCommandDock')
        dock.setLayoutDirection(Qt.LeftToRight)
        dock.setFixedHeight(82)
        dock.setStyleSheet("""
            QFrame#miraCommandDock {
                background: rgba(10, 15, 36, 0.95);
                border: 1px solid rgba(66, 120, 240, 0.28);
                border-radius: 24px;
            }
        """)
        dl = QBoxLayout(QBoxLayout.LeftToRight, dock)
        self.dock_layout=dl
        dl.setContentsMargins(18, 8, 18, 8)
        dl.setSpacing(10)

        # 1. Left Pill: Mira Status & Mini Wave
        left_chip = QFrame()
        left_chip.setObjectName('dockStatusChip')
        self.dock_status_chip=left_chip
        left_chip.setFixedHeight(54)
        left_chip.setStyleSheet("QFrame#dockStatusChip {background:rgba(18,25,56,0.8); border:1px solid rgba(66,120,240,0.2); border-radius:16px;}")
        lcl = QHBoxLayout(left_chip)
        lcl.setContentsMargins(10, 4, 12, 4)
        lcl.setSpacing(10)

        avatar_lbl = QLabel()
        avatar_lbl.setPixmap(QPixmap(str(ROOT / 'mira-icon-v2.png')).scaled(34,34,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        lcl.addWidget(avatar_lbl)

        status_col = QVBoxLayout()
        status_col.setSpacing(1)
        name_t = QLabel("MIRA")
        name_t.setFont(QFont("Noto Sans Arabic", 10, QFont.Bold))
        name_t.setStyleSheet("color:#FFF;")
        self.dock_sub = QLabel("○ جارٍ الاتصال")
        self.dock_sub.setFont(QFont("Noto Sans Arabic", 9))
        self.dock_sub.setStyleSheet("color:#00FF88;")
        status_col.addWidget(name_t)
        status_col.addWidget(self.dock_sub)
        lcl.addLayout(status_col)

        self.dock_wave = DockWave()
        lcl.addWidget(self.dock_wave)
        dl.addWidget(left_chip)

        self.conversation_composer.setParent(dock)
        dl.addWidget(self.conversation_composer, 1)

        # 2. Center: Write, Big Mic FAB, Stop
        center_ctl = QHBoxLayout()
        center_ctl.setSpacing(12)

        # Glowing Neon Mic Button
        self.mic_btn = QPushButton("🎙")
        self.mic_btn.setFixedSize(66, 66)
        self.mic_btn.setCursor(Qt.PointingHandCursor)
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.7, stop:0 #00E5FF, stop:0.5 #6366F1, stop:1 #A855F7);
                color: #FFFFFF;
                border: 2px solid rgba(0, 229, 255, 0.8);
                border-radius: 33px;
                font-size: 26px;
            }
            QPushButton:hover {
                border: 2px solid #00E5FF;
            }
        """)
        self.mic_btn.clicked.connect(self.tap_to_talk)
        center_ctl.addWidget(self.mic_btn)

        self.stop_btn = QPushButton("⏹\nإيقاف")
        self.stop_btn.setFixedSize(54, 52)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setStyleSheet("background:rgba(45,18,34,0.8); color:#FF4DAB; border:1px solid rgba(255,77,171,0.3); border-radius:14px; font-size:10px;")
        self.stop_btn.clicked.connect(self.bridge.cancel_voice)
        self.stop_btn.setEnabled(False)
        center_ctl.addWidget(self.stop_btn)

        dl.addLayout(center_ctl)

        # Actions use actual service routes; they are not another copy of navigation.
        self.dock_quick = QWidget()
        quick = QHBoxLayout(self.dock_quick)
        quick.setContentsMargins(0,0,0,0)
        quick.setSpacing(6)
        for label, command in [('إطفاء الأضواء', 'ميرا، أطفئي كل الأضواء'),
                               ('حالة الكمبيوتر', 'ميرا، افحصي حالة الكمبيوتر')]:
            button=QPushButton(label)
            button.setObjectName('quickAction')
            button.setStyleSheet('QPushButton { background:#182448; color:#E9EEFA; border:1px solid #364D79; border-radius:10px; padding:8px 12px; } QPushButton:hover { background:#21345F; }')
            button.clicked.connect(lambda checked=False, text=command: self._send_command(text))
            quick.addWidget(button)
        dl.addWidget(self.dock_quick)

        self.dock_categories = QWidget()
        cats_l = QHBoxLayout(self.dock_categories)
        cats_l.setContentsMargins(0, 0, 0, 0)
        cats_l.setSpacing(6)
        for ic, name, tab_idx in [
            ("🏠", "البيت", 1),
            ("💻", "الكمبيوتر", 3),
            ("💬", "المحادثة", 2),
            ("🔧", "الإعدادات", 4),
        ]:
            b = QPushButton(f"{ic} {name}")
            b.setStyleSheet("""
                QPushButton {
                    background: rgba(18, 25, 55, 0.7);
                    color: #C5D2E8;
                    border: 1px solid rgba(66, 120, 240, 0.22);
                    border-radius: 12px;
                    padding: 8px 12px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    color: #00E5FF;
                    background: rgba(0, 229, 255, 0.12);
                    border-color: rgba(0, 229, 255, 0.5);
                }
            """)
            b.clicked.connect(lambda checked=False, idx=tab_idx: self.tabs.setCurrentIndex(idx))
            cats_l.addWidget(b)
        dl.addWidget(self.dock_categories)
        parent_layout.addWidget(dock)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'stage_layout'):
            self.apply_responsive_layout()

    def apply_responsive_layout(self):
        width=self.width()
        compact=width<900
        self.stage_layout.setDirection(QBoxLayout.TopToBottom if compact else QBoxLayout.LeftToRight)
        self.context_panel.setVisible(not compact)
        if compact:
            self.conversation_panel.setMinimumWidth(0)
            self.conversation_panel.setMaximumWidth(16777215)
        else:
            self.conversation_panel.setFixedWidth(350)
        self.conversation_panel.setMaximumHeight(260 if compact else 16777215)
        self.orb.setMinimumHeight(230 if compact else 320)
        for route in self.stage_routes:route.setVisible(width>=1150)
        self.profile_chip.setVisible(width>=1250)
        for index,button in self.top_nav_buttons:
            button.setVisible(width>=1100 or index in (0,1) and width>=700 or index==0)
        self.dock_status_chip.setVisible(width>=1000)
        self.dock_quick.setVisible(width>=1250)
        if hasattr(self, 'dock_categories'):
            self.dock_categories.setVisible(width>=1350)
        self.dock_layout.setDirection(QBoxLayout.TopToBottom if width<700 else QBoxLayout.LeftToRight)
        self.dock_layout.parentWidget().setFixedHeight(126 if width<700 else 82)
        self.mobile_menu_button.setVisible(width<1100)
        narrow=width<700
        self.home_header_layout.setDirection(QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight)
        self.home_bulk_layout.setDirection(QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight)
        self.home_panes.setOrientation(Qt.Vertical if narrow else Qt.Horizontal)
        if narrow:self.home_panes.setSizes([180,360])
        columns=2 if narrow else 6
        for i,button in enumerate(self.pc_buttons):
            self.pc_grid.addWidget(button,i//columns,i%columns)

    # ─── Signals and Handlers ───────────────────────────────────────
    def _connect_signals(self):
        self.bridge.connected.connect(self.on_device_connected)
        self.bridge.state.connect(self.on_device_state)
        self.bridge.error.connect(self.on_device_error)
        self.bridge.command_state.connect(self.on_device_command_state)
        self.bridge.voice_state.connect(self.on_voice_state)
        self.chat_bridge.reply.connect(self.on_chat_reply)
        self.chat_bridge.error.connect(self.on_chat_error)

    def on_device_connected(self, es):
        self.bykey={entity.key:entity for entity in es}
        self.connection_dot.setText('● متصل')
        self.connection_dot.setStyleSheet('color:#4ADE80;')
        self.dock_sub.setText("● متصل")
        self.dock_sub.setStyleSheet("color:#00FF88;")
        self.voice_bar.set_status('Echo متصل · أهيّئ نموذج النداء', phase='off')
        self.device_state.setText('Echo Mira متصل · جارٍ تحديث حالة الميكروفون')
        self.speaker_volume.setEnabled(True)
        self.wake_threshold.setEnabled(True)

    def on_device_state(self,state):
        entity=self.bykey.get(state.key)
        if not entity:return
        name=entity.object_id
        if name=='speaker' and getattr(state,'volume',None) is not None:
            self.speaker_volume.setValue(round(state.volume*100))
        elif name=='wake_threshold_1' and getattr(state,'state',None) is not None:
            self.wake_threshold.setValue(round(state.state*100))
        elif name=='mic_mute':
            muted=bool(state.state)
            self.device_state.setText('ميكروفون Echo مكتوم من الجهاز' if muted else 'ميكروفون Echo مفتوح')
            if muted:self.orb.set_phase('off')

    def on_device_error(self, err):
        self.connection_dot.setText('○ غير متصل')
        self.connection_dot.setStyleSheet('color:#EF4444;')
        self.dock_sub.setText("○ غير متصل")
        self.dock_sub.setStyleSheet("color:#EF4444;")
        self.voice_bar.set_status("تعذّر الاتصال بجهاز الصوت", phase='error')
        self.device_state.setText('Echo غير متصل · '+err)
        self.speaker_volume.setEnabled(False)
        self.wake_threshold.setEnabled(False)

    def on_device_command_state(self, kind, status):
        if kind == 'wake': print('Mira wake command:',status.split(':',1)[0],flush=True)
        if status.startswith('error:'):
            self.wake_request_seq += 1
            self._add_chat_msg('error', 'لم يصل الأمر إلى Echo · ' + status.split(':',1)[1])
            self.voice_bar.set_status('تعذّر إرسال طلب الاستماع', phase='error')
        elif kind == 'wake' and status == 'sent':
            self.voice_bar.set_status('أُرسل طلب الاستماع إلى Echo · بانتظار استجابته', phase='ready')

    def on_voice_state(self, kind, text):
        if kind in ('activating','listening','thinking','executing','speaking','ready','off','error'):
            print('Mira voice state:',kind,flush=True)
        if kind == 'level':
            self.orb.level = float(text)
            self.voice_bar.level=self.orb.level
            self.voice_bar.update()
            self.dock_wave.level = self.orb.level
            self.dock_wave.update()
            if self.orb.isVisible(): self.orb.update()
        elif kind == 'activating':
            self.wake_request_seq += 1
            self.device_state.setText('Echo التقط النداء · '+datetime.now().strftime('%H:%M:%S'))
            self.voice_bar.set_status('Echo استجاب · أهيّئ المحادثة الصوتية…', phase='thinking')
            self.orb.set_phase('thinking')
            self.voice_phase='thinking'
        elif kind == 'listening':
            self.wake_request_seq += 1
            self.device_state.setText('التقط Echo النداء · '+datetime.now().strftime('%H:%M:%S'))
            self.voice_bar.set_status("أستمع إليك الآن...", phase='listening')
            self.orb.set_phase('listening')
            self.voice_phase='listening'
        elif kind == 'thinking':
            self.voice_bar.set_status("أفكر في الإجابة...", phase='thinking')
            self.orb.set_phase('thinking')
            self.voice_phase='thinking'
        elif kind == 'executing':
            self.voice_bar.set_status('أنفّذ الطلب وأتحقق منه…',phase='executing')
            self.orb.set_phase('executing')
            self.voice_phase='executing'
        elif kind == 'speaking':
            self.voice_bar.set_status("ميرا تتحدث...", phase='speaking')
            self.orb.set_phase('speaking')
            self.voice_phase='speaking'
        elif kind == 'heard':
            self._add_chat_msg('user',text)
        elif kind == 'reply':
            self._add_chat_msg('mira', text)
        elif kind == 'action':
            self._add_chat_msg('action',text)
        elif kind == 'stats':
            try:
                stats=json.loads(text)
                received=int(stats.get('microphone_bytes') or 0)
                peak=int(stats.get('microphone_peak') or 0)
                answered=int(stats.get('reply_bytes') or 0)
                heard=bool(stats.get('heard'))
                print(f'Mira voice result: mic_bytes={received} peak={peak} '
                      f'heard={heard} reply_bytes={answered}',flush=True)
                if received == 0:
                    self.voice_bar.set_status('لم يصل صوت من Echo · افحص ميكروفون الجهاز',phase='ready')
                elif not heard and not answered:
                    self.voice_bar.set_status('وصل صوت لكن لم يُفهم السؤال · تكلم بعد ظهور «أستمع» قرب Echo',phase='ready')
                elif heard and not answered:
                    self.voice_bar.set_status('فهمت السؤال لكن لم يصل جواب صوتي · أعد المحاولة',phase='ready')
            except (ValueError,TypeError):
                pass
        elif kind == 'ready':
            label=('الصوت بالزر جاهز · النداء المحلي قيد الاختبار'
                   if self.local_wake_enabled else 'الصوت بالزر جاهز · النداء المحلي متوقف')
            self.voice_bar.set_status(label, phase='ready')
            self.orb.set_phase('ready')
            self.voice_phase='ready'
        elif kind in ('off','error'):
            self.wake_request_seq += 1
            self.voice_phase=kind
            self.voice_bar.set_status('المحادثة الصوتية متوقفة' if kind=='off' else 'تعذّر الصوت: '+text,phase=kind)
            self.orb.set_phase(kind)
            if kind=='error':self._add_chat_msg('error','تعذّر الصوت: '+text)
        self.device_voice_toggle.setText('تشغيل المحادثة الصوتية' if self.voice_phase in ('off','error') else 'إيقاف المحادثة الصوتية')
        self.stop_btn.setEnabled(self.voice_phase in ('listening','thinking','executing','speaking'))

    def on_chat_reply(self, text):
        self._add_chat_msg('mira', text)

    def on_chat_error(self, err):
        self._add_chat_msg('mira', f"عذراً: {err}")

    def dock_result(self, data):
        if 'error' in data:
            self._add_chat_msg('error', data['error'])
        elif 'dispatch' in data and data['dispatch']:
            res = data['dispatch']
            status=res['result'].get('status','error')
            self._add_chat_msg('action' if status=='ok' else 'error', res['message'])
            if res.get('kind')=='home':self.home_jobs.run()
        elif 'dispatch' in data:
            self.chat_bridge.ask(data['text'])

    def tap_to_talk(self):
        if self.bridge.online and self.voice_phase not in ('off','error'):
            self.wake_request_seq += 1
            attempt = self.wake_request_seq
            self.voice_bar.set_status('أطلب من Echo بدء الاستماع…', phase='ready')
            self.bridge.command('wake', 'wake_assistant_1')
            QTimer.singleShot(18000, lambda:self._wake_timeout(attempt))
        else:self._add_chat_msg('error','المحادثة الصوتية غير جاهزة؛ افحص Echo أو شغّلها من الإعدادات.')

    def set_local_wake(self, enabled):
        self.local_wake_enabled = enabled
        self.settings.setValue('local_wake_enabled', enabled)
        if enabled:self.start_local_wake()
        else:self.stop_local_wake()

    def available_microphones(self):
        fallback='alsa_input.usb-Linux_Foundation_Webcam_gadget-02.mono-fallback'
        if os.environ.get('MIRA_TEST_MODE')=='1':return [fallback]
        try:
            result=subprocess.run(['pactl','list','short','sources'],capture_output=True,
                                  text=True,timeout=3,check=True)
            sources=[line.split('\t')[1] for line in result.stdout.splitlines()
                     if len(line.split('\t'))>1 and '.monitor' not in line.split('\t')[1]]
            default=subprocess.run(['pactl','get-default-source'],capture_output=True,
                                   text=True,timeout=3,check=True).stdout.strip()
            return ([default]+[source for source in sources if source!=default]) if default in sources else (sources or [fallback])
        except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
            return [fallback]

    def select_mic_source(self, _index=None):
        source=self.mic_source_picker.currentData()
        if not source:return
        if source==self.settings.value('local_wake_source',''):return
        self.settings.setValue('local_wake_source',source)
        if self.local_wake_enabled:
            self.stop_local_wake()
            self.start_local_wake()

    def start_local_wake(self):
        if self.local_wake_process and self.local_wake_process.poll() is None:return
        worker_python=Path.home()/'.local/share/mira/wake-venv/bin/python'
        model=Path.home()/'.local/share/mira/wake-model'
        source=str(self.settings.value('local_wake_source','') or self.mic_source_picker.currentData() or
                   'alsa_input.usb-Linux_Foundation_Webcam_gadget-02.mono-fallback')
        if not worker_python.exists() or not (model/'model.bin').exists():
            self.local_wake_state.setText('النداء المحلي غير مثبت بعد')
            return
        try:
            self.local_wake_process=subprocess.Popen(
                [str(worker_python),str(ROOT/'local_wake.py'),'--model',str(model),
                 '--source',source,'--parent-pid',str(os.getpid()),'--uid',str(os.getuid())],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.local_wake_state.setText('مستمع النداء بدأ · بانتظار وصول صوت')
            QTimer.singleShot(5000,self.check_local_wake)
        except OSError as exc:
            self.local_wake_state.setText('تعذّر تشغيل النداء المحلي · '+type(exc).__name__)

    def check_local_wake(self):
        worker=self.local_wake_process
        if not self.local_wake_enabled:return
        if worker and worker.poll() is not None:
            self.local_wake_state.setText('توقّف مستمع النداء المحلي؛ افحص الميكروفون')
            return
        try:
            health=json.loads(Path(f'/run/user/{os.getuid()}/mira-wake-health.json').read_text())
            if time.time()-health.get('at',0)>10:
                label='الميكروفون متصل لكن لم تصل إطارات حديثة'
            elif time.time()-health.get('last_match_at',0)<30:
                label='التقطت «ميرا» وأرسلت طلب الاستماع إلى Echo'
            elif health.get('last_result')=='wake_match':
                label='طابق المستمع اسم ميرا وأرسل طلب الاستماع'
            elif health.get('last_result')=='not_matched':
                label='وصل صوت لكن لم يُطابق اسم ميرا · اقترب من ميكروفون الكمبيوتر'
            elif health.get('frames',0)>0:
                label='ميكروفون الكمبيوتر يرسل صوتاً · بانتظار «ميرا»'
            else:
                label='ميكروفون الكمبيوتر متصل · بانتظار الصوت'
            self.local_wake_state.setText(label)
        except (OSError,ValueError,TypeError):
            self.local_wake_state.setText('أتحقق من ميكروفون الكمبيوتر…')
        QTimer.singleShot(5000,self.check_local_wake)

    def handle_instance_command(self, command):
        if command==b'wake':
            print('Mira wake source: local microphone',flush=True)
            if self.local_wake_enabled and self.voice_phase=='ready':
                self.showNormal()
                self.raise_()
                self.activateWindow()
                self.tap_to_talk()
        elif command==b'show':
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def stop_local_wake(self):
        worker=self.local_wake_process
        self.local_wake_process=None
        if worker and worker.poll() is None:worker.terminate()
        self.local_wake_state.setText('النداء المحلي متوقف')

    def _wake_timeout(self, attempt):
        if attempt != self.wake_request_seq or self.voice_phase in ('listening','thinking','speaking','executing'):
            return
        self.voice_bar.set_status('Echo لم يؤكد بدء الاستماع', phase='error')
        self._add_chat_msg('error','لم يبدأ Echo الاستماع بعد طلب الميكروفون. افحص اتصال الجهاز ثم أعد المحاولة.')

    def submit_suggestion(self, text):
        self._send_command(text)

    def _send_command(self,text):
        self._add_chat_msg('user',text)
        self.command_bridge.run(text)

    def attach_text(self):
        path,_=QFileDialog.getOpenFileName(self,'إرفاق ملف نصي',str(Path.home()),'Text files (*.txt *.md *.json *.csv *.log)')
        if not path:return
        try:
            data=Path(path)
            if data.stat().st_size>12000:raise ValueError('الملف النصي كبير؛ الحد 12 KB')
            content=data.read_text(encoding='utf-8')
            if '\x00' in content:raise ValueError('الملف ليس نصاً')
            self.chat_input.setText((self.chat_input.text()+'\n'+content).strip())
            self._add_chat_msg('action','أُرفق نص '+data.name+' · يُرسل عند الضغط على Enter')
        except (OSError,UnicodeError,ValueError) as exc:
            self._add_chat_msg('error',str(exc))


# ─── Application Main ───────────────────────────────────────────────
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName('Mira')
    app.setDesktopFileName('mira')

    socket_name = f'mo-dot-desktop-{os.getuid()}'
    existing = QLocalSocket()
    existing.connectToServer(socket_name)
    if existing.waitForConnected(300):
        existing.write(b'show')
        existing.waitForBytesWritten(300)
        sys.exit(0)

    QLocalServer.removeServer(socket_name)
    instance = QLocalServer()
    instance.listen(socket_name)
    os.chmod('/tmp/'+socket_name,0o600)

    server = HTTPServer(('0.0.0.0', 18769), ToneServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    app.setStyle('Fusion')
    app.setStyleSheet(build_stylesheet())

    window = Window()
    window.show()

    def activate():
        conn = instance.nextPendingConnection()
        if not conn:return
        def receive():
            command=bytes(conn.readAll()).strip()
            window.handle_instance_command(command)
            conn.disconnectFromServer()
        conn.readyRead.connect(receive)
    instance.newConnection.connect(activate)
    if window.local_wake_enabled and '--capture' not in sys.argv:window.start_local_wake()
    app.aboutToQuit.connect(window.stop_local_wake)

    if '--live-snapshot' in sys.argv:
        QTimer.singleShot(6000, lambda: window.grab().save(str(ROOT / 'desktop.png')))
    if '--capture' in sys.argv:
        QTimer.singleShot(6000, lambda: (window.grab().save(str(ROOT / 'desktop.png')), app.quit()))

    sys.exit(app.exec())
