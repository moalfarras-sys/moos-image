import 'dart:ui' show PlatformDispatcher;

import 'package:flutter/widgets.dart';

import '../../services/weather/weather_service.dart' show WeatherKind;

/// Trilingual UI copy — Arabic, English, German — Arabic first.
///
/// Every user-visible MoOS surface (Mo AI, Welcome, the `.desktop` files, the
/// installer) speaks Arabic and English, and the maintainer's own desktop runs
/// Arabic on a German locale. An IPTV player that only spoke English would be
/// the one app in the system that did not.
///
/// This is a plain lookup table rather than generated ARB/intl, and the choice
/// is load-bearing: the three translations sit on **one line, side by side**, so
/// a missing German string is not a runtime fallback to English that nobody
/// notices for a year — it is a **compile error**, at the call site, today. A
/// table can also be read and corrected by someone who does not know Flutter,
/// which is not true of a generated `AppLocalizations`.
enum Lang {
  ar('العربية', TextDirection.rtl),
  en('English', TextDirection.ltr),
  de('Deutsch', TextDirection.ltr);

  const Lang(this.label, this.direction);

  final String label;
  final TextDirection direction;

  /// The enum's own `name` is the language code — keep it that way.
  String get code => name;

  Locale get locale => Locale(code);

  /// What is stored in settings. A null (never chosen) means "follow the
  /// session": a MoOS user who set the system to Arabic should not have to say
  /// so a second time here.
  static Lang fromWire(String? code) => switch (code) {
    'en' => Lang.en,
    'ar' => Lang.ar,
    'de' => Lang.de,
    _ => fromSystem(PlatformDispatcher.instance.locale),
  };

  static Lang fromSystem(Locale systemLocale) =>
      switch (systemLocale.languageCode) {
        'ar' => Lang.ar,
        'de' => Lang.de,
        _ => Lang.en,
      };
}

class S {
  const S(this.lang);

  final Lang lang;

  bool get isAr => lang == Lang.ar;
  TextDirection get direction => lang.direction;

  /// Arabic, English, German — always all three, always in that order.
  String _(String ar, String en, String de) => switch (lang) {
    Lang.ar => ar,
    Lang.en => en,
    Lang.de => de,
  };

  // ── Shell / navigation ─────────────────────────────────────────────────────
  String get appName => 'MoPlayer';
  String get appTagline =>
      _('من Moalfarras', 'by Moalfarras', 'von Moalfarras');
  String get forMoOS => _('لنظام MoOS', 'for MoOS', 'für MoOS');
  String get home => _('الرئيسية', 'Home', 'Start');
  String get live => _('البث المباشر', 'Live TV', 'Live-TV');
  String get movies => _('الأفلام', 'Movies', 'Filme');
  String get series => _('المسلسلات', 'Series', 'Serien');
  String get search => _('بحث', 'Search', 'Suche');
  String get favorites => _('المفضلة', 'Favorites', 'Favoriten');
  String get settings => _('الإعدادات', 'Settings', 'Einstellungen');
  String get library => _('مكتبتي', 'Library', 'Bibliothek');

  // ── Window ─────────────────────────────────────────────────────────────────
  String get windowClose =>
      _('إغلاق النافذة', 'Close window', 'Fenster schließen');
  String get windowMinimize => _('تصغير', 'Minimize', 'Minimieren');
  String get windowMaximize => _('تكبير', 'Maximize', 'Maximieren');
  String get windowRestore => _('استعادة', 'Restore', 'Wiederherstellen');

