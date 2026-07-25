import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/glass.dart';
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
import '../../widgets/media_card.dart';
import '../../widgets/network_poster.dart';
import '../../widgets/state_views.dart';
import '../../widgets/tiles.dart';

/// Live TV, in the three panes every serious IPTV client eventually converges
/// on: categories, channels, and what is on.
///
/// Clicking a channel starts it, and starting it raises the player over the top
/// of this screen. That is intended — the player is a mode of the shell, not a
/// place you navigate to (see `app/routes.dart`), so dismissing it drops the
/// user back here with the stream still running.
///
/// **Looking is not tuning.** The third pane follows the channel the cursor (or
/// the keyboard) is on, not the one that is playing — the way a receiver's guide
/// does. Without that, finding out what is on a channel costs a tune: on an
/// account limited to one connection, browsing the list by clicking it is how a
/// viewer knocks their own stream off the air.
class LiveScreen extends ConsumerStatefulWidget {
  const LiveScreen({super.key});

  @override
  ConsumerState<LiveScreen> createState() => _LiveScreenState();
}

class _LiveScreenState extends ConsumerState<LiveScreen> {
  LiveChannel? _previewed;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const _Pane(width: 260, child: _CategoryPane()),
        _Pane(
          width: 360,
          child: _ChannelPane(
            onPreview: (channel) => setState(() => _previewed = channel),
          ),
        ),
        Expanded(child: _NowPlayingPane(previewed: _previewed)),
      ],
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
      decoration: const BoxDecoration(
        border: BorderDirectional(
          end: BorderSide(color: AppColors.borderSubtle),
        ),
      ),
      child: child,
    );
  }
}

