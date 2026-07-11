# CODEX_HANDOFF.md — خطة إكمال MoOS إلى نظام كامل بلا نقص

> **لمن:** Codex، يعمل **داخل النظام MoOS المثبَّت على جهاز حقيقي** + على نفس مستودع البناء `moos-image/`.
> **الهدف:** MoOS كامل الهوية، الثيم مطبَّق بالكامل، Mo AI شغّال محلياً، صفر أثر لأي نظام آخر (Fedora/KDE/Breeze) في الواجهة.
> **آخر تحديث:** 2026-07-11 • كتبها Claude بعد جلسة إصلاح التثبيت والإقلاع.

---

## 0) ميزتك الحاسمة (استغلّها)

أنت **داخل النظام المثبَّت على عتاد حقيقي** (GPU حقيقي، لا قيود QEMU). أنا (Claude) كنت محصوراً بمحاكاة على ويندوز بلا GPU، فتعذّر عليّ اختبار السطح الرسومي حياً. **أنت تقدر:**
- تشغّل أوامر فعلية على النظام الحي (`plasma-apply-lookandfeel`، `journalctl`، `kscreen-doctor`، `ramalama`).
- تشوف الشكل بعينك وتصلح فوراً.
- تعدّل الريبو + تدفع + تحدّث النظام بـ `bootc upgrade`.

**دورة العمل:** عدّل `moos-image/` → `git push` → CI يبني ويوقّع ويدفع `ghcr.io/moalfarras-sys/moos:latest` (~11 دقيقة) → على الجهاز `sudo bootc upgrade && systemctl reboot`. للتجارب السريعة على السطح (ثيم/إعدادات مستخدم) طبّقها مباشرة بلا إعادة بناء.

---

## 1) الحالة المؤكَّدة (يعمل — لا تلمسه)

| البند | الحالة | دليل |
|---|---|---|
| **التثبيت** (Anaconda ostreecontainer، يحتاج إنترنت) | ✅ نجح على عتاد حقيقي | المستخدم ثبّت v20 |
| **الإقلاع بلا Emergency Mode** | ✅ مُثبَت | `ostree-prepare-root` في الـ initramfs + إقلاع qcow2 بصفر emergency، دخل "Welcome to MoOS 0.1 (Nova)" |
| **Plymouth** | ✅ `moos-nova` (شاشة الإقلاع MoOS) | `/etc/plymouth/plymouthd.conf` Theme=moos-nova |
| **الهوية النصية** | ✅ | os-release ID=moos، system-release "MoOS release 44"، GRUB entry "MoOS 0.1 (Nova)" |
| **سياسة الحاويات** | ✅ `insecureAcceptAnything` لـ ghcr.io/moalfarras-sys → `bootc upgrade` يعمل | build.sh (z3) |

**تحذير:** لا تعِد `sigstoreSigned` في policy.json بلا wiring كامل (`use-sigstore-attachments` + اختبار) — كسر التثبيت مرة (`A signature was required, but no signature exists`).

---

## 2) النواقص (رتّبها كأولويات)

### أولوية P0 — الثيم لا يُطبَّق كاملاً على المستخدم المثبَّت (المشكلة الأساسية)
**العرض:** النظام يقلع لكن السطح يبدو Breeze/عام، لا MoOS Nova (خلفية عامة، مظهر ناقص).
**السبب الجذري:** `/etc/xdg/kdeglobals` يضبط `[KDE] LookAndFeelPackage=org.moos.nova`، لكن **Plasma 6 يطبّق تلقائياً الألوان/الأيقونات فقط من الثيم الافتراضي — لا الخلفية ولا المظهر الكامل**.
**ما عملته أنا (v21):** أضفت `/usr/bin/moos-apply-theme` + autostart `org.moos.apply-theme.desktop` يطبّق `plasma-apply-lookandfeel org.moos.nova` + الخلفية + NovaDark عند أول دخول (علامة `~/.local/state/moos-nova-theme-applied`).
**مهمتك:**
1. حدّث الجهاز (`bootc upgrade` → reboot → login) واختبر: هل تطبّق الثيم؟ افحص `~/.cache/moos-apply-theme.log` و `~/.local/state/moos-nova-theme-applied`.
2. لو لم يطبّق كاملاً، شخّص حياً: `plasma-apply-lookandfeel -a org.moos.nova` يدوياً في Konsole وشوف الأخطاء. تحقق أن `org.moos.nova` يحوي كل ما يلزم (قد ينقص `contents/previews` أو مكونات — أكمِلها).
3. تأكد من كل عنصر: خلفية NovaHorizon، NovaDark، أيقونات Nova، مؤشر NovaIce، splash `org.moos.nova`، خطوط IBM Plex، الـ Dock (قالب `defaultPanel` — Mo AI أول أيقونة).