  // ── Common actions ─────────────────────────────────────────────────────────
  String get play => _('تشغيل', 'Play', 'Abspielen');
  String get pause => _('إيقاف مؤقت', 'Pause', 'Pause');
  String get resume => _('متابعة', 'Resume', 'Fortsetzen');
  String get stop => _('إيقاف', 'Stop', 'Stopp');
  String get retry => _('إعادة المحاولة', 'Retry', 'Erneut versuchen');
  String get refresh => _('تحديث', 'Refresh', 'Aktualisieren');
  String get cancel => _('إلغاء', 'Cancel', 'Abbrechen');
  String get save => _('حفظ', 'Save', 'Speichern');
  String get sourceNotSaved => _(
    'تعذّر حفظ السيرفر في مساحة التطبيق الخاصة. تحقق من مساحة القرص وصلاحيات المجلد ثم حاول مرة أخرى.',
    'The server could not be written to private app storage. Check disk space and folder permissions, then retry.',
    'Der Server konnte nicht im privaten App-Speicher gesichert werden. Prüfe Speicherplatz und Ordnerrechte und versuche es erneut.',
  );
  String get remove => _('إزالة', 'Remove', 'Entfernen');
  String get delete => _('حذف', 'Delete', 'Löschen');
  String get close => _('إغلاق', 'Close', 'Schließen');
  String get back => _('رجوع', 'Back', 'Zurück');
  String get connect => _('اتصال', 'Connect', 'Verbinden');
  String get all => _('الكل', 'All', 'Alle');
  String get more => _('المزيد', 'More', 'Mehr');
  String get done => _('تم', 'Done', 'Fertig');
  String get undo => _('تراجع', 'Undo', 'Rückgängig');
  String get apply => _('تطبيق', 'Apply', 'Übernehmen');
  String get addToFavorites =>
      _('أضف إلى المفضلة', 'Add to favorites', 'Zu Favoriten hinzufügen');
  String get removeFromFavorites =>
      _('إزالة من المفضلة', 'Remove from favorites', 'Aus Favoriten entfernen');

  // ── Login / sources ────────────────────────────────────────────────────────
  String get welcomeTitle => _(
    'أهلاً بك في MoPlayer',
    'Welcome to MoPlayer',
    'Willkommen bei MoPlayer',
  );
  String get welcomeBody => _(
    'أضف مصدرك لتبدأ المشاهدة. كل شيء يبقى على جهازك.',
    'Add your source to start watching. Everything stays on your device.',
    'Fügen Sie Ihre Quelle hinzu, um loszulegen. Alles bleibt auf Ihrem Gerät.',
  );
  String get xtream => _('حساب Xtream', 'Xtream account', 'Xtream-Konto');
  String get xtreamHint => _(
    'رابط الخادم واسم المستخدم وكلمة المرور',
    'Server URL, username and password',
    'Server-URL, Benutzername und Passwort',
  );
  String get m3u => _('رابط M3U', 'M3U playlist', 'M3U-Playlist');
  String get m3uHint => _(
    'رابط قائمة تشغيل مباشر',
    'A direct playlist link',
    'Ein direkter Playlist-Link',
  );
  String get activation =>
      _('رمز التفعيل', 'Activation code', 'Aktivierungscode');
  String get activationHint => _(
    'امسح الرمز من الهاتف',
    'Scan the code from your phone',
    'Code mit dem Telefon scannen',
  );
  String get serverUrl => _('رابط الخادم', 'Server URL', 'Server-URL');
  String get username => _('اسم المستخدم', 'Username', 'Benutzername');
  String get password => _('كلمة المرور', 'Password', 'Passwort');
  String get playlistName =>
      _('اسم القائمة', 'Playlist name', 'Name der Playlist');
  String get playlistUrl => _('رابط القائمة', 'Playlist URL', 'Playlist-URL');
  String get sources => _('المصادر', 'Sources', 'Quellen');
  String get addSource => _('إضافة مصدر', 'Add source', 'Quelle hinzufügen');
  String get activeSource =>
      _('المصدر النشط', 'Active source', 'Aktive Quelle');
  String get switchSource =>
      _('تبديل المصدر', 'Switch source', 'Quelle wechseln');
  String get signOut => _('تسجيل الخروج', 'Sign out', 'Abmelden');
  String get connecting => _('جارٍ الاتصال…', 'Connecting…', 'Verbinden…');
  String get connected => _('تم الاتصال', 'Connected', 'Verbunden');
  String channelsFound(int n) =>
      _('تم العثور على $n قناة', 'Found $n channels', '$n Sender gefunden');
  String get waitingForActivation => _(
    'بانتظار التفعيل…',
    'Waiting for activation…',
    'Warte auf Aktivierung…',
  );
  String get activationScanHint => _(
    'افتح moalfarras.space/activate وأدخل الرمز، أو امسح رمز QR.',
    'Open moalfarras.space/activate and enter the code, or scan the QR.',
    'Öffnen Sie moalfarras.space/activate, geben Sie den Code ein oder scannen Sie den QR-Code.',
  );
  String get activationNoSource => _(
    'تم التفعيل، لكن لا يوجد مصدر مرتبط بهذا الجهاز بعد.',
    'Activated, but no source has been linked to this device yet.',
    'Aktiviert, aber diesem Gerät ist noch keine Quelle zugeordnet.',
  );

