/// Defensive coercion helpers for the notoriously inconsistent data returned
/// by Xtream Codes panels (values arrive as String, int, double, null or are
/// simply absent — sometimes all within the same response).
class JsonX {
  const JsonX._();

  static String asString(dynamic v, {String fallback = ''}) {
    if (v == null) return fallback;
    if (v is String) return v;
    return v.toString();
  }

  static String? asStringOrNull(dynamic v) {
    if (v == null) return null;
    final s = v is String ? v : v.toString();
    final t = s.trim();
    if (t.isEmpty || t.toLowerCase() == 'null') return null;
    return t;
  }

  static int asInt(dynamic v, {int fallback = 0}) {
    if (v == null) return fallback;
    if (v is int) return v;
    if (v is double) return v.toInt();
    if (v is bool) return v ? 1 : 0;
    return int.tryParse(v.toString().trim()) ??
        double.tryParse(v.toString().trim())?.toInt() ??
        fallback;
  }

  static int? asIntOrNull(dynamic v) {
    if (v == null) return null;
    if (v is int) return v;
    if (v is double) return v.toInt();
    final s = v.toString().trim();
    if (s.isEmpty) return null;
    return int.tryParse(s) ?? double.tryParse(s)?.toInt();
  }

  static double asDouble(dynamic v, {double fallback = 0}) {
    if (v == null) return fallback;
    if (v is num) return v.toDouble();
    return double.tryParse(v.toString().trim().replaceAll(',', '.')) ??
        fallback;
  }

  static double? asDoubleOrNull(dynamic v) {
    if (v == null) return null;
    if (v is num) return v.toDouble();
    final s = v.toString().trim().replaceAll(',', '.');
    if (s.isEmpty) return null;
    return double.tryParse(s);
  }

  static bool asBool(dynamic v, {bool fallback = false}) {
    if (v == null) return fallback;
    if (v is bool) return v;
    if (v is num) return v != 0;
    final s = v.toString().trim().toLowerCase();
    return s == '1' || s == 'true' || s == 'yes' || s == 'on';
  }

  /// Parses a unix timestamp (seconds) that may arrive as String/int/null.
  static DateTime? asUnixSeconds(dynamic v) {
    final i = asIntOrNull(v);
    if (i == null || i == 0) return null;
    return DateTime.fromMillisecondsSinceEpoch(i * 1000);
  }

  static List<dynamic> asList(dynamic v) {
    if (v is List) return v;
    return const [];
  }
}
