# MoOS Nova logout greeter

واجهة الخروج والإطفاء الرسمية لـ **MoOS Nova UI**. تعتمد عقد المضيف الحقيقي في KDE Plasma 6.7، مع تنفيذ بصري أصلي ثنائي اللغة ويدعم RTL.

## Contract baseline

- KDE Plasma Workspace commit: `e717f5d2c325f8fc190cd0c838827e4d7b6851f9`
- Upstream contract: <https://invent.kde.org/plasma/plasma-workspace/-/blob/e717f5d2c325f8fc190cd0c838827e4d7b6851f9/lookandfeel/org.kde.breeze/contents/logout/Logout.qml>
- Host signal wiring: <https://invent.kde.org/plasma/plasma-workspace/-/blob/e717f5d2c325f8fc190cd0c838827e4d7b6851f9/logout-greeter/shutdowndlg.cpp#L274-283>

يحافظ `Logout.qml` على الإشارات العشر التي يربطها المضيف حرفيًا، وقواعد القدرات الفعلية (`maysd`, `canLogout`, `spdMethods`) وخيارات التحديثات غير المتصلة. لا يعتمد على مكونات Breeze البصرية.

## Local verification

```bash
/usr/libexec/ksmserver-logout-greeter --windowed --lookandfeel org.moos.nova
```

افحص العربية والإنجليزية، لوحة المفاتيح، `Esc`، التحديثات المعلّقة، وحالات suspend/hibernate المتاحة فعليًا.

## License and attribution

- `Logout.qml`: GPL-2.0-or-later. عقد المضيف مشتق من KDE Breeze، © 2014 Aleix Pol Gonzalez. التنفيذ البصري الأصلي لـ MoOS، © 2026 Moalfarras.
- `NovaActionButton.qml`: GPL-2.0-or-later، © 2026 Moalfarras.

## Known issue

يحتاج التحقق البصري النهائي إلى Plasma 6.7 داخل VM/ISO؛ Windows لا يملك runtime لمضيف `ksmserver-logout-greeter`.
