"""Resolve the actual source font/policy in private native Qt fixtures.

An isolated HOME correctly excludes user-local development fonts. Without
this explicit dependency, a source test asking for Meyar silently tests Noto.
"""
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]


def configure(env, private):
    fonts = ROOT / 'system_files/usr/share/fonts/meyar'
    policy = ROOT / 'system_files/etc/fonts/conf.d/61-moos-brand.conf'
    if not fonts.is_dir() or not policy.is_file():
        raise RuntimeError('Source Meyar font/policy dependency is missing')
    target = Path(private) / 'meyar-fonts.conf'
    target.write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n'
        '<fontconfig><include>/etc/fonts/fonts.conf</include><dir>' + escape(str(fonts)) + '</dir>'
        '<include>' + escape(str(policy)) + '</include><cachedir>' + escape(str(Path(private) / 'font-cache'))
        + '</cachedir></fontconfig>\n')
    env['FONTCONFIG_FILE'] = str(target)
