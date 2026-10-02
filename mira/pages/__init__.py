"""Mira's pages: one QObject per destination of her window, each in its own module.

A page owns its backend calls, its state map for QML and its own words (`STRINGS`, merged into
`mira.s` by i18n.table). The controller creates every page listed in `PAGES` and exposes it to QML
as `mira.<name>Page`; a page never imports the controller, it is handed the few shared services it
may use (see pages.base.Page).
"""
import importlib

# (module, property name on the controller) in navigation order after the Mira stage itself.
PAGES = [
    ('home', 'homePage'),
    ('lumen', 'lumenPage'),
    ('pc', 'pcPage'),
    ('apps', 'appsPage'),
    ('system', 'systemPage'),
    ('workbench', 'workbenchPage'),
    ('connect', 'connectPage'),
    ('brain', 'brainPage'),
]


def modules():
    """The page modules that exist (a missing module is skipped, never fatal)."""
    out = []
    for name, _prop in PAGES:
        try:
            out.append(importlib.import_module('pages.' + name))
        except ImportError:
            continue
    return out


def strings():
    merged = {}
    for module in modules():
        merged.update(getattr(module, 'STRINGS', {}))
    return merged