  // ── Home / dashboard ───────────────────────────────────────────────────────
  String get continueWatching =>
      _('تابع المشاهدة', 'Continue watching', 'Weiterschauen');
  String get liveNow => _('يُبث الآن', 'On air now', 'Jetzt im Programm');
  String get recentlyAdded =>
      _('أُضيف حديثاً', 'Recently added', 'Neu hinzugefügt');
  String get topRated => _('الأعلى تقييماً', 'Top rated', 'Top bewertet');
  String get yourFavorites => _('مفضلتك', 'Your favorites', 'Ihre Favoriten');
  String get watchAgain => _('شاهد مجدداً', 'Watch again', 'Erneut ansehen');
  String get featured => _('مميّز', 'Featured', 'Empfohlen');
  String get moreInfo => _('تفاصيل أكثر', 'More info', 'Mehr Infos');
  String get recentChannels =>
      _('قنوات شاهدتها مؤخراً', 'Recent channels', 'Zuletzt gesehene Sender');
  String minutesLeft(int n) =>
      _('بقيت $n دقيقة', '$n min left', 'Noch $n Min.');

  /// Arabic counts nouns by number, and "5 قناة" is simply wrong — the singular
  /// after 3–10 is the mistake that marks an interface as machine-translated.
  /// One is a word, two is a dual, 3–10 takes the plural, and 11+ goes back to
  /// the singular (تمييز مفرد). English and German only ever need the two.
  String liveChannelsAvailable(int n) {
    final ar = switch (n) {
      1 => 'قناة واحدة متاحة',
      2 => 'قناتان متاحتان',
      >= 3 && <= 10 => '$n قنوات متاحة',
      _ => '$n قناة متاحة',
    };
    return _(
      ar,
      n == 1 ? '1 channel available' : '$n channels available',
      n == 1 ? '1 Sender verfügbar' : '$n Sender verfügbar',
    );
  }

  String greeting(String name) =>
      _('أهلاً، $name', 'Hello, $name', 'Hallo, $name');
  String get goodMorning => _('صباح الخير', 'Good morning', 'Guten Morgen');
  String get goodAfternoon => _('مساء الخير', 'Good afternoon', 'Guten Tag');
  String get goodEvening => _('مساء الخير', 'Good evening', 'Guten Abend');

  // ── Dashboard widgets ──────────────────────────────────────────────────────
  String get widgetNetwork => _('الشبكة', 'Network', 'Netzwerk');
  String get widgetLibrary => _('المكتبة', 'Library', 'Bibliothek');
  String get widgetSubscription => _('الاشتراك', 'Subscription', 'Abonnement');
  String get subscriptionActive => _('فعّال', 'Active', 'Aktiv');
  String get subscriptionUnlimited => _('غير محدود', 'Unlimited', 'Unbegrenzt');
  String get subscriptionExpired => _('منتهٍ', 'Expired', 'Abgelaufen');
  String daysLeft(int n) =>
      _('$n يوماً متبقياً', '$n days left', 'Noch $n Tage');
  String get expiresToday =>
      _('ينتهي اليوم', 'Expires today', 'Läuft heute ab');
  String get channelCount => _('قناة', 'channels', 'Sender');
  String get movieCount => _('فيلم', 'movies', 'Filme');
  String get seriesCountLabel => _('مسلسل', 'series', 'Serien');

  // ── Home widgets: what is on, and what it is like outside ─────────────────
  String get todaysMatches =>
      _('مباريات اليوم', 'Today\'s matches', 'Spiele heute');
  String get newestMovies => _('أحدث الأفلام', 'Newest films', 'Neueste Filme');
  String get newestSeries =>
      _('أحدث المسلسلات', 'Newest series', 'Neueste Serien');

  /// The WMO code table collapses to seven pictures, and this is what each one
  /// is called. Kept next to the rest of the copy rather than in the weather
  /// service: it is a *phrase*, and a phrase is translated.
  String weatherPhrase(WeatherKind kind) => switch (kind) {
    WeatherKind.clear => _('صحو', 'Clear', 'Klar'),
    WeatherKind.partlyCloudy => _(
      'غائم جزئياً',
      'Partly cloudy',
      'Teils bewölkt',
    ),
    WeatherKind.cloudy => _('غائم', 'Cloudy', 'Bewölkt'),
    WeatherKind.fog => _('ضباب', 'Fog', 'Nebel'),
    WeatherKind.rain => _('ممطر', 'Rain', 'Regen'),
    WeatherKind.snow => _('ثلوج', 'Snow', 'Schnee'),
    WeatherKind.storm => _('عواصف رعدية', 'Thunderstorms', 'Gewitter'),
  };

