# moos-image — مستودع بناء صورة MoOS

هذا هو مستودع المصدر والبناء لنظام **MoOS**: صورة bootc/OCI مبنية تقنياً فوق `ghcr.io/ublue-os/kinoite-main:44` مع Plasma Wayland. GitHub Actions يبني الصورة ويوقعها بـcosign ويدفعها إلى GHCR. كل تغيير دائم في النظام يبدأ هنا، يمر عبر CI، ثم يُنشر إلى الأجهزة بواسطة bootc.

آخر تحديث: 2026-07-11

> حالة التنفيذ الحالية وبوابات الوصول إلى إصدار كامل موثقة في
> [`MOOS_ROADMAP.md`](MOOS_ROADMAP.md). هذه الصورة تجاوزت نطاق هيكل M0 القديم:
> هوية Nova وتطبيقات MoOS وMo AI ومسارا ISO/NVIDIA موجودة فعلياً الآن.

> استبدل `moalfarras-sys` في كل الأوامر أدناه باسم مستخدمك على GitHub.

## هيكل المستودع (Repository layout)

```
moos-image/
├── Containerfile              # FROM ghcr.io/ublue-os/kinoite-main:44 + طبقات MoOS
├── Justfile                   # أوامر البناء المحلية (WSL2/podman) — الصورة فقط
├── build_files/build.sh       # branding + uupd + cleanup (يعمل داخل البناء)
├── system_files/              # ملفات تُنسخ كما هي إلى / داخل الصورة
│   ├── etc/moos/              # إعدادات MoOS (هيكل)
│   └── usr/share/
│       ├── plasma/look-and-feel/org.moos.nova/   # Global Theme (هيكل + metadata)
│       ├── sddm/themes/moos-nova/                # ثيم الدخول (Phase 5)
│       ├── plymouth/themes/moos-nova/            # ثيم الإقلاع (Phase 5)
│       └── wallpapers/NovaHorizon/               # خلفيات kpackage (Phase 3)
├── .github/workflows/
│   ├── build.yml              # بناء + دفع + توقيع cosign (أسبوعي + عند كل push)
│   └── build-iso.yml          # Titanoboa live ISO (يدوي + شهري) — CI فقط
├── iso/flatpaks.list          # تطبيقات Flatpak المحملة مسبقاً في الـ ISO
├── .gitattributes / .gitignore
└── README.md                  # هذا الملف
```

## 1) من مجلد محلي إلى مستودع GitHub

```bash
# داخل WSL2 أو Git Bash، من مجلد moos-image/
git init -b main
git add .
git commit -m "MoOS M0 Nova Seed: initial image scaffold"

# أنشئ مستودعاً عاماً وادفع (يتطلب gh CLI مسجل الدخول)
gh repo create moos-image --public --source=. --push
```

## 2) إعداد مفتاح التوقيع (SIGNING_SECRET) — إلزامي قبل أول بناء

كل صور MoOS موقعة بـcosign، والمفتاح العام المتعقب هو `cosign.pub`:

```bash
# 1. توليد زوج المفاتيح (اترك passphrase فارغة لسهولة الاستخدام في CI)
cosign generate-key-pair

# 2. المفتاح الخاص -> سر في GitHub Actions (لا يُرفع أبداً — موجود في .gitignore)
gh secret set SIGNING_SECRET < cosign.key

# 3. المفتاح العام يُرفع إلى المستودع ليتحقق منه المستخدمون
git add cosign.pub && git commit -m "Add cosign public key" && git push
```

## 3) أول بناء

- **في CI (الطريقة الرسمية):** أي push إلى `main` يشغّل `build.yml` تلقائياً، أو شغّله يدوياً من تبويب Actions -> "Build MoOS image" -> Run workflow. الناتج: `ghcr.io/moalfarras-sys/moos:latest` + وسم بالتاريخ `YYYYMMDD`.
- بعد أول نجاح: اجعل الحزمة عامة (GitHub -> Packages -> moos -> Package settings -> Change visibility -> Public) وإلا سيفشل `bootc switch` بدون تسجيل دخول.
- **محلياً (حلقة التطوير السريعة، داخل WSL2 فقط):**