### أولوية P1 — استئصال أي أثر لنظام آخر في الواجهة
**مهمتك (على النظام الحي — أنت تقدر تشوف):**
- افحص "About this System" (kinfocenter) → لازم MoOS + شعار moos-logo.
- افحص القوائم/الأيقونات/الحوارات بحثاً عن أي "Fedora/KDE/Breeze".
- **"شعار Fedora عند الإقلاع"** (شكوى المستخدم المتكررة): أثبتُّ أن **الصورة نظيفة** (Plymouth=moos-nova، لا ثيم GRUB فيه Fedora، لا شعار fedora في الصورة). الأثر المتبقي يُنشأ **وقت التثبيت** (إدخال UEFI باسم "Fedora" في الـ NVRAM + مسار shim‏ `EFI/fedora` + grub.cfg المولّد)، فلا يُصلَح من الصورة بل **على النظام الحي**. شحنتُ لهذا سكربتاً جاهزاً:
  - شخّص (آمن، للقراءة فقط): `sudo moos-fix-boot-branding`
  - أصلح (يعيد تسمية إدخال UEFI لـ MoOS + يثبّت Plymouth + يطبّق ثيم GRUB، كله محروس): `sudo moos-fix-boot-branding --apply`
  - **اطلب من المستخدم صورة للشاشة بالضبط** وطابقها مع أقسام السكربت: قسم 2 = اسم إدخال الإقلاع في الـ firmware، قسم 3 = شاشة GRUB، ولا شيء منهما = شعار اللوحة الأم (BGRT — خارج سيطرتنا).

### أولوية P2 — Mo AI شغّال محلياً بالكامل (v1 حالياً)
**الحالة الحقيقية:** الواجهة (Kirigami/QML) تفتح + `moai-start` موجود، **لكن يحتاج تحميل موديل يدوياً + RamaLama، وليس auto-start كامل**.
**الملفات:** `system_files/usr/share/moos/apps/moai/main.qml` (الواجهة — تتصل بـ `http://127.0.0.1:8080/v1/chat/completions`)، `/usr/bin/moai` (مُشغّل qml-qt6)، `/usr/bin/moai-start` (ينزّل الموديل + يشغّل ramalama)، `/usr/bin/moai-do` (أفعال النظام عبر pkexec).
**مهمتك:**
1. على الجهاز: `moai-start` → تأكد أنه ينزّل Qwen3 عبر RamaLama ويشغّل الخادم على 8080.
2. افتح Mo AI → أرسل رسالة → تأكد أن الموديل المحلي يجيب.
3. أضف **auto-start اختياري** (systemd user service لـ ramalama) مع احترام الموارد — واجعل الواجهة تعرض حالة "يُحمّل الموديل" بوضوح.
4. لا تدّعِ "Mo AI كامل" — وثّق بصدق ما يعمل.

