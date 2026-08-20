# moos-image — مستودع بناء نظام MoOS

هذا هو مستودع المصدر والحقيقة لنظام **MoOS**: نظام تشغيل حقيقي مبني على
**Fedora Atomic (bootc/OSTree)** و**KDE Plasma 6 (Wayland)** فوق القاعدة المثبتة
`ghcr.io/ublue-os/kinoite-main:44`. GitHub Actions يبني الصور ويوقعها بـcosign
ويدفعها إلى GHCR، والأجهزة المثبتة تسحب التحديثات الموقعة منها مباشرة —
**بما فيها جهاز المشرف اليومي**.

آخر تحديث: 2026-08-20

> ## ⚠️ قراءة إلزامية قبل أي تعديل
>
> 1. [`skills/moos-engineering/SKILL.md`](skills/moos-engineering/SKILL.md) —
>    **المهارة الإلزامية لكل إيجنت**: ما هو MoOS، قواعد العمل، والممنوعات.
> 2. [`AGENTS.md`](AGENTS.md) — القواعد وعقد الهوية وبوابات البناء.
> 3. [`PROJECT_STATE.md`](PROJECT_STATE.md) — الخريطة الحية: ما هو موجود فعلاً،
>    وما هي الفخاخ التي كلفت المشروع أياماً.
> 4. [`RELEASE.md`](RELEASE.md) — عقد الإصدار الحالي من candidate إلى artifacts
>    مُقلعة ثم promotion؛ لا تستنتج مسار النشر من handoff أو سجل جلسة قديم.
>
> هذا النظام مثبّت على جهاز حقيقي يسحب من `main` عبر CI. لا توجد بيئة تجريبية
> بين الدمج وبين جهاز قد يفشل في الإقلاع — وقد حدث ذلك فعلاً مرة. الحراسات في
> `build_files/build.sh` **تُفشل البناء بصوت عالٍ** عمداً؛ لا تُزل حارساً لأنه
> أزعجك، ولا تدّعِ نجاح شيء لم تختبره.

## نظام التصميم: MoOS UI — Liquid Glass Design System

**MoOS UI** هو نظام التصميم الرسمي لكل ما يراه المستخدم: سطح المكتب، اللوحة
(الدوك)، قائمة التطبيقات، الإشعارات، النوافذ (Plasma Style + Aurorae)، شاشات
تسجيل الدخول والقفل والإطفاء/إعادة التشغيل والتحديث، المثبّت، وتطبيقات MoOS —
**Mo AI** و**Mo Store** و**MoPlayer** و**Mo PC Remote**.

- التنفيذ على محرك **UI2** (`org.moos.ui2.*`): عائلة ثيمات كاملة (Graphite داكن /
  Tidal فاتح + أعضاء لوحية منها Nova وAmethyst وMidnight وAurora)، تتولد من
  `artwork/generate_moos_ui2.py` و`artwork/generate_moos_themes.py`.
- «Nova» اليوم اسم **عضو واحد** من العائلة (`MoOS UI · Nova`) وجيلٍ أول متقاعد —
  وليس اسم نظام التصميم.
- الزجاج مدروس لا مبالغ فيه (لا `BlurStrength` فوق 15)، الحركة تحترم إعداد
  "الحركات مطفأة"، والعربية وRTL وشاشات 4K/HiDPI أهداف من الدرجة الأولى.
- مصادر الألوان الحية: `artwork/moos-ui2/palette.json` +
  `artwork/moos-themes/palettes.json`؛ والعقد الكامل في
  [`artwork/MOOS_UI2_DESIGN.md`](artwork/MOOS_UI2_DESIGN.md).

## الصور المنشورة (كلها من شجرة واحدة وContainerfile واحد)

| الصورة | ماذا تكون | القاعدة |
|---|---|---|
| `ghcr.io/moalfarras-sys/moos` | سطح المكتب العام | `kinoite-main:44` المثبتة |
| `ghcr.io/moalfarras-sys/moos-nvidia` | نفس القاعدة + سواقة NVIDIA المفتوحة مطبّقة كطبقة | نفسها |
| `ghcr.io/moalfarras-sys/moos-cloud` | نسخة الخوادم (VPS): بلا حزم ألعاب/أندرويد، SSH هو الباب، سطح مكتب عبر المتصفح | نفسها |

كل build يومي أو يدوي أو ناتج من `main` يُدفع أولًا بوسم candidate مربوط بـrun
وcommit، ثم يوقّع digest ويُتحقق منه. لا يحرّك `build.yml` وسم `latest`.
`latest` ووسم الإصدار لا يتحركان إلا من `promote-x86.yml` بعد إقلاع نفس digest
داخل QCOW2 وISO النهائيين والتحقق من أدلتهما. **النظام المثبت يفرض التحقق من
التوقيع** (سياسة sigstoreSigned + `/etc/pki/containers/moos.pub`؛ المفتاح العام
المتعقب هنا هو `cosign.pub`).

## هيكل المستودع