  // ── Live ───────────────────────────────────────────────────────────────────
  String get categories => _('التصنيفات', 'Categories', 'Kategorien');
  String get channels => _('القنوات', 'Channels', 'Sender');
  String get onAir => _('مباشر', 'LIVE', 'LIVE');
  String get nowPlaying => _('يُعرض الآن', 'Now playing', 'Läuft jetzt');
  String get upNext => _('التالي', 'Up next', 'Als Nächstes');
  String get noEpg =>
      _('لا يوجد دليل برامج', 'No programme guide', 'Kein Programmführer');
  String get searchChannels =>
      _('ابحث في القنوات', 'Search channels', 'Sender suchen');
  String get pickChannel => _(
    'اختر قناة لتبدأ المشاهدة.',
    'Pick a channel to start watching.',
    'Wählen Sie einen Sender, um zu starten.',
  );
  String get watchFullscreen =>
      _('مشاهدة بملء الشاشة', 'Watch fullscreen', 'Vollbild ansehen');
  String get hideCategories =>
      _('إخفاء التصنيفات', 'Hide categories', 'Kategorien ausblenden');
  String get showCategories =>
      _('إظهار التصنيفات', 'Show categories', 'Kategorien einblenden');
  String get preview => _('معاينة', 'Preview', 'Vorschau');

  // ── Movies / series ────────────────────────────────────────────────────────
  String get seasons => _('المواسم', 'Seasons', 'Staffeln');
  String season(int n) => _('الموسم $n', 'Season $n', 'Staffel $n');

  /// Season 0. Panels put pilots, recaps and Christmas episodes here.
  String get specials => _('حلقات خاصة', 'Specials', 'Specials');
  String episode(int n) => _('الحلقة $n', 'Episode $n', 'Folge $n');
  String get episodes => _('الحلقات', 'Episodes', 'Folgen');
  String get searchMovies =>
      _('ابحث في الأفلام', 'Search movies', 'Filme suchen');
  String get searchSeries =>
      _('ابحث في المسلسلات', 'Search series', 'Serien suchen');
  String get clearSearch => _('مسح البحث', 'Clear search', 'Suche löschen');
  String moviesCount(int n) => _('$n فيلم', '$n movies', '$n Filme');
  String seriesCount(int n) => _('$n مسلسل', '$n series', '$n Serien');
  String get cast => _('الطاقم', 'Cast', 'Besetzung');
  String get director => _('الإخراج', 'Director', 'Regie');
  String get genre => _('النوع', 'Genre', 'Genre');
  String get released => _('تاريخ الإصدار', 'Released', 'Erschienen');
  String get duration => _('المدة', 'Duration', 'Laufzeit');
  String get plot => _('القصة', 'Plot', 'Handlung');
  String get playFromStart =>
      _('التشغيل من البداية', 'Play from start', 'Von vorn abspielen');
  String resumeAt(String time) =>
      _('متابعة من $time', 'Resume at $time', 'Fortsetzen bei $time');
  String get related => _('مشابه', 'Related', 'Ähnliches');
  String get watched => _('شوهد', 'Watched', 'Gesehen');
  String get trailer => _('الإعلان', 'Trailer', 'Trailer');
  String get rating => _('التقييم', 'Rating', 'Bewertung');

  // ── Sorting and filtering ──────────────────────────────────────────────────
  String get sortBy => _('ترتيب حسب', 'Sort by', 'Sortieren nach');
  String get sortRecent => _('الأحدث', 'Recently added', 'Zuletzt hinzugefügt');
  String get sortTitle => _('الاسم', 'Title', 'Titel');
  String get sortYear => _('السنة', 'Year', 'Jahr');
  String get sortRating => _('التقييم', 'Rating', 'Bewertung');
  String get filter => _('تصفية', 'Filter', 'Filter');

  // ── Search ─────────────────────────────────────────────────────────────────
  String get searchPlaceholder => _(
    'ابحث في القنوات والأفلام والمسلسلات…',
    'Search channels, movies and series…',
    'Sender, Filme und Serien suchen…',
  );
  String get searchPrompt => _(
    'اكتب حرفين على الأقل',
    'Type at least two characters',
    'Mindestens zwei Zeichen eingeben',
  );
  String noResults(String q) =>
      _('لا نتائج لـ «$q»', 'No results for “$q”', 'Keine Treffer für „$q“');
  String get searchHistory =>
      _('عمليات بحث سابقة', 'Recent searches', 'Letzte Suchen');
  String get clearHistory => _('مسح السجل', 'Clear history', 'Verlauf löschen');
  String resultsCount(int n) => _('$n نتيجة', '$n results', '$n Treffer');

