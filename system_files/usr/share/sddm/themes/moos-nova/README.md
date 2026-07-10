# moos-nova — ثيم شاشة الدخول SDDM (MoOS Nova)

ثيم شاشة الدخول الرسمي لـ MoOS: مظهر Nova داكن (كحلي عميق + أزرق كهربائي) مبني على SilentSDDM بمحرك Qt6/QML، مع لوحة مفاتيح افتراضية تدعم الإدخال العربي. القرار موثق: SDDM 0.21+ وليس Plasma Login Manager (لا يدعم ثيمات QML مخصصة).

آخر تحديث: 2026-07-10

## NOTICE / الإسناد (Attribution)

**Based on [SilentSDDM](https://github.com/uiriansan/SilentSDDM) by uiriansan — GPL-3.0-or-later. The upstream license file is kept at `LICENSE` in this directory.** MoOS changes: rebranded `metadata.desktop` (Theme-Id=moos-nova), added the single production preset `configs/moos-nova.conf`, native-4K login/lock artwork, IBM Plex Sans/Arabic typography, bilingual visible copy, and neutral Nova session icons. Upstream demo videos, presets, bundled Red Hat fonts, and third-party desktop logos were removed from the production image.

## البنية (Layout)

```
moos-nova/
├── metadata.desktop           # Name=MoOS Nova, Theme-Id=moos-nova, QtVersion=6,
│                              # ConfigFile=configs/moos-nova.conf
├── Main.qml + qmldir          # المشهد الرئيسي (من SilentSDDM)
├── components/                # QML components + QtQuick VirtualKeyboard style
├── configs/moos-nova.conf     # ألوان Nova: خلفية nova-dark.png، تمييز #2E7BFF،
│                              # ثانوي #8B5CF6، نص #E6EDF7، أسطح #0B1220/#111A2E، blur مفعّل
├── backgrounds/nova-dark.png  # خلفية دخول/قفل MoOS أصلية 3840×2160
├── backgrounds/default.jpg    # fallback آمن من فن Nova نفسه؛ لا غابة stock
├── icons/                     # أيقونات Nova + session mark محايد لكل أسماء التوافق
└── LICENSE                    # GPL-3.0 (upstream SilentSDDM)
```

## الربط مع النظام (System wiring)

- `/etc/sddm.conf.d/moos.conf` يضبط `Current=moos-nova` ويفعّل `InputMethod=qtvirtualkeyboard` مع `QML2_IMPORT_PATH` لمكونات الثيم (مطلوب للوحة المفاتيح الافتراضية/الإدخال العربي).
- التبعيات (تُثبّت في `build_files/build.sh`): `qt6-qtsvg`, `qt6-qtvirtualkeyboard`, `qt6-qtmultimedia`, `qt6-qtimageformats`.

## اختبار داخل VM

```bash
sddm-greeter-qt6 --test-mode --theme /usr/share/sddm/themes/moos-nova
```

## قيود معروفة (Known Issues)

- خلفيات الفيديو المتحركة من upstream غير مشمولة (حجم الصورة)؛ الثيم يستخدم خلفية ثابتة.
- النصوص التي يملكها SDDM نفسه تتبع ترجمة SDDM؛ نصوص الثيم المخصصة ظاهرة بصيغة `العربية | English`.
- يلزم اختبار حي عبر `sddm-greeter-qt6 --test-mode` على Plasma/Fedora الهدف وبالدقات 100%/150%/200%؛ Windows لا يشغّل greeter Qt6.