```
moos-image/
├── Containerfile               # النسخ الثلاث؛ IMAGE_NAME يحدد هل تُطبَّق سواقة NVIDIA
├── build_files/build.sh        # الهوية + الحزم + بوابات الإقلاع/الهوية (يُفشل البناء عند الخطر)
├── build_files/verify_*.py     # بوابات الصورة: الهوية، التجربة، لا-هوية-أجنبية، المتجر
├── system_files/               # تُنسخ حرفياً إلى / داخل الصورة (ثيمات، تطبيقات، وحدات systemd)
├── artwork/                    # مولدات MoOS UI ومصادر الفن + بواباته البصرية
├── moremote/                   # Mo PC Remote (وكيل .NET + واجهة ويب) — يُبنى داخل الصورة
├── moplayer/                   # MoPlayer (Flutter، منسوخ من MoPlayerMoOS) — يُبنى داخل الصورة
├── tests/                      # نفس البوابات التي يشغلها CI + post-update-check.sh للجهاز الحي
├── skills/moos-engineering/    # المهارة الإلزامية لكل إيجنت
├── iso/                        # قائمة Flatpaks المحملة مسبقاً في الـ ISO
├── .github/workflows/
│   ├── build.yml               # بناء + دفع + توقيع الصور الثلاث (push + يومي + يدوي)
│   ├── build-iso.yml           # Titanoboa live ISO (يدوي + شهري)
│   ├── build-disk.yml          # صورة قرص qcow2 (يدوي)
│   ├── build-arm.yml           # ARM native + QCOW2 boot proof + promotion
│   └── promote-x86.yml         # promotion بعد إثبات build + QCOW2 + ISO
├── Justfile                    # build / build-nvidia / build-cloud / lint / sync-moplayer
├── AGENTS.md · PROJECT_STATE.md · MOOS_ROADMAP.md   # القواعد · الخريطة · الحالة
└── cosign.pub                  # المفتاح العام للتحقق من كل الصور
```

## البناء والاختبار

- **الرسمي (CI):** أي push إلى `main` يشغّل `build.yml` فيبني الصور الثلاث
  ويوقع digests ويدفع candidates فقط. بوابات المستودع (خطوة "Repo gates") تعمل
  أولاً. اتبع [`RELEASE.md`](RELEASE.md) لبناء artifacts من digest العام نفسه
  ثم promotion؛ مجرد نجاح container build ليس إصدارًا.
- **محلياً:**

```bash
# البوابات السريعة (ثوانٍ، بلا حاوية) — نفس قائمة build.yml حرفياً:
bash -n build_files/build.sh
python3 tests/verify_user_experience.py   # … بقية القائمة في build.yml

# بناء صورة كامل (يشغّل كل بوابات الصورة: الهوية، initramfs، NVIDIA، تشغيل تطبيقات QML):
just build            # أو build-nvidia / build-cloud
just lint             # فحص bootc container lint
```

## التحديث على جهاز مثبت

```bash
moai-do update        # يجهز أحدث digest موقّع وثابت؛ يُطبق عند إعادة التشغيل
# التراجع في أي وقت: sudo bootc rollback ثم إعادة التشغيل، أو اختيار الإصدار السابق من GRUB
# بعد أول إقلاع من تحديث: bash tests/post-update-check.sh
```

التثبيت الأول على جهاز Kinoite قائم:

```bash
cosign verify --key https://raw.githubusercontent.com/moalfarras-sys/moos-image/main/cosign.pub \
  ghcr.io/moalfarras-sys/moos:latest
sudo ostree admin pin 0
sudo bootc switch ghcr.io/moalfarras-sys/moos:latest && sudo systemctl reboot
```

## ISO وqcow2

من تبويب Actions: **Build MoOS Live ISO** (Titanoboa) أو **Build MoOS disk image
(qcow2)**. الناتج workflow artifact تنتهي صلاحيته خلال أيام (حد GitHub Releases
هو 2GB) — الاستضافة الدائمة لم تُفعّل بعد. اكتب الـ ISO بـ Fedora Media Writer
أو Rufus — **Ventoy ممنوع** (يكسر live ISOs الخاصة بـ bootc). مسار المثبت جُرّب
كاملاً في QEMU (تثبيت offline حتى إقلاع القرص المستهدف)؛ **لم يُجرَّب بعد على
عتاد حقيقي**.

الـQCOW2 الخاص بـx86 هو fixture لاختبار مسار القرص المثبت وليس artifact دخول
لمستخدم نهائي؛ كلمة اختباره العشوائية تُتلف عمدًا. الـISO هو artifact x86
التفاعلي. ARM ينتج QCOW2 مخصصًا لـOracle/UTM مع provisioning آمن موثق في
[`docs/MOOS_ARM_ORACLE.md`](docs/MOOS_ARM_ORACLE.md).

## أين الحقيقة؟

- **الواقع أولًا:** الجهاز الجاري وjournal/deployments، ثم HEAD والاختبارات
  المنفذة حديثًا، ثم artifacts المُقلعة؛ وثيقة قديمة لا تتغلب على أي منها.
- **عقد الإصدار الحالي:** [`RELEASE.md`](RELEASE.md)
- **الحالة والفخاخ التاريخية:** [`PROJECT_STATE.md`](PROJECT_STATE.md) و
  [`MOOS_ROADMAP.md`](MOOS_ROADMAP.md)؛ استعملهما كسياق لا كدليل runtime.
- **ما هو غير منجَز** (ولا يجوز ادعاء عكسه): قسم "What is NOT done" في
  [`AGENTS.md`](AGENTS.md)