  // ── Player ─────────────────────────────────────────────────────────────────
  String get fullscreen => _('ملء الشاشة', 'Fullscreen', 'Vollbild');
  String get exitFullscreen =>
      _('إنهاء ملء الشاشة', 'Exit fullscreen', 'Vollbild beenden');
  String get audioTrack => _('المسار الصوتي', 'Audio track', 'Tonspur');
  String get subtitles => _('الترجمة', 'Subtitles', 'Untertitel');
  String get subtitlesOff => _('بدون ترجمة', 'Off', 'Aus');
  String get speed => _('السرعة', 'Speed', 'Geschwindigkeit');
  String get quality => _('الجودة', 'Quality', 'Qualität');
  String get volume => _('الصوت', 'Volume', 'Lautstärke');
  String get mute => _('كتم', 'Mute', 'Stumm');
  String get unmute => _('إلغاء الكتم', 'Unmute', 'Ton an');
  String get nextEpisode =>
      _('الحلقة التالية', 'Next episode', 'Nächste Folge');
  String get previousEpisode =>
      _('الحلقة السابقة', 'Previous episode', 'Vorherige Folge');
  String get nextChannel =>
      _('القناة التالية', 'Next channel', 'Nächster Sender');
  String get previousChannel =>
      _('القناة السابقة', 'Previous channel', 'Vorheriger Sender');
  String get buffering => _('جارٍ التحميل…', 'Buffering…', 'Puffern…');
  String get reconnecting =>
      _('إعادة الاتصال…', 'Reconnecting…', 'Neu verbinden…');
  String reconnectingAttempt(int attempt, int total) => _(
    'تتم استعادة البث ($attempt من $total)…',
    'Restoring playback ($attempt of $total)…',
    'Wiedergabe wird wiederhergestellt ($attempt von $total)…',
  );
  String get playbackFailed => _(
    'تعذّر تشغيل هذا المحتوى. تحقّق من الاتصال أو أعد المحاولة.',
    'This content could not be played. Check the connection or try again.',
    'Dieser Inhalt konnte nicht abgespielt werden. Verbindung prüfen oder erneut versuchen.',
  );
  String get reconnect => _('إعادة الاتصال', 'Reconnect', 'Neu verbinden');
  String get playerOptions =>
      _('إعدادات المشغّل', 'Player options', 'Player-Optionen');
  String get tenSecondsBack =>
      _('للخلف 10 ثوانٍ', 'Back 10 seconds', '10 Sekunden zurück');
  String get tenSecondsForward =>
      _('للأمام 10 ثوانٍ', 'Forward 10 seconds', '10 Sekunden vor');
  String get miniPlayer => _('المشغل المصغّر', 'Mini player', 'Mini-Player');
  String get shortcuts =>
      _('اختصارات لوحة المفاتيح', 'Keyboard shortcuts', 'Tastenkürzel');
  String get pictureInPicture =>
      _('صورة داخل صورة', 'Picture in picture', 'Bild-in-Bild');
  String get aspectRatio => _('نسبة العرض', 'Aspect ratio', 'Seitenverhältnis');
  String get aspectFit => _('احتواء', 'Fit', 'Einpassen');
  String get aspectFill => _('ملء', 'Fill', 'Ausfüllen');
  String get aspectOriginal => _('الأصلية', 'Original', 'Original');
  String get backToLive =>
      _('العودة للبث المباشر', 'Back to live', 'Zurück zu Live');
  String get channelList => _('قائمة القنوات', 'Channel list', 'Senderliste');
  String get episodeList => _('قائمة الحلقات', 'Episode list', 'Folgenliste');
  String get infoPanel => _('معلومات', 'Information', 'Informationen');
  String get subtitleSync =>
      _('مزامنة الترجمة', 'Subtitle sync', 'Untertitel-Sync');

