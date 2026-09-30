import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import '../../core/config/app_config.dart';
import '../../core/error/failures.dart';

/// A GET that is safe to run inside a background isolate.
///
/// Plain `dart:io`, not Dio: the catalogue jobs fetch, cache and parse in one
/// isolate so that a 12 MB series list never crosses into the UI isolate as a
/// string, and they need nothing from Dio but a timeout. Every failure leaves
/// as a [Failure] with no `cause`, because an error thrown inside an isolate is
/// copied back out, and only plain data survives the copy.
Future<Uint8List> fetchBytes(
  Uri uri, {
  Map<String, String> headers = const {},
  Duration connectTimeout = const Duration(seconds: 20),
  Duration timeout = const Duration(seconds: 150),
  int retries = 1,
}) async {
  for (var attempt = 0; ; attempt++) {
    try {
      return await _fetchOnce(uri, headers, connectTimeout, timeout);
    } on Failure catch (failure) {
      final transient =
          failure.kind == FailureKind.timeout ||
          failure.kind == FailureKind.network;
      if (!transient || attempt >= retries) rethrow;
      await Future<void>.delayed(Duration(milliseconds: 600 * (attempt + 1)));
    }
  }
}

Future<Uint8List> _fetchOnce(
  Uri uri,
  Map<String, String> headers,
  Duration connectTimeout,
  Duration timeout,
) async {
  final client = HttpClient()
    ..connectionTimeout = connectTimeout
    ..idleTimeout = const Duration(seconds: 5)
    ..userAgent = headers['User-Agent'] ?? AppConfig.apiUserAgent
    ..autoUncompress = true;
  try {
    final request = await client.getUrl(uri).timeout(connectTimeout);
    request.followRedirects = true;
    request.maxRedirects = 8;
    headers.forEach((name, value) {
      if (name.toLowerCase() != 'user-agent') request.headers.set(name, value);
    });
    final response = await request.close().timeout(timeout);
    final status = response.statusCode;
    if (status == 401 || status == 403) {
      await response.drain<void>().catchError((Object _) {});
      throw Failure.auth();
    }
    if (status < 200 || status >= 300) {
      await response.drain<void>().catchError((Object _) {});
      throw Failure.server('Server error (HTTP $status).');
    }
    final builder = BytesBuilder(copy: false);
    await response.timeout(timeout).forEach(builder.add);
    return builder.takeBytes();
  } on Failure {
    rethrow;
  } on TimeoutException {
    throw Failure.timeout();
  } on HandshakeException {
    throw Failure.server('The server has an invalid SSL certificate.');
  } on SocketException {
    throw Failure.network('Could not reach the server. Check the URL.');
  } on HttpException {
    throw Failure.network('The connection to the server was interrupted.');
  } on Object {
    // Deliberately no detail: the error text of a failed request quotes its
    // URI, and an Xtream URI carries the account's password.
    throw Failure.network('Could not reach the server.');
  } finally {
    client.close(force: true);
  }
}
