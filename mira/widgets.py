"""
Mira Neural OS — High-End Custom Widgets
Pixel-perfect futuristic widgets matching the reference design.
"""
import math
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QFrame, QPushButton, QLabel, QVBoxLayout, QHBoxLayout,
    QSizePolicy, QGridLayout, QLineEdit, QScrollArea
)
from PySide6.QtGui import (
    QPainter, QColor, QPainterPath, QPen, QBrush, QFont, QRadialGradient,
    QLinearGradient, QPixmap, QIcon
)
from PySide6.QtCore import (
    Qt, QRect, QRectF, QTimer, QDateTime, QLocale, QPointF, Signal
)

# ─── Color Palette ──────────────────────────────────────────────────
BG_GLASS = QColor(14, 20, 46, 210)
BORDER_GLASS = QColor(66, 120, 240, 50)
BORDER_ACTIVE = QColor(0, 229, 255, 120)

NEON_CYAN = QColor(0, 229, 255)
NEON_VIOLET = QColor(168, 85, 247)
NEON_ROSE = QColor(255, 77, 171)
STATUS_GREEN = QColor(0, 255, 136)
STATUS_GRAY = QColor(100, 116, 139)

TEXT_PRIMARY = QColor(245, 248, 255)
TEXT_SECONDARY = QColor(140, 155, 185)


# ─── 1. Glass Card Frame ────────────────────────────────────────────
class GlassCard(QFrame):
    """Futuristic semi-transparent card with subtle glowing border."""
    def __init__(self, radius=18, parent=None):
        super().__init__(parent)
        self.radius = radius
        self.setAttribute(Qt.WA_Hover)
        self._hover = False

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)

        # Gradient dark glass
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, QColor(16, 24, 52, 230))
        grad.setColorAt(1, QColor(10, 15, 36, 240))
        p.fillPath(path, grad)

        # Border
        border_col = QColor(0, 229, 255, 90) if self._hover else BORDER_GLASS
        p.setPen(QPen(border_col, 1.2))
        p.drawPath(path)


