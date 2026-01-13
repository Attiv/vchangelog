#!/usr/bin/env python3
"""CLI tool to generate changelog between two versions from git history."""

import subprocess
import re
import argparse
import sys
import os
import json
import ssl
import certifi

CONFIG_PATH = os.path.expanduser('~/.vchangelog.json')

# 支持多种版本格式: 3.0.6+71, v1.2.3, 1.0.0, 2.0.0-beta.1 等
VERSION_PATTERN = r'^v?\d+\.\d+(\.\d+)?([+\-].+)?$'
COMMIT_PATTERN = r'\[([a-f0-9]+)\] \| (.+?) \{\{.+\}\}'
ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[[0-9;]*m')

CATEGORIES = {
    'feat': ('✨ Features', 1),
    'fix': ('🐛 Bug Fixes', 2),
    'perf': ('⚡ Performance', 3),
    'chore': ('🔧 Chores', 4),
    'docs': ('📚 Documentation', 5),
    'refactor': ('♻️ Refactors', 6),
    'test': ('🧪 Tests', 7),
    'other': ('📝 Other', 99),
}


def _strip_emoji_prefix(text):
    return re.sub(r'^\s*[^\w\s]+\s*', '', text)


def get_category_title(cat_type, emoji=True):
    title = CATEGORIES.get(cat_type, ('📝 Other', 99))[0]
    return title if emoji else _strip_emoji_prefix(title)


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"配置已保存到 {CONFIG_PATH}")


def spinner(stop_event):
    """Display a spinner animation."""
    import itertools
    chars = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
    while not stop_event.is_set():
        sys.stdout.write(f'\r🤖 AI 总结中... {next(chars)}')
        sys.stdout.flush()
        stop_event.wait(0.1)
    sys.stdout.write('\r' + ' ' * 20 + '\r')
    sys.stdout.flush()


def call_ai(commits, from_v, to_v, config, lang='zh'):
    """Call AI API to summarize commits."""
    import urllib.request
    import threading
    
    url = config.get('url', '').rstrip('/')
    key = config.get('key', '')
    model = config.get('model', 'gpt-3.5-turbo')
    emoji = config.get('emoji', False)
    
    if not url or not key:
        print("错误: 请先配置 AI API (vchangelog --config)", file=sys.stderr)
        sys.exit(1)
    
    commits_text = '\n'.join(commits)
    
    # Start spinner
    stop_event = threading.Event()
    spin_thread = threading.Thread(target=spinner, args=(stop_event,))
    spin_thread.start()
    
    if lang == 'zh':
        requirements = (
            "要求：1. 按类型分组（Features/Bug Fixes/Performance/Chores 等）"
            "2. 合并相似的提交 3. 用简洁的中文描述"
        )
        if emoji:
            requirements += " 4. 使用 emoji 前缀"
        else:
            requirements += " 4. 不使用 emoji"
        prompt = (
            "请总结以下 git commits 生成 changelog，版本从 "
            f"{from_v} 到 {to_v}。\n"
            f"{requirements}\n"
            "Commits:\n"
            f"{commits_text}"
        )
    else:
        requirements = (
            "Requirements: 1. Group by type "
            "(Features/Bug Fixes/Performance/Chores etc.) "
            "2. Merge similar commits 3. Use concise English"
        )
        if emoji:
            requirements += " 4. Use emoji prefixes"
        else:
            requirements += " 4. Do not use emoji"
        prompt = (
            "Summarize the following git commits into a changelog, from "
            f"version {from_v} to {to_v}.\n"
            f"{requirements}\n"
            "Commits:\n"
            f"{commits_text}"
        )

    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
    )
    
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=60, context=context) as resp:
            result = json.loads(resp.read())
            stop_event.set()
            spin_thread.join()
            return result['choices'][0]['message']['content']
    except Exception as e:
        stop_event.set()
        spin_thread.join()
        print(f"AI 调用失败: {e}", file=sys.stderr)
        sys.exit(1)


def get_staged_diff():
    """获取 staged 的 diff 内容"""
    result = subprocess.run(['git', 'diff', '--cached'], capture_output=True, text=True)
    return result.stdout.strip()


