import '../core/utils/json_x.dart';

/// A live TV channel from either an Xtream panel or an M3U playlist.
class LiveChannel {
  const LiveChannel({
    required this.streamId,
    required this.name,
    this.logo,
    this.categoryId,
    this.epgChannelId,
    this.number,
    this.directUrl,
    this.containerExtension,
    this.tvArchive = false,
  });

  /// For Xtream this is the numeric stream id (kept as String for unity with
  /// M3U which has no numeric id — we hash the url instead).
  final String streamId;
  final String name;
  final String? logo;
  final String? categoryId;
  final String? epgChannelId;
  final int? number;

  /// Present for M3U channels (a full ready-to-play URL). For Xtream the URL
  /// is built from credentials + streamId at play time.
  final String? directUrl;
  final String? containerExtension;
  final bool tvArchive;

  factory LiveChannel.fromXtream(Map<String, dynamic> json) {
    return LiveChannel(
      streamId: JsonX.asString(json['stream_id']),
      name: JsonX.asString(json['name'], fallback: 'Channel'),
      logo: JsonX.asStringOrNull(json['stream_icon']),
      categoryId: JsonX.asStringOrNull(json['category_id']),
      epgChannelId: JsonX.asStringOrNull(json['epg_channel_id']),
      number: JsonX.asIntOrNull(json['num']),
      containerExtension:
          JsonX.asStringOrNull(json['container_extension']) ?? 'ts',
      tvArchive: JsonX.asBool(json['tv_archive']),
    );
  }

  Map<String, dynamic> toPayload() => {
    'streamId': streamId,
    'name': name,
    'logo': logo,
    'categoryId': categoryId,
    'epgChannelId': epgChannelId,
    'directUrl': directUrl,
    'containerExtension': containerExtension,
  };

  factory LiveChannel.fromPayload(Map<String, dynamic> json) {
    return LiveChannel(
      streamId: JsonX.asString(json['streamId']),
      name: JsonX.asString(json['name'], fallback: 'Channel'),
      logo: JsonX.asStringOrNull(json['logo']),
      categoryId: JsonX.asStringOrNull(json['categoryId']),
      epgChannelId: JsonX.asStringOrNull(json['epgChannelId']),
      directUrl: JsonX.asStringOrNull(json['directUrl']),
      containerExtension: JsonX.asStringOrNull(json['containerExtension']),
    );
  }
}