# ─── 2. Weather & Clock Card (Robust Layout) ────────────────────────
class WeatherClockCard(QFrame):
    """Clean 2-column card with live clock on left and weather telemetry on right."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(94)
        self.setStyleSheet("""
            WeatherClockCard {
                background: rgba(16, 24, 54, 0.92);
                border: 1px solid rgba(66, 120, 240, 0.28);
                border-radius: 16px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(8)

        # Left Column: Date & Clock
        left_col = QVBoxLayout()
        left_col.setSpacing(1)
        self.date_lbl = QLabel("")
        self.date_lbl.setFont(QFont("Noto Sans Arabic", 8))
        self.date_lbl.setStyleSheet("color: #8E9BB5;")
        left_col.addWidget(self.date_lbl)

        self.time_lbl = QLabel("")
        self.time_lbl.setFont(QFont("Noto Sans Arabic", 24, QFont.Bold))
        self.time_lbl.setStyleSheet("color: #FFFFFF;")
        left_col.addWidget(self.time_lbl)

        # Sub-status: system ready
        telemetry_lbl = QLabel("NEURAL // READY")
        telemetry_lbl.setFont(QFont("Noto Sans Mono", 7))
        telemetry_lbl.setStyleSheet("color: #00E5FF; letter-spacing: 1px;")
        left_col.addWidget(telemetry_lbl)
        layout.addLayout(left_col, 1)

        # Subtle vertical separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("background: rgba(66, 120, 240, 0.25); width: 1px;")
        layout.addWidget(sep)

        # Right Column: City, Weather & Micro Telemetry
        right_col = QVBoxLayout()
        right_col.setSpacing(1)
        right_col.setAlignment(Qt.AlignRight)

        self.city_lbl = QLabel("الطقس")
        self.city_lbl.setFont(QFont("Noto Sans Arabic", 8))
        self.city_lbl.setStyleSheet("color: #8E9BB5;")
        self.city_lbl.setAlignment(Qt.AlignRight)
        right_col.addWidget(self.city_lbl)

        temp_row = QHBoxLayout()
        temp_row.setSpacing(6)
        temp_row.setAlignment(Qt.AlignRight)
        self.weather_icon = QLabel("○")
        self.weather_icon.setFont(QFont("Noto Sans Arabic", 14))
        self.temp_lbl = QLabel("—°")
        self.temp_lbl.setFont(QFont("Noto Sans Arabic", 16, QFont.Bold))
        self.temp_lbl.setStyleSheet("color: #FFFFFF;")
        temp_row.addWidget(self.weather_icon)
        temp_row.addWidget(self.temp_lbl)
        right_col.addLayout(temp_row)

        self.desc_lbl = QLabel("حدّد المدينة من الإعدادات")
        self.desc_lbl.setFont(QFont("Noto Sans Arabic", 8))
        self.desc_lbl.setStyleSheet("color: #8E9BB5;")
        self.desc_lbl.setAlignment(Qt.AlignRight)
        right_col.addWidget(self.desc_lbl)

        # Micro telemetry pills: humidity and wind
        micro_row = QHBoxLayout()
        micro_row.setSpacing(4)
        micro_row.setAlignment(Qt.AlignRight)
        self.humid_lbl = QLabel("💧 —")
        self.humid_lbl.setFont(QFont("Noto Sans Arabic", 7))
        self.humid_lbl.setStyleSheet("color: #8BD3E6; background: rgba(0,229,255,0.08); border-radius: 4px; padding: 1px 3px;")
        self.wind_lbl = QLabel("💨 —")
        self.wind_lbl.setFont(QFont("Noto Sans Arabic", 7))
        self.wind_lbl.setStyleSheet("color: #A855F7; background: rgba(168,85,247,0.08); border-radius: 4px; padding: 1px 3px;")
        micro_row.addWidget(self.humid_lbl)
        micro_row.addWidget(self.wind_lbl)
        right_col.addLayout(micro_row)

        layout.addLayout(right_col, 1)

        self.locale = QLocale(QLocale.Arabic, QLocale.SaudiArabia)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()

    def set_weather(self, temp_c, condition_ar, icon="🌤", city="", humidity=None, wind=None):
        self.city_lbl.setText(city)
        self.temp_lbl.setText(f"{round(float(temp_c))}°C")
        self.desc_lbl.setText(condition_ar)
        self.weather_icon.setText(icon)
        self.humid_lbl.setText(f"💧 {humidity or '—'}")
        self.wind_lbl.setText(f"💨 {wind or '—'}")

    def set_weather_error(self, message):
        self.weather_icon.setText("○")
        self.temp_lbl.setText("—°")
        self.desc_lbl.setText(message)
        self.humid_lbl.setText("💧 —")
        self.wind_lbl.setText("💨 —")

    def update_time(self):
        dt = QDateTime.currentDateTime()
        self.time_lbl.setText(dt.toString("HH:mm"))
        self.date_lbl.setText(self.locale.toString(dt.date(), "dddd d MMMM yyyy"))


# ─── 3. Device Item Card with Interactive Neon Toggle ───────────────
class DeviceItemCard(QPushButton):
    """Clickable card with icon box on left, text in middle, and interactive toggle switch on right."""
    toggle_requested = Signal(bool)

    def __init__(self, icon_str, title, subtitle, status_color=STATUS_GREEN, parent=None):
        super().__init__(parent)
        self.icon_str = icon_str
        self.title_text = title
        self.subtitle_text = subtitle
        self.status_color = status_color
        self.setFixedHeight(54)
        self.setCursor(Qt.PointingHandCursor)
        self.is_on = ('on' in subtitle.lower() or 'متاحة' in subtitle.lower() or 'مضاءة' in subtitle.lower())
        self.toggle_enabled = True

    def set_toggle_enabled(self, enabled):
        self.toggle_enabled = bool(enabled)
        self.update()

    def set_state(self, subtitle, status_color, is_on=None):
        self.subtitle_text = subtitle
        self.status_color = status_color
        self.is_on = bool(is_on) if is_on is not None else (
            'on' in subtitle.lower() or 'متاحة' in subtitle.lower() or 'مضاءة' in subtitle.lower() or status_color == STATUS_GREEN)
        self.update()

    def mousePressEvent(self, event):
        # If clicked on the toggle switch area (last 50 pixels)
        if self.toggle_enabled and event.pos().x() >= self.width() - 50:
            # The backend readback, not a click, owns the visible state.
            self.toggle_requested.emit(not self.is_on)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 13, 13)

        is_hover = self.underMouse()
        p.fillPath(path, QColor(25, 36, 76, 210) if is_hover else QColor(14, 20, 46, 180))
        p.setPen(QPen(QColor(0, 229, 255, 90) if is_hover else BORDER_GLASS, 1))
        p.drawPath(path)

        # Icon box on left
        icon_box = QRectF(10, 9, 36, 36)
        icon_path = QPainterPath()
        icon_path.addRoundedRect(icon_box, 9, 9)
        p.fillPath(icon_path, QColor(25, 38, 80, 160))
        p.setPen(QPen(QColor(60, 100, 200, 50), 1))
        p.drawPath(icon_path)

        p.setFont(QFont("Noto Sans Arabic", 14))
        p.setPen(TEXT_PRIMARY)
        p.drawText(icon_box, Qt.AlignCenter, self.icon_str)

        # Middle texts
        w = self.width()
        p.setFont(QFont("Noto Sans Arabic", 11, QFont.Bold))
        p.setPen(TEXT_PRIMARY)
        p.drawText(QRectF(54, 8, w - 105, 20), Qt.AlignLeft | Qt.AlignVCenter, self.title_text)

        p.setFont(QFont("Noto Sans Arabic", 9))
        p.setPen(TEXT_SECONDARY)
        p.drawText(QRectF(54, 28, w - 105, 18), Qt.AlignLeft | Qt.AlignVCenter, self.subtitle_text)

        # Right interactive toggle switch
        sw_w, sw_h = 36.0, 18.0
        sw_x = w - sw_w - 12.0
        sw_y = (self.height() - sw_h) / 2.0
        sw_rect = QRectF(sw_x, sw_y, sw_w, sw_h)
        sw_path = QPainterPath()
        sw_path.addRoundedRect(sw_rect, 9, 9)

        if self.is_on:
            # Active neon cyan/green track
            p.fillPath(sw_path, QColor(0, 229, 255, 60))
            p.setPen(QPen(QColor(0, 229, 255, 180), 1.2))
            p.drawPath(sw_path)
            # Knob on right
            knob_center = QPointF(sw_x + sw_w - 9.0, sw_y + 9.0)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 255, 136))
            p.drawEllipse(knob_center, 6.0, 6.0)
            p.setBrush(QColor(0, 255, 136, 60))
            p.drawEllipse(knob_center, 9.0, 9.0)
        else:
            # Inactive dark track
            p.fillPath(sw_path, QColor(20, 28, 55, 120))
            p.setPen(QPen(QColor(66, 120, 240, 50), 1.0))
            p.drawPath(sw_path)
            # Knob on left
            knob_center = QPointF(sw_x + 9.0, sw_y + 9.0)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(100, 116, 139))
            p.drawEllipse(knob_center, 5.0, 5.0)