def generate_commit_message(config, lang='zh'):
    """用 AI 生成 commit 消息"""
    import urllib.request
    import threading

    diff = get_staged_diff()
    if not diff:
        print("没有 staged 的更改，请先 git add", file=sys.stderr)
        sys.exit(1)

    url = config.get('url', '').rstrip('/')
    key = config.get('key', '')
    model = config.get('model', 'gpt-3.5-turbo')

    if not url or not key:
        print("错误: 请先配置 AI API (vchangelog --config)", file=sys.stderr)
        sys.exit(1)

    stop_event = threading.Event()
    spin_thread = threading.Thread(target=spinner, args=(stop_event,))
    spin_thread.start()

    if lang == 'zh':
        prompt = (
            "根据以下 git diff 生成一条 commit 消息。\n"
            "要求：\n"
            "1. 使用 conventional commits 格式：type(scope): description\n"
            "2. type 必须是: feat/fix/docs/style/refactor/perf/test/chore 之一\n"
            "3. scope 可选，描述影响范围\n"
            "4. description 用简洁的中文，不超过50字\n"
            "5. 只输出 commit 消息本身，不要其他解释\n\n"
            f"Diff:\n{diff}"
        )
    else:
        prompt = (
            "Generate a commit message based on the following git diff.\n"
            "Requirements:\n"
            "1. Use conventional commits format: type(scope): description\n"
            "2. type must be one of: feat/fix/docs/style/refactor/perf/test/chore\n"
            "3. scope is optional, describes the affected area\n"
            "4. description should be concise, under 50 characters\n"
            "5. Output only the commit message, no explanations\n\n"
            f"Diff:\n{diff}"
        )

    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
    )

    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=60, context=context) as resp:
            result = json.loads(resp.read())
            stop_event.set()
            spin_thread.join()
            return result['choices'][0]['message']['content'].strip()
    except Exception as e:
        stop_event.set()
        spin_thread.join()
        print(f"AI 调用失败: {e}", file=sys.stderr)
        sys.exit(1)


