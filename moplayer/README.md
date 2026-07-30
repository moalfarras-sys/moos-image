# MoPlayer for MoOS — مشغّل MoPlayer لنظام MoOS

مشغّل IPTV سينمائي **أصيل لسطح مكتب MoOS**: بث مباشر، أفلام، مسلسلات — من Xtream
Codes أو M3U — مبني على نفس محرّك التشغيل الذي يشحنه النظام أصلاً (`libmpv`)،
ومتكامل مع بلازما تكاملاً حقيقياً: مفاتيح الوسائط، لوحة الوسائط، منع إطفاء الشاشة،
وواجهة عربية/إنجليزية بدعم RTL كامل.

الإصدار **1.2** يطوّر هوم السينمائي والمشغّل المكتبي ويجعل تحميل المكتبة أسرع.
أصبح فيه تقديم/إرجاع 10 ثوانٍ، قناة أو حلقة سابقة/تالية، شريط زمني، صوت وكتم،
ملء الشاشة، اختيار نسبة العرض
(`احتواء`/`ملء`/`أصلي`)، سرعات التشغيل، مسارات الصوت والترجمة، وحالة واضحة
للتخزين المؤقت وإعادة الاتصال مع زر محاولة يدوية. تُحفظ بيانات المصدر داخل
مجلد التطبيق الخاص بصلاحيات لينكس `0600` دون فتح KDE Wallet. فتح رابط أو ملف
في MoPlayer وهو يعمل يرسله إلى النافذة الموجودة بدل تشغيل نسخة ثانية.

> مستودع جديد. **لم يُعدَّل مستودع `MoPlayerios` إطلاقاً** — أُخذت منه الهوية
> (الشعار، الألوان) والقلب (Xtream API، محلّل M3U، النماذج، المستودعات)، وأُعيدت
> كتابة الواجهة بالكامل لسطح المكتب.

---

## لماذا Flutter وليس QML؟

تطبيقات MoOS الأصلية (Mo AI، الترحيب) هي QML خالص، وكان الطبيعي أن يكون هذا كذلك.
لم يكن ذلك ممكناً، لسبب واحد حاسم:

**QML لا يستطيع تشغيل IPTV.** محرّك `QtMultimedia` يتعثّر في MPEG-TS المتقطّع وHLS
الذي تبثّه لوحات IPTV الحقيقية. أمّا `libmpv` فهو المرجع الفعلي لتشغيل هذه البثوث
على لينكس — و**هو موجود أصلاً داخل صورة MoOS** بحزمة `mpv-libs`. و`media_kit`
ليست محرّكاً ثانياً، بل غلاف Flutter حول `libmpv` نفسه.

النتيجة: التطبيق يستخدم محرّك النظام ذاته، **لا يضيف أي اعتماد جديد على الصورة**،
ويحتفظ بقلب MoPlayer كما هو بدل إعادة كتابته بلغة أخرى.

## ما الذي يجعله "أصيلاً" في MoOS؟

| | |
|---|---|
| **المحرّك** | `libmpv` — نفس `mpv-libs` في الصورة. لا نسخة ثانية. |
| **مفاتيح الوسائط** | MPRIS2 عبر D-Bus: زر التشغيل/الإيقاف يعمل، والقناة تظهر في لوحة وسائط بلازما وفي شاشة القفل، و`playerctl` يتحكّم بها. |
| **الأيقونة والنافذة** | `app_id = org.moos.moplayer` مطابق لملف `.desktop` — بلازما تعرف نافذتها. لا شريط عنوان GNOME: KWin يزخرف النافذة بثيم MoOS Nova. |
| **الخط** | IBM Plex Sans + IBM Plex Sans Arabic — خط Nova نفسه، من النظام، بلا تحزيم. |
| **الشاشة** | يمنع الإطفاء أثناء التشغيل فقط (`org.freedesktop.ScreenSaver`)، لا أثناء الإيقاف المؤقت. |
| **اللغة** | يتبع لغة الجلسة تلقائياً. عربي كامل RTL: التنقّل، الأشرطة، شريط التقدّم. |
| **التصميم** | رموز Nova (المسافات، الأنصاف، سُلّم الخط) مع هوية MoPlayer الجمرية — انظر [`DESIGN.md`](DESIGN.md). |

