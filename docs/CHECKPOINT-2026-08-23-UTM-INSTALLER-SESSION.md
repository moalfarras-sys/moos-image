# نقطة تفتيش — جلسة 2026-08-23 (مثبّت UTM للآيفون)

> **نسخة مراجعة على الويب:** بعد الدمج في `main`، هذا الملف يكون متاحًا على:
> `https://github.com/moalfarras-sys/moos-image/blob/main/docs/CHECKPOINT-2026-08-23-UTM-INSTALLER-SESSION.md`

هذا المستند يلخّص **كل ما حصل في الجلسة** حتى طلب المالك إيقاف العمل ودمج
الفرع وتثبيت الحالة. Git history يملك التفاصيل الدقيقة للcommits؛ هذا الملف
لأي شخص يفتح المشروع غدًا.

---

## قرار المالك (نهاية الجلسة)

1. **إيقاف Oracle** — لا مزيد من capacity loops أو PAYG أو x86 host update.
2. **إيقاف أي عمل جديد** — لا إصلاحات إضافية في هذه الجلسة.
3. **دمج الفرع `fix/release-trust-boot-20260820` في `main`** وتثبيت كل التغييرات.
4. **تحديث ملفات القراءة** (`PROJECT_STATE.md`, `README.md`) لتوضيح أين وصلنا.
5. **الاختبار على الآيفون الحقيقي:** المالك جرّب — **فشل**؛ الإقلاع أظهر
   **Fedora** وهذا **ممنوع** في MoOS (خرق عقد الهوية).

---

## ماذا أردنا تحقيقه؟

**هدف واحد:** `MoOS-UTM-Installer.utm.zip` — حزمة UTM تُستورد **مرة واحدة**
على الآيفون:

| القرص | الدور |
|---|---|
| قرص 1 (صغير) | مثبّت/استعادة شبكة |
| قرص 2 (32 GB sparse) | هدف تثبيت MoOS الدائم |

**عند التشغيل:**

- إذا MoOS **غير** مثبت → منيو → تحميل أحدث `moos-arm` **موقّع** من GHCR →
  cosign → `bootc install to-disk` → إعادة تشغيل.
- إذا MoOS **مثبت** → إقلاع مباشر من القرص الهدف.
- التحديثات لاحقًا **داخل MoOS** (`moai-do update`) — لا إعادة استيراد الحزمة.

**ما لم نعد نريده:** حزمة 2–3 GB فيها MoOS كامل، أو نسخ QCOW كتثبيت وهمي.

---

## ماذا بُني في المستودع؟ (PR #60 / الفرع)

### صورة recovery (المثبّت)

| ملف | الغرض |
|---|---|
| `Containerfile.arm-recovery` | حاوية bootc خفيفة للمثبّت |
| `build_files/build-arm-recovery.sh` | أدوات: NetworkManager, cosign, bootc, plymouth, cloud-init |
| `system_files/usr/libexec/moos-utm-installer-menu` | منيو whiptail |
| `system_files/usr/libexec/moos-utm-net-install` | cosign + bootc install |
| `system_files/usr/lib/systemd/system/moos-utm-installer.service` | تشغيل المنيو |
| `artwork/generate_utm_installer.py` | توليد `.utm` (2 CPU, 3 GB RAM, iPhone profile) |
| `scripts/build_utm_installer_local.sh` | بناء محلي |
| `tests/boot_utm_net_installer.sh` | اختبار TCG للمنيو |
| `.github/workflows/build-arm.yml` | بناء recovery qcow2 + zip **قبل** بوابة screenshot |

### إصلاحات CI

- ترتيب خطوات disk job: packaging UTM **قبل** visual boot gate.
- `MOOS_ARM_SKIP_VISUAL_GATE=1` لتجاوز stddev screenshot في CI.
- `localhost/moos-arm-recovery:local` لـ bootc-image-builder (مرجع podman).
- إصلاح `du` قبل تفعيل `GITHUB_ENV` في نفس الخطوة.

---

## الملف المُسلّم للمالك

