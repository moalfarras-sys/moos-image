import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:media_kit_video/media_kit_video.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/motion.dart';
import '../../core/theme/nova.dart';
import '../../core/utils/formatters.dart';
import '../../models/category.dart';
import '../../models/epg_entry.dart';
import '../../models/library_items.dart';
import '../../models/live_channel.dart';
import '../../models/media_kind.dart';
import '../../providers/content_providers.dart';
import '../../providers/core_providers.dart';
import '../../providers/library_providers.dart';
import '../../providers/playback_providers.dart';
import '../../providers/system_providers.dart';
import '../../widgets/buttons.dart';
import '../../widgets/focus_surface.dart';
import '../../widgets/media_card.dart';
import '../../widgets/network_poster.dart';
import '../../widgets/state_views.dart';
import '../../widgets/tiles.dart';
import '../../widgets/calm_spinner.dart';

/// Live TV: categories, channels, and a **stage**.
///
/// The stage is the new idea. A channel picked from the list plays *here*, on
/// the page, beside the list it was picked from — the way a receiver's guide
/// shows the picture in a window — and the viewer decides when to go full
/// screen (click the playing channel again, press Enter on it, or double-click
/// the picture). Browsing stays one click from watching, and watching never
/// takes the list away.
///
/// **Looking is not tuning.** Hovering a channel shows its guide on the stage
/// without opening it. On an account limited to one connection — the owner's
/// is — finding out what is on a channel by tuning it knocks the channel you
/// were watching off the air.
class LiveScreen extends ConsumerStatefulWidget {
  const LiveScreen({super.key});

  @override
  ConsumerState<LiveScreen> createState() => _LiveScreenState();
}

class _LiveScreenState extends ConsumerState<LiveScreen> {
  LiveChannel? _previewed;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 1180;
        return Row(
          children: [
            _Pane(width: wide ? 250 : 210, child: const _CategoryPane()),
            _Pane(
              width: wide ? 400 : 340,
              child: _ChannelPane(
                onPreview: (channel) => setState(() => _previewed = channel),
              ),
            ),
            Expanded(child: _Stage(previewed: _previewed)),
          ],
        );
      },
    );
  }
}

/// A pane and the hairline that separates it from the next one.
///
/// `BorderDirectional`, not `Border`: in Arabic the panes run the other way and
/// a `right:` border would draw the line down the wrong edge of each one.
class _Pane extends StatelessWidget {
  const _Pane({required this.width, required this.child});

  final double width;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      decoration: BoxDecoration(
        color: AppColors.surface1.withValues(alpha: 0.55),
        border: const BorderDirectional(
          end: BorderSide(color: AppColors.borderSubtle),
        ),
      ),
      child: child,
    );
  }
}

class _PaneHeader extends StatelessWidget {
  const _PaneHeader({required this.title, this.trailing});

  final String title;
  final String? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsetsDirectional.fromSTEB(
        Nova.space4,
        Nova.space5,
        Nova.space4,
        Nova.space3,
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppText.section,
            ),
          ),
          if (trailing != null)
            Text(
              trailing!,
              style: AppText.caption,
              textDirection: TextDirection.ltr,
            ),
        ],
      ),
    );
  }
}

class _CategoryPane extends ConsumerWidget {
  const _CategoryPane();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final categories = ref.watch(liveCategoriesProvider);
    final selected = ref.watch(selectedLiveCategoryProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _PaneHeader(title: s.categories),
        Expanded(
          child: categories.when(
            skipLoadingOnReload: true,
            loading: () => const LoadingView(),
            error: (error, _) => ErrorView(
              strings: s,
              error: error,
              onRetry: () => ref.read(catalogRefreshProvider.notifier).state++,
            ),
            data: (list) => ListView.builder(
              padding: EdgeInsets.fromLTRB(
                Nova.space2,
                0,
                Nova.space2,
                MediaQuery.paddingOf(context).bottom + Nova.space4,
              ),
              itemCount: list.length,
              itemBuilder: (context, i) {
                final category = list[i];
                return _CategoryRow(
                  // The "All" row is synthesised in `liveCategoriesProvider`
                  // with a hard-coded English name, because a provider has no
                  // business reading the string table. It is labelled here.
                  label: category.id == Category.allId ? s.all : category.name,
                  count: category.count,
                  selected: category.id == selected,
                  onTap: () =>
                      ref.read(selectedLiveCategoryProvider.notifier).state =
                          category.id,
                );
              },
            ),
          ),
        ),
      ],
    );
  }
}

