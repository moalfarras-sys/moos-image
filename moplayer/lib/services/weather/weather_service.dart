import 'package:dio/dio.dart';

import '../../core/utils/app_logger.dart';
import '../../core/utils/json_x.dart';

/// The weather where the user is, with no key, no account and no setting.
///
/// Location comes from the IP address and the forecast from Open-Meteo, which is
/// the same pair MoOS's own desktop widget uses — proven on this machine rather
/// than chosen from a list.
///
/// **`ipapi.co` is deliberately not used, and this is not a preference.** It
/// answers `curl` correctly and answers a *browser* User-Agent with a Cloudflare
/// challenge page — and a Dio/Flutter client sends a browser-ish User-Agent. The
/// widget then receives HTML where it expected JSON and shows nothing at all,
/// with no error anywhere. `ipwho.is` answers both the same way. Testing a
/// weather API with curl proves nothing about the API *as the app sees it*.
class WeatherService {
  WeatherService({Dio? dio})
    : _dio =
          dio ??
          Dio(
            BaseOptions(
              connectTimeout: const Duration(seconds: 8),
              receiveTimeout: const Duration(seconds: 8),
            ),
          );

  final Dio _dio;

  Future<WeatherNow?> fetch() async {
    try {
      final place = await _locate();
      if (place == null) return null;

      final res = await _dio.get<dynamic>(
        'https://api.open-meteo.com/v1/forecast',
        queryParameters: {
          'latitude': place.latitude,
          'longitude': place.longitude,
          'current': 'temperature_2m,weather_code,is_day',
          'daily': 'temperature_2m_max,temperature_2m_min',
          'timezone': 'auto',
          'forecast_days': 1,
        },
      );

      final body = res.data;
      if (body is! Map) return null;

      final current = body['current'];
      if (current is! Map) return null;
      final daily = body['daily'];

      double? dayValue(String key) {
        if (daily is! Map) return null;
        final list = daily[key];
        if (list is! List || list.isEmpty) return null;
        return JsonX.asDoubleOrNull(list.first);
      }

      return WeatherNow(
        city: place.city,
        temperature: JsonX.asDoubleOrNull(current['temperature_2m']) ?? 0,
        code: JsonX.asIntOrNull(current['weather_code']) ?? 0,
        isDay: (JsonX.asIntOrNull(current['is_day']) ?? 1) == 1,
        high: dayValue('temperature_2m_max'),
        low: dayValue('temperature_2m_min'),
      );
    } catch (e) {
      // No weather is a widget that does not appear. It is never an error the
      // user has to dismiss on the way to watching television.
      log.d('weather unavailable: $e');
      return null;
    }
  }

  Future<_Place?> _locate() async {
    final res = await _dio.get<dynamic>('https://ipwho.is/');
    final body = res.data;
    if (body is! Map) return null;
    if (JsonX.asBool(body['success']) == false) return null;

    final lat = JsonX.asDoubleOrNull(body['latitude']);
    final lon = JsonX.asDoubleOrNull(body['longitude']);
    if (lat == null || lon == null) return null;

    return _Place(
      city: JsonX.asString(body['city'], fallback: ''),
      latitude: lat,
      longitude: lon,
    );
  }
}

class _Place {
  const _Place({
    required this.city,
    required this.latitude,
    required this.longitude,
  });

  final String city;
  final double latitude;
  final double longitude;
}

/// What the widget draws.
class WeatherNow {
  const WeatherNow({
    required this.city,
    required this.temperature,
    required this.code,
    required this.isDay,
    this.high,
    this.low,
  });

  final String city;
  final double temperature;

  /// WMO weather code. Mapped to an icon and a phrase by the widget — the
  /// mapping is presentation, and it is translated.
  final int code;
  final bool isDay;
  final double? high;
  final double? low;

  /// The families the WMO table collapses to, which is all a weather *icon* can
  /// honestly say. Drizzle and rain are one picture.
  WeatherKind get kind => switch (code) {
    0 => WeatherKind.clear,
    1 || 2 => WeatherKind.partlyCloudy,
    3 => WeatherKind.cloudy,
    45 || 48 => WeatherKind.fog,
    >= 51 && <= 67 => WeatherKind.rain,
    >= 71 && <= 77 => WeatherKind.snow,
    >= 80 && <= 82 => WeatherKind.rain,
    >= 85 && <= 86 => WeatherKind.snow,
    >= 95 => WeatherKind.storm,
    _ => WeatherKind.cloudy,
  };
}

enum WeatherKind { clear, partlyCloudy, cloudy, fog, rain, snow, storm }
