#!/usr/bin/env python3
"""Check MoOS's reviewed top-level Actions pins and credential boundaries.

This checks the maintained workflow format, not arbitrary YAML semantics or
transitive downloads inside an upstream action. GitHub validates workflow YAML.
"""
import json
from pathlib import Path
import re
import sys

USES = re.compile(r"^(\s*)(?:-\s*)?uses:\s*([^\s#]+)", re.M)
OWNER_JOBS = {
    'claude.yml': ('claude', '${{ github.actor == github.repository_owner }}'),
    'claude-code-review.yml': (
        'claude-review', '${{ github.actor == github.repository_owner && '
        'github.event.pull_request.head.repo.full_name == github.repository }}'),
}


def verify(root):
    root = Path(root)
    manifest = json.loads((root / '.github/action-pins.json').read_text())
    if manifest.get('schema') != 1:
        raise ValueError('Unsupported action pin manifest')
    allowed = set()
    for pin in manifest['actions']:
        repo, sha = pin['repository'], pin['sha']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            raise ValueError('Invalid upstream action repository')
        if not re.fullmatch(r'[0-9a-f]{40}', sha):
            raise ValueError('Action pin must be a complete commit SHA')
        if pin['commit_url'] != f'https://github.com/{repo}/commit/{sha}':
            raise ValueError('Action pin provenance disagrees with repository/SHA')
        allowed.add(f'{repo}@{sha}')
    files = list((root / '.github/workflows').glob('*.yml'))
    files += list((root / '.github/workflows').glob('*.yaml'))
    count = 0
    for file in files:
        source = file.read_text()
        if re.search(r'^\s*pull_request_target\s*:', source, re.M):
            raise ValueError(f'{file.name}: unreviewed privileged PR trigger')
        if re.search(r'^\s*permissions:\s*write-all\b', source, re.M):
            raise ValueError(f'{file.name}: broad write permissions')
        lines = source.splitlines()
        for match in USES.finditer(source):
            action = match.group(2).strip('\"\'')
            if action.startswith('./'):
                continue
            if not re.fullmatch(r'[^@\s]+@[0-9a-f]{40}', action):
                raise ValueError(f'{file.name}: mutable action reference {action}')
            if action not in allowed:
                raise ValueError(f'{file.name}: action is absent from reviewed pins: {action}')
            count += 1
            if action.startswith('actions/checkout@'):
                index = source[:match.start()].count('\n')
                line = lines[index]
                indent = len(line) - len(line.lstrip())
                field = indent + 2 if line.lstrip().startswith('- ') else indent
                end = index + 1
                while end < len(lines):
                    text = lines[end]
                    if text.strip() and not text.lstrip().startswith('#'):
                        depth = len(text) - len(text.lstrip())
                        if depth < field or (depth == field and text.lstrip().startswith('- ')):
                            break
                    end += 1
                values = [text.strip() for text in lines[index+1:end]
                          if re.match(r'^\s*persist-credentials\s*:', text)]
                if values != ['persist-credentials: false']:
                    raise ValueError(f'{file.name}: checkout must not persist credentials')
        if file.name in OWNER_JOBS:
            job, required = OWNER_JOBS[file.name]
            section = re.search(r'^  '+re.escape(job)+r':\s*\n(.*?)(?=^  [\w-]+:|\Z)',
                                source, re.M | re.S)
            if not section:
                raise ValueError(f'{file.name}: secret-bearing job is missing')
            conditions = re.findall(r'^    if:\s*([^\n]+)', section.group(1), re.M)
            if conditions != [required]:
                raise ValueError(f'{file.name}: secret-bearing job lacks its exact owner boundary')
    if not files or count == 0:
        raise ValueError('No maintained workflows/actions found')
    for filename in OWNER_JOBS:
        if not (root / '.github/workflows' / filename).is_file():
            raise ValueError(f'Missing secret-bearing workflow {filename}')
    return count


if __name__ == '__main__':
    try:
        count = verify(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
    except (OSError, KeyError, ValueError) as error:
        raise SystemExit(f'WORKFLOW SECURITY FATAL: {error}')
    print(f'Workflow security OK: {count} reviewed SHA pins; owner and checkout boundaries retained')