class _CategoryRow extends StatefulWidget {
  const _CategoryRow({
    required this.label,
    required this.selected,
    required this.onTap,
    this.count,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final int? count;

  @override
  State<_CategoryRow> createState() => _CategoryRowState();
}

class _CategoryRowState extends State<_CategoryRow> {
  bool _hovered = false;
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final selected = widget.selected;
    final accent = AppColors.primary;

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: FocusSurface(
        onTap: widget.onTap,
        onFocusChange: (focused) => setState(() => _focused = focused),
        radius: Nova.radiusControl,
        scale: 1,
        bloom: false,
        selected: selected,
        semanticLabel: widget.label,
        child: AnimatedContainer(
          duration: Motion.duration(context, Nova.fast),
          margin: const EdgeInsets.only(bottom: 2),
          padding: const EdgeInsets.symmetric(
            horizontal: Nova.space3,
            vertical: 11,
          ),
          decoration: BoxDecoration(
            color: selected
                ? accent.withValues(alpha: 0.14)
                : (_hovered || _focused
                      ? AppColors.surface3
                      : Colors.transparent),
            borderRadius: BorderRadius.circular(Nova.radiusControl),
          ),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  widget.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.control.copyWith(
                    fontSize: 14,
                    color: selected
                        ? AppColors.textPrimary
                        : AppColors.textSecondary,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                  ),
                ),
              ),
              if (widget.count != null && widget.count! > 0) ...[
                const SizedBox(width: Nova.space2),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 7,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: selected
                        ? accent.withValues(alpha: 0.22)
                        : AppColors.surface2,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    Fmt.compact(widget.count!),
                    style: AppText.caption.copyWith(
                      fontSize: 11,
                      color: selected
                          ? AppColors.primaryBright
                          : AppColors.textMuted,
                    ),
                    textDirection: TextDirection.ltr,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ChannelPane extends ConsumerStatefulWidget {
  const _ChannelPane({required this.onPreview});

  final ValueChanged<LiveChannel> onPreview;

  @override
  ConsumerState<_ChannelPane> createState() => _ChannelPaneState();
}

class _ChannelPaneState extends ConsumerState<_ChannelPane> {
  final TextEditingController _search = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final categoryId = ref.watch(selectedLiveCategoryProvider);
    final categories = ref.watch(liveCategoriesProvider).valueOrNull;
    final channels = ref.watch(liveStreamsProvider(categoryId));
    final playing = ref.watch(playbackProvider);
    final favorites = ref.watch(favoritesProvider);
    final playlistId = ref.watch(activePlaylistProvider)?.id ?? '';

    final playingId = playing?.kind == MediaKind.live ? playing?.refId : null;
    final categoryName = categoryId == Category.allId
        ? s.channels
        : (categories
                  ?.where((c) => c.id == categoryId)
                  .map((c) => c.name)
                  .firstOrNull ??
              s.channels);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _PaneHeader(
          title: categoryName,
          trailing: channels.valueOrNull == null
              ? null
              : Fmt.compact(channels.valueOrNull!.length),
        ),
        Padding(
          padding: const EdgeInsetsDirectional.fromSTEB(
            Nova.space3,
            0,
            Nova.space3,
            Nova.space3,
          ),
          child: TextField(
            controller: _search,
            style: AppText.control,
            decoration: InputDecoration(
              hintText: s.searchChannels,
              isDense: true,
              prefixIcon: const Icon(Icons.search_rounded, size: 18),
              suffixIcon: _query.isEmpty
                  ? null
                  : IconPill(
                      icon: Icons.close_rounded,
                      size: 28,
                      onPressed: () {
                        _search.clear();
                        setState(() => _query = '');
                      },
                    ),
            ),
            // Filtering is local. The panel is not asked again: it already
            // handed over the whole category, and a request per keystroke is
            // how a session gets rate-limited.
            onChanged: (value) => setState(() => _query = value.trim()),
          ),
        ),
        Expanded(
          child: channels.when(
            skipLoadingOnReload: true,
            loading: () => const LoadingView(),
            error: (error, _) => ErrorView(
              strings: s,
              error: error,
              onRetry: () => ref.read(catalogRefreshProvider.notifier).state++,
            ),
            data: (list) {
              final filtered = _filter(list, _query);
              if (filtered.isEmpty) {
                return EmptyView(
                  icon: Icons.tv_off_rounded,
                  message: _query.isEmpty ? s.empty : s.noResults(_query),
                );
              }

              return ListView.builder(
                padding: EdgeInsets.fromLTRB(
                  Nova.space2,
                  0,
                  Nova.space2,
                  MediaQuery.paddingOf(context).bottom + Nova.space4,
                ),
                itemExtent: 76,
                itemCount: filtered.length,
                itemBuilder: (context, i) {
                  final channel = filtered[i];
                  return _ChannelRow(
                    channel: channel,
                    channels: filtered,
                    playlistId: playlistId,
                    selected: channel.streamId == playingId,
                    isFavorite: favorites.any(
                      (f) =>
                          f.kind == MediaKind.live &&
                          f.refId == channel.streamId,
                    ),
                    onPreview: () => widget.onPreview(channel),
                  );
                },
              );
            },
          ),
        ),
      ],
    );
  }
}

List<LiveChannel> _filter(List<LiveChannel> all, String query) {
  if (query.isEmpty) return all;
  final needle = query.toLowerCase();
  return all.where((c) => c.name.toLowerCase().contains(needle)).toList();
}

class _ChannelRow extends ConsumerWidget {
  const _ChannelRow({
    required this.channel,
    required this.channels,
    required this.playlistId,
    required this.selected,
    required this.isFavorite,
    required this.onPreview,
  });

