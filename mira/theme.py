"""
Mira Neural OS Design System - Theme Module
Contains all visual tokens, color constants, font definitions, sizing, and the master QSS stylesheet.
"""

class MiraColors:
    BG_DEEPEST = '#050816'
    BG_DARK = '#0A0E24'
    BG_NAVY = '#0E1333'
    GLASS_SURFACE = 'rgba(12, 18, 45, 0.82)'
    GLASS_BORDER = 'rgba(80, 140, 255, 0.15)'
    GLASS_BORDER_ACTIVE = 'rgba(0, 212, 255, 0.35)'
    NEON_CYAN = '#00D4FF'
    NEON_CYAN_DIM = '#4DFFFF'
    NEON_VIOLET = '#8B5CF6'
    NEON_VIOLET_DIM = '#A78BFA'
    NEON_ROSE = '#FF4DAB'
    NEON_ROSE_DIM = '#FF6EB8'
    TEXT_PRIMARY = '#F0EAFF'
    TEXT_SECONDARY = '#8B9CC0'
    TEXT_BRAND = '#FCEBFF'
    STATUS_GREEN = '#4ADE80'
    STATUS_ORANGE = '#FBBF24'
    STATUS_RED = '#EF4444'
    BUBBLE_USER = '#1A3A5C'
    BUBBLE_MIRA = '#2A2A50'
    BUBBLE_ACTION = '#1E3A4F'
    BUBBLE_ERROR = '#4A1A2E'
    DOCK_GRADIENT_START = '#0F1335'
    DOCK_GRADIENT_MID = '#1A1845'
    DOCK_GRADIENT_END = '#141D42'

    STATE_COLORS = {
        'ready': '#74B9CC',
        'listening': '#00D4FF',
        'thinking': '#8B5CF6',
        'speaking': '#FF4DAB',
        'executing': '#A78BFA',
        'error': '#EF4444',
        'off': '#4B5563'
    }

class MiraFonts:
    FAMILY = 'Noto Sans Arabic'
    MONO = 'Noto Sans Mono'

    TINY = 9
    SMALL = 11
    BODY = 13
    MEDIUM = 15
    LARGE = 18
    XLARGE = 22
    HERO = 28
    BRAND = 26

class MiraSizes:
    class Radii:
        SMALL = 8
        MEDIUM = 12
        LARGE = 16
        XLARGE = 20
        PILL = 24
        CIRCLE = 33

    class Spacing:
        XS = 4
        SM = 8
        MD = 12
        LG = 16
        XL = 24
        XXL = 32

    class Breakpoints:
        COMPACT = 900
        NARROW = 760
        TINY = 560

class MiraMotion:
    CROSSFADE = 280
    BLINK_DURATION = 180
    BLINK_MIN = 4600
    BLINK_MAX = 8800
    IDLE_INTERVAL = 320
    DOCK_BEAT = 280

