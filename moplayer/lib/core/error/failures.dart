/// A typed, user-presentable failure. Every layer maps low-level exceptions
/// into one of these so the UI can render a clear message and offer a retry.
class Failure implements Exception {
  const Failure(this.message, {this.kind = FailureKind.unknown, this.cause});

  final String message;
  final FailureKind kind;
  final Object? cause;

  factory Failure.network([String? msg]) => Failure(
    msg ?? 'No internet connection. Check your network and try again.',
    kind: FailureKind.network,
  );

  factory Failure.timeout([String? msg]) => Failure(
    msg ?? 'The server took too long to respond. Please try again.',
    kind: FailureKind.timeout,
  );

  factory Failure.auth([String? msg]) => Failure(
    msg ?? 'Invalid credentials. Please check your login details.',
    kind: FailureKind.auth,
  );

  factory Failure.server([String? msg]) => Failure(
    msg ?? 'The IPTV server returned an unexpected response.',
    kind: FailureKind.server,
  );

  factory Failure.parse([String? msg]) => Failure(
    msg ?? 'Could not read the playlist data.',
    kind: FailureKind.parse,
  );

  factory Failure.notConfigured([String? msg]) => Failure(
    msg ?? 'This feature requires a backend that is not configured.',
    kind: FailureKind.notConfigured,
  );

  @override
  String toString() => 'Failure($kind): $message';
}

enum FailureKind {
  network,
  timeout,
  auth,
  server,
  parse,
  notConfigured,
  unknown,
}
