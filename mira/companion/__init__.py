"""Mira Companion: Mira on the owner's phone, over his Tailscale network.

The desktop app holds one `CompanionService` (adapter.py). It observes the controller, keeps the
pairing token in `~/.config/mo-dot/companion.json` (0600) and runs `CompanionServer` (server.py,
stdlib asyncio) on its own thread, bound only to this computer's Tailscale address. The phone app
is `static/`. The phone can chat (through Mira's own brain), talk through the Echo and use the
Home controls; it has no route of its own to the computer's tools.
"""
from .adapter import CompanionService, ControllerAdapter, FaceRenderer, panel_text, qr_code
from .server import DEFAULT_PORT, CompanionServer, Tailnet, TokenStore, find_tailscale

__all__ = ['CompanionService', 'ControllerAdapter', 'FaceRenderer', 'panel_text', 'qr_code', 'DEFAULT_PORT',
           'CompanionServer', 'Tailnet', 'TokenStore', 'find_tailscale']
