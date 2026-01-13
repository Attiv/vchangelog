# vChangelog

从 Git 历史生成版本间的 Changelog，支持 AI 智能总结。

Generate changelog between versions from Git history, with AI summarization support.

## 安装 / Install

```bash
./install.sh
```

## 配置 AI / Configure AI

```bash
vchangelog --config
```

配置项 / Config options:
- `url`: API 完整路径 / Full API URL (e.g. `https://api.openai.com/v1/chat/completions`)
- `key`: API Key
- `model`: 模型名称 / Model name (default: `gpt-3.5-turbo`)
- `lang`: 输出语言 / Output language (`zh` 中文 / `en` English)

配置保存在 / Config saved at `~/.vchangelog.json`

## 使用 / Usage

```bash
# 查看两个版本之间的 changelog / View changelog between two versions
vchangelog 1.0.0+68 1.0.1+71

# 使用 AI 总结 / Use AI to summarize
vchangelog 1.0.0+68 1.0.1+71 --ai

# 查看最近两个版本 / View latest two versions
vchangelog --latest
vchangelog --latest --ai

# 列出所有版本 / List all versions
vchangelog --list

# 输出 Markdown 格式 / Output in Markdown format
vchangelog 1.0.0+68 1.0.1+71 -f md

# 复制到剪贴板 / Copy to clipboard
vchangelog 1.0.0+68 1.0.1+71 --copy
vchangelog --latest --ai --copy

# 查看 git diff / View git diff
vchangelog 1.0.0+68 1.0.1+71 --diff
vchangelog 1.0.1+71 --diff
vchangelog --latest --diff
vchangelog --diff
```

## 输出示例 / Output Example

```
Changelog: 1.0.0+68 → 1.0.1+71

✨ Features:
  - sync: exclude post-ad videos from current sync cycle

🐛 Bug Fixes:
  - offline: increase upload timeout to 120 seconds
  - ad: fix missing ads and placeholder image sizing issues

⚡ Performance:
  - placeholder: add caching mechanism for same URL and duration
```

## 支持的版本格式 / Supported Version Formats

- `1.0.6+71`
- `v1.2.3`
- `1.0.0`
- `2.0.0-beta.1`