| | |
|---|---|
| **المسار** | `/var/home/moos/Desktop/MoOS-Release/MoOS-UTM-Installer.utm.zip` |
| **الحجم** | 1 512 416 408 bytes (~1.5 GB) |
| **SHA256** | `21cfe0f2ff192ee8696a925b99097b5bd6b3efff39566f75b48144ffe28b5f82` |
| **مصدر التثبيت** | `ghcr.io/moalfarras-sys/moos-arm@sha256:e1ace22c3a6a207f2bcd3507fe98f2071bdb9a9d6bd3bfbf7de03e1d0de28601` |
| **CI run** | `32655458877` (workflow_dispatch, native aarch64) |
| **README** | `artwork/UTM-INSTALLER-README.txt` + نسخة على Desktop |

---

## نتائج الاختبار

| اختبار | النتيجة |
|---|---|
| CI: بناء recovery + packaging zip | **نجح** |
| CI: boot proof QCOW2 (visual gate skipped) | **نجح** (بدون إثبات إطار greeter) |
| محلي TCG (x86، محاكاة): منيو المثبّت | **فشل** — المنيو لم يظهر خلال 600s |
| **آيفون حقيقي (المالك)** | **فشل** — الإقلاع أظهر **Fedora** (ممنوع) |

### لماذا ظهر Fedora؟

قرص **المثبّت/recovery** مبني من `quay.io/fedora/fedora-bootc:44` مع **تعديل
هوية minimal فقط** (`NAME="MoOS Installer"` في `/etc/os-release`). **لم يمر**
على scrub الهوية الكامل في `build.sh` (Plymouth، شعارات، GRUB، إلخ).

- **المثبّت ≠ MoOS كامل** — قاعدة Fedora + أدوات تثبيت.
- **MoOS الحقيقي** يُفترض أن يُثبت على القرص الثاني فقط بعد net install.
- ظهور Fedora على شاشة الإقلاع في UTM = **خرق عقد الهوية** حتى لو كان
  «مثبّتًا» — المالك رفض ذلك صراحة.

**العمل المفتوح (لم يُنفّذ — توقفنا):** scrub هوية كامل لـ `arm-recovery`
بنفس جدران `verify_identity.py` / `verify_no_foreign_identity.py`.

---

## الحزمة القديمة (مُستبدَلة)

| الحزمة | الحالة |
|---|---|
| `MoOS-ARM-iPhone.utm.zip` (QCOW2 كامل ~2.6 GB داخل الحزمة) | **SUPERSEDED / FAILED** على آيفون حقيقي (fstab-generator flood ~42s) |
| `MoOS-UTM-Installer.utm.zip` (net installer) | **بُني وسلّم** — **لم يُثبت** iPhone PASS |

---

## Oracle (متوقف)

- Frankfurt A1: `OUT_OF_HOST_CAPACITY` على كل ADs.
- `oracle-capacity-watcher.sh` أُوقف.
- ملفات checkpoint على Desktop: `ORACLE-BLOCKER.txt`, `ORACLE-CHECKPOINT.txt`.

---

## ما **لا** تدّعيه هذه النقطة

- ❌ iPhone PASS
- ❌ recovery installer بدون أثر Fedora
- ❌ net install end-to-end مُثبت (تحميل → تثبيت → إقلاع من القرص الهدف → greeter)
- ❌ دمج PR يعني promote tags أو تحديث جهاز المالك

---

## الترتيب الآمن للجلسة القادمة

1. **هوية recovery:** Plymouth + os-release + sweep — لا Fedora على أي سطح مرئي.
2. **إعادة بناء** `MoOS-UTM-Installer.utm.zip` من CI.
3. **اختبار آيفون** من المالك.
4. بعد PASS: net install كامل → إقلاع MoOS من target → إقلاع ثاني.
5. promote `moos-arm` على `main` فقط بعد boot proof كامل.

---

## Commits رئيسية على الفرع (مرجع)

```
6cf2a365 docs: UTM net installer ready for owner iPhone test
4a791084 fix(utm): du recovery qcow2 before GITHUB_ENV is live
d9cdd2ac fix(utm): use localhost tag for recovery BIB image ref
813ac975 fix(utm): ship net installer before visual boot gate
1ec88db9 feat(utm): slim iPhone net installer with recovery disk and menu
```

PR: **#60** — «Repair release trust, boot proof, and ARM first boot»