```bash
# الصورة الرئيسية
just build          # = podman build --build-arg BASE_IMAGE=ghcr.io/ublue-os/kinoite-main:44 -t moos:latest .

# متغير NVIDIA
just build-nvidia

# فحص bootc (يعمل تلقائياً أيضاً كآخر خطوة في الـ Containerfile)
just lint
```

> **تحذير:** بناء ISO غير مدعوم في WSL2. مساره الرسمي هو `build-iso.yml`، لكنه خارج مهمة إصلاح وتحديث النظام المثبّت الحالية.

## 4) تجربة الصورة في VM (rebase عبر bootc switch)

في Hyper-V أنشئ Gen2 VM (Secure Boot: معطّل أو قالب "Microsoft UEFI Certificate Authority") وثبّت فيه Fedora Kinoite 44 عادي، ثم من داخل الـ VM:

```bash
# التحقق من التوقيع (اختياري لكنه موصى به)
cosign verify --key https://raw.githubusercontent.com/moalfarras-sys/moos-image/main/cosign.pub \
  ghcr.io/moalfarras-sys/moos:latest

# ثبّت الحالة الحالية كنقطة رجوع قبل أي تغيير جذري
sudo ostree admin pin 0

# التحويل إلى صورة MoOS
sudo bootc switch ghcr.io/moalfarras-sys/moos:latest
sudo systemctl reboot
```

بعد الإقلاع تحقق من deployment الفعلي:

```bash
cat /etc/os-release        # NAME="MoOS" و PRETTY_NAME="MoOS 0.1 (Nova Seed)"
systemctl status uupd.timer
bootc status
```

التراجع في أي وقت:

```bash
sudo bootc rollback && sudo systemctl reboot
# أو اختر الإصدار السابق من قائمة GRUB عند الإقلاع
```

## 5) بناء الـ ISO

من تبويب Actions -> "Build MoOS Live ISO" -> Run workflow (أو انتظر الجدولة الشهرية). الناتج يُرفع كـ workflow artifact مؤقتاً؛ الاستضافة الدائمة على Cloudflare R2 تأتي لاحقاً (حد GitHub Releases هو 2GB للملف). اكتب الـ ISO على USB بـ Fedora Media Writer أو Rufus — **Ventoy ممنوع** (يكسر live ISOs الخاصة بـ bootc).

## أين هذا من الخطة الكاملة؟

المستودع أصبح صورة MoOS وظيفية تتجاوز M0: يبني الهوية، الثيمات، المثبت،
تطبيقات النظام، Mo AI، وصورة NVIDIA. استخدم `MOOS_ROADMAP.md` كمصدر الحقيقة
للحالة والبوابات المتبقية، ولا تعتمد على أرقام المراحل التاريخية وحدها.

## قيود معروفة (Known Issues)

- أسماء مدخلات Titanoboa action في `build-iso.yml` مفترضة من توثيق v0.1.x — يجب التحقق من `action.yml` في https://github.com/ublue-os/titanoboa قبل أول تشغيل، والتثبيت على وسم إصدار فور توفره.
- سياسة الحاويات تسمح حالياً بسجل MoOS لكنها لا تفرض تحقق cosign أثناء
  التثبيت/التحديث؛ يجب إكمال واختبار مسار sigstore قبل جعله إلزامياً.
- يلزم اختبار SDDM/Plymouth/المثبت على عتاد حقيقي وبمقاييس عرض متعددة.
- تصنيفات Bazaar المنسقة موجودة، لكن ربطها الكامل بالمتجر ما زال مطلوباً.
- artifacts الـ ISO تنتهي صلاحيتها خلال 7 أيام — R2 hosting لم يُفعّل بعد.

## الخطوات التالية (Next Actions)

1. تشغيل CI على الدفعة الحالية والتحقق من صورتي MoOS وMoOS NVIDIA.
2. اختبار صورة NVIDIA على RTX 2080 SUPER ثم التحقق من Wayland/Vulkan والصوت.
3. اختبار خدمة Mo AI الاختيارية وتنزيل النموذج وحالات الفشل على الجهاز الحقيقي.
4. تنفيذ مصفوفة الهوية المرئية والعتاد والأمان في `MOOS_ROADMAP.md`.