  // ── Settings: the control centre ───────────────────────────────────────────
  String get playback => _('التشغيل', 'Playback', 'Wiedergabe');
  String get appearance => _('المظهر', 'Appearance', 'Darstellung');
  String get language => _('اللغة', 'Language', 'Sprache');
  String get systemIntegration =>
      _('التكامل مع MoOS', 'MoOS integration', 'MoOS-Integration');
  String get about => _('حول', 'About', 'Über');
  String get storage => _('التخزين', 'Storage', 'Speicher');
  String get account =>
      _('الحساب والتفعيل', 'Account & activation', 'Konto & Aktivierung');
  String get audio => _('الصوت', 'Audio', 'Audio');
  String get network => _(
    'الشبكة والاستعادة',
    'Network & recovery',
    'Netzwerk & Wiederherstellung',
  );
  String get remoteAndKeyboard => _(
    'جهاز التحكم ولوحة المفاتيح',
    'Remote & keyboard',
    'Fernbedienung & Tastatur',
  );
  String get diagnostics => _('التشخيص', 'Diagnostics', 'Diagnose');

  String get preferHls => _(
    'تفضيل HLS للبث المباشر',
    'Prefer HLS for live',
    'HLS für Live bevorzugen',
  );
  String get preferHlsHint => _(
    'أكثر توافقاً؛ أطفئه إن تأخّر بدء القنوات (TS أسرع استجابة).',
    'More compatible; turn it off if channels are slow to start (TS zaps faster).',
    'Kompatibler; ausschalten, wenn Sender langsam starten (TS schaltet schneller um).',
  );
  String get autoplayNext => _(
    'تشغيل الحلقة التالية تلقائياً',
    'Autoplay next episode',
    'Nächste Folge automatisch abspielen',
  );
  String get rememberLastChannel =>
      _('تذكّر آخر قناة', 'Remember last channel', 'Letzten Sender merken');
  String get syncOnLaunch =>
      _('مزامنة عند التشغيل', 'Sync on launch', 'Beim Start synchronisieren');
  String get cinematicMotion =>
      _('الحركة السينمائية', 'Cinematic motion', 'Kinoreife Animationen');
  String get cinematicMotionHint => _(
    'انتقالات ناعمة وتأثيرات زجاجية. أطفئها على جهاز ضعيف.',
    'Soft transitions and glass effects. Turn off on a weak GPU.',
    'Weiche Übergänge und Glaseffekte. Bei schwacher GPU ausschalten.',
  );
  String get compactGrids =>
      _('شبكات مضغوطة', 'Compact grids', 'Kompakte Raster');
  String get compactGridsHint => _(
    'بطاقات أصغر، وعدد أكبر منها في الشاشة.',
    'Smaller cards, more of them on screen.',
    'Kleinere Karten, mehr davon auf dem Bildschirm.',
  );
  String get previewAutoplay =>
      _('معاينة تلقائية', 'Preview autoplay', 'Vorschau automatisch starten');
  String get previewAutoplayHint => _(
    'شغّل معاينة القناة عند اختيارها في شاشة البث المباشر.',
    'Start a channel preview when it is selected in the Live screen.',
    'Startet eine Sendervorschau, wenn im Live-Bereich ein Sender gewählt wird.',
  );
  String get clearCache =>
      _('مسح الذاكرة المؤقتة', 'Clear cache', 'Zwischenspeicher leeren');
  String get privateStorage => _(
    'حفظ الحسابات محلياً',
    'Private account storage',
    'Privater Kontospeicher',
  );
  String get privateStorageHint => _(
    'محفوظ داخل مجلد التطبيق بصلاحيات خاصة، دون KDE Wallet.',
    'Stored in MoPlayer’s private app folder, without KDE Wallet.',
    'Im privaten MoPlayer-App-Ordner gespeichert, ohne KDE Wallet.',
  );
  String get storageReady => _('جاهز', 'Ready', 'Bereit');
  String get storageSessionOnly =>
      _('لهذه الجلسة فقط', 'Session only', 'Nur für diese Sitzung');
  String get clearCacheHint => _(
    'يحذف القوائم المخزّنة فقط، لا يحذف مفضلتك.',
    'Drops cached catalogues only — your favorites stay.',
    'Löscht nur zwischengespeicherte Kataloge — Ihre Favoriten bleiben.',
  );
  String get wipeData =>
      _('حذف كل البيانات', 'Erase all data', 'Alle Daten löschen');
  String get wipeDataHint => _(
    'المفضلة والسجل والمصادر. لا يمكن التراجع.',
    'Favorites, history and sources. This cannot be undone.',
    'Favoriten, Verlauf und Quellen. Kann nicht rückgängig gemacht werden.',
  );
  String get mprisTitle => _('مفاتيح الوسائط', 'Media keys', 'Medientasten');
  String get mprisHint => _(
    'التحكم بالتشغيل من شريط مهام Plasma ومن مفاتيح الوسائط في لوحة المفاتيح.',
    'Control playback from the Plasma panel and your keyboard media keys.',
    'Wiedergabe über die Plasma-Leiste und die Medientasten der Tastatur steuern.',
  );
  String get inhibitTitle =>
      _('منع إطفاء الشاشة', 'Keep the screen awake', 'Bildschirm wach halten');
  String get inhibitHint => _(
    'يمنع مُوفّر الشاشة أثناء التشغيل.',
    'Inhibits the screen locker while something is playing.',
    'Verhindert die Bildschirmsperre während der Wiedergabe.',
  );