  final LiveChannel channel;
  final List<LiveChannel> channels;
  final String playlistId;
  final bool selected;
  final bool isFavorite;
  final VoidCallback onPreview;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // The guide is read *here*, in the row, rather than in the pane above: a
    // `ListView.builder` only builds the rows on screen, so only those rows
    // look up a programme.
    final now = _liveNow(
      ref
          .watch(
            epgProvider((
              streamId: channel.streamId,
              epgChannelId: channel.epgChannelId,
            )),
          )
          .valueOrNull,
    );

    return ChannelTile(
      name: channel.name,
      logoUrl: channel.logo,
      number: channel.number,
      selected: selected,
      onPreview: onPreview,
      nowTitle: now?.title,
      nowProgress: now?.progress,
      isFavorite: isFavorite,
      onTap: () {
        final playback = ref.read(playbackProvider.notifier);
        if (selected) {
          // Already on the stage: a second press is "show me it big".
          ref.read(playerViewProvider.notifier).expand();
        } else {
          playback.playLive(channel, channels: channels, expand: false);
        }
      },
      onToggleFavorite: () => ref
          .read(libraryActionsProvider)
          .toggleFavorite(
            FavoriteItem(
              playlistId: playlistId,
              kind: MediaKind.live,
              refId: channel.streamId,
              title: channel.name,
              imageUrl: channel.logo,
              payload: channel.toPayload(),
            ),
          ),
    );
  }
}

/// The four fields the pane draws, taken from ONE source.
class NowPlayingSubject {
  const NowPlayingSubject({
    required this.title,
    required this.streamId,
    this.logo,
    this.epgChannelId,
  });

  final String title;
  final String streamId;
  final String? logo;
  final String? epgChannelId;
}

/// Which channel the pane is about: the previewed one when there is one, else
/// whatever is playing live. Null means there is nothing to show.
///
/// This is a function, not four `??` expressions inline, because the inline form
/// shipped a crash. `previewed?.logo ?? playing!.imageUrl` reads as "fall back to
/// the playing stream if there is no previewed channel" — but `??` falls through
/// when the *field* is null, not only when the channel is. `logo` and
/// `epgChannelId` are optional on LiveChannel, thousands of the 12,653 channels
/// on this panel carry neither, and previewing one of them while nothing was
/// playing dereferenced a null `playing` — on every frame, until the app
/// segfaulted (2026-07-13, in the shipped image).
///
/// Fields never mix: a previewed channel with no logo shows no logo, rather than
/// borrowing the poster of an unrelated stream.
NowPlayingSubject? resolveNowPlaying({
  LiveChannel? previewed,
  NowPlaying? playing,
}) {
  final live = playing != null && playing.kind == MediaKind.live;

  if (previewed != null) {
    return NowPlayingSubject(
      title: previewed.name,
      streamId: previewed.streamId,
      logo: previewed.logo,
      epgChannelId: previewed.epgChannelId,
    );
  }
  if (!live) return null;

  return NowPlayingSubject(
    title: playing.media.title,
    streamId: playing.refId,
    logo: playing.imageUrl,
    epgChannelId: playing.payload['epgChannelId'] as String?,
  );
}

