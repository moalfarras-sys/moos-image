"""Resolve the actual source font/policy in private native Qt fixtures.

An isolated HOME correctly excludes user-local development fonts. Without
this explicit dependency, a source test asking for Meyar silently tests Noto.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def configure(env, private, *, defaults=True):
    fonts = ROOT / 'system_files/usr/share/fonts/meyar'
    policy = ROOT / 'system_files/etc/fonts/conf.d/61-moos-brand.conf'
    if not fonts.is_dir() or not policy.is_file():
        raise RuntimeError('Source Meyar font/policy dependency is missing')
    private = Path(private)
    # Keep native generic-name normalization and vendor aliases, but do not
    # import the running image's MoOS policies into source/old-policy controls.
    # Private HOME alone did not isolate these after signed Meyar was installed.
    native = ET.parse('/etc/fonts/fonts.conf')
    tree = native.getroot()
    includes = tree.findall('include')
    if len(includes) != 1 or includes[0].text.strip() != 'conf.d':
        raise RuntimeError('Unreviewed native Fontconfig include layout')
    vendor = private / 'vendor-fontconfig'
    vendor.mkdir(exist_ok=True)
    owned = {'00-moos-meyar-defaults.conf', '61-moos-brand.conf'}
    for path in sorted(Path('/etc/fonts/conf.d').glob('[0-9]*.conf')):
        if path.name in owned or path.name in {'50-user.conf', '51-local.conf'}:
            continue
        link = vendor / path.name
        if not link.exists():
            link.symlink_to(path.resolve(strict=True))
    includes[0].text = str(vendor)
    if defaults:
        node = ET.Element('include')
        node.text = str(ROOT / 'system_files/etc/fonts/conf.d/00-moos-meyar-defaults.conf')
        tree.insert(list(tree).index(includes[0]), node)
    # Scan metadata is cached too: never reuse a host cache that already tagged
    # the old-control font as fixed-width, or a previous control's private cache.
    for node in tree.findall('cachedir'):
        tree.remove(node)
    ET.SubElement(tree, 'cachedir').text = str(private / 'font-cache')
    ET.SubElement(tree, 'dir').text = str(fonts)
    ET.SubElement(tree, 'include').text = str(policy)
    rejected = ET.SubElement(ET.SubElement(tree, 'selectfont'), 'rejectfont')
    ET.SubElement(rejected, 'glob').text = '/usr/share/fonts/meyar'
    target = private / 'meyar-fonts.conf'
    native.write(target, encoding='unicode')
    env['FONTCONFIG_FILE'] = str(target)
