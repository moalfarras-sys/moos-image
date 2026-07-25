import 'dart:typed_data';
import 'dart:ui';

import 'package:flutter/material.dart';

import 'app_colors.dart';
import 'nova.dart';

/// Glass — the material MoPlayer's chrome is made of.
///
/// The recipe has five layers and every one of them is doing a job:
///
///  1. **A soft dark shadow**, so the pane sits *above* the scene rather than
///     being painted onto it.
///  2. **A real blur** of whatever is behind it.
///  3. **A dark fill at real opacity.** This is the load-bearing one. Nova's
///     rule — *no text on a variable background without an opaque-enough surface
///     beneath it* — is stricter here than anywhere else in MoOS, because the
///     "variable background" is a moving video frame. Turn the blur off and the
///     panel must still be legible; the blur is decoration, never the thing that
///     makes the text readable.
///  4. **A warm hairline border**, tinted with the surface's own hue. A neutral
///     grey line on a warm black reads as dirt.
///  5. **An inner highlight on the top edge only.** Real glass catches light on
///     the edge that faces it and nowhere else, and that single asymmetry is
///     most of what separates "a material" from "a translucent rectangle".
///
/// ## Where glass is allowed
///
/// On **chrome**: the dock, the window caption, the player's controls, the mini
/// player, a dashboard widget, a dialog. Never on a card in a scrolling grid —
/// every [BackdropFilter] is a save-layer, and forty of them in a poster wall is
/// how you drop frames on the integrated GPU a MoOS laptop is likely to have.
/// Cards are solid ([SolidCard]); only what floats *over* something is glass.
class GlassPanel extends StatelessWidget {
  const GlassPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(Nova.space4),
    this.radius = Nova.radiusPanel,
    this.blur = 24,
    this.fill,
    this.stroke,
    this.glow = false,
    this.shadow = true,
    this.highlight = true,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final double blur;
  final Color? fill;
  final Color? stroke;

  /// An ember bloom behind the panel. Reserved for the one primary surface on a
  /// screen; more than one, and neither reads as primary.
  final bool glow;
  final bool shadow;

  /// The lit top edge. Off for a panel that is flush against the top of the
  /// window, where there is no light above it to catch.
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    final borderRadius = BorderRadius.circular(radius);
    final base = fill ?? AppColors.glassFill;

    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: borderRadius,
        boxShadow: [
          if (shadow)
            const BoxShadow(
              color: Color(0x80000000),
              blurRadius: 32,
              offset: Offset(0, 12),
              spreadRadius: -10,
            ),
          if (glow)
            BoxShadow(
              color: AppColors.primary.withValues(alpha: 0.18),
              blurRadius: 48,
              spreadRadius: -12,
            ),
        ],
      ),
      child: ClipRRect(
        borderRadius: borderRadius,
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: base,
              borderRadius: borderRadius,
              border: Border.all(color: stroke ?? AppColors.glassStroke),
              // The lit edge. A gradient rather than a second border, because a
              // border is uniform and light is not.
              gradient: highlight
                  ? LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        AppColors.glassHighlight,
                        base.withValues(alpha: 0),
                      ],
                      stops: const [0.0, 0.14],
                    )
                  : null,
            ),
            child: Padding(padding: padding, child: child),
          ),
        ),
      ),
    );
  }
}

/// A solid card — the default surface for anything that scrolls.
///
/// See the note on [GlassPanel]: this exists so that a grid of two hundred
/// posters costs two hundred `DecoratedBox`es instead of two hundred save-layers.
class SolidCard extends StatelessWidget {
  const SolidCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(Nova.space4),
    this.radius = Nova.radiusCard,
    this.color,
    this.border = true,
    this.onTap,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final Color? color;
  final bool border;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final borderRadius = BorderRadius.circular(radius);
    final surface = Container(
      padding: padding,
      decoration: BoxDecoration(
        color: color ?? AppColors.surface2,
        borderRadius: borderRadius,
        border: border ? Border.all(color: AppColors.borderSubtle) : null,
      ),
      child: child,
    );

    if (onTap == null) return surface;
    return Material(
      color: Colors.transparent,
      borderRadius: borderRadius,
      child: InkWell(
        onTap: onTap,
        borderRadius: borderRadius,
        hoverColor: AppColors.surface3.withValues(alpha: 0.6),
        child: surface,
      ),
    );
  }
}

/// The old name, kept so the ported core still compiles.
typedef NovaCard = SolidCard;

/// The ambient scene: the warm graphite wash, the amber bloom in the top corner,
/// a controlled vignette, and a film grain at the threshold of visibility.
///
/// This is drawn once, behind everything, by the shell. It is what stops the app
/// from looking like a dark rectangle with widgets on it — and every layer of it
/// is static, so it costs nothing per frame.
class AmbientScene extends StatelessWidget {
  const AmbientScene({super.key, required this.child, this.grain = true});

