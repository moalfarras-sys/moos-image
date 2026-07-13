import '../core/utils/json_x.dart';

/// A series list item.
class SeriesItem {
  const SeriesItem({
    required this.seriesId,
    required this.name,
    this.cover,
    this.categoryId,
    this.rating,
    this.plot,
    this.genre,
    this.releaseDate,
    this.lastModified,
    this.backdrop,
  });

  final String seriesId;
  final String name;
  final String? cover;
  final String? categoryId;
  final double? rating;
  final String? plot;
  final String? genre;
  final String? releaseDate;
  final DateTime? lastModified;
  final String? backdrop;

  factory SeriesItem.fromXtream(Map<String, dynamic> json) {
    final backdrops = JsonX.asList(json['backdrop_path']);
    return SeriesItem(
      seriesId: JsonX.asString(json['series_id']),
      name: JsonX.asString(json['name'], fallback: 'Series'),
      cover: JsonX.asStringOrNull(json['cover']),
      categoryId: JsonX.asStringOrNull(json['category_id']),
      rating: JsonX.asDoubleOrNull(json['rating']),
      plot: JsonX.asStringOrNull(json['plot']),
      genre: JsonX.asStringOrNull(json['genre']),
      releaseDate:
          JsonX.asStringOrNull(json['releaseDate']) ??
          JsonX.asStringOrNull(json['release_date']),
      lastModified: JsonX.asUnixSeconds(json['last_modified']),
      backdrop: backdrops.isNotEmpty
          ? JsonX.asStringOrNull(backdrops.first)
          : null,
    );
  }

  Map<String, dynamic> toPayload() => {
    'seriesId': seriesId,
    'name': name,
    'cover': cover,
    'categoryId': categoryId,
    'rating': rating,
  };

  factory SeriesItem.fromPayload(Map<String, dynamic> json) => SeriesItem(
    seriesId: JsonX.asString(json['seriesId']),
    name: JsonX.asString(json['name'], fallback: 'Series'),
    cover: JsonX.asStringOrNull(json['cover']),
    categoryId: JsonX.asStringOrNull(json['categoryId']),
    rating: JsonX.asDoubleOrNull(json['rating']),
  );
}

/// A single episode within a season.
class Episode {
  const Episode({
    required this.id,
    required this.title,
    required this.episodeNum,
    required this.seasonNumber,
    this.containerExtension,
    this.durationSecs,
    this.plot,
    this.image,
    this.rating,
    this.added,
  });

  final String id;
  final String title;
  final int episodeNum;
  final int seasonNumber;
  final String? containerExtension;
  final int? durationSecs;
  final String? plot;
  final String? image;
  final double? rating;
  final DateTime? added;

  factory Episode.fromXtream(Map<String, dynamic> json, int seasonNumber) {
    final info = (json['info'] is Map)
        ? Map<String, dynamic>.from(json['info'] as Map)
        : <String, dynamic>{};
    return Episode(
      id: JsonX.asString(json['id']),
      title: JsonX.asString(json['title'], fallback: 'Episode'),
      episodeNum: JsonX.asInt(json['episode_num'], fallback: 0),
      seasonNumber: JsonX.asIntOrNull(json['season']) ?? seasonNumber,
      containerExtension:
          JsonX.asStringOrNull(json['container_extension']) ?? 'mp4',
      durationSecs: JsonX.asIntOrNull(info['duration_secs']),
      plot: JsonX.asStringOrNull(info['plot']),
      image:
          JsonX.asStringOrNull(info['movie_image']) ??
          JsonX.asStringOrNull(info['cover_big']),
      rating: JsonX.asDoubleOrNull(info['rating']),
      added: JsonX.asUnixSeconds(json['added']),
    );
  }

  Map<String, dynamic> toPayload() => {
    'id': id,
    'title': title,
    'episodeNum': episodeNum,
    'seasonNumber': seasonNumber,
    'containerExtension': containerExtension,
    'image': image,
  };

  factory Episode.fromPayload(Map<String, dynamic> json) => Episode(
    id: JsonX.asString(json['id']),
    title: JsonX.asString(json['title'], fallback: 'Episode'),
    episodeNum: JsonX.asInt(json['episodeNum']),
    seasonNumber: JsonX.asInt(json['seasonNumber']),
    containerExtension: JsonX.asStringOrNull(json['containerExtension']),
    image: JsonX.asStringOrNull(json['image']),
  );
}

/// A season grouping episodes.
class Season {
  const Season({
    required this.number,
    required this.episodes,
    this.name,
    this.cover,
  });

  final int number;
  final List<Episode> episodes;
  final String? name;
  final String? cover;

  String get displayName => name?.trim().isNotEmpty == true
      ? name!
      : (number == 0 ? 'Specials' : 'Season $number');
}

/// Full series details with seasons and episodes from `get_series_info`.
class SeriesDetail {
  const SeriesDetail({required this.series, required this.seasons});

  final SeriesItem series;
  final List<Season> seasons;

  factory SeriesDetail.fromXtream(Map<String, dynamic> json, SeriesItem base) {
    final info = (json['info'] is Map)
        ? Map<String, dynamic>.from(json['info'] as Map)
        : <String, dynamic>{};

    final mergedSeries = SeriesItem(
      seriesId: base.seriesId,
      name: JsonX.asStringOrNull(info['name']) ?? base.name,
      cover: JsonX.asStringOrNull(info['cover']) ?? base.cover,
      categoryId: base.categoryId,
      rating: JsonX.asDoubleOrNull(info['rating']) ?? base.rating,
      plot: JsonX.asStringOrNull(info['plot']) ?? base.plot,
      genre: JsonX.asStringOrNull(info['genre']) ?? base.genre,
      releaseDate:
          JsonX.asStringOrNull(info['releaseDate']) ?? base.releaseDate,
      backdrop: base.backdrop,
    );

    final episodesRaw = json['episodes'];
    final seasons = <Season>[];
    if (episodesRaw is Map) {
      final entries =
          episodesRaw.entries
              .map(
                (entry) => (
                  number: int.tryParse(entry.key.toString()) ?? 0,
                  value: entry.value,
                ),
              )
              .toList()
            ..sort((a, b) => a.number.compareTo(b.number));
      for (final entry in entries) {
        final seasonNo = entry.number;
        final list = JsonX.asList(entry.value);
        final episodes =
            list
                .whereType<Map>()
                .map(
                  (e) => Episode.fromXtream(
                    Map<String, dynamic>.from(e),
                    seasonNo,
                  ),
                )
                .toList()
              ..sort((a, b) => a.episodeNum.compareTo(b.episodeNum));
        if (episodes.isNotEmpty) {
          seasons.add(Season(number: seasonNo, episodes: episodes));
        }
      }
    } else if (episodesRaw is List) {
      final grouped = <int, List<Episode>>{};
      for (final raw in episodesRaw.whereType<Map>()) {
        final map = Map<String, dynamic>.from(raw);
        final seasonNo = JsonX.asIntOrNull(map['season']) ?? 1;
        grouped
            .putIfAbsent(seasonNo, () => <Episode>[])
            .add(Episode.fromXtream(map, seasonNo));
      }
      final keys = grouped.keys.toList()..sort();
      for (final seasonNo in keys) {
        final episodes = grouped[seasonNo]!
          ..sort((a, b) => a.episodeNum.compareTo(b.episodeNum));
        if (episodes.isNotEmpty) {
          seasons.add(Season(number: seasonNo, episodes: episodes));
        }
      }
    }

    return SeriesDetail(series: mergedSeries, seasons: seasons);
  }
}
