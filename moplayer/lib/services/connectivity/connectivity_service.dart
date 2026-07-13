import 'package:connectivity_plus/connectivity_plus.dart';

/// Thin wrapper over `connectivity_plus` exposing a simple online/offline
/// boolean and a stream for reactive UI.
class ConnectivityService {
  ConnectivityService([Connectivity? connectivity])
    : _connectivity = connectivity ?? Connectivity();

  final Connectivity _connectivity;

  Future<bool> get isOnline async {
    final result = await _connectivity.checkConnectivity();
    return _online(result);
  }

  Stream<bool> get onStatusChange =>
      _connectivity.onConnectivityChanged.map(_online);

  bool _online(List<ConnectivityResult> result) {
    return result.any((r) => r != ConnectivityResult.none);
  }
}
