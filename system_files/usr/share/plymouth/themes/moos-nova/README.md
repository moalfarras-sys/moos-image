# moos-nova — ثيم إقلاع Plymouth الخاص بـ MoOS

ثيم إقلاع MoOS الرسمي (flicker-free) مبني على الـ plugin **two-step** — نفس الـ plugin الذي تستخدمه ثيمات Fedora الرسمية (bgrt/spinner) ضمن مسار Flicker-Free Boot.

آخر تحديث: 2026-07-09 — **الثيم مكتمل ومفعّل** (لم يعد placeholder).

## المحتويات (Contents)

```
moos-nova/
├── moos-nova.plymouth        # الوصف: ModuleName=two-step + الألوان والمحاذاة
├── throbber-0001.png ...     # 30 إطار spinner (64×64، شفاف): قوس "مذنّب" يدور
│   throbber-0030.png         #   12°/إطار، رأس سماوي #22D3EE يتلاشى عبر #2E7BFF
├── watermark.png             # شعار MoOS (200×200) أسفل الشاشة (محاذاة 0.96)
└── README.md                 # هذا الملف
```

الخلفية لون صلب `nova.navy.deepest` (#050A14) من `branding/PALETTE.md`
(`BackgroundStartColor` = `BackgroundEndColor` — بلا تدرّج، بلا وميض).
شريط التقدّم (التحديثات/الترقيات): خلفية #111A2E وتعبئة #2E7BFF.

## التوليد (Asset generation)

الإطارات و watermark وُلّدت برمجياً بـ Python + Pillow (رسم بدقة 4× ثم تصغير
LANCZOS للحواف الناعمة). المصدر: شعار MoOS في
`/usr/share/moos/moos-logo.png` (بشفافية أصلية — لا قصّ دائري مطلوب).

## التفعيل (Activation)

يتم في `build_files/build.sh` قسم (c2) قبل إعادة توليد initramfs:

```bash
plymouth-set-default-theme moos-nova   # بدون -R
```

بدون `-R` عمداً: أمر dracut التالي في السكربت يعيد بناء initramfs أصلاً،
وموديول plymouth في dracut يلتقط الثيم الحالي تلقائياً. حزمة
`plymouth-plugin-two-step` تُثبَّت في نفس القسم (موجودة أصلاً في Kinoite
عبر bgrt/spinner — التثبيت الصريح ضمانة غير ضارّة).

## الإسناد (Attribution)

بنية ملف `moos-nova.plymouth` والأسماء المتوقّعة للإطارات
(`throbber-XXXX.png`, `watermark.png`) تتبع ثيم **spinner** المرجعي من مشروع
Plymouth (freedesktop.org):
https://gitlab.freedesktop.org/plymouth/plymouth/-/blob/main/themes/spinner/spinner.plymouth.desktop
جميع الصور هنا أصلية (شعار MoOS + إطارات مولّدة) — لا أصول طرف ثالث.

المرجع العام: https://fedoraproject.org/wiki/Changes/FlickerFreeBoot