# ─── 4. Quick Action Pill ───────────────────────────────────────────
class QuickPill(QPushButton):
    """Quick suggestion pill button with icon and label."""
    def __init__(self, icon_str, label, parent=None):
        super().__init__(parent)
        self.icon_str = icon_str
        self.label_text = label
        self.setFixedHeight(38)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        is_hover = self.underMouse()
        p.fillPath(path, QColor(25, 36, 75, 220) if is_hover else QColor(14, 20, 44, 180))
        p.setPen(QPen(QColor(0, 229, 255, 110) if is_hover else QColor(60, 100, 200, 40), 1))
        p.drawPath(path)

        p.setFont(QFont("Noto Sans Arabic", 11))
        p.setPen(TEXT_PRIMARY)
        p.drawText(QRectF(10, 0, 24, self.height()), Qt.AlignCenter, self.icon_str)

        p.setFont(QFont("Noto Sans Arabic", 10))
        p.setPen(TEXT_PRIMARY if is_hover else TEXT_SECONDARY)
        p.drawText(QRectF(38, 0, self.width() - 58, self.height()), Qt.AlignLeft | Qt.AlignVCenter, self.label_text)

        # Micro arrow indicator
        p.setFont(QFont("Noto Sans Mono", 10))
        p.setPen(QColor(0, 229, 255, 140 if is_hover else 50))
        p.drawText(QRectF(self.width() - 20, 0, 14, self.height()), Qt.AlignCenter, "›")


# ─── 5. Floating Action Tag with Laser Docking Port ─────────────────
class FloatingTag(QPushButton):
    """Pill tag with glowing icon that connects to the neural halo around Mira."""
    def __init__(self, icon_str, label, is_right=False, parent=None):
        super().__init__(parent)
        self.icon_str = icon_str
        self.label_text = label
        self.is_right = is_right
        self.setFixedHeight(38)
        self.setFixedWidth(128)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)

        is_hover = self.underMouse()
        p.fillPath(path, QColor(25, 36, 75, 230) if is_hover else QColor(14, 20, 48, 200))
        border_col = QColor(0, 229, 255, 160) if is_hover else QColor(100, 140, 240, 70)
        p.setPen(QPen(border_col, 1.2))
        p.drawPath(path)

        # Icon box
        icon_box = QRectF(6, 5, 28, 28)
        ib_path = QPainterPath()
        ib_path.addRoundedRect(icon_box, 8, 8)
        p.fillPath(ib_path, QColor(0, 229, 255, 30) if is_hover else QColor(20, 28, 60, 140))
        p.setFont(QFont("Noto Sans Arabic", 12))
        p.setPen(NEON_CYAN if is_hover else QColor(168, 85, 247))
        p.drawText(icon_box, Qt.AlignCenter, self.icon_str)

        # Text
        p.setFont(QFont("Noto Sans Arabic", 10, QFont.DemiBold))
        p.setPen(TEXT_PRIMARY if is_hover else QColor(225, 235, 255))
        p.drawText(QRectF(38, 0, self.width() - 44, self.height()), Qt.AlignLeft | Qt.AlignVCenter, self.label_text)

        # Laser docking socket dot on inner side
        dock_x = 2.0 if self.is_right else (self.width() - 2.0)
        dock_y = self.height() / 2.0
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 229, 255, 220 if is_hover else 120))
        p.drawEllipse(QPointF(dock_x, dock_y), 2.5, 2.5)


