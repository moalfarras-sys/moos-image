"""
Mira Neural OS — Futuristic Sci-Fi Core & Holographic Face Widget
Silky-smooth 30 FPS HUD animations, rotating concentric rings, glowing connector vectors,
breathing energy field, and particle constellation. Preserves both Rose and Holo faces.
"""
import math
import random
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QVariantAnimation, Signal, QPointF, QRectF, QObject
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QRadialGradient, QLinearGradient,
    QPen, QBrush, QFont, QPainterPath
)

ROOT = Path(__file__).parent


class NeuralCanvas(QWidget):
    """Living cosmic background with pre-cached nebula grid and drifting cyber star motes."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._step = 0.0
        self._stars = []
        self._bg_cache = None
        rnd = random.Random(1337)
        for _ in range(35):
            self._stars.append({
                'x': rnd.random(),
                'y': rnd.random(),
                'speed': rnd.uniform(0.0004, 0.0014),
                'size': rnd.uniform(1.2, 2.4),
                'alpha': rnd.randint(70, 180),
                'phase': rnd.uniform(0, 6.28)
            })
        self._timer = QTimer(self)
        self._timer.setInterval(40)  # Smooth 25 FPS
        self._timer.timeout.connect(self._animate_bg)
        self._timer.start()

    def resizeEvent(self, event):
        self._bg_cache = None
        super().resizeEvent(event)

    def _animate_bg(self):
        if not self.isVisible():
            return
        self._step += 0.02
        for star in self._stars:
            star['y'] -= star['speed']
            if star['y'] < 0:
                star['y'] = 1.0
                star['x'] = random.random()
        self.update()

    def _render_bg_cache(self, w, h):
        pix = QPixmap(w, h)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        # 1. Deep cosmic void gradient
        grad = QRadialGradient(w * 0.5, h * 0.45, max(w, h) * 0.75)
        grad.setColorAt(0.0, QColor(28, 14, 48))    # soft glowing violet core
        grad.setColorAt(0.35, QColor(10, 16, 42))  # deep cyber navy
        grad.setColorAt(0.75, QColor(6, 9, 24))    # cosmic black-blue
        grad.setColorAt(1.0, QColor(4, 5, 14))     # deepest space void
        p.fillRect(QRectF(0, 0, w, h), grad)

        # 2. Subtle sci-fi grid lines
        p.setPen(QPen(QColor(60, 110, 220, 12), 1))
        grid_size = 48
        for x in range(0, w, grid_size):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, grid_size):
            p.drawLine(0, y, w, y)

        p.end()
        return pix

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        if self._bg_cache is None or self._bg_cache.width() != w or self._bg_cache.height() != h:
            self._bg_cache = self._render_bg_cache(w, h)

        p.drawPixmap(0, 0, self._bg_cache)

        # Drifting star particles
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        for star in self._stars:
            pulse = (math.sin(self._step * 1.5 + star['phase']) + 1) * 0.5
            alpha = int(star['alpha'] * (0.6 + 0.4 * pulse))
            p.setBrush(QColor(0, 229, 255, alpha))
            px = star['x'] * w
            py = star['y'] * h
            p.drawEllipse(QPointF(px, py), star['size'], star['size'])


class Orb(QWidget):
    """Central interactive face with rotating sci-fi HUD rings and energetic animations."""
    activated = Signal()
    face_toggle_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('face')
        self.setMinimumHeight(340)
        self.setCursor(Qt.PointingHandCursor)
        self.phase = 'ready'
        self.level = 0.0
        self.motion = True

        # ─── PRESERVE: Verified Sprite Loading ───────────────────────
        sheet = QPixmap(str(ROOT / 'mira-holo-moods-v1.png'))
        w = sheet.width() // 3
        h = sheet.height() // 2
        holo = [sheet.copy(x * w, y * h, w, h) for y in range(2) for x in range(3)]

        sheet = QPixmap(str(ROOT / 'mira-holo-moods-2-v1.png'))
        w = sheet.width() // 3
        h = sheet.height() // 2
        holo.extend(sheet.copy(x * w, y * h, w, h) for y in range(2) for x in range(3))

        sheet = QPixmap(str(ROOT / 'mira-holo-speech-v1.png'))
        w = sheet.width() // 3
        holo.extend(sheet.copy(x * w, 0, w, sheet.height()) for x in range(3))

        sheet = QPixmap(str(ROOT / 'mira-rose-frames-v3.png'))
        w = sheet.width() // 2
        h = sheet.height() // 2
        rose = [sheet.copy(x * w, y * h, w, h) for y in range(2) for x in range(2)]

        for filename in ('mira-expressions-a.png', 'mira-expressions-b.png'):
            sheet = QPixmap(str(ROOT / filename))
            w = sheet.width() // 3
            h = sheet.height() // 2
            rose.extend(sheet.copy(x * w, y * h, w, h) for y in range(2) for x in range(3))

        self.frames_by_style = {'holo': holo, 'rose': rose}
        self.indices_by_style = {
            'holo': {
                'neutral': 0, 'happy': 0, 'excited': 1, 'curious': 2, 'attentive': 3,
                'sad': 4, 'annoyed': 5, 'playful': 6, 'thinking': 7, 'surprised': 8,
                'proud': 9, 'reassuring': 10, 'sleepy': 11, 'blink': 12,
                'speaking_round': 13, 'speaking_open': 14
            },
            'rose': {
                name: i for i, name in enumerate((
                    'neutral', 'speaking_open', 'speaking_round', 'blink', 'happy',
                    'excited', 'playful', 'thinking', 'sad', 'annoyed', 'attentive',
                    'surprised', 'reassuring', 'curious', 'proud', 'sleepy'
                ))
            }
        }

        self.face_style = 'rose'
        self.frames = rose
        self.indices = self.indices_by_style['rose']
        self.emotion = 'neutral'
        self.previous_frame = 0
        self.cache = {}
        self.blinking = False

        # Smooth animation clock
        self.hud_step = 0.0
        self.hud_angle = 0.0
        self._last_geom = None
        self._connector_paths_left = []
        self._connector_paths_right = []
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(40)  # Smooth 25 FPS
        self.anim_timer.timeout.connect(self._tick)
        self.anim_timer.start()

        # Blink timer
        self.blink_timer = QTimer(self)
        self.blink_timer.setSingleShot(True)
        self.blink_timer.timeout.connect(self._blink)
        self._schedule_blink()

        # Crossfade animation
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(240)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.valueChanged.connect(lambda v: self.update())

        # Cosmic Particles
        self._particles = []
        rnd = random.Random(42)
        for _ in range(24):
            self._particles.append({
                'speed': rnd.uniform(0.4, 1.8),
                'offset': rnd.uniform(0, 6.28),
                'dist_add': rnd.uniform(25, 75),
                'alpha': rnd.randint(110, 240),
                'size': rnd.uniform(1.5, 3.2),
                'dir': 1 if rnd.random() > 0.5 else -1
            })

        # Holographic Scanner & Interactive Shockwave Ripples
        self.scan_y = 0.0
        self.scan_dir = 1.0
        self.ripples = []
        self.setMouseTracking(True)
        self.hover_offset = QPointF(0.0, 0.0)

    def _schedule_blink(self):
        if self.motion:
            self.blink_timer.start(random.randint(2800, 6500))

    def _blink(self):
        if self.motion and self.isVisible():
            self.blinking = True
            self.update()
            QTimer.singleShot(180, self._end_blink)
        self._schedule_blink()

    def _end_blink(self):
        self.blinking = False
        self.update()

    def mouseMoveEvent(self, e):
        w, h = self.width(), self.height()
        cx, cy = w / 2, h * 0.46
        dx = (e.position().x() - cx) / (w / 2) if w else 0
        dy = (e.position().y() - cy) / (h / 2) if h else 0
        self.hover_offset = QPointF(max(-6.0, min(6.0, dx * 6.0)), max(-5.0, min(5.0, dy * 5.0)))
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self.hover_offset = QPointF(0.0, 0.0)
        super().leaveEvent(e)

    def _tick(self):
        if not self.isVisible():
            return
        # Dynamic rotation speed based on state
        speed = 0.6
        if self.phase in ('listening', 'speaking'):
            speed = 1.4 + self.level * 2.5
        elif self.phase == 'thinking':
            speed = 2.2
        elif self.phase in ('off', 'error'):
            speed = 0.2

        self.hud_angle = (self.hud_angle + speed) % 360.0
        self.hud_step += 0.05

        # Advance Holographic Scanline
        self.scan_y += 0.016 * self.scan_dir
        if self.scan_y >= 1.0:
            self.scan_y = 1.0
            self.scan_dir = -1.0
        elif self.scan_y <= 0.0:
            self.scan_y = 0.0
            self.scan_dir = 1.0

        # Advance Interactive Ripples
        alive_ripples = []
        for r in self.ripples:
            r['radius'] += 3.8
            r['alpha'] = max(0, r['alpha'] - 9)
            if r['alpha'] > 0 and r['radius'] < r['max_radius']:
                alive_ripples.append(r)
        self.ripples = alive_ripples

        self.update()

    def mousePressEvent(self, e):
        w, h = self.width(), self.height()
        radius = min(w * 0.44, h * 0.56)
        self.ripples.append({
            'radius': 12.0,
            'max_radius': radius * 1.4,
            'alpha': 240,
            'width': 2.4
        })
        self.ripples.append({
            'radius': 2.0,
            'max_radius': radius * 1.15,
            'alpha': 180,
            'width': 1.6
        })
        self.activated.emit()
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        w, h = self.width(), self.height()
        radius = min(w * 0.44, h * 0.56)
        self.ripples.append({
            'radius': 16.0,
            'max_radius': radius * 1.6,
            'alpha': 255,
            'width': 3.2
        })
        self.face_toggle_requested.emit()
        super().mouseDoubleClickEvent(e)

    def set_emotion(self, name):
        if name not in self.indices: return
        if name == self.emotion: return
        self.previous_frame = self.indices[self.emotion]
        self.emotion = name
        if self.motion and self.isVisible():
            self.anim.start()
        self.update()

    def set_face_style(self, style):
        if style not in self.frames_by_style: return
        self.face_style = style
        self.frames = self.frames_by_style[style]
        self.indices = self.indices_by_style[style]
        self.previous_frame = self.indices.get(self.emotion, 0)
        self.cache.clear()
        self.update()

    def set_phase(self, phase):
        self.previous_frame = self.indices.get(self.emotion, 0)
        self.phase = phase
        if phase == 'listening': self.emotion = 'attentive'
        elif phase == 'thinking': self.emotion = 'thinking'
        elif phase == 'executing': self.emotion = 'proud'
        elif phase == 'error': self.emotion = 'sad'
        elif phase == 'off': self.emotion = 'sleepy'
        elif phase == 'ready' and self.emotion in ('attentive', 'sleepy', 'sad', 'thinking', 'proud'):
            self.emotion = 'neutral'
        if self.motion and self.isVisible():
            self.anim.start()
        else:
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        center = QPointF(w / 2, h * 0.46)
        radius = min(w * 0.44, h * 0.56)

        # Phase color themes adapted to face style
        if self.face_style == 'rose':
            color_map = {
                'ready': QColor(255, 77, 171),       # Hot Holographic Rose
                'listening': QColor(0, 255, 180),   # Neon Mint/Aqua
                'thinking': QColor(168, 85, 247),   # Electric Violet
                'executing': QColor(224, 36, 195),  # Neon Magenta
                'speaking': QColor(255, 110, 184),  # Soft Rose
                'error': QColor(239, 68, 68),       # Crimson
                'off': QColor(100, 116, 139)        # Slate Gray
            }
        else:
            color_map = {
                'ready': QColor(0, 229, 255),       # Cyber Neon Cyan
                'listening': QColor(0, 255, 180),   # Neon Mint/Aqua
                'thinking': QColor(168, 85, 247),   # Electric Violet
                'executing': QColor(139, 92, 246),  # Indigo
                'speaking': QColor(255, 77, 171),   # Hot Rose
                'error': QColor(239, 68, 68),       # Crimson
                'off': QColor(100, 116, 139)        # Slate Gray
            }
        theme_col = color_map.get(self.phase, QColor(0, 229, 255))

        # ─── 1. Breathing Aura Field ─────────────────────────────────
        pulse = (math.sin(self.hud_step * 1.2) + 1) * 0.5
        aura_rad = radius * (1.15 + 0.08 * pulse + self.level * 0.25)
        aura = QRadialGradient(center, aura_rad)
        c_core = QColor(theme_col)
        c_core.setAlpha(int(35 + 25 * pulse + self.level * 40))
        aura.setColorAt(0.0, c_core)
        aura.setColorAt(0.65, QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 12))
        aura.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), aura)

        # ─── 2. Face Portrait with Feathered Edges ───────────────────
        frame = self.indices.get(self.emotion, 0)
        if self.motion:
            if self.blinking:
                frame = self.indices['blink']
            elif self.phase == 'speaking':
                frame = self.indices['speaking_open'] if self.level > 0.4 else self.indices['speaking_round'] if self.level > 0.1 else frame

        def rendered(index):
            key = (int(w), int(h), index)
            if key not in self.cache:
                if len(self.cache) > 20: self.cache.clear()
                scale_factor = 1.08 if self.face_style == 'rose' else 1.02
                orig = self.frames[index].scaledToHeight(round(h * scale_factor), Qt.SmoothTransformation)
                feathered = QPixmap(orig.size())
                feathered.fill(Qt.transparent)
                mask = QPainter(feathered)
                mask.drawPixmap(0, 0, orig)
                mask.setCompositionMode(QPainter.CompositionMode_DestinationIn)
                edge = QLinearGradient(0, 0, orig.width(), 0)
                for pos, a in ((0, 0), (0.14, 255), (0.86, 255), (1, 0)):
                    edge.setColorAt(pos, QColor(255, 255, 255, a))
                mask.fillRect(feathered.rect(), edge)
                fade = QLinearGradient(0, 0, 0, orig.height())
                for pos, a in ((0, 0), (0.08, 255), (0.78, 255), (1, 0)):
                    fade.setColorAt(pos, QColor(255, 255, 255, a))
                mask.fillRect(feathered.rect(), fade)
                mask.end()
                self.cache[key] = feathered
            return self.cache[key]

        portrait = rendered(frame)
        drift_y = math.sin(self.hud_step * 0.8) * 3
        px = (w - portrait.width()) / 2
        py = (h - portrait.height()) / 2 + drift_y

        progress = float(self.anim.currentValue() or 0) if self.anim.state() == QVariantAnimation.Running else 1.0
        if progress < 1.0 and self.motion and self.previous_frame != frame:
            prev = rendered(self.previous_frame)
            p.setOpacity(1.0 - progress)
            p.drawPixmap(int((w - prev.width()) / 2), int((h - prev.height()) / 2 + drift_y), prev)
            p.setOpacity(progress)

        p.drawPixmap(int(px), int(py), portrait)
        p.setOpacity(1.0)

        # ─── 2.5 Holographic Laser Scanline Sweep ────────────────────
        scan_y_pos = center.y() - radius * 0.85 + (radius * 1.7 * self.scan_y)
        scan_w = radius * 0.9
        scan_grad = QLinearGradient(center.x() - scan_w, scan_y_pos, center.x() + scan_w, scan_y_pos)
        scan_grad.setColorAt(0.0, QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 0))
        scan_grad.setColorAt(0.2, QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 120))
        scan_grad.setColorAt(0.5, QColor(255, 255, 255, 200))
        scan_grad.setColorAt(0.8, QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 120))
        scan_grad.setColorAt(1.0, QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 0))
        p.setPen(QPen(QBrush(scan_grad), 1.6))
        p.drawLine(QPointF(center.x() - scan_w, scan_y_pos), QPointF(center.x() + scan_w, scan_y_pos))

        # ─── 2.6 Expanding Interactive Shockwaves ────────────────────
        for r in self.ripples:
            p.setBrush(Qt.NoBrush)
            r_width = r.get('width', 2.0)
            p.setPen(QPen(QColor(theme_col.red(), theme_col.green(), theme_col.blue(), r['alpha']), r_width))
            p.drawEllipse(center, r['radius'], r['radius'])

        # ─── 3. Concentric Sci-Fi HUD Rings ──────────────────────────
        # Ring 1: Outer segmented radar arc (Clockwise)
        r_outer = radius + 12 + self.level * 18
        arc_box = QRectF(center.x() - r_outer, center.y() - r_outer, r_outer * 2, r_outer * 2)
        p.setBrush(Qt.NoBrush)
        pen_radar = QPen(QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 120), 1.8)
        pen_radar.setCapStyle(Qt.RoundCap)
        p.setPen(pen_radar)

        base_a = int(self.hud_angle * 16)
        for arc_start, arc_len in ((10, 60), (100, 45), (175, 70), (280, 50)):
            p.drawArc(arc_box, (base_a + arc_start * 16) % 5760, arc_len * 16)

        # Ring 2: Primary glowing halo with multi-layer neon blur
        for offset, alpha, thickness in ((0, 150, 2.5), (3, 75, 4.5), (8, 28, 8.0)):
            c_glow = QColor(theme_col)
            c_glow.setAlpha(int(alpha * (0.8 + 0.2 * pulse)))
            p.setPen(QPen(c_glow, thickness))
            p.drawEllipse(center, radius + offset, radius + offset)

        # Ring 3: Counter-rotating tech tick ring with Degree Markers
        r_ticks = radius + 22
        p.setPen(QPen(QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 90), 1.2))
        counter_a = -self.hud_angle * 0.75
        for deg in range(0, 360, 15):
            rad = math.radians(deg + counter_a)
            is_cardinal = deg % 90 == 0
            t_in = r_ticks
            t_out = r_ticks + (10 if is_cardinal else 7 if deg % 45 == 0 else 4)
            p.drawLine(
                QPointF(center.x() + math.cos(rad) * t_in, center.y() + math.sin(rad) * t_in),
                QPointF(center.x() + math.cos(rad) * t_out, center.y() + math.sin(rad) * t_out)
            )

        # ─── 3.5 Cyber Targeting Corner Brackets & Telemetry ─────────
        p.setFont(QFont("Noto Sans Mono", 7))
        is_focused = self.underMouse()
        b_alpha = 150 if is_focused else 75
        bracket_color = QColor(theme_col.red(), theme_col.green(), theme_col.blue(), b_alpha)
        p.setPen(QPen(bracket_color, 1.4 if is_focused else 1.2))
        b_len = 20 if is_focused else 16
        b_margin = radius + (25 if is_focused else 28)
        left_bx = center.x() - b_margin
        right_bx = center.x() + b_margin
        top_by = center.y() - b_margin * 0.9
        bot_by = center.y() + b_margin * 0.9

        # Top-Left Bracket & Sys tag
        p.drawLine(QPointF(left_bx, top_by + b_len), QPointF(left_bx, top_by))
        p.drawLine(QPointF(left_bx, top_by), QPointF(left_bx + b_len, top_by))
        tag_tl = "SYS::MIRA // ACTIVE" if is_focused else "SYS::MIRA // READY"
        p.drawText(QPointF(left_bx + 4, top_by - 4), tag_tl)

        # Top-Right Bracket & Sync tag
        p.drawLine(QPointF(right_bx, top_by + b_len), QPointF(right_bx, top_by))
        p.drawLine(QPointF(right_bx, top_by), QPointF(right_bx - b_len, top_by))
        tag_tr = "SYNC::100% [LOCK]" if is_focused else "SYNC::99.8%"
        p.drawText(QPointF(right_bx - (85 if is_focused else 70), top_by - 4), tag_tr)

        # Bottom-Left Bracket & Freq tag
        p.drawLine(QPointF(left_bx, bot_by - b_len), QPointF(left_bx, bot_by))
        p.drawLine(QPointF(left_bx, bot_by), QPointF(left_bx + b_len, bot_by))
        tag_bl = "CORE::5.2GHz [BOOST]" if is_focused else "CORE::4.8GHz"
        p.drawText(QPointF(left_bx + 4, bot_by + 12), tag_bl)

        # Bottom-Right Bracket & State tag
        p.drawLine(QPointF(right_bx, bot_by - b_len), QPointF(right_bx, bot_by))
        p.drawLine(QPointF(right_bx, bot_by), QPointF(right_bx - b_len, bot_by))
        tag_br = "NEURAL::TARGETED" if is_focused else "QUANTUM"
        p.drawText(QPointF(right_bx - (80 if is_focused else 60), bot_by + 12), tag_br)

        # ─── 4. Animated Laser Connector Lines to Capsules ───────────
        # Glowing cyber data lines leading out to left & right floating capsules
        p.setBrush(Qt.NoBrush)
        line_col = QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 55)
        p.setPen(QPen(line_col, 1.2, Qt.DashLine))

        geom_key = (int(w), int(h), int(radius), int(center.x()), int(center.y()))
        if self._last_geom != geom_key:
            self._last_geom = geom_key
            self._connector_paths_left = []
            left_targets_y = [h * 0.22, h * 0.38, h * 0.54, h * 0.70]
            for idx, ty in enumerate(left_targets_y):
                angle_left = math.pi + 0.35 - (idx * 0.22)
                orig_x = center.x() + math.cos(angle_left) * (radius + 24)
                orig_y = center.y() + math.sin(angle_left) * (radius + 24)
                target_x = 0.0
                path = QPainterPath()
                path.moveTo(orig_x, orig_y)
                mid_x = (orig_x + target_x) * 0.5
                path.cubicTo(mid_x, orig_y, mid_x, ty, target_x, ty)
                self._connector_paths_left.append(path)

            self._connector_paths_right = []
            right_targets_y = [h * 0.16, h * 0.30, h * 0.44, h * 0.58, h * 0.72]
            for idx, ty in enumerate(right_targets_y):
                angle_right = -0.35 + (idx * 0.18)
                orig_x = center.x() + math.cos(angle_right) * (radius + 24)
                orig_y = center.y() + math.sin(angle_right) * (radius + 24)
                target_x = float(w)
                path = QPainterPath()
                path.moveTo(orig_x, orig_y)
                mid_x = (orig_x + target_x) * 0.5
                path.cubicTo(mid_x, orig_y, mid_x, ty, target_x, ty)
                self._connector_paths_right.append(path)

        for idx, path in enumerate(self._connector_paths_left):
            p.drawPath(path)
            pulse_t = (self.hud_step * 0.8 + idx * 0.25) % 1.0
            pt = path.pointAtPercent(pulse_t)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 200))
            p.drawEllipse(pt, 2.5, 2.5)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(line_col, 1.2, Qt.DashLine))

        for idx, path in enumerate(self._connector_paths_right):
            p.drawPath(path)
            pulse_t = (self.hud_step * 0.75 + idx * 0.2) % 1.0
            pt = path.pointAtPercent(pulse_t)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 200))
            p.drawEllipse(pt, 2.5, 2.5)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(line_col, 1.2, Qt.DashLine))

        # ─── 5. Orbiting Particle Constellation & Neural Web ────────
        part_points = []
        for part in self._particles:
            angle = part['offset'] + (self.hud_angle * 0.02 * part['speed'] * part['dir'])
            dist = radius + part['dist_add'] + (math.sin(self.hud_step + part['offset']) * 8)
            px = center.x() + math.cos(angle) * dist
            py = center.y() + math.sin(angle) * dist
            part_points.append((px, py, part['size'], part['alpha']))

        # Draw faint cyber neural links between close particles
        for i in range(len(part_points)):
            x1, y1, _, _ = part_points[i]
            for j in range(i + 1, min(i + 6, len(part_points))):
                x2, y2, _, _ = part_points[j]
                d2 = (x1 - x2) ** 2 + (y1 - y2) ** 2
                if d2 < 2500:  # ~50px
                    alpha_link = int(40 * (1.0 - math.sqrt(d2) / 50.0))
                    p.setPen(QPen(QColor(theme_col.red(), theme_col.green(), theme_col.blue(), alpha_link), 0.9))
                    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        p.setPen(Qt.NoPen)
        for px, py, pr, p_alpha in part_points:
            part_color = QColor(theme_col)
            part_color.setAlpha(p_alpha)
            p.setBrush(part_color)
            p.drawEllipse(QPointF(px, py), pr, pr)


class DockWave(QWidget):
    """Dynamic multi-harmonic fluid audio waveform."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 36)
        self.level = 0.0
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        self._phase += 0.12
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cy = h / 2

        num_bars = 18
        bar_w = 3.5
        spacing = (w - (num_bars * bar_w)) / (num_bars - 1)

        for i in range(num_bars):
            norm_i = (i - num_bars / 2) / (num_bars / 2)
            env = math.exp(-3 * norm_i * norm_i)
            osc = math.sin(self._phase + i * 0.45)
            bh = 4.0 + (12.0 * env * abs(osc)) + (self.level * 18.0 * env)

            x = i * (bar_w + spacing)
            # Vibrant gradient from cyan to magenta
            frac = i / num_bars
            r = int(0 * (1 - frac) + 255 * frac)
            g = int(229 * (1 - frac) + 77 * frac)
            b = int(255 * (1 - frac) + 171 * frac)

            p.setPen(Qt.NoPen)
            p.setBrush(QColor(r, g, b, 210))
            rect = QRectF(x, cy - bh / 2, bar_w, bh)
            p.drawRoundedRect(rect, 1.5, 1.5)


class Gauge(QWidget):
    """Circular radial status meter."""
    def __init__(self, title, color='#6BD3EA'):
        super().__init__()
        self.title = title
        self.color = QColor(color)
        self.value = 0.0
        self.setMinimumSize(80, 80)

    def set_value(self, val):
        self.value = max(0.0, min(1.0, val))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height())
        rect = QRectF((self.width() - side) / 2 + 6, (self.height() - side) / 2 + 6, side - 12, side - 12)

        # Background track
        p.setPen(QPen(QColor(60, 100, 200, 40), 4))
        p.drawArc(rect, 0, 5760)

        # Active arc
        p.setPen(QPen(self.color, 4, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 1440, int(-self.value * 5760))
