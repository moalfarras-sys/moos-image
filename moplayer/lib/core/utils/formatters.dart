/// Pure formatting helpers used across the UI.
class Fmt {
  const Fmt._();

  /// Formats a duration as `1:02:33` or `12:05`.
  static String duration(Duration d) {
    final h = d.inHours;
    final m = d.inMinutes.remainder(60);
    final s = d.inSeconds.remainder(60);
    String two(int v) => v.toString().padLeft(2, '0');
    if (h > 0) return '$h:${two(m)}:${two(s)}';
    return '${two(m)}:${two(s)}';
  }

  /// Compact item counts: 12500 -> "12.5K".
  static String compact(int value) {
    if (value < 1000) return '$value';
    if (value < 1000000) {
      final v = value / 1000;
      return '${v.toStringAsFixed(v >= 10 ? 0 : 1)}K';
    }
    final v = value / 1000000;
    return '${v.toStringAsFixed(v >= 10 ? 0 : 1)}M';
  }

  /// Best-effort minutes -> "1h 45m".
  static String runtimeMinutes(int? minutes) {
    if (minutes == null || minutes <= 0) return '';
    final h = minutes ~/ 60;
    final m = minutes % 60;
    if (h > 0 && m > 0) return '${h}h ${m}m';
    if (h > 0) return '${h}h';
    return '${m}m';
  }

  /// Initials fallback for a missing logo/poster ("BBC One" -> "BO").
  static String initials(String name) {
    final parts = name
        .replaceAll(RegExp(r'[^\w\s]'), ' ')
        .trim()
        .split(RegExp(r'\s+'))
        .where((p) => p.isNotEmpty)
        .toList();
    if (parts.isEmpty) return '?';
    if (parts.length == 1) {
      return parts.first
          .substring(0, parts.first.length >= 2 ? 2 : 1)
          .toUpperCase();
    }
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
}