  /// The word next to an integration light in Settings. A grey dot on its own
  /// tells the user nothing, and an integration that failed silently is
  /// indistinguishable from one that was never checked.
  String get detected => _('مُفعَّل', 'Detected', 'Erkannt');
  String get notDetected => _('غير متوفر', 'Not detected', 'Nicht erkannt');

  String get version => _('الإصدار', 'Version', 'Version');

  /// The vertical list of a panel's own categories, down the side of a browse
  /// page. Called "groups" and not "categories" because that is what an M3U
  /// calls them (`group-title`) and what the panels themselves show.
  String get groups => _('المجموعات', 'Groups', 'Gruppen');

  // ── Update centre ─────────────────────────────────────────────────────────
  String get updates => _('التحديثات', 'Updates', 'Updates');
  String get checkForUpdates =>
      _('التحقق من التحديثات', 'Check for updates', 'Nach Updates suchen');
  String get checkingForUpdates =>
      _('جارٍ التحقق…', 'Checking…', 'Wird geprüft…');
  String get upToDate => _(
    'لديك أحدث إصدار',
    'You have the latest version',
    'Sie haben die neueste Version',
  );
  String updateAvailable(String version) => _(
    'الإصدار $version متاح',
    'Version $version is available',
    'Version $version ist verfügbar',
  );

  /// MoPlayer ships *inside* the image. It is not a Flatpak and it does not
  /// self-update — `bootc` replaces the whole operating system, MoPlayer with
  /// it, atomically. Saying so is the honest thing; offering an "Update" button
  /// that cannot update anything is not.
  String get updatesViaSystem => _(
    'يأتي MoPlayer مع نظام MoOS ويُحدَّث معه. تحديث النظام يحدّث التطبيق.',
    'MoPlayer ships with MoOS and updates with it. Updating the system updates the app.',
    'MoPlayer wird mit MoOS ausgeliefert und mit ihm aktualisiert.',
  );
  String get device => _('الجهاز', 'Device', 'Gerät');
  String get playbackEngine =>
      _('محرك التشغيل', 'Playback engine', 'Wiedergabe-Engine');
  String get moosVersion => _('إصدار MoOS', 'MoOS version', 'MoOS-Version');
  String get cacheSize =>
      _('حجم الذاكرة المؤقتة', 'Cache size', 'Größe des Zwischenspeichers');
  String get copyDiagnostics =>
      _('نسخ معلومات التشخيص', 'Copy diagnostics', 'Diagnose kopieren');
  String get copied => _('تم النسخ', 'Copied', 'Kopiert');
  String get testConnection =>
      _('اختبار الاتصال', 'Test connection', 'Verbindung testen');
  String get testing => _('جارٍ الاختبار…', 'Testing…', 'Wird getestet…');
  String get reachable =>
      _('الخادم يستجيب', 'Server is reachable', 'Server erreichbar');
  String get unreachable => _(
    'الخادم لا يستجيب',
    'Server is not reachable',
    'Server nicht erreichbar',
  );

