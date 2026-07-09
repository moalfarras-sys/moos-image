# NovaHorizon — حزمة خلفيات MoOS (kpackage) — الهيكل فقط في M0

هذا المجلد يحجز مكان حزمة الخلفيات الرسمية "Nova Horizon" بنمط time-of-day (فاتح نهاراً/داكن ليلاً). الصور تأتي من الأصول الموجودة في `branding/` بالمشروع (`moos-wallpaper-light.png` و`moos-wallpaper-dark.png` بدقة 4K)، وتُضاف مع `metadata.json` في Phase 3.

آخر تحديث: 2026-07-09

## البنية المستهدفة (kpackage layout)

```
NovaHorizon/
├── metadata.json                        # KPlugin Id=NovaHorizon (Phase 3)
└── contents/
    ├── images/
    │   └── 3840x2160.png               # من branding/moos-wallpaper-light.png
    └── images_dark/
        └── 3840x2160.png               # من branding/moos-wallpaper-dark.png
```

- Plasma 6 يختار تلقائياً `images_dark/` في الوضع الداكن — هذا ما يعطي سلوك time-of-day/الوضعين بدون كود إضافي.
- أحجام إضافية (2560x1440، 1920x1080) تُشتق من نفس الأصلين في Phase 3 لدعم 1080p/2K.

## قيود معروفة (Known Issues)

- لا توجد صور ولا `metadata.json` بعد — المجلد هيكل فقط؛ إسقاط الصور بدون metadata لن يُظهر الخلفية في واجهة الإعدادات.

## الخطوات التالية (Next Actions)

- Phase 3 (انظر `MOOS_BUILD_WORKFLOW.md`): نسخ الصورتين من `branding/`، توليد الأحجام الإضافية، وكتابة `metadata.json` وضبطها كخلفية افتراضية في Global Theme `org.moos.nova`.
