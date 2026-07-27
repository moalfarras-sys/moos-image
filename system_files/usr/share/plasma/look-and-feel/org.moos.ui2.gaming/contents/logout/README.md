# MoOS UI logout — Arena

واجهة الخروج الرسمية للحزمة `org.moos.ui2.gaming`. تحافظ على إشارات وقدرات مضيف
KDE Plasma 6 الفعلية (logout, lock, suspend, hibernate, restart, shutdown)
وتستخدم مكوّن `MoOSUI2ActionButton.qml` المحلي المطابق للوحة Arena.

```bash
/usr/libexec/ksmserver-logout-greeter --windowed --lookandfeel org.moos.ui2.gaming
```

`Logout.qml` و`MoOSUI2ActionButton.qml`: GPL-2.0-or-later. عقد المضيف مشتق
من KDE Breeze؛ التنفيذ البصري لـ MoOS، © 2026 Moalfarras.
