import '../core/utils/json_x.dart';

/// A VOD (movie) list item.
class VodMovie {
  const VodMovie({
    required this.streamId,
    required this.name,
    this.poster,
    this.categoryId,
    this.rating,
    this.year,
    this.added,
    this.containerExtension,
    this.directUrl,
  });

  final String streamId;
  final String name;
  final String? poster;
  final String? categoryId;
  final double? rating;
  final String? year;
  final DateTime? added;
  final String? containerExtension;
  final String? directUrl;

  factory VodMovie.fromXtream(Map<String, dynamic> json) {
    return VodMovie(
      streamId: JsonX.asString(json['stream_id']),
      name: JsonX.asString(json['name'], fallback: 'Movie'),
      poster:
          JsonX.asStringOrNull(json['stream_icon']) ??
          JsonX.asStringOrNull(json['cover']),
      categoryId: JsonX.asStringOrNull(json['category_id']),
      rating: JsonX.asDoubleOrNull(json['rating']),
      year: JsonX.asStringOrNull(json['year']),
      added: JsonX.asUnixSeconds(json['added']),
      containerExtension:
          JsonX.asStringOrNull(json['container_extension']) ?? 'mp4',
    );
  }

  Map<String, dynamic> toPayload() => {
    'streamId': streamId,
    'name': name,
    'poster': poster,
    'categoryId': categoryId,
    'rating': rating,
    'year': year,
    'containerExtension': containerExtension,
    'directUrl': directUrl,
  };

  factory VodMovie.fromPayload(Map<String, dynamic> json) => VodMovie(
    streamId: JsonX.asString(json['streamId']),
    name: JsonX.asString(json['name'], fallback: 'Movie'),
    poster: JsonX.asStringOrNull(json['poster']),
    categoryId: JsonX.asStringOrNull(json['categoryId']),
    rating: JsonX.asDoubleOrNull(json['rating']),
    year: JsonX.asStringOrNull(json['year']),
    containerExtension: JsonX.asStringOrNull(json['containerExtension']),
    directUrl: JsonX.asStringOrNull(json['directUrl']),
  );
}

/// Extended movie metadata from `get_vod_info`.
class MovieDetail {
  const MovieDetail({
    required this.movie,
    this.plot,
    this.cast,
    this.director,
    this.genre,
    this.releaseDate,
    this.durationSecs,
    this.backdrop,
    this.country,
    this.trailer,
    this.tmdbId,
  });

  final VodMovie movie;
  final String? plot;
  final String? cast;
  final String? director;
  final String? genre;
  final String? releaseDate;
  final int? durationSecs;
  final String? backdrop;
  final String? country;
  final String? trailer;
  final String? tmdbId;

  factory MovieDetail.fromXtream(Map<String, dynamic> json, VodMovie base) {
    final info = (json['info'] is Map)
        ? Map<String, dynamic>.from(json['info'] as Map)
        : <String, dynamic>{};
    final movieData = (json['movie_data'] is Map)
        ? Map<String, dynamic>.from(json['movie_data'] as Map)
        : <String, dynamic>{};

    final backdrops = JsonX.asList(info['backdrop_path']);
    final container =
        JsonX.asStringOrNull(movieData['container_extension']) ??
        base.containerExtension;

    return MovieDetail(
      movie: VodMovie(
        streamId: base.streamId,
        name: base.name,
        poster: JsonX.asStringOrNull(info['movie_image']) ?? base.poster,
        categoryId: base.categoryId,
        rating: JsonX.asDoubleOrNull(info['rating']) ?? base.rating,
        year: base.year,
        containerExtension: container,
      ),
      plot:
          JsonX.asStringOrNull(info['plot']) ??
          JsonX.asStringOrNull(info['description']),
      cast:
          JsonX.asStringOrNull(info['cast']) ??
          JsonX.asStringOrNull(info['actors']),
      director: JsonX.asStringOrNull(info['director']),
      genre: JsonX.asStringOrNull(info['genre']),
      releaseDate:
          JsonX.asStringOrNull(info['releasedate']) ??
          JsonX.asStringOrNull(info['release_date']),
      durationSecs: JsonX.asIntOrNull(info['duration_secs']),
      backdrop: backdrops.isNotEmpty
          ? JsonX.asStringOrNull(backdrops.first)
          : JsonX.asStringOrNull(info['cover_big']),
      country: JsonX.asStringOrNull(info['country']),
      trailer: JsonX.asStringOrNull(info['youtube_trailer']),
      tmdbId: JsonX.asStringOrNull(info['tmdb_id']),
    );
  }
}