/// The right-hand side: the picture, the channel, and its guide.
class _Stage extends ConsumerWidget {
  const _Stage({this.previewed});

  final LiveChannel? previewed;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final playing = ref.watch(playbackProvider);
    final live = playing != null && playing.kind == MediaKind.live;

    // The guide follows the pointer; the picture follows what is playing.
    final subject = resolveNowPlaying(previewed: previewed, playing: playing);
    final isPlayingSubject = live && playing.refId == subject?.streamId;

    return Padding(
      padding: EdgeInsets.fromLTRB(
        Nova.space6,
        Nova.space5,
        Nova.space6,
        MediaQuery.paddingOf(context).bottom,
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final screenHeight = (constraints.maxWidth * 9 / 16).clamp(
            180.0,
            constraints.maxHeight * 0.58,
          );
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SizedBox(
                height: screenHeight,
                child: live
                    ? const _StageScreen()
                    : _StagePlate(channel: previewed),
              ),
              const SizedBox(height: Nova.space5),
              if (subject == null)
                Expanded(
                  child: EmptyView(
                    icon: Icons.live_tv_rounded,
                    message: s.pickChannel,
                  ),
                )
              else ...[
                _ChannelHeading(
                  subject: subject,
                  playingThis: isPlayingSubject,
                  channel: previewed,
                ),
                const SizedBox(height: Nova.space4),
                Expanded(
                  child: _Guide(
                    streamId: subject.streamId,
                    epgChannelId: subject.epgChannelId,
                  ),
                ),
              ],
            ],
          );
        },
      ),
    );
  }
}

/// The live picture on the stage, with its controls on hover.
///
/// It mounts the one shared `VideoController` — the same texture the full
/// player and the mini card use — so moving between them never reopens the
/// stream. It steps aside (draws a plate) while the full player is up, so the
/// texture is only ever on screen once.
class _StageScreen extends ConsumerStatefulWidget {
  const _StageScreen();

  @override
  ConsumerState<_StageScreen> createState() => _StageScreenState();
}

