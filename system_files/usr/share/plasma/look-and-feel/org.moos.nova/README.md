# org.moos.nova — MoOS Nova Global Theme (هيكل أولي)

هذا هو هيكل حزمة الـ Global Theme الداكن الافتراضي لـ MoOS على KDE Plasma 6.7+ (Wayland فقط). في M0 يحتوي `metadata.json` صالحاً + ملف `contents/defaults` هيكلياً فقط؛ القيم الحقيقية (ألوان NovaDark من `branding/PALETTE.md`، أيقونات Nova، مؤشر Nova Ice، Klassy decorations، splash) تُبنى في Phase 3.

آخر تحديث: 2026-07-09

## البنية المستهدفة (Target layout)

```
org.moos.nova/
├── metadata.json            # KPlugin (Id=org.moos.nova) + KPackageStructure=Plasma/LookAndFeel  ✔ موجود
├── contents/
│   ├── defaults             # ColorScheme/Theme/Icons/Cursors defaults  ✔ هيكل موجود
│   ├── previews/            # preview.png + fullscreenpreview.jpg      ← Phase 3
│   ├── splash/              # شاشة splash QML بألوان Nova              ← Phase 3
│   └── layouts/             # org.kde.plasma.desktop-layout.js         ← Phase 6
```

النسخة الفاتحة `org.moos.nova.light` حزمة شقيقة منفصلة تُنشأ في Phase 3 بنفس البنية.

## اختبار محلي داخل VM

```bash
kpackagetool6 --type Plasma/LookAndFeel --install org.moos.nova
lookandfeeltool --apply org.moos.nova
```

## قيود معروفة (Known Issues)

- `contents/defaults` يشير إلى ColorScheme باسم `NovaDark` لكن ملف الـ color scheme نفسه (`NovaDark.colors`) لم يُنشأ بعد — تطبيق الثيم الآن سيسقط إلى الافتراضي.
- لا previews ولا splash بعد.

## الخطوات التالية (Next Actions)

- Phase 3 (انظر `MOOS_BUILD_WORKFLOW.md`): توليد `NovaDark.colors` من `design/tokens.json`، إضافة previews، وإنشاء `org.moos.nova.light`.
