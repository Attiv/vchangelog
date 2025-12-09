#!/usr/bin/env python3
"""CLI tool to generate changelog between two versions from git history."""

import subprocess
import re
import argparse
import sys
import os
import json

CONFIG_PATH = os.path.expanduser('~/.vchangelog.json')

# 支持多种版本格式: 3.0.6+71, v1.2.3, 1.0.0, 2.0.0-beta.1 等
VERSION_PATTERN = r'^v?\d+\.\d+(\.\d+)?([+\-].+)?$'
COMMIT_PATTERN = r'\[([a-f0-9]+)\] \| (.+?) \{\{.+\}\}'

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

def call_ai(commits, from_v, to_v, config):
    """Call AI API to summarize commits."""
    import urllib.request
    import threading
    
    url = config.get('url', '').rstrip('/')
    key = config.get('key', '')
    model = config.get('model', 'gpt-3.5-turbo')
    lang = config.get('lang', 'zh')
    
    if not url or not key:
        print("错误: 请先配置 AI API (vchangelog --config)", file=sys.stderr)
        sys.exit(1)
    
    commits_text = '\n'.join(commits)
    
    # Start spinner
    stop_event = threading.Event()
    spin_thread = threading.Thread(target=spinner, args=(stop_event,))
    spin_thread.start()
    
    if lang == 'zh':
        prompt = f"""请总结以下 git commits 生成 changelog，版本从 {from_v} 到 {to_v}。
要求：1. 按类型分组（Features/Bug Fixes/Performance/Chores 等）2. 合并相似的提交 3. 用简洁的中文描述 4. 使用 emoji 前缀
Commits:
{commits_text}"""
    else:
        prompt = f"""Summarize the following git commits into a changelog, from version {from_v} to {to_v}.
Requirements: 1. Group by type (Features/Bug Fixes/Performance/Chores etc.) 2. Merge similar commits 3. Use concise English 4. Use emoji prefixes
Commits:
{commits_text}"""

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
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            stop_event.set()
            spin_thread.join()
            return result['choices'][0]['message']['content']
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

def format_output(from_v, to_v, categorized, fmt='text'):
    lines = []
    lines.append(f"{'## ' if fmt == 'md' else ''}Changelog: {from_v} → {to_v}\n")
    
    sorted_cats = sorted(categorized.items(), key=lambda x: CATEGORIES.get(x[0], ('', 99))[1])
    
    for cat_type, commits in sorted_cats:
        if not commits:
            continue
        cat_name = CATEGORIES.get(cat_type, ('📝 Other', 99))[0]
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
    
    args = parser.parse_args()
    
    # 配置 AI
    if args.config:
        config = load_config()
        print("配置 AI API (Configure AI API)")
        print("URL 需要完整路径，如 https://api.openai.com/v1/chat/completions")
        print("URL should be full path, e.g. https://api.openai.com/v1/chat/completions\n")
        config['url'] = input(f"API URL [{config.get('url', '')}]: ").strip() or config.get('url', '')
        config['key'] = input(f"API Key [{config.get('key', '')[:8] + '...' if config.get('key') else ''}]: ").strip() or config.get('key', '')
        config['model'] = input(f"Model [{config.get('model', 'gpt-3.5-turbo')}]: ").strip() or config.get('model', 'gpt-3.5-turbo')
        config['lang'] = input(f"Language (zh/en) [{config.get('lang', 'zh')}]: ").strip() or config.get('lang', 'zh')
        save_config(config)
        return
    
    if args.list:
        for v in get_versions()[:20]:
            print(v)
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
    
    if args.ai:
        config = load_config()
        output = call_ai(commits, args.from_version, args.to_version, config)
    else:
        categorized = categorize_commits(commits)
        output = format_output(args.from_version, args.to_version, categorized, args.format)
    
    print(output)
    
    if args.copy:
        try:
            subprocess.run(['pbcopy'], input=output.encode(), check=True)
            print("(Copied to clipboard)", file=sys.stderr)
        except:
            print("(Could not copy to clipboard)", file=sys.stderr)

if __name__ == '__main__':
    main()
