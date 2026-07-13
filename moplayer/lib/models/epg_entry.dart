import 'dart:convert';

import '../core/utils/json_x.dart';

/// A single EPG (electronic programme guide) programme entry.
class EpgEntry {
  const EpgEntry({
    required this.title,
    required this.start,
    required this.end,
    this.description,
  });

  final String title;
  final DateTime start;
  final DateTime end;
  final String? description;

  bool get isLiveNow {
    final now = DateTime.now();
    return now.isAfter(start) && now.isBefore(end);
  }

  /// Progress 0..1 through the current programme.
  double get progress {
    final total = end.difference(start).inSeconds;
    if (total <= 0) return 0;
    final elapsed = DateTime.now().difference(start).inSeconds;
    return (elapsed / total).clamp(0.0, 1.0);
  }

  /// Xtream returns EPG titles/descriptions base64 encoded.
  static String _decode(dynamic v) {
    final s = JsonX.asString(v);
    if (s.isEmpty) return '';
    try {
      return utf8.decode(base64.decode(s));
    } catch (_) {
      return s;
    }
  }

  factory EpgEntry.fromXtream(Map<String, dynamic> json) {
    final start =
        JsonX.asUnixSeconds(json['start_timestamp']) ??
        DateTime.tryParse(JsonX.asString(json['start'])) ??
        DateTime.now();
    final end =
        JsonX.asUnixSeconds(json['stop_timestamp']) ??
        DateTime.tryParse(JsonX.asString(json['end'])) ??
        start.add(const Duration(minutes: 30));
    return EpgEntry(
      title: _decode(json['title']),
      description: _decode(json['description']),
      start: start,
      end: end,
    );
  }
}
