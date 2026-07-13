import 'dart:convert';
import 'dart:math';

import 'package:dio/dio.dart';

import '../../core/config/app_config.dart';
import '../../core/error/failures.dart';
import '../../models/playlist_config.dart';
import '../device/device_service.dart';

class ActivationSession {
  const ActivationSession({
    required this.code,
    required this.expiresAt,
    required this.sourcePullToken,
    required this.activationUrl,
  });

  final String code;
  final DateTime expiresAt;
  final String sourcePullToken;
  final Uri activationUrl;
}

class ActivationStatus {
  const ActivationStatus({
    required this.status,
    this.message,
    this.publicDeviceId,
    this.sourcePending = false,
    this.sourceStatus,
  });

  final String status;
  final String? message;
  final String? publicDeviceId;
  final bool sourcePending;
  final String? sourceStatus;

  bool get isActivated => status == 'activated';
}

class SourcePullResult {
  const SourcePullResult.empty({this.message})
    : sourceId = null,
      playlist = null;

  const SourcePullResult.available({
    required this.sourceId,
    required this.playlist,
  }) : message = null;

  final String? sourceId;
  final PlaylistConfig? playlist;
  final String? message;

  bool get hasSource => sourceId != null && playlist != null;
}

class ActivationService {
  ActivationService({Dio? dio})
    : _dio =
          dio ??
          Dio(
            BaseOptions(
              connectTimeout: AppConfig.connectTimeout,
              receiveTimeout: AppConfig.receiveTimeout,
              headers: const {'User-Agent': 'MoPlayerPro-iOS/1.0'},
            ),
          );

  final Dio _dio;

  Uri get _base =>
      Uri.parse(AppConfig.webBaseUrl.replaceAll(RegExp(r'/+$'), ''));

  Future<ActivationSession> create(DeviceService device) async {
    final token = _token();
    final uri = _base.replace(path: '/api/app/activation/create');
    try {
      final res = await _dio.postUri<Map<String, dynamic>>(
        uri,
        data: {
          'publicDeviceId': device.deviceId,
          'deviceName': device.model,
          'deviceType': AppConfig.deviceType,
          'platform': AppConfig.platform,
          'appVersion': device.appVersion,
          'sourcePullToken': token,
          'productSlug': AppConfig.productSlug,
        },
      );
      final data = res.data ?? const {};
      if (data['status'] != 'waiting') {
        throw Failure.server(
          '${data['message'] ?? 'Activation was not created.'}',
        );
      }
      final code = '${data['code'] ?? ''}';
      final expiresAt =
          DateTime.tryParse('${data['expiresAt'] ?? ''}') ??
          DateTime.now().add(const Duration(minutes: 15));
      return ActivationSession(
        code: code,
        expiresAt: expiresAt,
        sourcePullToken: token,
        activationUrl: _base.replace(
          path: '/activate',
          queryParameters: {'product': AppConfig.productSlug, 'code': code},
        ),
      );
    } on DioException catch (e) {
      throw _failure(e, 'Could not create activation code.');
    }
  }

  Future<ActivationStatus> status(String code) async {
    final uri = _base.replace(
      path: '/api/app/activation/status',
      queryParameters: {'product': AppConfig.productSlug, 'code': code},
    );
    try {
      final res = await _dio.getUri<Map<String, dynamic>>(
        uri,
        options: Options(
          validateStatus: (status) => status != null && status < 500,
        ),
      );
      final data = res.data ?? const {};
      return ActivationStatus(
        status: '${data['status'] ?? 'pending'}',
        message: data['message'] as String?,
        publicDeviceId: data['publicDeviceId'] as String?,
        sourcePending: data['sourcePending'] == true,
        sourceStatus: data['sourceStatus'] as String?,
      );
    } on DioException catch (e) {
      throw _failure(e, 'Could not check activation status.');
    }
  }

  Future<SourcePullResult> pullSource({
    required String publicDeviceId,
    required String token,
  }) async {
    final uri = _base.replace(
      path: '/api/app/activation/source',
      queryParameters: {
        'product': AppConfig.productSlug,
        'publicDeviceId': publicDeviceId,
        'token': token,
      },
    );
    try {
      final res = await _dio.getUri<Map<String, dynamic>>(
        uri,
        options: Options(
          validateStatus: (status) => status != null && status < 500,
        ),
      );
      final data = res.data ?? const {};
      if (data['status'] != 'source_available') {
        return SourcePullResult.empty(message: data['message'] as String?);
      }

      final source = (data['source'] as Map?)?.cast<String, dynamic>();
      if (source == null) return const SourcePullResult.empty();
      return SourcePullResult.available(
        sourceId: '${data['sourceId'] ?? ''}',
        playlist: _playlistFromSource(source),
      );
    } on DioException catch (e) {
      throw _failure(e, 'Could not pull the provider source.');
    }
  }

  Future<void> ackSource({
    required String publicDeviceId,
    required String token,
    required String sourceId,
    bool imported = true,
    String? message,
  }) async {
    final uri = _base.replace(path: '/api/app/activation/source/ack');
    final payload = <String, dynamic>{
      'publicDeviceId': publicDeviceId,
      'token': token,
      'sourceId': sourceId,
      'status': imported ? 'imported' : 'failed',
    };
    if (message != null) {
      payload['message'] = message;
    }
    try {
      await _dio.postUri<Map<String, dynamic>>(uri, data: payload);
    } on DioException {
      // Ack is best-effort; the server-side queue expires quickly anyway.
    }
  }

  PlaylistConfig _playlistFromSource(Map<String, dynamic> source) {
    final type = '${source['type'] ?? ''}';
    final id = 'qr_${DateTime.now().microsecondsSinceEpoch}';
    if (type == 'xtream') {
      return PlaylistConfig(
        id: id,
        type: PlaylistType.xtream,
        name: '${source['name'] ?? 'MoPlayer Source'}',
        serverUrl: '${source['serverUrl'] ?? ''}',
        username: '${source['username'] ?? ''}',
        password: '${source['password'] ?? ''}',
      );
    }
    return PlaylistConfig(
      id: id,
      type: PlaylistType.m3u,
      name: '${source['name'] ?? 'MoPlayer Source'}',
      m3uUrl: '${source['playlistUrl'] ?? ''}',
    );
  }

  String _token() {
    final rng = Random.secure();
    final bytes = List<int>.generate(36, (_) => rng.nextInt(256));
    return base64Url.encode(bytes).replaceAll('=', '');
  }

  Failure _failure(DioException e, String fallback) {
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout) {
      return Failure.timeout();
    }
    final data = e.response?.data;
    if (data is Map && data['message'] is String) {
      return Failure.server(data['message'] as String);
    }
    return Failure.network(fallback);
  }

  void close() => _dio.close(force: true);
}