  // ── States / errors ────────────────────────────────────────────────────────
  String get loading => _('جارٍ التحميل…', 'Loading…', 'Wird geladen…');
  String get empty =>
      _('لا يوجد شيء هنا بعد', 'Nothing here yet', 'Noch nichts hier');
  String get emptyFavorites => _(
    'لم تضف شيئاً إلى المفضلة بعد.',
    'You have not added anything to favorites yet.',
    'Sie haben noch nichts zu den Favoriten hinzugefügt.',
  );
  String get emptyFavoritesAction =>
      _('تصفّح المحتوى', 'Browse content', 'Inhalte durchsuchen');
  String get emptyCategory => _(
    'هذا التصنيف فارغ.',
    'This category is empty.',
    'Diese Kategorie ist leer.',
  );
  String get emptyHistory => _(
    'لم تشاهد شيئاً بعد.',
    'You have not watched anything yet.',
    'Sie haben noch nichts angesehen.',
  );
  String get errorTitle =>
      _('حدث خطأ', 'Something went wrong', 'Etwas ist schiefgelaufen');
  String get errNetwork => _(
    'تعذّر الاتصال بالشبكة.',
    'Could not reach the network.',
    'Netzwerk nicht erreichbar.',
  );
  String get errTimeout => _(
    'انتهت مهلة الخادم.',
    'The server timed out.',
    'Zeitüberschreitung beim Server.',
  );
  String get errAuth => _(
    'بيانات الدخول غير صحيحة أو الحساب منتهٍ.',
    'Wrong credentials, or the account has expired.',
    'Falsche Zugangsdaten oder das Konto ist abgelaufen.',
  );
  String get errServer => _(
    'الخادم لم يستجب كما يجب.',
    'The server answered badly.',
    'Der Server hat fehlerhaft geantwortet.',
  );
  String get errParse => _(
    'رد الخادم غير مفهوم.',
    'The server sent something unreadable.',
    'Der Server hat Unlesbares gesendet.',
  );
  String get errNotConfigured => _(
    'هذا المصدر لا يدعم هذه الميزة.',
    'This source does not support that.',
    'Diese Quelle unterstützt das nicht.',
  );
  String get errPlayback => _(
    'تعذّر تشغيل هذا البث.',
    'This stream would not play.',
    'Dieser Stream ließ sich nicht abspielen.',
  );
  String get errUnknown =>
      _('خطأ غير متوقع.', 'An unexpected error.', 'Ein unerwarteter Fehler.');
  String get offline => _('غير متصل', 'Offline', 'Offline');
  String get online => _('متصل', 'Online', 'Online');
}

/// Keyboard-shortcut copy, kept next to the strings it documents.
class ShortcutHelp {
  const ShortcutHelp(this.keys, this.ar, this.en, this.de);

  final String keys;
  final String ar;
  final String en;
  final String de;

  String text(S s) => switch (s.lang) {
    Lang.ar => ar,
    Lang.en => en,
    Lang.de => de,
  };

  static const List<ShortcutHelp> all = [
    ShortcutHelp(
      'Space / K',
      'تشغيل أو إيقاف مؤقت',
      'Play or pause',
      'Abspielen oder pausieren',
    ),
    ShortcutHelp(
      '← / →',
      'قفز ١٠ ثوانٍ',
      'Seek 10 seconds',
      '10 Sekunden springen',
    ),
    ShortcutHelp(
      'Shift + ← / →',
      'قفز دقيقة',
      'Seek one minute',
      'Eine Minute springen',
    ),
    ShortcutHelp(
      '↑ / ↓',
      'رفع أو خفض الصوت',
      'Volume up or down',
      'Lauter oder leiser',
    ),
    ShortcutHelp('F / F11', 'ملء الشاشة', 'Fullscreen', 'Vollbild'),
    ShortcutHelp(
      'Esc',
      'خروج من ملء الشاشة أو رجوع',
      'Leave fullscreen, or go back',
      'Vollbild verlassen oder zurück',
    ),
    ShortcutHelp('M', 'كتم الصوت', 'Mute', 'Stummschalten'),
    ShortcutHelp(
      'S',
      'تبديل الترجمة',
      'Cycle subtitles',
      'Untertitel wechseln',
    ),
    ShortcutHelp(
      'A',
      'تبديل المسار الصوتي',
      'Cycle audio track',
      'Tonspur wechseln',
    ),
    ShortcutHelp(
      'N / P · PgUp / PgDn',
      'القناة أو الحلقة التالية والسابقة',
      'Next or previous channel or episode',
      'Nächster oder vorheriger Sender bzw. Folge',
    ),
    ShortcutHelp(
      '[ / ]',
      'إبطاء أو تسريع',
      'Slower or faster',
      'Langsamer oder schneller',
    ),
    ShortcutHelp('Ctrl + F', 'بحث', 'Search', 'Suche'),
    ShortcutHelp(
      'F6',
      'الانتقال إلى الشريط السفلي',
      'Jump to the dock',
      'Zum Dock springen',
    ),
    ShortcutHelp(
      'Ctrl + 1…5',
      'تنقّل بين الأقسام',
      'Jump between sections',
      'Zwischen Bereichen wechseln',
    ),
    ShortcutHelp('Ctrl + Q', 'إغلاق التطبيق', 'Quit', 'Beenden'),
  ];
}
