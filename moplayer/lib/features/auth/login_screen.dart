import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../app/routes.dart';
import '../../core/error/result.dart';
import '../../core/l10n/strings.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/glass.dart';
import '../../core/theme/nova.dart';
import '../../models/playlist_config.dart';
import '../../providers/core_providers.dart';
import '../../providers/library_providers.dart';
import '../../providers/system_providers.dart';
import '../../services/activation/activation_service.dart';
import '../../services/source/source_link.dart';
import '../../widgets/app_logo.dart';
import '../../widgets/backdrop.dart';
import '../../widgets/buttons.dart';
import '../../widgets/state_views.dart';

enum _Method { xtream, m3u, activation }

/// The one screen that stands between a fresh install and a picture.
///
/// It is also how a second source is added (`?add=1` from Settings), which is
/// why it has to work when there is already an active playlist — hence
/// [isAdditional], which turns the "welcome" into an "add" and gives the user a
/// way back out.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key, this.isAdditional = false});

  final bool isAdditional;

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final ActivationService _activation = ActivationService();

  final TextEditingController _serverCtrl = TextEditingController();
  final TextEditingController _userCtrl = TextEditingController();
  final TextEditingController _passCtrl = TextEditingController();
  final TextEditingController _nameCtrl = TextEditingController();
  final TextEditingController _urlCtrl = TextEditingController();

  _Method _method = _Method.xtream;
  bool _busy = false;
  String? _error;
  String? _status;

  /// The status line is a wait, not a result — it gets a spinner, not a tick.
  bool _pending = false;

  ActivationSession? _session;
  Timer? _timer;
  bool _polling = false;

  @override
  void dispose() {
    _timer?.cancel();
    _activation.close();
    _serverCtrl.dispose();
    _userCtrl.dispose();
    _passCtrl.dispose();
    _nameCtrl.dispose();
    _urlCtrl.dispose();
    super.dispose();
  }

  S get _s => ref.read(stringsProvider);

  void _selectMethod(_Method method) {
    if (_method == method) return;
    setState(() {
      _method = method;
      _error = null;
      _status = null;
      _pending = false;
    });
    if (method == _Method.activation && _session == null && !_busy) {
      unawaited(_createSession());
    }
  }

  String _newId() => 'pl_${DateTime.now().microsecondsSinceEpoch}';

  /// The shared tail of all three flows: persist, pull the user's library down,
  /// and get out of the way.
  Future<void> _activate(PlaylistConfig config) async {
    await ref.read(activePlaylistProvider.notifier).activate(config);
    await ref.read(libraryActionsProvider).syncFromCloud();
    if (!mounted) return;
    // Settings pushed this screen to add a second source: it is still on the
    // stack underneath, and it is where the user was going back to anyway.
    if (widget.isAdditional) {
      context.pop();
    } else {
      context.go(Routes.home);
    }
  }

  void _fail(Object failure) {
    if (!mounted) return;
    setState(() {
      _busy = false;
      _pending = false;
      _status = null;
      _error = failureMessage(_s, failure);
    });
  }

  // ── Xtream ─────────────────────────────────────────────────────────────────

  Future<void> _submitXtream() async {
    final username = _userCtrl.text.trim();
    final config = PlaylistConfig(
      id: _newId(),
      type: PlaylistType.xtream,
      name: username,
      serverUrl: _serverCtrl.text.trim(),
      username: username,
      password: _passCtrl.text,
    );

    setState(() {
      _busy = true;
      _error = null;
      _status = null;
    });

    final result = await ref.read(authRepositoryProvider).testXtream(config);
    if (!mounted) return;

    if (result is Err<XtreamAccountInfo>) {
      _fail(result.failure);
      return;
    }
    setState(() => _status = _s.connected);
    await _activate(config);
  }

  // ── M3U ────────────────────────────────────────────────────────────────────

  Future<void> _submitM3u() async {
    final link = _urlCtrl.text.trim();
    final name = _nameCtrl.text.trim();

    setState(() {
      _busy = true;
      _error = null;
      _status = null;
    });

    // The link is read for what it *is*, not for the field it was typed into.
    //
    // A subscription is sold as one URL, and it is nearly always
    // `…/get.php?username=U&password=P&type=m3u_plus`. That URL works in this
    // field — and that is the trap it is worth writing code to avoid. Taken as a
    // playlist it yields live channels and nothing else: no films, no series, no
    // guide. Taken as what it is — a panel and an account — it opens the whole
    // API. On the maintainer's own subscription that is the difference between
    // 12,653 channels and 12,653 channels *plus* 20,187 films and 10,550 series,
    // from the same string of text.
    final detected = SourceLink.parse(link, id: _newId());

    if (detected != null && detected.isXtream) {
      final upgraded = name.isEmpty
          ? detected
          : detected.copyWith(name: name);

      final probe = await ref
          .read(authRepositoryProvider)
          .testXtream(upgraded);
      if (!mounted) return;

      if (probe is Ok<XtreamAccountInfo>) {
        setState(() => _status = _s.connected);
        await _activate(upgraded);
        return;
      }
      // The link carried credentials and the panel rejected them. Falling back
      // to importing it as a playlist would hide a wrong password behind a
      // half-working source, so the failure is reported as what it is.
      _fail((probe as Err<XtreamAccountInfo>).failure);
      return;
    }

    final config =
        detected ??
        PlaylistConfig(
          id: _newId(),
          type: PlaylistType.m3u,
          name: name.isEmpty ? _s.m3u : name,
          m3uUrl: link,
        );

    final result = await ref
        .read(authRepositoryProvider)
        .testM3u(name.isEmpty ? config : config.copyWith(name: name));
    if (!mounted) return;

    if (result is Err<int>) {
      _fail(result.failure);
      return;
    }
    setState(() => _status = _s.channelsFound((result as Ok<int>).value));
    await _activate(name.isEmpty ? config : config.copyWith(name: name));
  }

  // ── Activation ─────────────────────────────────────────────────────────────

  Future<void> _createSession() async {
    _timer?.cancel();
    setState(() {
      _busy = true;
      _error = null;
      _status = null;
      _pending = false;
      _session = null;
    });

    try {
      final session = await _activation.create(ref.read(deviceServiceProvider));
      if (!mounted) return;
      setState(() {
        _busy = false;
        _session = session;
        _status = _s.waitingForActivation;
        _pending = true;
      });
      _timer = Timer.periodic(
        const Duration(seconds: 4),
        (_) => unawaited(_poll()),
      );
    } on Object catch (error) {
      _fail(error);
    }
  }

  Future<void> _poll() async {
    final session = _session;
    if (session == null || _polling || !mounted) return;

    // An expired code is not an error the user should have to read about — it
    // is a code that needs replacing, so replace it.
    if (DateTime.now().isAfter(session.expiresAt)) {
      _timer?.cancel();
      await _createSession();
      return;
    }

    _polling = true;
    try {
      final status = await _activation.status(session.code);
      if (!mounted || !status.isActivated) return;

      final deviceId =
          status.publicDeviceId ?? ref.read(deviceServiceProvider).deviceId;
      final source = await _activation.pullSource(
        publicDeviceId: deviceId,
        token: session.sourcePullToken,
      );
      if (!mounted) return;

      // Approved, but nobody has attached a source to the account yet. Say so
      // and leave the timer running — the next tick will find it the moment one
      // is pushed, which is what `sourcePending` means.
      if (!source.hasSource) {
        setState(() => _status = _s.activationNoSource);
        return;
      }

      _timer?.cancel();
      setState(() => _busy = true);

      await _activation.ackSource(
        publicDeviceId: deviceId,
        token: session.sourcePullToken,
        sourceId: source.sourceId!,
      );
      await _activate(source.playlist!);
    } on Object catch (error) {
      _fail(error);
    } finally {
      _polling = false;
    }
  }

  // ── Build ──────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);

    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: SceneBackdrop(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(
              horizontal: Nova.space5,
              vertical: Nova.space6,
            ),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 560),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Center(
                    child: AppLogo(
                      size: 88,
                      showWordmark: true,
                      showTagline: true,
                    ),
                  ),
                  const SizedBox(height: Nova.space6),
                  GlassPanel(
                    padding: const EdgeInsets.all(Nova.space5),
                    radius: Nova.radiusOverlay,
                    glow: true,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          widget.isAdditional ? s.addSource : s.welcomeTitle,
                          style: AppText.headline,
                        ),
                        if (!widget.isAdditional) ...[
                          const SizedBox(height: Nova.space1),
                          Text(s.welcomeBody, style: AppText.body),
                        ],
                        const SizedBox(height: Nova.space5),
                        _MethodTabs(
                          method: _method,
                          strings: s,
                          onChanged: _selectMethod,
                        ),
                        const SizedBox(height: Nova.space3),
                        Text(_methodHint(s), style: AppText.caption),
                        const SizedBox(height: Nova.space5),
                        _form(s),
                        if (_status != null) ...[
                          const SizedBox(height: Nova.space4),
                          _Message(text: _status!, pending: _pending),
                        ],
                        if (_error != null) ...[
                          const SizedBox(height: Nova.space4),
                          _Message(text: _error!, danger: true),
                        ],
                        if (widget.isAdditional) ...[
                          const SizedBox(height: Nova.space4),
                          Align(
                            alignment: AlignmentDirectional.centerStart,
                            child: GhostButton(
                              label: s.cancel,
                              icon: Icons.close_rounded,
                              onPressed: () => context.pop(),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  String _methodHint(S s) => switch (_method) {
    _Method.xtream => s.xtreamHint,
    _Method.m3u => s.m3uHint,
    _Method.activation => s.activationHint,
  };

  Widget _form(S s) => switch (_method) {
    _Method.xtream => _xtreamForm(s),
    _Method.m3u => _m3uForm(s),
    _Method.activation => _activationForm(s),
  };

  Widget _xtreamForm(S s) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _Field(
          controller: _serverCtrl,
          label: s.serverUrl,
          icon: Icons.dns_rounded,
          latin: true,
        ),
        const SizedBox(height: Nova.space4),
        _Field(
          controller: _userCtrl,
          label: s.username,
          icon: Icons.person_outline_rounded,
          latin: true,
        ),
        const SizedBox(height: Nova.space4),
        _Field(
          controller: _passCtrl,
          label: s.password,
          icon: Icons.lock_outline_rounded,
          latin: true,
          obscure: true,
          onSubmitted: (_) => _submitXtream(),
        ),
        const SizedBox(height: Nova.space5),
        EmberButton(
          label: s.connect,
          icon: Icons.login_rounded,
          expand: true,
          busy: _busy,
          onPressed: _submitXtream,
        ),
      ],
    );
  }

  Widget _m3uForm(S s) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _Field(
          controller: _nameCtrl,
          label: s.playlistName,
          icon: Icons.label_outline_rounded,
        ),
        const SizedBox(height: Nova.space4),
        _Field(
          controller: _urlCtrl,
          label: s.playlistUrl,
          icon: Icons.link_rounded,
          latin: true,
          onSubmitted: (_) => _submitM3u(),
        ),
        const SizedBox(height: Nova.space5),
        EmberButton(
          label: s.connect,
          icon: Icons.playlist_add_check_rounded,
          expand: true,
          busy: _busy,
          onPressed: _submitM3u,
        ),
      ],
    );
  }

  Widget _activationForm(S s) {
    final session = _session;

    if (session == null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          EmberButton(
            label: s.activation,
            icon: Icons.qr_code_2_rounded,
            expand: true,
            busy: _busy,
            onPressed: () => unawaited(_createSession()),
          ),
        ],
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Center(
          child: Container(
            padding: const EdgeInsets.all(Nova.space3),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(Nova.radiusCard),
              boxShadow: [
                BoxShadow(
                  color: AppColors.primary.withValues(alpha: 0.22),
                  blurRadius: 30,
                  spreadRadius: -10,
                ),
              ],
            ),
            child: QrImageView(
              data: session.activationUrl.toString(),
              size: 180,
              backgroundColor: Colors.white,
            ),
          ),
        ),
        const SizedBox(height: Nova.space5),
        Center(
          child: SelectableText(
            session.code,
            style: AppText.display.copyWith(letterSpacing: 6),
            textDirection: TextDirection.ltr,
          ),
        ),
        const SizedBox(height: Nova.space3),
        Text(
          s.activationScanHint,
          style: AppText.body,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: Nova.space4),
        Center(
          child: GhostButton(
            label: s.refresh,
            icon: Icons.refresh_rounded,
            onPressed: _busy ? null : () => unawaited(_createSession()),
          ),
        ),
      ],
    );
  }
}

