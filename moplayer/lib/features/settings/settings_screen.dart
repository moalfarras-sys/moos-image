import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/motion.dart';
import '../../core/theme/nova.dart';
import '../../providers/system_providers.dart';
import '../../widgets/section_header.dart';
import '../../widgets/tiles.dart';
import 'settings_panels.dart';

/// Settings, as a *panel*: the sections down the leading edge, the selected one
/// beside them.
///
/// The old screen was one long scroll of cards, and a long scroll is what you
/// build when you do not want to decide what the sections are. It has two costs
/// the two-column shape does not: the user has to *find* a setting by scrolling
/// past every other one, and every new setting makes the page longer for people
/// who will never touch it. Here the list on the side is a map of the whole app's
/// behaviour, readable in one glance, and each pane is short enough to have no
/// scrollbar at all on most of them.
///
/// The pane the user is looking at is a piece of state and nothing else in the
/// app cares about it, so it is local to this widget rather than a provider.
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  SettingsSection _section = SettingsSection.sources;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        // Below ~900 px the two columns leave the content pane narrower than a
        // switch row wants, so the section list becomes a strip across the top
        // instead. The same eight sections, the same panes — one column.
        final wide = constraints.maxWidth >= 900;

        if (wide) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _Sidebar(selected: _section, onSelect: _select),
              Expanded(child: _Pane(section: _section)),
            ],
          );
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _SectionStrip(selected: _section, onSelect: _select),
            Expanded(child: _Pane(section: _section)),
          ],
        );
      },
    );
  }

  void _select(SettingsSection section) {
    if (section == _section) return;
    setState(() => _section = section);
  }
}

/// The list of sections.
///
/// `BorderDirectional`, not `Border`: in Arabic the sidebar is on the right and
/// a `right:` border would draw the hairline down the wrong edge of it.
class _Sidebar extends ConsumerWidget {
  const _Sidebar({required this.selected, required this.onSelect});

  final SettingsSection selected;
  final ValueChanged<SettingsSection> onSelect;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);

    return Container(
      width: 268,
      decoration: const BoxDecoration(
        border: BorderDirectional(
          end: BorderSide(color: AppColors.borderSubtle),
        ),
      ),
      child: ListView(
        // The dock floats over the foot of every page and the shell hands the
        // screen its height; a list that ignores it hides its own last row.
        padding: EdgeInsetsDirectional.fromSTEB(
          Nova.space3,
          Nova.space6,
          Nova.space3,
          MediaQuery.paddingOf(context).bottom + Nova.space5,
        ),
        children: [
          Padding(
            padding: const EdgeInsetsDirectional.only(
              start: Nova.space2,
              bottom: Nova.space5,
            ),
            child: SectionHeader(title: s.settings, accent: true),
          ),
          for (final section in SettingsSection.values)
            ListRow(
              title: section.title(s),
              selected: section == selected,
              leading: Icon(
                section.icon,
                size: 19,
                color: section == selected
                    ? AppColors.primary
                    : AppColors.textMuted,
              ),
              onTap: () => onSelect(section),
            ),
        ],
      ),
    );
  }
}

/// The narrow-window form of the sidebar: the same sections, as a strip of pills
/// the user scrolls sideways.
class _SectionStrip extends ConsumerWidget {
  const _SectionStrip({required this.selected, required this.onSelect});

  final SettingsSection selected;
  final ValueChanged<SettingsSection> onSelect;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);

    return Container(
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.borderSubtle)),
      ),
      padding: const EdgeInsets.symmetric(vertical: Nova.space4),
      // 36 px is a pill's natural height; a shorter strip would overflow the
      // label out of the bottom of every one of them.
      child: SizedBox(
        height: 38,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: Nova.space5),
          itemCount: SettingsSection.values.length,
          separatorBuilder: (_, _) => const SizedBox(width: Nova.space2),
          itemBuilder: (context, i) {
            final section = SettingsSection.values[i];
            return CategoryPill(
              label: section.title(s),
              selected: section == selected,
              onTap: () => onSelect(section),
            );
          },
        ),
      ),
    );
  }
}

/// The selected section: its title, then its rows.
///
/// The pane crossfades rather than cutting — and under reduced motion the fade
/// collapses to 60 ms rather than to nothing, because content that teleports is
/// worse than content that moves.
class _Pane extends ConsumerWidget {
  const _Pane({required this.section});

  final SettingsSection section;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);

    return AnimatedSwitcher(
      duration: Motion.duration(context, Nova.panel),
      switchInCurve: Ease.enter,
      switchOutCurve: Ease.exit,
      child: SingleChildScrollView(
        key: ValueKey(section),
        padding: EdgeInsetsDirectional.fromSTEB(
          Nova.space6,
          Nova.space6,
          Nova.space6,
          MediaQuery.paddingOf(context).bottom + Nova.space6,
        ),
        child: Align(
          alignment: AlignmentDirectional.topStart,
          child: ConstrainedBox(
            // A settings form stretched across a 1440-pixel window puts its
            // switches a hand's width from the labels they belong to.
            constraints: const BoxConstraints(maxWidth: 760),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SectionHeader(title: section.title(s)),
                const SizedBox(height: Nova.space5),
                SettingsPanel(section: section),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