# ─── 6. Center Voice Waveform Bar ───────────────────────────────────
class CenterVoiceBar(QWidget):
    """The glowing pill status bar beneath Mira's face with animated waveform."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.status_text = "جارٍ الاتصال بجهاز ميرا…"
        self.level = 0.0
        self.phase = 'ready'
        self.phase_step = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def _tick(self):
        self.phase_step = (self.phase_step + 0.15) % (2 * math.pi)
        self.update()

    def set_status(self, text, phase='ready'):
        self.status_text = text
        self.phase = phase
        if phase in ('listening', 'thinking', 'speaking', 'executing'):
            self.timer.start(80)
        else:
            self.timer.stop()
            self.phase_step = 0.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 22, 22)

        grad = QLinearGradient(0, 0, rect.width(), 0)
        grad.setColorAt(0, QColor(15, 24, 58, 230))
        grad.setColorAt(0.5, QColor(25, 32, 70, 240))
        grad.setColorAt(1, QColor(15, 24, 58, 230))
        p.fillPath(path, grad)

        phase_colors = {
            'ready': QColor(0, 229, 255),
            'listening': QColor(0, 255, 136),
            'thinking': QColor(168, 85, 247),
            'executing': QColor(139, 92, 246),
            'speaking': QColor(255, 77, 171),
            'error': QColor(239, 68, 68),
            'off': QColor(100, 116, 139)
        }
        theme_col = phase_colors.get(self.phase, QColor(0, 229, 255))

        p.setPen(QPen(QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 120), 1.4))
        p.drawPath(path)

        # Animated 16 wave bars with phase coloring
        wave_cx = 42
        num_bars = 16
        for i in range(num_bars):
            activity = (self.level if self.phase in ('listening', 'speaking') else 0.45 if self.phase in ('thinking', 'executing') else 0.05)
            h = 3.0 + 17.0 * activity * abs(math.sin(self.phase_step + i * 0.4)) * math.exp(-((i - num_bars / 2) / 4.5) ** 2)
            px = wave_cx + (i - num_bars / 2) * 4.0
            p.setPen(QPen(theme_col, 2.0, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(px, self.height() / 2 - h / 2), QPointF(px, self.height() / 2 + h / 2))

        # Status text
        p.setFont(QFont("Noto Sans Arabic", 12, QFont.DemiBold))
        p.setPen(TEXT_PRIMARY)
        text_rect = QRectF(85, 0, rect.width() - 130, self.height())
        p.drawText(text_rect, Qt.AlignCenter, self.status_text)

        # Pulse dots on right
        right_cx = rect.width() - 36
        for i in range(3):
            dot_x = right_cx + (i - 1) * 8
            dot_a = int(120 + 130 * math.sin(self.phase_step + i * 0.8))
            p.setBrush(QColor(theme_col.red(), theme_col.green(), theme_col.blue(), max(40, min(255, dot_a))))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(dot_x, self.height() / 2), 2.4, 2.4)


# ─── 7. Dock Category Tab ───────────────────────────────────────────
class DockTabButton(QPushButton):
    """Icon on top, label on bottom with glowing active state."""
    def __init__(self, icon_str, label_str, parent=None):
        super().__init__(parent)
        self.icon_str = icon_str
        self.label_str = label_str
        self.setCheckable(True)
        self.setFixedSize(68, 54)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)

        is_checked = self.isChecked()
        is_hover = self.underMouse()

        if is_checked:
            p.fillPath(path, QColor(0, 229, 255, 30))
            p.setPen(QPen(QColor(0, 229, 255, 130), 1.2))
        elif is_hover:
            p.fillPath(path, QColor(25, 35, 75, 180))
            p.setPen(QPen(BORDER_GLASS, 1))
        else:
            p.fillPath(path, QColor(14, 20, 44, 120))
            p.setPen(QPen(QColor(60, 100, 200, 30), 1))
        p.drawPath(path)

        p.setFont(QFont("Noto Sans Arabic", 14))
        p.setPen(NEON_CYAN if is_checked else (TEXT_PRIMARY if is_hover else TEXT_SECONDARY))
        p.drawText(QRectF(0, 6, self.width(), 24), Qt.AlignCenter, self.icon_str)

        p.setFont(QFont("Noto Sans Arabic", 9))
        p.setPen(TEXT_PRIMARY if is_checked else TEXT_SECONDARY)
        p.drawText(QRectF(0, 32, self.width(), 16), Qt.AlignCenter, self.label_str)


# ─── 8. Rich Chat Message Cards ─────────────────────────────────────
class ChatTVCard(QFrame):
    """Interactive TV card in the conversation feed with power button."""
    power_toggled = Signal()

    def __init__(self, name="Samsung TV", is_on=True, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self.name = name
        self.is_on = is_on

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(10)

        # Screen preview box
        screen_box = QFrame()
        screen_box.setFixedSize(48, 38)
        screen_box.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #1E3A8A, stop:1 #3B82F6);
                border: 1px solid rgba(0, 229, 255, 0.4);
                border-radius: 8px;
            }
        """)
        s_layout = QVBoxLayout(screen_box)
        s_layout.setContentsMargins(0, 0, 0, 0)
        tv_ic = QLabel("📺")
        tv_ic.setAlignment(Qt.AlignCenter)
        tv_ic.setFont(QFont("Noto Sans Arabic", 14))
        s_layout.addWidget(tv_ic)
        layout.addWidget(screen_box)

        # TV Details
        info_col = QVBoxLayout()
        info_col.setSpacing(1)
        name_l = QLabel(name)
        name_l.setFont(QFont("Noto Sans Arabic", 10, QFont.Bold))
        name_l.setStyleSheet("color: #FFFFFF;")
        status_l = QLabel("متصل الآن ●" if is_on else "مطفأ ○")
        status_l.setFont(QFont("Noto Sans Arabic", 8))
        status_l.setStyleSheet("color: #00E5FF;" if is_on else "color: #8E9BB5;")
        info_col.addWidget(name_l)
        info_col.addWidget(status_l)
        layout.addLayout(info_col, 1)

        # Power button on right
        self.pwr_btn = QPushButton("⏻")
        self.pwr_btn.setFixedSize(32, 32)
        self.pwr_btn.setCursor(Qt.PointingHandCursor)
        self.pwr_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.15);
                color: #00E5FF;
                border: 1px solid rgba(0, 229, 255, 0.5);
                border-radius: 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.35);
            }
        """)
        self.pwr_btn.clicked.connect(self.power_toggled.emit)
        layout.addWidget(self.pwr_btn)

        self.setStyleSheet("""
            ChatTVCard {
                background: rgba(14, 25, 55, 0.9);
                border: 1px solid rgba(0, 229, 255, 0.3);
                border-radius: 12px;
            }
        """)


class ChatWeatherCard(QFrame):
    """Rich interactive weather forecast card."""
    def __init__(self, temp="16°C", desc="غائم جزئياً", rain="20%", max_temp="18°", min_temp="10°", parent=None):
        super().__init__(parent)
        self.setFixedHeight(82)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        icon = QLabel("🌤")
        icon.setFont(QFont("Noto Sans Arabic", 20))
        top_row.addWidget(icon)

        temp_lbl = QLabel(f"{temp} · {desc}")
        temp_lbl.setFont(QFont("Noto Sans Arabic", 11, QFont.Bold))
        temp_lbl.setStyleSheet("color:#FFF;")
        top_row.addWidget(temp_lbl, 1)

        rain_lbl = QLabel(f"أمطار {rain}")
        rain_lbl.setFont(QFont("Noto Sans Arabic", 9))
        rain_lbl.setStyleSheet("color:#00E5FF; background:rgba(0,229,255,0.1); border-radius:6px; padding:2px 6px;")
        top_row.addWidget(rain_lbl)
        layout.addLayout(top_row)

        details = QLabel(f"العظمى: {max_temp}   |   الصغرى: {min_temp}")
        details.setFont(QFont("Noto Sans Arabic", 9))
        details.setStyleSheet("color:#8B9CC0;")
        layout.addWidget(details)

        self.setStyleSheet("""
            ChatWeatherCard {
                background: rgba(14, 25, 55, 0.9);
                border: 1px solid rgba(168, 85, 247, 0.3);
                border-radius: 12px;
            }
        """)