## البناء

MoOS نظام ذرّي بلا مترجم؛ البناء يجري داخل حاوية والمضيف يبقى نظيفاً.

```bash
just setup     # ينشئ حاوية moplayer-dev ويثبّت Flutter وأدوات البناء
just build     # نسخة الإصدار -> build/linux/x64/release/bundle/
just install   # يثبّتها في ~/.local فتظهر في قائمة التطبيقات
just run       # تشغيل من المصدر
just check     # analyze + test  (نفس بوابة CI)
```

## التثبيت داخل صورة النظام

عندما يصبح جزءاً من MoOS بدل `~/.local`:
[`packaging/moos/moos-image/README.md`](packaging/moos/moos-image/README.md) —
مقطع `Containerfile`، بوابة البناء الواجب إضافتها، ومسار `moos://app/moplayer`.

## البنية

```
lib/
├── app/          القشرة والتوجيه والإقلاع (main_shell = التنقّل + سطح المشغّل)
├── core/         الثيم (Nova Cinema)، اللغة، الإعدادات، الأدوات
├── models/       ← منقولة كما هي من MoPlayerios
├── services/
│   ├── xtream/   ← منقولة كما هي
│   ├── m3u/      ← منقولة كما هي
│   ├── player/   libmpv عبر media_kit + ضبط خاص بـ IPTV
│   └── system/   MPRIS2 (D-Bus) + النافذة + منع الإطفاء   ← جديد كلياً
├── repositories/ ← منقولة كما هي
├── providers/    حالة Riverpod + متحكّم التشغيل
├── features/     الواجهة — مكتوبة من الصفر لسطح المكتب
└── widgets/      مكتبة الودجت (Nova Cinema)
```

## اختصارات لوحة المفاتيح

| | |
|---|---|
| `مسافة` / `K` | تشغيل / إيقاف مؤقت |
| `→` `←` | ±١٠ ثوانٍ |
| `↑` `↓` | الصوت |
| `F` / `F11` | ملء الشاشة |
| `M` | كتم |
| `S` / `A` | تبديل الترجمة / الصوت |
| `N` / `P` · `PgUp` / `PgDn` | القناة أو الحلقة التالية / السابقة |
| `Esc` | خروج من ملء الشاشة ثم تصغير المشغّل |
| `Ctrl+1…5` | الرئيسية · البث · الأفلام · المسلسلات · المفضلة |
| `Ctrl+F` · `Ctrl+,` | البحث · الإعدادات |

---

## English

A cinematic IPTV player **native to the MoOS desktop**: live TV, movies and
series over Xtream Codes or M3U, on the same playback engine the OS already ships
(`libmpv`), integrated with Plasma for real — media keys, the media applet,
screen-saver inhibition — and fully bilingual with RTL.

**Why Flutter and not QML,** when every other first-party MoOS app is pure QML:
QML cannot play IPTV. `QtMultimedia`'s FFmpeg backend chokes on the ragged
MPEG-TS and HLS that real panels serve. `libmpv` is the reference implementation
for exactly that, and MoOS already ships it as `mpv-libs`; media_kit is not a
second engine but a binding to that same `libmpv`. The app therefore adds **zero**
new runtime dependencies to the image, and MoPlayer's core — Xtream client, M3U
parser, models, repositories — is reused rather than rewritten in another
language.

Build with `just setup && just build && just install`. The design system is in
[`DESIGN.md`](DESIGN.md); the rules that will bite you are in [`AGENTS.md`](AGENTS.md).

Version 1.2 adds faster catalogue loading, previous/next live-channel zapping,
full keyboard navigation, resilient IPTV buffering, and a complete professional
playback deck. Source credentials live in a private 0600 application file and
never open KDE Wallet. A URL or media file opened while MoPlayer is already
running is forwarded to that window instead of starting a competing player.
