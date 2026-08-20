# MoOS release contract

هذا الملف يصف مسار الإصدار الحالي فقط. سجل الجلسات والـhandoffs ليس عقد نشر.

## القاعدة

لا يُنشر `latest` لأن container بُني بنجاح. المرشح المقبول هو digest موقّع من
revision واحد، ثم يُقلع artifact النهائي نفسه، ثم يُرقّى ذلك digest بعينه.

## x86

1. ثبّت branch نظيفًا وشغّل البوابات المحلية (`just check`). لا تغيّر tree بعد
   بدء المرشح.
2. شغّل **Build MoOS image** يدويًا على branch. الإصدارات الثلاثة تُدفع بوسم
   `candidate-<run-id>-<sha12>` فقط، وتُوقّع، ويرفع كل matrix job ملف
   `moos-candidate-proof-<edition>/candidate.txt`.
3. استخرج مرجع `moos@sha256:…` من proof وشغّل على **نفس revision**:

   - **Build MoOS disk image (qcow2)** مع `image-ref=<exact ref>`؛ يجب أن ينجح
     sealing وUEFI والإقلاع وإعادة الإقلاع والإطفاء ورفع proof.
   - **Build MoOS Live ISO** مع `image_ref=<exact ref>`؛ يجب أن يقلع ISO النهائي
     read-only إلى live desktop، يرى offline image بالدجست نفسه، ثم يطفئ نظيفًا.

4. لا تستخدم **Re-run jobs** لهذه runs؛ promotion يقبل `run_attempt == 1` فقط.
   أصلح السبب وشغّل workflow_dispatch جديدًا كي لا تختلط artifacts بين attempts.
5. ادمج branch بطريقة تحفظ candidate commit كـancestor وتجعل tree النهائي على
   `main` مطابقًا له (merge commit مناسب). أي تغيير source بعد الأدلة يفرض مرشحًا
   جديدًا.
6. من `main` شغّل **Promote boot-proven MoOS x86 release** وأدخل candidate
   revision وrun IDs الثلاثة. الـworkflow يعيد التحقق من:

   - تطابق candidate tree مع tree الجاري على `main` لحظة الترقية؛
   - نجاح runs الثلاثة ومساراتها وSHA وattempt؛
   - manifests للإصدارات الثلاثة؛
   - signed OSTree origin في إقلاعي QCOW2؛
   - live/offline digest وإطفاء ISO؛
   - cosign والـOCI revision لكل digest.

   بعدها يجهز ويفحص date tags للنسخ الثلاث، ثم يحرّك `latest`.

الـQCOW2 x86 اسمه `moos-ci-verified-disk-qcow2` وهو CI fixture بلا credential
قابل للاستعمال البشري. artifact المستخدم النهائي هو `moos-live-iso`.

## ARM

`build-arm.yml` هو pipeline واحد: native aarch64 candidate → cosign → QCOW2 →
sealing إلى signed origin → UEFI/runtime/reboot/poweroff proof → artifact →
promotion. Job `promote` يحتاج نجاح `[build, disk]`، ولا يعمل على PR أو branch
dispatch. تعليمات Oracle وUTM وfirst boot في
[`docs/MOOS_ARM_ORACLE.md`](docs/MOOS_ARM_ORACLE.md).

## الجهاز الحقيقي

قبل stage أو reboot:

- أثبت وجود deployment rollback موقّع وصالح.
- سجّل digest الجاري والوحدات الفاشلة وboot timing.
- لا تستخدم tag غير مثبت؛ update backend يحل `latest` ثم يثبت exact signed digest.

بعد تطبيق الإصدار: راقب الإقلاع بصريًا، ثم شغّل `moos-selfcheck` و
`tests/post-update-check.sh`، وافحص system/user failed units وkernel warnings،
واختبر تطبيقات MoOS والـGPU والصوت والشبكة وBluetooth وsuspend/resume وإعادة
الإقلاع والإطفاء. أي بند لم يُختبر فعليًا يُذكر صراحة ولا يُستنتج من الكود.
