# moos-nova — ثيم شاشة الدخول SDDM (placeholder — يُبنى في Phase 5)

هذا المجلد يحجز مكان ثيم SDDM الخاص بـ MoOS. الثيم الفعلي سيُبنى في Phase 5 (Boot & Installer) كثيم Qt6/QML مبني على SilentSDDM (لوحة مفاتيح افتراضية تدعم الإدخال العربي) بألوان Nova من `branding/PALETTE.md`. القرار موثق: SDDM 0.21+ وليس Plasma Login Manager (لا يدعم ثيمات QML مخصصة).

آخر تحديث: 2026-07-09

## البنية المستهدفة (Target layout)

```
moos-nova/
├── metadata.desktop      # MUST contain QtVersion=6 (SDDM 0.21+ يشغل الثيم بـ Qt6)
├── Main.qml              # المشهد الرئيسي (مشتق من SilentSDDM)
├── theme.conf            # ألوان/خلفية من Nova tokens
└── components/ backgrounds/ fonts/ ...
```

المصدر الأساس: https://github.com/uiriansan/SilentSDDM

## اختبار داخل VM

```bash
sddm-greeter-qt6 --test-mode --theme /usr/share/sddm/themes/moos-nova
```

## قيود معروفة (Known Issues)

- placeholder فقط — لا يوجد `metadata.desktop` بعد، فلن يظهر الثيم في أي قائمة اختيار حتى Phase 5.

## الخطوات التالية (Next Actions)

- Phase 5 (انظر `MOOS_BUILD_WORKFLOW.md`): fork من SilentSDDM، تلوين بـ Nova tokens، `metadata.desktop` مع `QtVersion=6`، وضبط `/etc/sddm.conf.d/theme.conf` في `system_files/etc/`.
