# مِعيار العربي — أساس عربي مفتوح المصدر

بناء مشتق صريح من **Noto Sans Arabic**، بعد أن رفض المالك رسم العربية
التجريبي السابق وطلب تعديل مصدر عربي مفتوح. ليس تصميمًا أصليًا من الصفر،
ولا إعادة تسمية لملف جاهز: يعيد البناء من مصادر Glyphs المثبتة ويعدّل النقاط
والتفاصيل الداخلية للميم قبل التحويل إلى الخطوط.

المصدر: [notofonts/arabic](https://github.com/notofonts/arabic)، revision
`f1ba474be91d6a5d2cfcc4374bb03cc5f1011088`. تسجل `upstream-lock.json` البصمات
والنسخة والرخصة؛ يرفض البناء أي اختلاف في المصدر المحفوظ.
حقوق المؤلفين الأصليين ورخصة **SIL OFL 1.1** محفوظة في `upstream/OFL.txt`.
التعديلات الخاصة بـMoOS مرخصة بالرخصة نفسها.

تحتفظ النسخة بأشكال الحروف العربية واتصالاتها وGSUB/GPOS/GDEF والنقاط
المرجعية وقياسات التقدم من المصدر الأصلي. تستخدم النقاط أكتافًا أهدأ وشكلًا
بين الدائرة والمربع، مع ضبط محدود لفتحة رأس الميم. تسجل
`source-changes.json` كل طبقة متغيرة. يمتد الوزن المتغير من100 إلى900.
تحجز مقاييس السطر1536 وحدة فوق خط الأساس و738 تحته لحماية الحركات المركبة
في الأوزان الثقيلة؛ فحص الحبر المشكّل يرافق فحص جداول اللغة.
هذه عائلة **Meyar Arabic** منفصلة؛ اللاتينية في النص المختلط تستخدم البدائل
الأصلية للنظام. لا تستبدل الخط الثابت العرض للطرفية.

```sh
# داخل بيئة التطوير الموجودة؛ لا تثبيت لحزم على نظام MoOS غير القابل للتغيير.
python -m pip install -r fonts/meyar-arabic/requirements.txt
python fonts/meyar-arabic/build.py --otf --output test-results/meyar-arabic/modified
python fonts/meyar-arabic/build.py --control --output test-results/meyar-arabic/upstream-control
python fonts/meyar-arabic/verify.py test-results/meyar-arabic/modified \
  test-results/meyar-arabic/upstream-control --output test-results/meyar-arabic/arabic-regression.json
QT_QPA_PLATFORM=offscreen python3 fonts/meyar-arabic/proof.py \
  test-results/meyar-arabic/modified test-results/meyar-arabic/specimen.png
```

يفحص الاختبار اختلاف الرسوم الفعلي، وتطابق جداول اللغة وترتيب المحارف
وخطوات التقدم، ثم يقارن2133 حالة تشكيل عبر تسعة أوزان والعربية والفارسية
والأردية. اختلاف بسيط في حافة الحبر للنقاط المائلة مسجل مستقلًا عن التقدم.
نجاح هذه الاختبارات لا يثبت قبول المالك، أو التغطية الكاملة لكل لغة، أو وصول
تحديث موقّع إلى نظام MoOS. النسخة التجريبية المحلية يجب أن تبقى محددة
ببصماتها إلى أن تُقبل بصريًا ويصل بديل مطابق عبر مسار الإصدار المعتاد.
