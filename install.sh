#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="/usr/local/bin/vchangelog"

ln -sf "$SCRIPT_DIR/vchangelog.py" "$TARGET" 2>/dev/null || sudo ln -sf "$SCRIPT_DIR/vchangelog.py" "$TARGET"

if [ -L "$TARGET" ]; then
    echo "✅ 安装成功！现在可以使用 vchangelog 命令了"
else
    echo "❌ 安装失败，请手动执行: sudo ln -sf $SCRIPT_DIR/vchangelog.py $TARGET"
fi
