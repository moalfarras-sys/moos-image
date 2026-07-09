# moos-nova — ثيم إقلاع Plymouth (placeholder — يُبنى في Phase 5)

هذا المجلد يحجز مكان ثيم Plymouth الخاص بـ MoOS. الثيم الفعلي سيُبنى في Phase 5 (Boot & Installer) كثيم **two-step** (الـ plugin الموصى به في مسار flicker-free الخاص بـ Fedora) مع شعار Mo monogram متحرك كسلسلة إطارات PNG، على خلفية `nova.navy.deepest` (#050A14) من `branding/PALETTE.md`.

آخر تحديث: 2026-07-09

## البنية المستهدفة (Target layout)

```
moos-nova/
├── moos-nova.plymouth        # ModuleName=two-step + مسارات الصور
├── animation-0001.png ...    # سلسلة إطارات Mo monogram المتحركة (من branding/)
├── watermark.png             # الشعار الثابت أسفل الشاشة
└── background-tile.png       # لون/تدرج الخلفية
```

التفعيل يتم في build.sh لاحقاً:

```bash
plymouth-set-default-theme moos-nova
```

المرجع: https://fedoraproject.org/wiki/Changes/FlickerFreeBoot — نستخدم two-step (وليس script plugin) لأنه مدعوم أفضل ويتكامل مع مسار flicker-free/BGRT.

## قيود معروفة (Known Issues)

- placeholder فقط — لا يوجد ملف `.plymouth` بعد؛ النظام يستخدم ثيم bgrt/spinner الافتراضي حتى Phase 5.
- تفعيل الثيم يتطلب إعادة توليد initramfs في مسار البناء — يوثَّق عند التنفيذ في Phase 5.

## الخطوات التالية (Next Actions)

- Phase 3: توليد إطارات PNG المتحركة من أصول `branding/`.
- Phase 5 (انظر `MOOS_BUILD_WORKFLOW.md`): كتابة `moos-nova.plymouth` وتفعيله في `build_files/build.sh`.
