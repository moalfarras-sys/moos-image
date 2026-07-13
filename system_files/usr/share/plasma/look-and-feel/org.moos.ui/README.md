# org.moos.ui — MoOS UI Global Theme

حزمة Look-and-Feel الداكنة الافتراضية لـ MoOS على KDE Plasma 6.7+ (Wayland فقط).

## Current surfaces

```text
org.moos.ui/
├── metadata.json
└── contents/
    ├── defaults
    ├── splash/
    │   ├── Splash.qml
    │   └── images/moos-logo.png
    └── logout/
        ├── Logout.qml
        ├── NovaActionButton.qml
        └── README.md
```

- `defaults` يطبق MoOSUIDark وNova icons وNovaIce وNova Horizon.
- `splash` شاشة بدء MoOS المخصصة.
- `logout` واجهة خروج/قفل/تعليق/إعادة تشغيل/إطفاء زجاجية، ثنائية اللغة، RTL-first، وتحافظ على عقد Plasma 6.7 وخيارات التحديثات offline.

## Verification

```bash
lookandfeeltool --apply org.moos.ui
/usr/libexec/ksmserver-logout-greeter --windowed --lookandfeel org.moos.ui
```

التحقق النهائي يحتاج Plasma 6.7 داخل VM/ISO. لا يمكن تشغيل مضيف logout الخاص بـ Plasma على Windows.

## Known issue

ملف `contents/defaults` يوثق إعدادات KWin إضافية لا يطبقها LookAndFeelManager تلقائيًا؛ القيم التشغيلية لها تبقى في `/etc/xdg` كما هو موضح في الملف نفسه. لم تُعدّل هذه الدفعة أي ملف يملكه Claude.
