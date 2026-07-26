import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/models/vod_movie.dart';
import 'package:moplayer_moos/providers/content_providers.dart';

VodMovie _movie(String id, double? rating) =>
    VodMovie(streamId: id, name: id, rating: rating);

void main() {
  test(
    'topRatedMovies drops unrated films, sorts, and bounds the home rail',
    () {
      final movies = [
        _movie('missing', null),
        _movie('zero', 0),
        for (var i = 0; i < 30; i++) _movie('rated-$i', i / 3),
      ];

      final top = topRatedMovies(movies);

      expect(top, hasLength(24));
      expect(top.first.streamId, 'rated-29');
      expect(top.last.streamId, 'rated-6');
      expect(top.every((movie) => movie.rating! > 0), isTrue);
    },
  );

  test('the provider memoises the expensive sort until its input changes', () {
    final container = ProviderContainer(
      overrides: [
        moviesProvider('__all__').overrideWith(
          (ref) async => [_movie('winner', 9), _movie('other', 7)],
        ),
      ],
    );
    addTearDown(container.dispose);

    return container.read(moviesProvider('__all__').future).then((_) {
      final first = container.read(topRatedMoviesProvider);
      final second = container.read(topRatedMoviesProvider);
      expect(identical(first, second), isTrue);
      expect(first.map((movie) => movie.streamId), ['winner', 'other']);
    });
  });
}
