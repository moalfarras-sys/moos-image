# بحث SMOCF05 — 2026-10-21، قراءة فقط

## الخلاصة
يوجد تطابق Linux موثوق وصريح لهذا HID: رقعة IIO v5 تضيف SMOCF05 إلى st_lsm6dsx_i2c بالقيمة ST_LSM6DS3TRC_ID. ليست مطابقة تخمينية لـSMOCF00. لكن لا يصح وصف الدعم بأنه موجود في نواة جهازنا أو إصدار منشور اعتمادًا على البحث.

## حالات التطوير منفصلة
- **Submitted:** رسالة lore الأصلية بتاريخ2026-09-28 16:06:48−0500 (21:06:48UTC)، Message-ID `20260928210648.17166-3-jwuerz@gmail.com`. نسخةHTML والنص محفوظتان. [رسالة الرقعة الأصلية](https://lore.kernel.org/linux-iio/20260928210648.17166-3-jwuerz@gmail.com/)
- **Reviewed:** v5 تحمل Reviewed-by من Andy Shevchenko؛ هذا مراجعة للرقعة، لا برهان شحن.
- **Maintainer testing:** ملف testing المجلوب من مستودع Jonathan Cameron يحتوي SMOCF05 فعلًا. `git ls-remote` قرأ testing=`43ffda3c7f8456bbe641ae8249a077a361b97880`. ربط ملف testing بتلك البصمة غير مثبت تمامًا: رابط الملف المثبت وواجهةcommit أعادا403. لذا نحفظ الملف وبصمته كمشاهدة testing متحركة، لا ننسب bytes نهائيًا إلىcommit لم نفكّه. صفحةlore تشير إلى ردMaintainer يوم2026-10-19 02:07UTC لكن جسمه403؛ لم ندّع محتواه. [ملف IIO testing المتحرك](https://git.kernel.org/pub/scm/linux/kernel/git/jic23/iio.git/plain/drivers/iio/imu/st_lsm6dsx/st_lsm6dsx_i2c.c?h=testing)
- **Torvalds mainline:** snapshot مثبت عند `4cbdd58dfa7aaad679bf62f81cdbc96a6cb7c6ae`، تاريخcommitter `2026-10-20T23:00:41Z`، لا يحتويSMOCF05. ACPI table فيهSMO8B30 وSMOCF00 فقط. blob=`edec898cb11fdce34b86032a422fa7932be2c8b2`، SHA256 للملف=`0b7505a74a95808ff529f60aa2d100c5f7890e2fe60ead5e8cb2d1a67579431a`. [ملف Torvalds المثبت](https://github.com/torvalds/linux/blob/4cbdd58dfa7aaad679bf62f81cdbc96a6cb7c6ae/drivers/iio/imu/st_lsm6dsx/st_lsm6dsx_i2c.c)
- **Released/distribution/booted:** لم نثبت أول إصدار يحمل التغيير، ولم نفحص RPM النواة أوmodules.alias أو جهازV3 الحالي؛ لا ادعاء دعم مثبت محليًا.

## ما نُقل عن جهاز ناشر الرقعة
الناشر يذكرV3 BIOS1.06 وV3SE BIOS1.03، ربط i2c-SMOCF05:00، WHO_AM_I=0x6a وظهورaccelerometer/gyro. هذه قراءات جهازه، وليست قراءات MoOS. إدراج ACPI alias يفسر لماذا قد يبقىIMU بلاdriver رغم وجود تعريف لعائلة الشريحة. لا يثبت أن جهازنا/BIOS لدينا له كل خصائص الاختبار نفسها.

## مصفوفة الاتجاه: دمج مثبت مستقل
systemd PR43941 مدمجة2026-09-28، mergecommit `583679fe4924e0afbf4dffa861f8b7c6b7be87eb`؛ author `2026-09-28T14:53:06Z` وcommitter `2026-09-28T17:46:03Z`. إصلاحZ لا يستخدمSLA0 المعكوسة كماهي؛ المصفوفة الحالية `-1, 0, 0; 0, -1, 0; 0, 0, 1`. hwdb يقيّد المطابقة بـACPI SMOCF05 وDMI `MicroComputer(HK)TechLimited`/`V3*`، فلا تُطبق علىكلحساس. snapshot الرئيسي المحفوظ يطابق التصحيح. لا برهان أن نسخةhwdb المثبتة لدينا تحتويه أوتطابقDMI فعليًا.
[طلب systemd المدمج](https://github.com/systemd/systemd/pull/43941)
[تصحيح systemd المثبت](https://github.com/systemd/systemd/commit/583679fe4924e0afbf4dffa861f8b7c6b7be87eb)

## اللمس ليس الدوران
مسارtouchscreen/libinput وأحداثmulti-touch مستقل عنIIO accelerometer واتجاهاته. مستشعرالضوء وحده لا يعطي اتجاه الشاشة. اكتشافIMU الصحيح، ثمالمصفوفة، ثمiio-sensor-proxy، ثمسياسةKScreen/KWin واختبارالأوضاعالأربعة واللمس بعدالتحويل مراحلمنفصلة. detached-keyboard/tablet-mode switch ليست نتيجة تلقائية لمجردوجودIMU.

## التوصية المحدودة
فسّر حالةunbound/no-rotation بأنها فجوةHID/kernel/provider محتملة لها مرشحupstream دقيق، وليست دليلًا علىعطلtouch أوعدمإمكاندعمLinux. المسار التالي بعدتجميدالمصدر: مراجعةمدخلاتالنواةالموقعةوتوافرالرقعةضمنالمزود، hwdb المطابق، ثمقبولV3 فعلي. لاsysfsnew_device، لاتحميلموديول، لاDSDT override، لاتعطيلSecureBoot، لاcustomkernel أو تثبيتتعريفمنالإنترنت في هذهالمهمة.

## حدود التنفيذ والأدلة
كلالكتابةداخل هذاالدليل فقط؛ لاrepo/PR/commit، لامراسلاتلأشخاص، ولافحصsysfs/تغييرالمضيف. مصادرHTML/API/النصوص وبصماتهافيsources.json/followup-sources.json؛ جلبGitفلترةshallow رفضهالخادم، فأُوقف فقطfetch المملوك بإشارةTERM/exit143 ولميستخدمكمصدر. أخطاء403 محفوظة ولا تتحول إلىحالةعدموجود.

جميع الاقتراحات التنفيذية تعود إلى P5.1 في الخطة الوحيدة؛ هذا سجل بحث، وليس قائمة مهام مستقلة أو إثبات تعريف على الجهاز.
