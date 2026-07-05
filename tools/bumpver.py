import argparse
import re
import sys
from pathlib import Path

VERSION_REGEX = re.compile(
    r'(?<![a-zA-Z0-9])(\d+\.\d+\.\d+)(?:-([^\s+"\'`]+))?(?:\+([^\s+"\'`]+))?')

DEFAULT_PATTERNS = [
    'pyproject.toml',
    'setup.py',
    'setup.cfg',
    '**/__init__.py',
    'Dockerfile',
]

AUTO_EXCLUDES = {'.git', 'node_modules', '.venv', '__pycache__'}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description='Scan and bump semver strings across project files.')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--patch', action='store_true')
    group.add_argument('--minor', action='store_true')
    group.add_argument('--major', action='store_true')
    group.add_argument('--set-version', metavar='VALUE')

    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--pattern', action='append', default=[])
    parser.add_argument('--exclude', action='append', default=[])
    parser.add_argument('--dir', default='.', metavar='PATH')

    args = parser.parse_args(argv)

    if not any([args.patch, args.minor, args.major, args.set_version]):
        parser.error('At least one of --patch, --minor, --major, or --set-version is required.')

    return args


def find_files(root, patterns, excludes):
    root = Path(root).resolve()
    excluded_names = AUTO_EXCLUDES | set(excludes)
    matched = []

    for pattern in patterns:
        for p in root.rglob(pattern):
            if not p.is_file():
                continue
            rel = p.relative_to(root)
            skip = False
            for part in rel.parts[:-1]:
                if part in excluded_names:
                    skip = True
                    break
            if not skip:
                matched.append(p)

    return sorted(set(matched))


def extract_versions(filepath):
    content = filepath.read_text(encoding='utf-8')
    matches = []
    for m in VERSION_REGEX.finditer(content):
        matches.append({
            'start': m.start(),
            'end': m.end(),
            'full': m.group(0),
            'base': m.group(1),
            'pre_release': m.group(2),
            'build': m.group(3),
        })
    return content, matches


def bump_version(base, kind):
    major, minor, patch = (int(x) for x in base.split('.'))
    if kind == 'patch':
        patch += 1
    elif kind == 'minor':
        minor += 1
        patch = 0
    elif kind == 'major':
        major += 1
        minor = 0
        patch = 0
    return f'{major}.{minor}.{patch}'


def collect_versions(files):
    file_versions = {}
    for fp in files:
        _, matches = extract_versions(fp)
        if matches:
            versions = set(m['base'] for m in matches)
            file_versions[str(fp)] = versions
    all_versions = set()
    for vs in file_versions.values():
        all_versions.update(vs)
    return file_versions, all_versions


def check_consistency(file_versions, all_versions):
    if len(all_versions) <= 1:
        return True, None
    lines = []
    for fp, versions in sorted(file_versions.items()):
        for v in sorted(versions):
            lines.append(f'  {fp}: {v}')
    return False, '\n'.join(lines)


def apply_changes(files, kind, new_version, dry_run=False):
    changed_files = []

    for fp in files:
        content, matches = extract_versions(fp)
        if not matches:
            continue

        new_content = content
        has_change = False

        for m in reversed(matches):
            if kind == 'set':
                replacement = new_version
            else:
                replacement = bump_version(m['base'], kind)

            new_content = (
                new_content[:m['start']] +
                replacement +
                new_content[m['end']:]
            )
            has_change = True

        if has_change:
            changed_files.append((fp, content, new_content))

    for fp, old_content, new_content in changed_files:
        print(f'Modifying {fp}:')
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        max_len = max(len(old_lines), len(new_lines))
        for i in range(max_len):
            ol = old_lines[i] if i < len(old_lines) else ''
            nl = new_lines[i] if i < len(new_lines) else ''
            if ol != nl:
                print(f'  {i + 1}: - {ol}')
                print(f'  {i + 1}: + {nl}')

        if not dry_run:
            Path(fp).write_text(new_content, encoding='utf-8')

    return len(changed_files)


def main(argv=None):
    args = parse_args(argv)
    root = Path(args.dir).resolve()

    if not root.is_dir():
        print(f'Error: {root} is not a directory.', file=sys.stderr)
        sys.exit(1)

    patterns = list(DEFAULT_PATTERNS) + args.pattern
    files = find_files(root, patterns, args.exclude)

    if not files:
        print('No matching files found. Use --pattern to add custom glob patterns.', file=sys.stderr)
        sys.exit(0)

    kind = None
    if args.patch:
        kind = 'patch'
    elif args.minor:
        kind = 'minor'
    elif args.major:
        kind = 'major'
    else:
        kind = 'set'

    file_versions, all_versions = collect_versions(files)

    if not file_versions:
        print('No semver strings found in matched files.', file=sys.stderr)
        sys.exit(0)

    if kind != 'set':
        consistent, detail = check_consistency(file_versions, all_versions)
        if not consistent:
            print('Inconsistent versions across files:', file=sys.stderr)
            print(detail, file=sys.stderr)
            sys.exit(1)

    if kind == 'set':
        new_version = args.set_version
    else:
        base = next(iter(all_versions))
        new_version = bump_version(base, kind)

    if args.dry_run:
        print(f'Dry run — would set version to {new_version}')

    count = apply_changes(files, kind, new_version, args.dry_run)

    if not args.dry_run:
        print(f'Updated {count} file(s) to version {new_version}.')


if __name__ == '__main__':
    main()
