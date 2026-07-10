# Nova Horizon — أفق نوفا

الخلفية الرسمية لـ **MoOS Nova UI** بوضعين متكاملين: نهاري فاتح وليلي داكن. هذه الدفعة تعيد بناء الفن من الصفر بدل تكبير أصل 1672×941 القديم.

## Assets

```text
contents/
├── images/                       # Light | فاتح
│   ├── 3840x2160.png             # 16:9 — native 4K master
│   ├── 3440x1440.png             # 21:9
│   └── 2560x1600.png             # 16:10
├── images_dark/                  # Dark | داكن
│   ├── 3840x2160.png             # 16:9 — native 4K master
│   ├── 3440x1440.png             # 21:9
│   └── 2560x1600.png             # 16:10
└── screenshot.png                # Plasma preview
```

## Art construction

- الحقل الضوئي مولّد حسابيًا مباشرة على canvas ‏3840×2160؛ لا توجد عملية upscale لمصدر صغير.
- المنحنيات والحواف والجسيمات رُسمت عند 4× ثم صُغّرت مرة واحدة بـ LANCZOS.
- شعار MoOS الأصلي 1024×1024 رُكّب بحجم أصغر من مصدره، بلا تكبير.
- نسختا 21:9 و16:10 مشتقتان من master 4K بالقص الواعي ثم التصغير فقط.
- كل PNG بصيغة sRGB وحجمه أقل من 8 MB.
- الألوان محصورة في `branding/PALETTE.md`: `#050A14`, `#0B1220`, `#22D3EE`, `#2E7BFF`, `#8B5CF6`, `#EEF3FB`, `#FFFFFF`.

## License

فن MoOS أصلي، © Moalfarras، مرخّص بـ CC-BY-SA-4.0 كما هو محدد في `metadata.json`.

## Verification

تحقق محليًا من الأبعاد، ICC profile، وحجم الملفات، ثم افحص النسخ الست على Plasma عند 100% و150% و200% scaling. التحقق البصري النهائي داخل VM/ISO ما زال مطلوبًا.