class _PaneHeader extends StatelessWidget {
  const _PaneHeader({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsetsDirectional.fromSTEB(
        Nova.space4,
        Nova.space4,
        Nova.space4,
        Nova.space3,
      ),
      child: Text(title, style: AppText.label),
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
            loading: () => const LoadingView(),
            error: (error, _) => ErrorView(
              strings: s,
              error: error,
              onRetry: () => ref.read(catalogRefreshProvider.notifier).state++,
            ),
            data: (list) => ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: Nova.space2),
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

  @override
  Widget build(BuildContext context) {
    final selected = widget.selected;

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: Nova.fast,
          margin: const EdgeInsets.only(bottom: 2),
          padding: const EdgeInsets.all(Nova.space3),
          decoration: BoxDecoration(
            color: selected
                ? AppColors.surface3
                : (_hovered ? AppColors.surface2 : Colors.transparent),
            borderRadius: BorderRadius.circular(Nova.radiusControl),
          ),
          child: Row(
            children: [
              AnimatedContainer(
                duration: Nova.fast,
                width: 3,
                height: selected ? 18 : 0,
                decoration: const BoxDecoration(
                  gradient: AppColors.emberGradient,
                  borderRadius: BorderRadius.all(Radius.circular(2)),
                ),
              ),
              // The indicator keeps its 3 px of width when it is not selected —
              // only its height animates — so the label never shifts sideways
              // as the selection moves down the list.
              const SizedBox(width: Nova.space2),
              Expanded(
                child: Text(
                  widget.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.control.copyWith(
                    color: selected
                        ? AppColors.textPrimary
                        : AppColors.textSecondary,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                  ),
                ),
              ),
              if (widget.count != null && widget.count! > 0) ...[
                const SizedBox(width: Nova.space2),
                Text(
                  Fmt.compact(widget.count!),
                  style: AppText.caption,
                  textDirection: TextDirection.ltr,
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
    final channels = ref.watch(liveStreamsProvider(categoryId));
    final playing = ref.watch(playbackProvider);
    final favorites = ref.watch(favoritesProvider);
    final playlistId = ref.watch(activePlaylistProvider)?.id ?? '';

    final playingId = playing?.kind == MediaKind.live ? playing?.refId : null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsetsDirectional.fromSTEB(
            Nova.space3,
            Nova.space4,
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
                padding: const EdgeInsets.symmetric(horizontal: Nova.space2),
                itemCount: filtered.length,
                itemBuilder: (context, i) {
                  final channel = filtered[i];
                  return _ChannelRow(
                    channel: channel,
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
    required this.playlistId,
    required this.selected,
    required this.isFavorite,
    required this.onPreview,
  });

  final LiveChannel channel;
  final String playlistId;
  final bool selected;
  final bool isFavorite;
  final VoidCallback onPreview;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // The guide is fetched *here*, in the row, rather than in the pane above.
    // A `ListView.builder` only builds the rows the user can see, so only those
    // rows ask the panel for a programme. Hoisting this one line into the list
    // would turn opening a 900-channel category into 900 `get_short_epg` calls.
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
      selected: selected,
      onPreview: onPreview,
      nowTitle: now?.title,
      nowProgress: now?.progress,
      isFavorite: isFavorite,
      onTap: () => ref.read(playbackProvider.notifier).playLive(channel),
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

/// What is on the channel the user is *looking at* — which is not necessarily
/// the one that is playing.
///
/// The previewed channel wins when there is one. That is the receiver behaviour
/// the owner asked for, and on this subscription it is also the safe one: the
/// account allows a single connection, so a viewer who has to tune a channel to
/// find out what is on it knocks their own stream off the air to read the guide.
class _NowPlayingPane extends ConsumerWidget {
  const _NowPlayingPane({this.previewed});

  final LiveChannel? previewed;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final playing = ref.watch(playbackProvider);
    final live = playing != null && playing.kind == MediaKind.live;

    // The Play button needs the channel itself, not just its fields.
    final channel = previewed;

    final subject = resolveNowPlaying(previewed: channel, playing: playing);
    if (subject == null) {
      return EmptyView(icon: Icons.live_tv_rounded, message: s.pickChannel);
    }

    final title = subject.title;
    final logo = subject.logo;
    final streamId = subject.streamId;
    final epgChannelId = subject.epgChannelId;

    // Is the pane looking at the thing that is playing, or at something else?
    // The answer decides the button: uncovering a running stream and starting a
    // new one are not the same action, and offering the wrong one is how a
    // viewer loses the match they were watching.
    final isPlayingThis = live && playing.refId == streamId;

    return Padding(
      padding: const EdgeInsets.all(Nova.space6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          NovaCard(
            radius: Nova.radiusPanel,
            padding: const EdgeInsets.all(Nova.space5),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 96,
                  height: 96,
                  child: NetworkPoster(
                    url: logo,
                    title: title,
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
                      if (isPlayingThis) LiveBadge(label: s.onAir),
                      if (isPlayingThis) const SizedBox(height: Nova.space3),
                      Text(
                        title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: AppText.title,
                      ),
                      const SizedBox(height: Nova.space4),
                      if (isPlayingThis)
                        EmberButton(
                          label: s.watchFullscreen,
                          icon: Icons.fullscreen_rounded,
                          // The stream is already running behind this screen; the
                          // player only has to be uncovered, never reopened.
                          onPressed: () =>
                              ref.read(playerViewProvider.notifier).expand(),
                        )
                      else
                        EmberButton(
                          label: s.play,
                          icon: Icons.play_arrow_rounded,
                          onPressed: channel == null
                              ? null
                              : () => ref
                                    .read(playbackProvider.notifier)
                                    .playLive(channel),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: Nova.space5),
          Expanded(
            child: _Guide(streamId: streamId, epgChannelId: epgChannelId),
          ),
        ],
      ),
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
          padding: EdgeInsets.zero,
          children: [
            if (current != null) ...[
              Text(s.nowPlaying, style: AppText.label),
              const SizedBox(height: Nova.space2),
              Text(current.title, style: AppText.section),
              const SizedBox(height: Nova.space2),
              Text(_range(context, current), style: AppText.timecode),
              const SizedBox(height: Nova.space3),
              ProgressBar(value: current.progress),
              if (current.description != null &&
                  current.description!.trim().isNotEmpty) ...[
                const SizedBox(height: Nova.space3),
                Text(
                  current.description!,
                  maxLines: 4,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.body,
                ),
              ],
              const SizedBox(height: Nova.space5),
            ],
            if (upcoming.isNotEmpty) ...[
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
      padding: const EdgeInsets.only(bottom: Nova.space3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 64,
            child: Text(
              _time(context, entry.start),
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
