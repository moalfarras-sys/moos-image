/// The four kinds of playable / browsable content in MoPlayer Pro.
enum MediaKind {
  live,
  movie,
  series,
  episode;

  String get wire => name;

  static MediaKind fromWire(String? v) {
    return MediaKind.values.firstWhere(
      (e) => e.wire == v,
      orElse: () => MediaKind.live,
    );
  }

  bool get isPlayable => this != MediaKind.series;
}
