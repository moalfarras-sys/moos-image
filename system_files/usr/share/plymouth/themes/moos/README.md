# moos — ثيم إقلاع Plymouth الخاص بـ MoOS

ثيم إقلاع MoOS الرسمي المبني على plugin ‏`two-step` نفسه المستخدم في مسار Fedora flicker-free. عقد `.plymouth` بقي ثابتًا؛ هذه الدفعة تستبدل الأصول فقط.

## Contents

```text
moos/
├── moos.plymouth
├── throbber-0001.png … throbber-0060.png   # 96×96 RGBA
├── watermark.png                           # 288×288 RGBA
└── README.md
```

- الـ throbber حلقة مدتها ثانيتان من 60 صورة فريدة. Plymouth 24.004.60 يعرضها عند **30 FPS ثابتة**؛ لا يوجد مفتاح `FrameRate`، لذلك 60 صورة لا تعني 60 FPS.
- كل إطار transparent RGBA، مرسوم عند 4× ثم مصغّر مرة واحدة بـ LANCZOS، مع glow وmotion trail وتدرج Mo الكامل.
- الـ watermark يستخدم شعار MoOS الأصلي مع هالة مضبوطة، ويُعرض بحجمه الأصلي لأن `two-step` لا يغيّر حجمه.
- كل PNG يحمل sRGB profile. الاستهلاك الخام للإطارات الستين يقارب 2.1 MiB فقط.

## Contract verification

تم التحقق مقابل tag الرسمي `24.004.60`:

- plugin keys: <https://gitlab.freedesktop.org/plymouth/plymouth/-/blob/24.004.60/src/plugins/splash/two-step/plugin.c>
- throbber loader and timing: <https://gitlab.freedesktop.org/plymouth/plymouth/-/blob/24.004.60/src/libply-splash-graphics/ply-throbber.c>
- reference descriptor: <https://gitlab.freedesktop.org/plymouth/plymouth/-/blob/24.004.60/themes/spinner/spinner.plymouth.desktop>

`throbber-` والامتداد lowercase `.png` ثابتان، والتحميل يتم بترتيب `versionsort`. يبقى `UseEndAnimation=false` إلزاميًا في كل وضع لأننا لا نشحن `animation-*`.

## Activation and testing

`build_files/build.sh` الموجود أصلًا يختار الثيم قبل إعادة بناء initramfs؛ لم تُعدّل هذه الدفعة أي wiring يملكه Claude. يلزم التحقق النهائي على عتاد/VM يوفّر DRM مبكرًا لأن QEMU الحالي قد يسقط إلى النص حتى مع ثيم صحيح.

## Attribution

عقد التسمية والبنية من Plymouth الرسمي. كل الصور أصلية لـ MoOS ولا تحتوي أصولًا من طرف ثالث.