### أولوية P3 — تطوير الشكل (بعد ثبات الأساس)
- حركات/motion على السطح (kwinrc: magiclamp/scale/slide — تحقق أنها مطبَّقة على العتاد الحقيقي).
- أزرار النوافذ يسار (macOS)، blur، زوايا مدوّرة.
- شاشة الدخول SDDM moos-nova — اختبرها حياً (لوحة مفاتيح عربية افتراضية).
- الأصول: 3 خلفيات Codex (NovaAurora/Deep/Pulse)، أيقونات التطبيقات، أصوات moos-nova (فعّلها [Sounds] Theme=moos-nova).

---

## 3) الملفات المفتاحية (خريطتك في `moos-image/`)

| الملف/المجلد | الدور |
|---|---|
| `build_files/build.sh` | **قلب البناء** — الحزم، الثيمات، إعادة بناء initramfs (مقطع c2 فيه إصلاح `--add ostree` + حارس)، os-release، سياسة الحاويات (z3)، مسح شعارات Fedora (z2) |
| `system_files/etc/xdg/kdeglobals` + `plasmarc` + `kwinrc` + `kcminputrc` | إعدادات Plasma الافتراضية (ألوان، ثيم، حركات، مؤشر) |
| `system_files/etc/xdg/autostart/org.moos.apply-theme.desktop` + `usr/bin/moos-apply-theme` | **تطبيق الثيم عند أول دخول** (إصلاح P0) |
| `system_files/usr/share/plasma/look-and-feel/org.moos.nova/` | الـ Global Theme (metadata + contents/defaults) |
| `system_files/usr/share/plasma/layout-templates/.../defaultPanel/contents/layout.js` | **الـ Dock** (Mo AI أول أيقونة + التطبيقات) |
| `system_files/usr/share/wallpapers/NovaHorizon/` (+ NovaAurora/Deep/Pulse) | الخلفيات |
| `system_files/usr/share/sddm/themes/moos-nova/` | شاشة الدخول |
| `system_files/usr/share/plymouth/themes/moos-nova/` | شاشة الإقلاع |
| `system_files/usr/share/moos/apps/moai/main.qml` | واجهة Mo AI |
| `system_files/usr/share/moos/grub-theme/` | ثيم GRUB (theme.txt + background.png) |
| `system_files/etc/default/grub` | إعداد GRUB (DISTRIBUTOR=MoOS + THEME) |
| `artwork/generate_nova_visuals.py` | مولّد الأصول (PIL) — أيقونات، خلفيات، إلخ |
| `.github/workflows/build.yml` | بناء+توقيع+دفع الصورة | 
| `.github/workflows/build-disk.yml` | **بناء qcow2 عبر bootc-image-builder + تحقّق initramfs** (أضفته للاختبار على Linux) |

---

## 4) دروس تقنية حرجة (لا تكرّر أخطائي)