class _StageScreenState extends ConsumerState<_StageScreen> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final now = ref.watch(playbackProvider);
    final view = ref.watch(playerViewProvider);
    final player = ref.watch(playerServiceProvider);
    final issue = ref.watch(playbackIssueProvider);
    final playback = ref.read(playbackProvider.notifier);
    if (now == null) return const SizedBox.shrink();

    void expand() => ref.read(playerViewProvider.notifier).expand();

    return MouseRegion(
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onDoubleTap: expand,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(Nova.radiusPanel),
          child: Stack(
            fit: StackFit.expand,
            children: [
              const ColoredBox(color: Colors.black),
              if (view != PlayerView.expanded)
                Video(
                  controller: player.controller,
                  controls: NoVideoControls,
                  fit: BoxFit.contain,
                  fill: Colors.black,
                ),
              StreamBuilder<bool>(
                stream: player.bufferingStream,
                initialData: player.isBuffering,
                builder: (context, snapshot) {
                  final failed = issue?.kind == PlaybackIssueKind.failed;
                  if (!failed && snapshot.data != true) {
                    return const SizedBox.shrink();
                  }
                  return Center(
                    child: failed
                        ? Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(
                                Icons.signal_wifi_bad_rounded,
                                color: Colors.white70,
                                size: 36,
                              ),
                              const SizedBox(height: Nova.space3),
                              Text(
                                s.playbackFailed,
                                style: AppText.control.copyWith(
                                  color: Colors.white,
                                ),
                              ),
                              const SizedBox(height: Nova.space3),
                              GhostButton(
                                label: s.retry,
                                icon: Icons.refresh_rounded,
                                onPressed: () => playback.reconnect(),
                              ),
                            ],
                          )
                        : const SizedBox(
                            width: 34,
                            height: 34,
                            child: CalmSpinner(strokeWidth: 3),
                          ),
                  );
                },
              ),
              // The controls. Shown instantly on hover, not faded: a fade is
              // an offscreen layer the size of the stage on this renderer.
              if (_hovered)
                PositionedDirectional(
                  start: 0,
                  end: 0,
                  bottom: 0,
                  child: Container(
                    padding: const EdgeInsets.all(Nova.space3),
                    color: const Color(0xB3000000),
                    child: Row(
                      children: [
                        LiveBadge(label: s.onAir),
                        const SizedBox(width: Nova.space3),
                        Expanded(
                          child: Text(
                            now.media.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppText.control.copyWith(
                              color: Colors.white,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        IconPill(
                          icon: Icons.skip_previous_rounded,
                          tooltip: s.previousChannel,
                          size: 38,
                          onPressed: now.hasPrevious ? playback.previous : null,
                        ),
                        StreamBuilder<bool>(
                          stream: player.playingStream,
                          initialData: player.isPlaying,
                          builder: (context, snapshot) => IconPill(
                            icon: snapshot.data == true
                                ? Icons.pause_rounded
                                : Icons.play_arrow_rounded,
                            tooltip: snapshot.data == true ? s.pause : s.play,
                            size: 42,
                            filled: true,
                            onPressed: player.playOrPause,
                          ),
                        ),
                        IconPill(
                          icon: Icons.skip_next_rounded,
                          tooltip: s.nextChannel,
                          size: 38,
                          onPressed: now.hasNext ? playback.next : null,
                        ),
                        const SizedBox(width: Nova.space2),
                        IconPill(
                          icon: Icons.fullscreen_rounded,
                          tooltip: s.fullscreen,
                          size: 38,
                          onPressed: expand,
                        ),
                        IconPill(
                          icon: Icons.stop_rounded,
                          tooltip: s.stop,
                          size: 38,
                          onPressed: playback.stop,
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The stage before anything plays: the hovered channel's mark, and the way in.
class _StagePlate extends ConsumerWidget {
  const _StagePlate({this.channel});

  final LiveChannel? channel;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final pick = channel;
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface1,
        borderRadius: BorderRadius.circular(Nova.radiusPanel),
        border: Border.all(color: AppColors.borderSubtle),
      ),
      child: Center(
        child: pick == null
            ? Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.live_tv_rounded,
                    size: 56,
                    color: AppColors.primary.withValues(alpha: 0.7),
                  ),
                  const SizedBox(height: Nova.space4),
                  Text(
                    s.pickChannel,
                    textAlign: TextAlign.center,
                    style: AppText.subtitle,
                  ),
                ],
              )
            : Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: 180,
                    height: 110,
                    child: NetworkPoster(
                      url: pick.logo,
                      title: pick.name,
                      logoMode: true,
                      radius: Nova.radiusCard,
                      background: AppColors.surface2,
                    ),
                  ),
                  const SizedBox(height: Nova.space5),
                  EmberButton(
                    label: s.play,
                    icon: Icons.play_arrow_rounded,
                    onPressed: () => ref
                        .read(playbackProvider.notifier)
                        .playLive(pick, expand: false),
                  ),
                ],
              ),
      ),
    );
  }
}

class _ChannelHeading extends ConsumerWidget {
  const _ChannelHeading({
    required this.subject,
    required this.playingThis,
    this.channel,
  });

  final NowPlayingSubject subject;
  final bool playingThis;
  final LiveChannel? channel;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final pick = channel;
    return Row(
      children: [
        SizedBox(
          width: 64,
          height: 64,
          child: NetworkPoster(
            url: subject.logo,
            title: subject.title,
            logoMode: true,
            radius: Nova.radiusCard,
          ),
        ),
        const SizedBox(width: Nova.space4),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              if (playingThis) ...[
                LiveBadge(label: s.onAir),
                const SizedBox(height: Nova.space2),
              ],
              Text(
                subject.title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppText.title,
              ),
            ],
          ),
        ),
        if (playingThis)
          GhostButton(
            label: s.watchFullscreen,
            icon: Icons.fullscreen_rounded,
            // The stream is already running on the stage; the player only has
            // to be uncovered, never reopened.
            onPressed: () => ref.read(playerViewProvider.notifier).expand(),
          )
        else if (pick != null)
          EmberButton(
            label: s.play,
            icon: Icons.play_arrow_rounded,
            onPressed: () => ref
                .read(playbackProvider.notifier)
                .playLive(pick, expand: false),
          ),
      ],
    );
  }
}

