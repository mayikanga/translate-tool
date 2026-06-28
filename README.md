# 划词翻译 / Clipboard Translate

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)

一款轻量级的 Windows 桌面划词翻译工具。复制即翻译，选中即译，即开即用。

A lightweight Windows desktop translation tool. Copy any text and get instant translations — just select and go.

---

## 功能特点 / Features

- **📋 剪贴板监听** — 复制任何文字后自动检测并翻译
- **⚡ 选中即复制** — 开启「自动」模式，选中文字直接翻译（每 300ms 扫描）
- **🌐 Microsoft Azure Translator** — 每月 200 万字符免费，国内可用
- **📖 历史记录** — 保存最近 5 条翻译，点击恢复或一键复制译文
- **📌 窗口置顶** — 始终在前，方便查阅
- **🖱️ 右键菜单** — 快速切换各项功能
- **💾 配置持久化** — 窗口大小、分割线位置自动保存

- **📋 Clipboard Monitoring** — Auto-detect and translate any copied text
- **⚡ Auto-Copy Mode** — Select text and it's translated instantly (300ms polling)
- **🌐 Microsoft Azure Translator** — 2M free chars/month, works in China
- **📖 History** — Last 5 translations saved, click to restore or copy
- **📌 Always on Top** — Stays visible while you work
- **🖱️ Context Menu** — Quick access to all features
- **💾 Persistent Settings** — Remembers window size and layout

## 快捷键 / Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl + L` | 清空面板 / Clear panel |
| `Ctrl + P` | 切换置顶 / Toggle always-on-top |
| `Ctrl + H` | 切换历史面板 / Toggle history panel |

## 安装 / Installation

### 依赖 / Requirements

- **Python 3.8+**
- Windows (使用了 Win32 API / Uses Win32 API)

### Windows
```bash
# 无需额外安装第三方库，全部使用标准库
# No third-party packages needed, pure standard library

python translate_gui.py
```

## 使用方法 / Usage

1. 启动程序: `python translate_gui.py`
2. **复制任意文字** → 自动翻译
3. 开启工具栏的「自动」按钮 → **选中文字即自动翻译**
4. 使用 `Ctrl+L` 清空，右键菜单查看更多选项

1. Launch: `python translate_gui.py`
2. **Copy any text** → auto-translated
3. Enable the "Auto" button → **select text to translate instantly**
4. `Ctrl+L` to clear, right-click for more options

## 技术栈 / Tech Stack

- **Python 3** (标准库, no third-party dependencies)
- **Tkinter** — GUI 框架 / UI framework
- **Win32 API** — 剪贴板监听 / Clipboard monitoring via `ctypes`
- **Microsoft Azure Translator API** — 翻译引擎 / Translation engine (free tier: 2M chars/month)

## 许可 / License

[MIT](LICENSE) © 2026 mayikanga