  final Widget child;
  final bool grain;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(gradient: AppColors.sceneGradient),
      child: DecoratedBox(
        decoration: BoxDecoration(gradient: AppColors.ambientAmber),
        child: DecoratedBox(
          // The vignette. Very slight — enough to keep the eye in the middle of
          // a 32-inch screen, not enough to be seen as a shape.
          decoration: const BoxDecoration(
            gradient: RadialGradient(
              center: Alignment.center,
              radius: 1.0,
              colors: [Color(0x00000000), Color(0x59000000)],
              stops: [0.55, 1.0],
            ),
          ),
          child: grain ? FilmGrain(child: child) : child,
        ),
      ),
    );
  }
}

/// A film grain, at 3% opacity, tiled from a 96×96 texture generated once.
///
/// Not decoration for its own sake: a large flat dark area on an 8-bit panel
/// *bands*, and the gradients in this app are exactly the kind that show it —
/// long, dark, and low-contrast. A little noise is the standard fix, and it is
/// the same trick the film grades this app is going to be displaying use.
class FilmGrain extends StatefulWidget {
  const FilmGrain({super.key, required this.child, this.opacity = 0.030});

  final Widget child;
  final double opacity;

  @override
  State<FilmGrain> createState() => _FilmGrainState();
}

class _FilmGrainState extends State<FilmGrain> {
  static Image? _texture;

  @override
  void initState() {
    super.initState();
    // Generated once for the whole process, from a fixed seed: the grain must
    // not shimmer between frames (that reads as a rendering fault) and must not
    // be re-decoded per rebuild.
    _texture ??= Image.memory(
      _grainPng,
      repeat: ImageRepeat.repeat,
      filterQuality: FilterQuality.none,
      gaplessPlayback: true,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        widget.child,
        Positioned.fill(
          child: IgnorePointer(
            child: Opacity(
              opacity: widget.opacity,
              child: RepaintBoundary(child: _texture),
            ),
          ),
        ),
      ],
    );
  }
}

/// A 64×64 8-bit greyscale PNG of uniform noise, from a fixed seed.
///
/// Inlined rather than shipped as an asset for one reason: it is 1.5 kB, and an
/// asset is a file that can go missing from a bundle. The scene must never be
/// one lookup away from failing to draw.
final Uint8List _grainPng = _makeGrain();

Uint8List _makeGrain() {
  const size = 64;

  // A tiny deterministic PRNG. `Random(seed)` would do, but this keeps the grain
  // byte-identical across Dart versions, which keeps golden tests stable.
  var state = 0x2545F491;
  int next() {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return state & 0xFF;
  }

  // Raw scanlines: filter byte 0, then `size` grey bytes, per row.
  final raw = Uint8List(size * (size + 1));
  var p = 0;
  for (var y = 0; y < size; y++) {
    raw[p++] = 0;
    for (var x = 0; x < size; x++) {
      raw[p++] = next();
    }
  }

  final png = BytesBuilder();
  png.add([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]);

  void chunk(String type, List<int> data) {
    final body = <int>[...type.codeUnits, ...data];
    png.add(_be32(data.length));
    png.add(body);
    png.add(_be32(_crc32(body)));
  }

  chunk('IHDR', [
    ..._be32(size), ..._be32(size),
    8, // bit depth
    0, // greyscale
    0, 0, 0,
  ]);
  chunk('IDAT', _zlibStore(raw));
  chunk('IEND', const []);

  return png.toBytes();
}

List<int> _be32(int v) => [
  (v >>> 24) & 0xFF,
  (v >>> 16) & 0xFF,
  (v >>> 8) & 0xFF,
  v & 0xFF,
];

/// zlib, stored (uncompressed) blocks. The grain is random data — deflate would
/// not shrink it, and this keeps the generator to twenty lines with no
/// dependency.
List<int> _zlibStore(Uint8List data) {
  final out = <int>[0x78, 0x01]; // CMF/FLG: deflate, 32k window, no dict
  var i = 0;
  while (i < data.length) {
    final n = (data.length - i).clamp(0, 65535);
    final last = i + n >= data.length ? 1 : 0;
    out.addAll([
      last,
      n & 0xFF,
      (n >>> 8) & 0xFF,
      ~n & 0xFF,
      (~n >>> 8) & 0xFF,
    ]);
    out.addAll(data.sublist(i, i + n));
    i += n;
  }
  var a = 1, b = 0;
  for (final byte in data) {
    a = (a + byte) % 65521;
    b = (b + a) % 65521;
  }
  out.addAll(_be32((b << 16) | a)); // adler32
  return out;
}

final List<int> _crcTable = List<int>.generate(256, (n) {
  var c = n;
  for (var k = 0; k < 8; k++) {
    c = (c & 1) != 0 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
  }
  return c;
});

int _crc32(List<int> data) {
  var c = 0xFFFFFFFF;
  for (final byte in data) {
    c = _crcTable[(c ^ byte) & 0xFF] ^ (c >>> 8);
  }
  return (c ^ 0xFFFFFFFF) & 0xFFFFFFFF;
}