def build_stylesheet() -> str:
    """
    Builds and returns the master QSS stylesheet for Mira Neural OS.
    """
    return f"""
    QWidget {{
        color: {MiraColors.TEXT_PRIMARY};
        font-family: '{MiraFonts.FAMILY}';
    }}

    #shell {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    stop:0 {MiraColors.BG_DEEPEST},
                                    stop:0.5 {MiraColors.BG_DARK},
                                    stop:1 #12102E);
    }}

    #topBar {{
        background-color: rgba(10, 14, 38, 0.88);
        border-radius: 16px;
        border: 1px solid rgba(80, 140, 255, 0.12);
        margin-bottom: 4px;
    }}

    #navRoute {{
        background-color: transparent;
        color: {MiraColors.TEXT_SECONDARY};
        border-radius: 10px;
        padding: 8px 16px;
    }}
    #navRoute:hover {{
        background-color: rgba(0, 212, 255, 0.08);
    }}
    #navRoute:checked {{
        background-color: rgba(0, 212, 255, 0.18);
        color: {MiraColors.NEON_CYAN};
        font-weight: 600;
    }}

    #contextRail, #conversationRail {{
        background-color: rgba(10, 15, 38, 0.75);
        border-radius: 16px;
        border: 1px solid rgba(80, 140, 255, 0.08);
    }}

    #commandDock {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                    stop:0 {MiraColors.DOCK_GRADIENT_START},
                                    stop:0.5 {MiraColors.DOCK_GRADIENT_MID},
                                    stop:1 {MiraColors.DOCK_GRADIENT_END});
        border-radius: 20px;
        border: 1px solid rgba(100, 160, 255, 0.14);
    }}

    QPushButton {{
        background-color: rgba(15, 20, 48, 0.7);
        color: {MiraColors.TEXT_PRIMARY};
        border: 1px solid rgba(80, 140, 255, 0.12);
        border-radius: 10px;
        padding: 10px 18px;
    }}
    QPushButton:hover {{
        background-color: rgba(0, 212, 255, 0.1);
        border-color: rgba(0, 212, 255, 0.3);
    }}
    QPushButton#compactIcon {{ padding: 0px; }}
    QPushButton:disabled {{ color:#72809C; background:#0D1223; border-color:#20283D; }}
    QPushButton:focus {{ border: 1px solid #A78BFA; }}
    QSlider::groove:horizontal:disabled {{ background:#263047; }}
    QSlider::sub-page:horizontal:disabled {{ background:#263047; }}
    QSlider::handle:horizontal:disabled {{ background:#647089; border:0px; }}
    QPushButton:pressed {{
        background-color: rgba(0, 212, 255, 0.15);
    }}

    QPushButton#voiceTrigger {{
        width: 68px;
        height: 68px;
        border-radius: 34px;
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.7,
                                    stop:0 {MiraColors.NEON_CYAN},
                                    stop:0.5 #6366F1,
                                    stop:1 {MiraColors.NEON_VIOLET});
        border: 2px solid rgba(0, 212, 255, 0.4);
        padding: 0px;
    }}
    QPushButton#voiceTrigger:hover {{
        border-color: rgba(0, 212, 255, 0.7);
    }}

    QPushButton#quickAction {{
        background-color: rgba(15, 20, 45, 0.6);
        border-radius: 12px;
        border: 1px solid rgba(80, 140, 255, 0.1);
        padding: 8px 14px;
    }}
    QPushButton#quickAction:hover {{
        background-color: rgba(0, 212, 255, 0.08);
        border-color: rgba(0, 212, 255, 0.25);
    }}

    QPushButton#routeAction {{
        background-color: rgba(0, 212, 255, 0.12);
        color: {MiraColors.NEON_CYAN};
        border: 1px solid rgba(0, 212, 255, 0.25);
        border-radius: 10px;
    }}

    QPushButton#stageTool {{
        background-color: rgba(15, 20, 50, 0.5);
        border-radius: 14px;
        border: 1px solid rgba(100, 160, 255, 0.1);
        padding: 12px 16px;
    }}
    QPushButton#stageTool:hover {{
        background-color: rgba(0, 212, 255, 0.08);
    }}

    QPushButton#suggestion {{
        background-color: rgba(20, 25, 55, 0.6);
        border-radius: 12px;
        border: 1px solid rgba(100, 160, 255, 0.12);
        padding: 10px 16px;
    }}
    QPushButton#suggestion:hover {{
        border-color: rgba(0, 212, 255, 0.3);
    }}

    QPushButton#deviceRoute {{
        background-color: rgba(12, 18, 42, 0.65);
        border-radius: 10px;
        border: 1px solid rgba(80, 140, 255, 0.1);
        padding: 9px 14px;
        text-align: right;
    }}
    QPushButton#deviceRoute:hover {{
        background-color: rgba(0, 212, 255, 0.08);
    }}

    QPushButton#faceChoice {{
        background-color: rgba(15, 20, 48, 0.6);
        border-radius: 14px;
        border: 2px solid rgba(80, 140, 255, 0.12);
        padding: 10px;
    }}
    QPushButton#faceChoice:checked {{
        border-color: rgba(0, 212, 255, 0.5);
        background-color: rgba(0, 212, 255, 0.08);
    }}

    QPushButton#categoryTab {{
        background-color: rgba(12, 16, 40, 0.5);
        border-radius: 12px;
        border: 1px solid rgba(80, 140, 255, 0.08);
        padding: 8px 14px;
        min-height: 46px;
    }}
    QPushButton#categoryTab:hover {{
        background-color: rgba(0, 212, 255, 0.06);
    }}
    QPushButton#categoryTab:checked {{
        background-color: rgba(0, 212, 255, 0.12);
        border-color: rgba(0, 212, 255, 0.3);
    }}

    QPushButton#sendAction {{
        background-color: rgba(0, 212, 255, 0.15);
        color: {MiraColors.NEON_CYAN};
        border: 1px solid rgba(0, 212, 255, 0.3);
        border-radius: 12px;
        font-weight: 600;
        padding: 10px 18px;
    }}

    QPushButton#stopAction {{
        background-color: rgba(255, 77, 171, 0.12);
        color: {MiraColors.NEON_ROSE};
        border: 1px solid rgba(255, 77, 171, 0.25);
        border-radius: 12px;
    }}

    QLabel#brand {{
        color: {MiraColors.TEXT_BRAND};
        font-size: 26px;
        font-weight: 750;
        letter-spacing: 5px;
    }}

    QLabel#eyebrow {{
        color: #9B8EC4;
        font-size: 10px;
        letter-spacing: 2px;
    }}

    QLabel#section {{
        color: #E8DCFF;
        font-size: 16px;
        font-weight: 650;
    }}

    QLabel#hero {{
        color: #FFF2FB;
        font-size: 28px;
        font-weight: 650;
    }}

    QLabel#muted {{
        color: #8B9CC0;
        font-size: 12px;
    }}

    QLabel#chip {{
        background-color: rgba(0, 212, 255, 0.1);
        color: #8EEAF0;
        border: 1px solid rgba(0, 212, 255, 0.2);
        border-radius: 12px;
        padding: 5px 12px;
    }}

    QLabel#service {{
        color: #8B9CC0;
        font-size: 12px;
    }}

    QLabel#taskState {{
        color: #8FE2E7;
        font-size: 11px;
    }}

    QLabel#contextItem {{
        background-color: rgba(12, 18, 42, 0.5);
        border-radius: 10px;
        border: 1px solid rgba(80, 140, 255, 0.08);
        padding: 10px 14px;
        color: {MiraColors.TEXT_PRIMARY};
        font-size: 13px;
    }}

    QLabel#detailTitle {{
        color: white;
        font-size: 20px;
        font-weight: 650;
    }}

    QLabel#workspaceTitle {{
        color: #FFF1FC;
        font-size: 24px;
        font-weight: 700;
    }}

    QLabel#emptySpark {{
        font-size: 40px;
        color: {MiraColors.NEON_CYAN};
    }}

    QLabel#emptyTitle {{
        font-size: 18px;
        font-weight: 600;
        color: #F0EAFF;
    }}

    QLabel#resultLine {{
        color: #9AE5D5;
        font-size: 13px;
    }}

    QLabel#liveValue {{
        color: {MiraColors.NEON_CYAN};
        font-size: 14px;
        font-weight: 600;
    }}

    QLabel#dockMode {{
        color: #8B9CC0;
        font-size: 12px;
    }}

    QLabel#clockTime {{
        color: #F0EAFF;
        font-size: 36px;
        font-weight: 700;
    }}

    QLabel#clockDate {{
        color: #8B9CC0;
        font-size: 11px;
    }}

    QLabel#weatherTemp {{
        color: #F0EAFF;
        font-size: 22px;
        font-weight: 600;
    }}

    QLabel#weatherDesc {{
        color: #8B9CC0;
        font-size: 11px;
    }}

    QLineEdit {{
        background-color: rgba(8, 14, 35, 0.85);
        color: {MiraColors.TEXT_PRIMARY};
        border: 1px solid rgba(80, 140, 255, 0.12);
        border-radius: 14px;
        padding: 10px 16px;
        font-size: 13px;
    }}
    QLineEdit:focus {{
        border-color: rgba(0, 212, 255, 0.4);
    }}

    QLineEdit#dockInput {{
        background-color: rgba(8, 14, 35, 0.75);
        border-radius: 20px;
        padding: 12px 20px;
        font-size: 14px;
    }}

    QPlainTextEdit {{
        background-color: rgba(8, 12, 30, 0.7);
        color: {MiraColors.TEXT_PRIMARY};
        border: 1px solid rgba(80, 140, 255, 0.08);
        border-radius: 14px;
        padding: 12px;
    }}

    QPlainTextEdit#inspector {{
        font-family: '{MiraFonts.MONO}';
        font-size: 12px;
        background-color: rgba(5, 8, 20, 0.85);
    }}

    QComboBox {{
        background-color: rgba(12, 18, 42, 0.7);
        color: {MiraColors.TEXT_PRIMARY};
        border: 1px solid rgba(80, 140, 255, 0.12);
        border-radius: 10px;
        padding: 8px 14px;
    }}
    QComboBox::drop-down {{
        border: none;
    }}
    QComboBox QAbstractItemView {{
        background-color: {MiraColors.BG_NAVY};
        border: 1px solid rgba(80, 140, 255, 0.15);
        outline: none;
    }}
    QComboBox QAbstractItemView::item:hover {{
        background-color: rgba(0, 212, 255, 0.1);
    }}

    QSlider::groove:horizontal {{
        background-color: rgba(30, 40, 80, 0.5);
        height: 6px;
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background-color: {MiraColors.NEON_CYAN};
        width: 16px;
        height: 16px;
        margin: -5px 0;
        border-radius: 8px;
        border: 2px solid rgba(0, 212, 255, 0.3);
    }}
    QSlider::sub-page:horizontal {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                    stop:0 {MiraColors.NEON_VIOLET},
                                    stop:1 {MiraColors.NEON_CYAN});
        border-radius: 3px;
    }}

    QScrollArea, QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}

    QScrollBar:vertical {{
        background-color: transparent;
        width: 6px;
    }}
    QScrollBar::handle:vertical {{
        background-color: rgba(80, 140, 255, 0.2);
        border-radius: 3px;
    }}

    QListWidget#homeList {{
        background-color: rgba(10, 15, 38, 0.92);
        color: {MiraColors.TEXT_PRIMARY};
        border: 1px solid rgba(80, 140, 255, 0.12);
        border-radius: 14px;
    }}
    QListWidget#homeList::viewport {{ background-color: transparent; }}
    QListWidget#homeList::item {{
        background-color: rgba(12, 18, 42, 0.5);
        color: {MiraColors.TEXT_PRIMARY};
        border-radius: 10px;
        padding: 10px 14px;
        margin: 3px;
    }}
    QListWidget#homeList::item:selected {{
        background-color: rgba(0, 212, 255, 0.1);
        border: 1px solid rgba(0, 212, 255, 0.25);
    }}

    QCheckBox {{
        color: {MiraColors.TEXT_PRIMARY};
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 1px solid rgba(80, 140, 255, 0.2);
        background-color: rgba(15, 20, 45, 0.6);
    }}
    QCheckBox::indicator:checked {{
        background-color: rgba(0, 212, 255, 0.3);
        border-color: {MiraColors.NEON_CYAN};
    }}

    QTabWidget::pane {{
        border: none;
        background-color: transparent;
    }}

    #workspacePage {{
        background-color: rgba(10, 14, 35, 0.75);
        border-radius: 16px;
    }}

    #workspaceLayer {{
        background-color: rgba(14, 20, 45, 0.65);
        border-radius: 14px;
        border: 1px solid rgba(80, 140, 255, 0.08);
    }}

    #controlGlass {{
        background-color: rgba(10, 15, 38, 0.78);
        border-radius: 18px;
        border: 1px solid rgba(80, 140, 255, 0.1);
    }}

    #pairPanel {{
        background-color: rgba(18, 24, 52, 0.85);
        border-radius: 14px;
        border: 1px solid rgba(100, 140, 255, 0.12);
    }}

    #coreStatus, #heroStage, #feedScroll, #feedHost, #emptyState, #voiceCanvas {{
        background-color: transparent;
        border: none;
    }}

    QPushButton#quiet {{
        background-color: transparent;
        color: #8B9CC0;
        border: none;
    }}
    QPushButton#quiet:hover {{
        color: {MiraColors.NEON_CYAN};
    }}

    QSplitter::handle {{
        background-color: rgba(80, 140, 255, 0.06);
        width: 2px;
    }}

    QMenu {{
        background-color: {MiraColors.BG_NAVY};
        border: 1px solid rgba(80, 140, 255, 0.15);
        border-radius: 10px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 8px 20px;
        border-radius: 6px;
    }}
    QMenu::item:selected {{
        background-color: rgba(0, 212, 255, 0.1);
    }}
    """