class _Guide extends ConsumerWidget {
  const _Guide({required this.streamId, this.epgChannelId});

  final String streamId;
  final String? epgChannelId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final epg = ref.watch(
      epgProvider((streamId: streamId, epgChannelId: epgChannelId)),
    );

    // A guide that fails to load is not an error worth a red icon and a retry
    // button: most IPTV channels simply carry no EPG at all, and the two cases
    // are indistinguishable from here. Both say the same quiet thing.
    final nothing = EmptyView(icon: Icons.event_busy_rounded, message: s.noEpg);

    return epg.when(
      loading: () => const LoadingView(),
      error: (_, _) => nothing,
      data: (entries) {
        if (entries.isEmpty) return nothing;

        final sorted = [...entries]..sort((a, b) => a.start.compareTo(b.start));
        final current = _liveNow(sorted);
        final now = DateTime.now();
        final upcoming = sorted
            .where((e) => e.start.isAfter(now))
            .take(8)
            .toList();

        return ListView(
          padding: EdgeInsets.only(
            bottom: MediaQuery.paddingOf(context).bottom + Nova.space4,
          ),
          children: [
            if (current != null)
              Container(
                padding: const EdgeInsets.all(Nova.space4),
                decoration: BoxDecoration(
                  color: AppColors.surface2,
                  borderRadius: BorderRadius.circular(Nova.radiusCard),
                  border: Border.all(color: AppColors.borderSubtle),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          s.nowPlaying,
                          style: AppText.label.copyWith(
                            color: AppColors.primaryBright,
                          ),
                        ),
                        const Spacer(),
                        Text(
                          _range(context, current),
                          // Times read left to right in every language.
                          textDirection: TextDirection.ltr,
                          style: AppText.timecode.copyWith(
                            color: AppColors.textMuted,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: Nova.space2),
                    Text(current.title, style: AppText.section),
                    const SizedBox(height: Nova.space3),
                    ProgressBar(
                      value: current.progress,
                      track: AppColors.surface3,
                    ),
                    if (current.description != null &&
                        current.description!.trim().isNotEmpty) ...[
                      const SizedBox(height: Nova.space3),
                      Text(
                        current.description!,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                        style: AppText.body,
                      ),
                    ],
                  ],
                ),
              ),
            if (upcoming.isNotEmpty) ...[
              const SizedBox(height: Nova.space5),
              Text(s.upNext, style: AppText.label),
              const SizedBox(height: Nova.space3),
              for (final entry in upcoming) _GuideRow(entry: entry),
            ],
          ],
        );
      },
    );
  }
}

class _GuideRow extends StatelessWidget {
  const _GuideRow({required this.entry});

  final EpgEntry entry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: Nova.space2),
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: Nova.space3,
          vertical: Nova.space3,
        ),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(Nova.radiusControl),
          border: Border.all(color: AppColors.borderSubtle),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 72,
              child: Text(
                _time(context, entry.start),
                textDirection: TextDirection.ltr,
                style: AppText.timecode.copyWith(color: AppColors.textMuted),
              ),
            ),
            const SizedBox(width: Nova.space3),
            Expanded(
              child: Text(
                entry.title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: AppText.body.copyWith(color: AppColors.textSecondary),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

EpgEntry? _liveNow(List<EpgEntry>? entries) {
  if (entries == null) return null;
  for (final entry in entries) {
    if (entry.isLiveNow) return entry;
  }
  return null;
}

/// Clock times come from [MaterialLocalizations], not from `intl`'s
/// `DateFormat`: the latter throws for `ar` unless `initializeDateFormatting`
/// has been called, and the app never calls it. This route is already loaded —
/// the delegates are installed for the Arabic UI — and it honours the locale's
/// own 12/24-hour convention for free.
String _time(BuildContext context, DateTime at) {
  return TimeOfDay.fromDateTime(at).format(context);
}

String _range(BuildContext context, EpgEntry entry) {
  return '${_time(context, entry.start)} – ${_time(context, entry.end)}';
}