class _MethodTabs extends StatelessWidget {
  const _MethodTabs({
    required this.method,
    required this.strings,
    required this.onChanged,
  });

  final _Method method;
  final S strings;
  final ValueChanged<_Method> onChanged;

  @override
  Widget build(BuildContext context) {
    final tabs = <(_Method, String, IconData)>[
      (_Method.xtream, strings.xtream, Icons.dns_rounded),
      (_Method.m3u, strings.m3u, Icons.link_rounded),
      (_Method.activation, strings.activation, Icons.qr_code_rounded),
    ];

    return Container(
      padding: const EdgeInsets.all(Nova.space1),
      decoration: BoxDecoration(
        color: AppColors.surface2.withValues(alpha: 0.8),
        borderRadius: BorderRadius.circular(Nova.radiusControl + 2),
        border: Border.all(color: AppColors.borderSubtle),
      ),
      child: Row(
        children: [
          for (final (value, label, icon) in tabs)
            Expanded(
              child: _Tab(
                label: label,
                icon: icon,
                selected: value == method,
                onTap: () => onChanged(value),
              ),
            ),
        ],
      ),
    );
  }
}

class _Tab extends StatefulWidget {
  const _Tab({
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  State<_Tab> createState() => _TabState();
}

class _TabState extends State<_Tab> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final selected = widget.selected;
    final color = selected
        ? Colors.white
        : (_hovered ? AppColors.textPrimary : AppColors.textSecondary);

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        behavior: HitTestBehavior.opaque,
        child: AnimatedContainer(
          duration: Nova.fast,
          height: 40,
          padding: const EdgeInsets.symmetric(horizontal: Nova.space2),
          decoration: BoxDecoration(
            gradient: selected ? AppColors.emberGradient : null,
            color: selected
                ? null
                : (_hovered ? AppColors.surface3 : Colors.transparent),
            borderRadius: BorderRadius.circular(Nova.radiusControl),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(widget.icon, size: 16, color: color),
              const SizedBox(width: Nova.space2),
              Flexible(
                child: Text(
                  widget.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.button.copyWith(color: color),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Field extends StatelessWidget {
  const _Field({
    required this.controller,
    required this.label,
    required this.icon,
    this.obscure = false,
    this.latin = false,
    this.onSubmitted,
  });

  final TextEditingController controller;
  final String label;
  final IconData icon;
  final bool obscure;

  /// A server URL, a username and a password are Latin strings even in the
  /// Arabic UI: laying them out right-to-left puts the cursor in the wrong place
  /// and makes a typo impossible to see.
  final bool latin;

  final ValueChanged<String>? onSubmitted;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      obscureText: obscure,
      autocorrect: false,
      enableSuggestions: false,
      cursorColor: AppColors.primary,
      textDirection: latin ? TextDirection.ltr : null,
      style: AppText.control,
      onSubmitted: onSubmitted,
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, size: 19),
      ),
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({
    required this.text,
    this.danger = false,
    this.pending = false,
  });

  final String text;
  final bool danger;
  final bool pending;

  @override
  Widget build(BuildContext context) {
    final color = danger
        ? AppColors.danger
        : (pending ? AppColors.textSecondary : AppColors.success);

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (pending)
          SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(strokeWidth: 2, color: color),
          )
        else
          Icon(
            danger
                ? Icons.error_outline_rounded
                : Icons.check_circle_outline_rounded,
            size: 18,
            color: color,
          ),
        const SizedBox(width: Nova.space2),
        Expanded(
          child: Text(text, style: AppText.body.copyWith(color: color)),
        ),
      ],
    );
  }
}