def run_git(args):
    result = subprocess.run(['git'] + args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Git error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def get_versions():
    log = run_git(['log', '--oneline', '--all', '--pretty=format:%s'])
    versions = []
    for line in log.split('\n'):
        match = re.match(VERSION_PATTERN, line.strip())
        if match:
            versions.append(line.strip())
    return versions


def find_commit_for_version(version):
    log = run_git(['log', '--all', '--pretty=format:%H %s'])
    for line in log.split('\n'):
        if version in line:
            return line.split()[0]
    return None


def get_diff_range(from_version, to_version):
    from_hash = find_commit_for_version(from_version)
    to_hash = find_commit_for_version(to_version)

    if not from_hash or not to_hash:
        print("未找到版本对应的提交", file=sys.stderr)
        sys.exit(1)

    return f'{from_hash}..{to_hash}'


def get_previous_version(target_version):
    versions = get_versions()
    if target_version not in versions:
        print("未找到版本号", file=sys.stderr)
        sys.exit(1)

    index = versions.index(target_version)
    if index + 1 >= len(versions):
        print("没有更早的版本可用于对比", file=sys.stderr)
        sys.exit(1)

    return versions[index + 1]


def format_diff_with_separators(diff_text):
    if not diff_text:
        return diff_text

    lines = diff_text.splitlines()
    formatted = []
    sep_line = '-' * 72

    for line in lines:
        clean_line = ANSI_ESCAPE_PATTERN.sub('', line)
        if clean_line.startswith('diff --git '):
            parts = clean_line.split()
            file_label = ''
            if len(parts) >= 4:
                a_path = parts[2][2:] if parts[2].startswith('a/') else parts[2]
                b_path = parts[3][2:] if parts[3].startswith('b/') else parts[3]
                file_label = f"{a_path} -> {b_path}" if a_path != b_path else a_path
            if formatted:
                formatted.append(sep_line)
            formatted.append(sep_line)
            if file_label:
                formatted.append(f"File: {file_label}")
            formatted.append(sep_line)
        formatted.append(line)

    return '\n'.join(formatted)


def build_diff_args(color, extra_args):
    args = []
    if color:
        args.extend([
            '-c', 'color.ui=always',
            '-c', 'color.diff.meta=yellow bold',
            '-c', 'color.diff.frag=cyan bold',
            '-c', 'color.diff.old=red bold',
            '-c', 'color.diff.new=green bold',
            'diff',
            '--color=always',
        ])
    else:
        args.extend(['diff', '--color=never'])
    args.extend(extra_args)
    return args


def build_diff_output(from_version, to_version, color=True):
    diff_range = get_diff_range(from_version, to_version)
    sections = [f"Diff: {from_version} → {to_version}\n"]

    diff_stat = run_git(build_diff_args(color, ['--stat', diff_range])).rstrip('\n')
    if diff_stat:
        sections.append("变更概览:")
        sections.append(diff_stat)
        sections.append("")

    diff_body = run_git(build_diff_args(color, [diff_range])).rstrip('\n')
    if diff_body:
        sections.append("详细差异:")
        sections.append(format_diff_with_separators(diff_body))
    else:
        sections.append("没有差异")

    return '\n'.join(sections)


def build_working_tree_diff_output(color=True):
    sections = ["Diff: working tree\n"]

    diff_stat = run_git(build_diff_args(color, ['--stat'])).rstrip('\n')
    if diff_stat:
        sections.append("变更概览:")
        sections.append(diff_stat)
        sections.append("")

    diff_body = run_git(build_diff_args(color, [])).rstrip('\n')
    if diff_body:
        sections.append("详细差异:")
        sections.append(format_diff_with_separators(diff_body))
    else:
        sections.append("没有差异")

    return '\n'.join(sections)


def get_commits_between(from_version, to_version):
    from_hash = find_commit_for_version(from_version)
    to_hash = find_commit_for_version(to_version)
    
    if not from_hash or not to_hash:
        print(f"Could not find commits for versions", file=sys.stderr)
        sys.exit(1)
    
    log = run_git(['log', '--pretty=format:%s', f'{from_hash}..{to_hash}'])
    return [line.strip() for line in log.split('\n') if line.strip()]


def parse_commit(message):
    if re.match(VERSION_PATTERN, message):
        return None
    match = re.match(r'^(\w+)(?:\(([^)]+)\))?: (.+)$', message)
    if match:
        return {'type': match.group(1).lower(), 'scope': match.group(2), 'description': match.group(3)}
    return {'type': 'other', 'scope': None, 'description': message}


def categorize_commits(commits):
    categorized = {}
    for msg in commits:
        parsed = parse_commit(msg)
        if not parsed:
            continue
        commit_type = parsed['type'] if parsed['type'] in CATEGORIES else 'other'
        if commit_type not in categorized:
            categorized[commit_type] = []
        categorized[commit_type].append(parsed)
    return categorized


def format_output(from_v, to_v, categorized, fmt='text', emoji=True):
    lines = []
    lines.append(f"{'## ' if fmt == 'md' else ''}Changelog: {from_v} → {to_v}\n")
    
    sorted_cats = sorted(categorized.items(), key=lambda x: CATEGORIES.get(x[0], ('', 99))[1])
    
    for cat_type, commits in sorted_cats:
        if not commits:
            continue
        cat_name = get_category_title(cat_type, emoji=emoji)
        lines.append(f"{'### ' if fmt == 'md' else ''}{cat_name}:")
        for c in commits:
            scope = f"{c['scope']}: " if c['scope'] else ""
            lines.append(f"  - {scope}{c['description']}")
        lines.append("")
    
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Generate changelog between versions')
    parser.add_argument('from_version', nargs='?', help='Start version (older)')
    parser.add_argument('to_version', nargs='?', help='End version (newer)')
    parser.add_argument('--latest', '-l', action='store_true', help='Show changelog for latest two versions')
    parser.add_argument('--list', action='store_true', help='List all versions')
    parser.add_argument('--format', '-f', choices=['text', 'md'], default='text', help='Output format')
    parser.add_argument('--copy', '-c', action='store_true', help='Copy to clipboard')
    parser.add_argument('--ai', '-a', action='store_true', help='Use AI to summarize')
    parser.add_argument('--config', action='store_true', help='Configure AI API')
    parser.add_argument('--commit', '--cm', action='store_true', help='Generate commit message with AI')
    parser.add_argument('--diff', '--d', action='store_true', help='Show git diff between versions')
    emoji_group = parser.add_mutually_exclusive_group()
    emoji_group.add_argument(
        '--emoji',
        dest='emoji',
        action='store_true',
        help='Output with emoji (override config)',
    )
    emoji_group.add_argument(
        '--no-emoji',
        dest='emoji',
        action='store_false',
        help='Output without emoji (override config)',
    )
    parser.set_defaults(emoji=None)

    lang_group = parser.add_mutually_exclusive_group()
    lang_group.add_argument('--zh', dest='lang', action='store_const', const='zh', help='中文输出')
    lang_group.add_argument('--en', dest='lang', action='store_const', const='en', help='English output')
    parser.set_defaults(lang='en')
    
    args = parser.parse_args()
    
    # AI 生成 commit 消息
    if args.commit:
        config = load_config()
        msg = generate_commit_message(config, lang=args.lang)
        print(msg)
        if args.copy:
            try:
                subprocess.run(['pbcopy'], input=msg.encode(), check=True)
                print("(Copied to clipboard)", file=sys.stderr)
            except:
                print("(Could not copy to clipboard)", file=sys.stderr)
        return

    # 配置 AI
    if args.config:
        config = load_config()
        print("配置 AI API (Configure AI API)")
        print("URL 需要完整路径，如 https://api.openai.com/v1/chat/completions")
        print("URL should be full path, e.g. https://api.openai.com/v1/chat/completions\n")
        config['url'] = input(f"API URL [{config.get('url', '')}]: ").strip() or config.get('url', '')
        config['key'] = input(f"API Key [{config.get('key', '')[:8] + '...' if config.get('key') else ''}]: ").strip() or config.get('key', '')
        config['model'] = input(f"Model [{config.get('model', 'gpt-3.5-turbo')}]: ").strip() or config.get('model', 'gpt-3.5-turbo')
        emoji_default = 'y' if config.get('emoji', False) else 'n'
        emoji_input = input(f"Emoji (y/n) [{emoji_default}]: ").strip().lower()
        if emoji_input:
            config['emoji'] = emoji_input in ('y', 'yes', 'true', '1')
        else:
            config['emoji'] = config.get('emoji', False)
        save_config(config)
        return
    
    if args.list:
        for v in get_versions()[:20]:
            print(v)
        return

    if args.diff:
        use_color = sys.stdout.isatty()
        if args.latest:
            versions = get_versions()
            if len(versions) < 2:
                print("Need at least 2 versions", file=sys.stderr)
                sys.exit(1)
            args.to_version = versions[0]
            args.from_version = versions[1]
        elif args.from_version and not args.to_version:
            args.to_version = args.from_version
            args.from_version = get_previous_version(args.to_version)
        elif not args.from_version and not args.to_version:
            output = build_working_tree_diff_output(color=use_color)
            print(output)
            if args.copy:
                try:
                    subprocess.run(['pbcopy'], input=output.encode(), check=True)
                    print("(Copied to clipboard)", file=sys.stderr)
                except:
                    print("(Could not copy to clipboard)", file=sys.stderr)
            return
        output = build_diff_output(args.from_version, args.to_version, color=use_color)
        print(output)
        if args.copy:
            try:
                subprocess.run(['pbcopy'], input=output.encode(), check=True)
                print("(Copied to clipboard)", file=sys.stderr)
            except:
                print("(Could not copy to clipboard)", file=sys.stderr)
        return
    
    if args.latest:
        versions = get_versions()
        if len(versions) < 2:
            print("Need at least 2 versions", file=sys.stderr)
            sys.exit(1)
        args.to_version = versions[0]
        args.from_version = versions[1]

    if not args.from_version or not args.to_version:
        parser.print_help()
        sys.exit(1)

    commits = get_commits_between(args.from_version, args.to_version)

    config = load_config()
    if args.emoji is None:
        emoji_enabled = config.get('emoji', False)
    else:
        emoji_enabled = args.emoji
    
    if args.ai:
        config['emoji'] = emoji_enabled
        output = call_ai(commits, args.from_version, args.to_version, config, lang=args.lang)
    else:
        categorized = categorize_commits(commits)
        output = format_output(
            args.from_version,
            args.to_version,
            categorized,
            fmt=args.format,
            emoji=emoji_enabled,
        )
    
    print(output)
    
    if args.copy:
        try:
            subprocess.run(['pbcopy'], input=output.encode(), check=True)
            print("(Copied to clipboard)", file=sys.stderr)
        except:
            print("(Could not copy to clipboard)", file=sys.stderr)

if __name__ == '__main__':
    main()