1. **`dracut --force` داخل buildah يُسقط وحدة `ostree` صامتاً** (فحص check() يشترط `-x` على `/usr/lib/ostree/ostree-prepare-root`) → لازم `chmod 0755` عليها + `--add ostree` + حارس يفحص سجل dracut. **هذا كان سبب Emergency Mode في v19.** (مُصلَح — لا تكسره.)
2. **`lsinitrd` يُنهي خطوة البناء داخل buildah** (يبتلع ذاكرة عند الالتقاط في متغير) → افحص سجل dracut `Including module: ostree` بدلاً منه، أو اكتب لملف بـ timeout.
3. **`ID=moos` يكسر أدوات تعتمد على معرّف التوزيعة:** anaconda profiles (حُلّت بـ profile.d/moos.conf)، bootc-image-builder (`missing DefaultRootFs` → حُلّت بـ `/usr/lib/bootc/install/00-moos.toml` type=xfs)، cosign policy. توقّع نفس النمط في أدوات أخرى.
4. **`sigstoreSigned` في policy.json يكسر التثبيت** بلا `use-sigstore-attachments` + مسار تحقق مُختبَر. (حالياً `insecureAcceptAnything` — التوقيع غير مُتحقَّق، موثّق بصدق. إن فعّلت cosign الحقيقي: اختبره عبر build-disk.yml أولاً.)
5. **Plasma 6 يطبّق الألوان/الأيقونات فقط من الثيم الافتراضي، لا الخلفية** → لازم `plasma-apply-lookandfeel` صريح (إصلاح P0).
6. **اختبار إقلاع القرص المثبَّت:** استخدم `build-disk.yml` (bootc-image-builder qcow2 على Linux CI) — يتجاوز حاجة anaconda/Docker/GPU. النتيجة أثبتت صفر emergency.
7. **فحص محتوى الصورة بلا VM:** استخرج `LiveOS/squashfs.img` من الـ ISO بـ 7-Zip، ثم استخرج الملفات (مسارات Windows بـ `\`). لفك ضغط initramfs: cpio مبكر ثم zstd (ابحث عن magic `28 b5 2f fd`).
8. **QEMU على ويندوز:** `-cpu max` يُعطّل OVMF على WHPX → استخدم `-cpu Haswell`. الـ ISO الحي يحتاج وصلاً كـ CD-ROM (kernel `root=live:CDLABEL=`) لا قرص virtio.

---

## 5) خطة التنفيذ المرتّبة (امشِ عليها)

**المرحلة A — تثبيت الأساس البصري (P0):**
1. `bootc upgrade` → reboot → login → افحص هل تطبّق `moos-apply-theme` (السجل + الشكل).
2. أصلح ما لا يطبّق (Global Theme كامل: خلفية + splash + مظهر). اختبر حياً بـ `plasma-apply-lookandfeel`.
3. تأكد من الـ Dock (Mo AI + تطبيقات)، الأيقونات، المؤشر، الخطوط.
4. **بوابة الخروج:** سطح مكتب يبدو MoOS Nova 100% لمستخدم جديد.

**المرحلة B — صفر أثر لنظام آخر (P1):**
5. اسحب كل سطح (About، القوائم، GRUB، SDDM، الإقلاع) وأزل أي Fedora/KDE/Breeze.
6. حدّد وأصلح "شعار Fedora عند الإقلاع" (GRUB grub.cfg / plymouth / BGRT).
7. **بوابة الخروج:** لا اسم/شعار غير MoOS في أي واجهة.

**المرحلة C — Mo AI محلي كامل (P2):**
8. `moai-start` ينزّل ويشغّل الموديل؛ الواجهة تجيب محلياً؛ auto-start اختياري بحالة واضحة.
9. **بوابة الخروج:** Mo AI يفتح ويجيب محلياً بلا خطوات يدوية معقّدة (أو بخطوة واحدة موثّقة).

**المرحلة D — الصقل والاختبار (P3):**
10. نفّذ `MOOS_TESTING_CHECKLIST.md` كاملاً على العتاد (WiFi/بلوتوث/سبات/صوت/تحديث/rollback).
11. حركات/motion، blur، شاشة الدخول، الأصوات.
12. **بوابة الخروج:** كل صفوف الاختبار خضراء على العتاد الحقيقي.

---

## 6) قواعد صارمة (طلب المستخدم)
- **ممنوع أي اسم/شعار نظام آخر داخل الواجهة** — MoOS فقط.
- **صدق كامل:** لا تدّعِ ميزة غير منفّذة (خاصة Mo AI و cosign). وثّق ما يعمل وما لا يعمل.
- **لا تكسر الإقلاع/التثبيت** — راجع دروس §4 قبل لمس build.sh (خاصة initramfs والسياسة).
- كل تغيير: اختبره حياً على العتاد قبل اعتباره منجزاً.

---

## 7) مراجع إضافية في الريبو
`BUILD_REPORT.md` (تشخيص عطل الإقلاع) • `INSTALL_TEST_REPORT.md` (براهين الإقلاع) • `REAL_HARDWARE_TEST_REPORT.md` • `CHANGELOG.md` (v13→v21) • `MOOS_TESTING_CHECKLIST.md` • `MOOS_AI_ASSISTANT_PLAN.md` • `MOOS_DESIGN_SYSTEM.md`.
