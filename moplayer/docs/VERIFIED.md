# ما جرى التحقق منه فعلياً — Verified on real hardware

> MoOS's own `AGENTS.md` says it plainly: **"A green build proves nothing about
> what the user sees."** So this file records what was actually run on the
> maintainer's MoOS desktop — with the commands, so anyone can re-run them — and,
> just as importantly, **what was not tested**.

آخر تحقق: **2026-07-19** — على جهاز MoOS حقيقي (Fedora Kinoite 44 · KDE Plasma 6 ·
Wayland · جلسة المشرف نفسها).

---

## 1. يبني ويعمل — Builds and runs

```bash
just build        # ✓ Built build/linux/x64/release/bundle/moplayer
flutter analyze   # ✓ No issues found!
```

`libmpv` لم يُحزم مع التطبيق: `mpv-libs-0.41.0-4.fc44` الموجود أصلاً في صورة MoOS هو
ما يشغّل الفيديو. عند الإقلاع يسجّل التطبيق:

```
package:media_kit_libs_linux registered.
media_kit: VideoOutput: Using H/W rendering.
```

**H/W rendering** — أي أن فك الترميز يمرّ على كرت الشاشة، لا على المعالج.

## 2. يشغّل بثاً حقيقياً — It actually plays

```bash
moplayer https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8
```

صورة الشاشة: [`screenshots/player.png`](screenshots/player.png). البث (HLS — نفس
الحاوية التي تبثّها لوحات IPTV) يعمل، وأدوات التحكّم السينمائية تظهر فوقه، وعنوان
النافذة صار اسم المادة (`x36xhzz.m3u8 — MoPlayer`)، وبلازما رسمت أيقونة الصوت على
أيقونة التطبيق في الشريط.

## 3. مفاتيح الوسائط ولوحة بلازما — MPRIS

هذا أهم ما يجعل التطبيق "من النظام" لا "على النظام". التحقق تم بمخاطبة ناقل الجلسة
مباشرةً — وهو حرفياً ما تفعله لوحة بلازما ومفاتيح الوسائط في لوحة المفاتيح:

```bash
busctl --user list | grep mpris
# org.mpris.MediaPlayer2.moplayer   ...   moplayer   mo

busctl --user get-property org.mpris.MediaPlayer2.moplayer \
  /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2 DesktopEntry
# s "org.moos.moplayer"      ← يطابق ملف .desktop، ولهذا تظهر أيقونة MoPlayer لا مربّع رمادي
```

| ما نفّذه سطح المكتب | النتيجة |
|---|---|
| `Raise` | ✓ رفعت النافذة إلى الأمام |
| `Pause` | ✓ `PlaybackStatus` صار `Paused` |
| `PlayPause` | ✓ عاد `Playing` |
| `Volume = 0.35` | ✓ انخفض صوت التطبيق فعلاً |
| `Position` | ✓ يتقدّم (28.4s → 31.4s) |
| `Metadata` | ✓ العنوان والـ trackId يصلان إلى بلازما |

## 4. ملف `.desktop` لا يَعِد بما لا ينفّذ

MoOS تعلّم هذا الدرس بالطريقة الصعبة (أحد عشر زرّاً شُحنت تفتح مسارات `moos://` غير
موجودة). لذلك كل وعد في ملف الإطلاق مربوط بكود:

```bash
xdg-mime query default application/x-mpegurl
# org.moos.moplayer.desktop          ← فتح ملفات M3U من Dolphin: منفَّذ

moplayer --section live ~/tv.m3u     # ✓ فتح على "البث المباشر" واستورد القائمة
desktop-file-validate ~/.local/share/applications/org.moos.moplayer.desktop
# (لا مخرجات = صالح)
```

## 5. يُستورد مصدر M3U ويُفهرَس

`moplayer assets/demo/demo.m3u` → القنوات والتصنيفات (`group-title`) والشعارات
(`tvg-logo`) ظهرت جميعها: [`screenshots/live.png`](screenshots/live.png).

## 6. الإغلاق وتغيير الشاشة — Close and display change

أُعيد إنتاج خطأ الإغلاق على NVIDIA/Wayland أولاً: طلب الإغلاق الحقيقي من KWin كان
ينهي Flutter داخل `libepoxy` بعد `eglMakeCurrent failed`. بعد ربط `delete-event`
بمسار خروج يسبق teardown المعيب، شُغّلت حزمة release نفسها على الجهاز الحي:

- الانتقال أثناء بقاء MoPlayer مفتوحاً من 1920×1080@60 إلى 3840×2160@60
  بمقياس 2 ثم الرجوع إلى 1080p: بقيت النافذة مرسومة، بلا شاشة سوداء.
- الإغلاق بطلب KWin: رمز الخروج 0، ولا عملية باقية.
- لا `coredump`، ولا خطأ EGL/libepoxy جديد، ولا وحدة systemd فاشلة.
- `flutter analyze` بلا ملاحظات، ونجحت اختبارات Flutter الـ95 وبناء release.

---

## ما لم يُختبَر بعد — Not tested yet

كتابة هذا القسم ليست تواضعاً؛ هي شرط ألّا يتحوّل هذا الملف إلى ضوء أخضر كاذب.

- **لوحة Xtream حقيقية.** كل ما سبق جرى على M3U وبثوث HLS عامة. مسار Xtream
  (`player_api.php`، الأفلام، المسلسلات، دليل البرامج) هو كود منقول من تطبيق iOS
  يعمل في الإنتاج، لكنه **لم يُشغَّل مقابل خادم حقيقي من هذا البناء**. يلزم حساب حقيقي.
- **رمز التفعيل (QR).** يحتاج خادم `moalfarras.space` — لم يُجرَّب من هنا.
- **مزامنة Supabase.** معطّلة افتراضياً (لا مفاتيح في البناء)، فلم تُختبر.
- **خزنة المفاتيح.** `flutter_secure_storage` على لينكس يحتاج Secret Service. حفظ
  المصدر نجح في هذه الجلسة، لكن **لم يُختبر على جهاز بلا محفظة KWallet مفتوحة**.
- **الترجمات والمسارات الصوتية المتعدّدة** ظاهرة في القائمة لكن لم تُبدَّل يدوياً في
  بثّ يحتوي عدّة مسارات.
- **الواجهة العربية (RTL)** مكتوبة بالكامل واللغة تتبع الجلسة، لكن اللقطات أعلاه
  أُخذت على جلسة إنجليزية.
- **التثبيت داخل صورة MoOS** (طبقة `bootc`) موصوف في
  [`../packaging/moos/moos-image/`](../packaging/moos/moos-image/) لكنه **لم يُدمج في
  `moos-image` ولم يمرّ عبر CI بعد**. ما جرى هنا هو تثبيت في `~/.local` بلا صلاحيات
  جذر وبلا إعادة إقلاع.
