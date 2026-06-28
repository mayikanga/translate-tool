import tkinter as tk
from tkinter import ttk, scrolledtext
import urllib.request
import urllib.parse
import json
import ctypes
from ctypes import wintypes
import threading
import time
import os
import sys

# ── Windows API for clipboard monitoring ──
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

GetClipboardSequenceNumber = user32.GetClipboardSequenceNumber
GetClipboardSequenceNumber.restype = wintypes.DWORD

OpenClipboard = user32.OpenClipboard
OpenClipboard.restype = wintypes.BOOL
OpenClipboard.argtypes = [wintypes.HWND]

CloseClipboard = user32.CloseClipboard
CloseClipboard.restype = wintypes.BOOL

GetClipboardData = user32.GetClipboardData
GetClipboardData.restype = wintypes.HANDLE
GetClipboardData.argtypes = [wintypes.UINT]

GlobalLock = kernel32.GlobalLock
GlobalLock.restype = wintypes.LPVOID
GlobalLock.argtypes = [wintypes.HGLOBAL]

GlobalUnlock = kernel32.GlobalUnlock
GlobalUnlock.restype = wintypes.BOOL
GlobalUnlock.argtypes = [wintypes.HGLOBAL]

CF_UNICODETEXT = 13

# ── 按键模拟（用于选中即复制） ──
def send_ctrl_c():
    """模拟按下 Ctrl+C（用 keybd_event，兼容性好）"""
    VK_CONTROL = 0x11
    VK_C = 0x43
    KEYEVENTF_KEYUP = 2
    user32.keybd_event(VK_CONTROL, 0, 0, 0)  # Ctrl 按下
    user32.keybd_event(VK_C, 0, 0, 0)        # C 按下
    user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)  # C 松开
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)  # Ctrl 松开


def read_clipboard(root=None):
    """读取剪贴板文字（兼容浏览器等不同来源）"""
    if OpenClipboard(None):
        try:
            handle = GetClipboardData(CF_UNICODETEXT)
            if handle:
                ptr = GlobalLock(handle)
                if ptr:
                    try:
                        text = ctypes.c_wchar_p(ptr).value or ""
                        if text.strip():
                            return text.strip()
                    finally:
                        GlobalUnlock(handle)
        finally:
            CloseClipboard()

    if root:
        try:
            text = root.clipboard_get()
            if text.strip():
                return text.strip()
        except:
            pass

    return ""


# ── 配置文件路径 ──
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".translate_config.json")


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f)
    except:
        pass


class TranslateWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("划词翻译")
        self.root.minsize(320, 350)
        self.root.configure(bg="#f0f0f0")

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("mayikang.translate.2")
        self.root.iconname("划词翻译")
        self.root.attributes("-topmost", True)

        # 设置窗口图标（用 PhotoImage 生成简易图标）
        try:
            icon = tk.PhotoImage(width=16, height=16)
            rows = []
            for y in range(16):
                row = []
                for x in range(16):
                    if y < 3 or (5 <= x <= 10):
                        row.append("#1a73e8")
                    else:
                        row.append("#f0f0f0")
                rows.append("{" + " ".join(row) + "}")
            icon.put(" ".join(rows))
            self.root.iconphoto(True, icon)
            self._app_icon = icon  # 防止 GC
        except:
            pass

        self.setup_style()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 变数
        self.last_seq = GetClipboardSequenceNumber()
        self.last_text = ""
        self.translating = False
        self.history = []
        self.history_visible = False
        self.auto_copy = False
        self.auto_copy_active = False

        # ── GUI ──
        self.setup_gui()

        # ── 加载配置 ──
        self.apply_config()

        # ── 开始监听 ──
        self.monitor_clipboard()

        # ── 快捷键 ──
        self.root.bind("<Control-l>", lambda e: self.clear_panel())
        self.root.bind("<Control-p>", lambda e: self.toggle_topmost())
        self.root.bind("<Control-h>", lambda e: self.toggle_history())

        # ── 窗口大小变化时保存 ──
        self.root.bind("<Configure>", self.on_window_resize)
        self._resize_timer = None
        # ── 定时保存（捕捉分割线拖动） ──
        self._periodic_save()

    def setup_style(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("vista")
        except:
            pass
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("TLabel", background="#f0f0f0")
        self.style.configure("TButton", padding=(4, 1))

    def setup_gui(self):
        # ── 工具栏 ──
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill="x", padx=8, pady=(6, 2))

        ttk.Label(toolbar, text="划词翻译", font=("Microsoft YaHei", 10, "bold")).pack(side="left")

        self.auto_btn = ttk.Button(toolbar, text="自动", command=self.toggle_auto_copy, width=5)
        self.auto_btn.pack(side="right", padx=1)
        self.pin_btn = ttk.Button(toolbar, text="取消固定", command=self.toggle_topmost, width=8)
        self.pin_btn.pack(side="right", padx=1)
        self.history_btn = ttk.Button(toolbar, text="历史", command=self.toggle_history, width=5)
        self.history_btn.pack(side="right", padx=1)
        ttk.Button(toolbar, text="清空", command=self.clear_panel, width=4).pack(side="right", padx=1)

        # ── 可拖拽分割的面板 ──
        self.pw = ttk.PanedWindow(self.root, orient="vertical")
        self.pw.pack(fill="both", expand=True, padx=8, pady=(0, 2))

        # 上面：原文
        top_frame = tk.Frame(self.pw, bg="#ffffff",
                             highlightbackground="#d0d0d0", highlightthickness=1)
        ttk.Label(top_frame, text="📖 原文", font=("Microsoft YaHei", 9)).pack(anchor="w", padx=8, pady=(4, 0))
        self.orig_text = scrolledtext.ScrolledText(
            top_frame, height=4, wrap="word",
            font=("Microsoft YaHei", 10), fg="#222",
            bg="#fafafa", relief="flat", borderwidth=0,
            padx=4, pady=4
        )
        self.orig_text.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self.pw.add(top_frame, weight=1)

        # 下面：译文
        bot_frame = tk.Frame(self.pw, bg="#ffffff",
                             highlightbackground="#d0d0d0", highlightthickness=1)
        ttk.Label(bot_frame, text="🌐 译文", font=("Microsoft YaHei", 9)).pack(anchor="w", padx=8, pady=(4, 0))
        self.trans_text = scrolledtext.ScrolledText(
            bot_frame, height=8, wrap="word",
            font=("Microsoft YaHei", 11), fg="#1a73e8",
            bg="#fafafa", relief="flat", borderwidth=0,
            padx=4, pady=4
        )
        self.trans_text.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self.pw.add(bot_frame, weight=2)

        # ── 历史面板（单行条目，复制按钮在最右）──
        self.history_frame = tk.Frame(self.pw, bg="#ffffff",
                                      highlightbackground="#cccccc", highlightthickness=1)
        self.history_label = tk.Label(self.history_frame, text="📋 剪贴板历史", bg="#ffffff", fg="#555",
                                       font=("Microsoft YaHei", 8, "bold"), anchor="w")
        self.history_label.pack(fill="x", padx=6, pady=(3, 0))

        # 可滚动容器
        self.history_canvas = tk.Canvas(self.history_frame, bg="#fafafa", highlightthickness=0)
        self.history_scrollbar = ttk.Scrollbar(self.history_frame, orient="vertical",
                                                command=self.history_canvas.yview)
        self.history_list = tk.Frame(self.history_canvas, bg="#fafafa")

        self.history_list.bind("<Configure>", lambda e: self.history_canvas.configure(
            scrollregion=self.history_canvas.bbox("all")))
        self.history_canvas.create_window((0, 0), window=self.history_list, anchor="nw", tags="history_window")
        self.history_canvas.bind("<Configure>", lambda e: self.history_canvas.itemconfig(
            "history_window", width=e.width))
        self.history_canvas.configure(yscrollcommand=self.history_scrollbar.set)
        self.history_canvas.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(2, 4))
        self.history_scrollbar.pack(side="right", fill="y", pady=(2, 4))

        # 鼠标滚轮支持
        def _on_wheel(event):
            self.history_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.history_canvas.bind("<Enter>", lambda e: self.history_canvas.bind_all("<MouseWheel>", _on_wheel))
        self.history_canvas.bind("<Leave>", lambda e: self.history_canvas.unbind_all("<MouseWheel>"))

        self.pw.add(self.history_frame, weight=2)
        self.history_visible = True

        # ── 状态栏 ──
        self.status_var = tk.StringVar(value="就绪 — Ctrl+C 复制后自动翻译  |  工具栏「自动」开启选中即复制")
        status_bar = ttk.Label(self.root, textvariable=self.status_var,
                                font=("Microsoft YaHei", 8), foreground="#888")
        status_bar.pack(fill="x", padx=8, pady=(0, 4))

        # ── 右键菜单 ──
        self.setup_context_menu()

    def setup_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="清空面板", command=self.clear_panel)
        self.context_menu.add_command(label="切换置顶", command=self.toggle_topmost)
        self.context_menu.add_command(label="剪贴板历史", command=self.toggle_history)
        self.context_menu.add_command(label="选中即复制", command=self.toggle_auto_copy)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="退出", command=self.on_close)
        self.root.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    # ── 配置持久化 ──

    def apply_config(self):
        cfg = load_config()
        # 清理损坏的分割线数据
        if "sash_pos" in cfg and cfg["sash_pos"] and min(cfg["sash_pos"]) <= 5:
            del cfg["sash_pos"]
            save_config(cfg)
        # 先设窗口大小
        geom = cfg.get("window_geometry", "400x500")
        self.root.geometry(geom)
        # 延迟恢复其他设置（等窗口显示、PanedWindow 布局完成）
        self._cfg_restore = cfg
        self.root.after(300, self._apply_delayed)

    def _apply_delayed(self):
        """窗口显示后恢复分割线和自动复制"""
        cfg = self._cfg_restore
        if not cfg:
            return
        try:
            # 恢复分割线位置（跳过明显错误的值）
            sash_pos = cfg.get("sash_pos", [])
            if sash_pos and min(sash_pos) <= 5:
                sash_pos = []  # 有坏数据就不恢复
            for i, pos in enumerate(sash_pos):
                try:
                    self.pw.sashpos(i, pos)
                except:
                    break
            # 恢复自动复制
            if cfg.get("auto_copy", False):
                self.toggle_auto_copy()
        except:
            pass

    def on_window_resize(self, event):
        if event.widget == self.root:
            # 防抖：用户停止调整 500ms 后再保存
            if self._resize_timer:
                self.root.after_cancel(self._resize_timer)
            self._resize_timer = self.root.after(500, self._do_save_config)

    def _do_save_config(self):
        cfg = load_config()
        cfg["window_geometry"] = self.root.geometry()
        if hasattr(self, 'pw'):
            try:
                num_panes = len(self.pw.panes())
                cfg["sash_pos"] = []
                for i in range(num_panes - 1):
                    pos = self.pw.sashpos(i)
                    if pos > 5:  # 只保存有效的位置
                        cfg["sash_pos"].append(pos)
            except:
                cfg["sash_pos"] = []
        cfg["auto_copy"] = self.auto_copy
        cfg["history_visible"] = True
        save_config(cfg)

    def _periodic_save(self):
        """每3秒自动保存（主要为了捕捉分割线拖动的位置）"""
        self._do_save_config()
        self.root.after(3000, self._periodic_save)

    # ── 功能按钮 ──

    def clear_panel(self):
        self.orig_text.delete("1.0", "end")
        self.trans_text.delete("1.0", "end")
        self.status_var.set("已清空")

    def toggle_topmost(self):
        current = self.root.attributes("-topmost")
        new_state = not current
        self.root.attributes("-topmost", new_state)
        self.pin_btn.config(text="取消固定" if new_state else "固定")
        self.status_var.set("固定: " + ("开" if new_state else "关"))

    def toggle_auto_copy(self):
        """切换选中即复制模式"""
        self.auto_copy = not self.auto_copy
        self.auto_btn.config(text="自动" if self.auto_copy else "手动",
                             style="Auto.TButton" if self.auto_copy else "TButton")
        if self.auto_copy:
            self.style.configure("Auto.TButton", foreground="#1a73e8")
        self.status_var.set("选中即复制: " + ("开" if self.auto_copy else "关"))
        self._do_save_config()

        if self.auto_copy and not self.auto_copy_active:
            self.auto_copy_active = True
            self._auto_copy_loop()
        elif not self.auto_copy:
            self.auto_copy_active = False

    def _auto_copy_loop(self):
        """每 300ms 发一次 Ctrl+C，选中内容自动进入翻译"""
        if not self.auto_copy_active:
            return
        try:
            send_ctrl_c()
        except:
            pass
        self.root.after(300, self._auto_copy_loop)

    # ── 历史记录 ──

    def toggle_history(self):
        self.history_visible = not self.history_visible
        if self.history_visible:
            self.refresh_history()
            self.pw.add(self.history_frame, weight=2)
            # 等布局更新后恢复之前保存的分割线位置
            self.root.after_idle(self._restore_sashes)
            self.history_btn.config(text="隐藏")
            self.status_var.set("历史: 显示")
        else:
            # 隐藏前记住分割线位置
            self._saved_sashes = []
            try:
                for i in range(len(self.pw.panes()) - 1):
                    self._saved_sashes.append(self.pw.sashpos(i))
            except:
                pass
            self.pw.forget(self.history_frame)
            self.history_btn.config(text="历史")
            self.status_var.set("历史: 隐藏")

    def _restore_sashes(self):
        """显示历史后恢复分割线位置"""
        try:
            self.root.update_idletasks()
            sashes = getattr(self, '_saved_sashes', None)
            if not sashes or len(sashes) < 2:
                return
            for i, pos in enumerate(sashes):
                try:
                    self.pw.sashpos(i, pos)
                except:
                    break
        except:
            pass

    def refresh_history(self):
        for w in self.history_list.winfo_children():
            w.destroy()
        if not self.history:
            lbl = tk.Label(self.history_list, text="暂无记录", fg="#aaa",
                           bg="#fafafa", font=("Microsoft YaHei", 9))
            lbl.pack(padx=4, pady=6)
            return

        for orig, trans in reversed(self.history):
            # 单行显示，超长截断
            o_line = orig.replace("\n", " ").strip()
            if len(o_line) > 28:
                o_line = o_line[:25] + "..."
            t_line = trans.replace("\n", " ").strip()
            if len(t_line) > 36:
                t_line = t_line[:33] + "..."

            row = tk.Frame(self.history_list, bg="#ffffff",
                           highlightbackground="#e8e8e8", highlightthickness=1)
            row.pack(fill="x", padx=2, pady=1)

            # 原文（点击恢复）
            o_lbl = tk.Label(row, text=f"📖 {o_line}", bg="#ffffff", fg="#333",
                             font=("Microsoft YaHei", 9), anchor="w", cursor="hand2")
            o_lbl.pack(side="left", padx=(4, 0))
            o_lbl.bind("<Button-1>", lambda e, o=orig, t=trans: self.restore_from_history(o, t))
            o_lbl.bind("<Enter>", lambda e: o_lbl.configure(bg="#eef6ff"))
            o_lbl.bind("<Leave>", lambda e: o_lbl.configure(bg="#ffffff"))

            # 译文（点击恢复）
            t_lbl = tk.Label(row, text=f"🌐 {t_line}", bg="#ffffff", fg="#1a73e8",
                             font=("Microsoft YaHei", 9, "bold"), anchor="w", cursor="hand2")
            t_lbl.pack(side="left", padx=(8, 0))
            t_lbl.bind("<Button-1>", lambda e, o=orig, t=trans: self.restore_from_history(o, t))
            t_lbl.bind("<Enter>", lambda e: t_lbl.configure(bg="#eef6ff"))
            t_lbl.bind("<Leave>", lambda e: t_lbl.configure(bg="#ffffff"))

            # 复制按钮（最后面）
            tk.Button(row, text="📋", font=("Microsoft YaHei", 8),
                      bg="#f0f0f0", relief="flat", cursor="hand2",
                      command=lambda t=trans: self.copy_to_clipboard(t)
                      ).pack(side="right", padx=(0, 2))

    def restore_from_history(self, orig, trans):
        self.orig_text.delete("1.0", "end")
        self.orig_text.insert("1.0", orig)
        self.trans_text.delete("1.0", "end")
        self.trans_text.insert("1.0", trans)
        self.status_var.set("↩ 已恢复历史记录")

    def copy_to_clipboard(self, text):
        """一键复制译文到剪贴板"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("📋 已复制译文")

    # ── 剪贴板监听 ──

    def monitor_clipboard(self):
        try:
            current_seq = GetClipboardSequenceNumber()
            if current_seq != self.last_seq:
                self.last_seq = current_seq
                text = read_clipboard(self.root)
                if text and text != self.last_text and len(text) > 0 and len(text) < 5000:
                    self.last_text = text
                    self.status_var.set("翻译中...")
                    threading.Thread(target=self.do_translate, args=(text,), daemon=True).start()
        except:
            pass
        self.root.after(50, self.monitor_clipboard)

    # ── 翻译 ──

    def do_translate(self, text):
        if self.translating:
            return
        self.translating = True
        try:
            result = self._call_api(text)
            self.root.after(0, self._update_display, text, result)
        except Exception as e:
            self.root.after(0, self._show_error, str(e))
        finally:
            self.translating = False

    def _call_api(self, text):
        url = (
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl=auto&tl=zh&dt=t&q={urllib.parse.quote(text)}"
        )
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            segments = []
            for item in data[0]:
                if item and len(item) > 0 and item[0]:
                    segments.append(item[0])
            return "".join(segments)

    def _update_display(self, original, translation):
        self.orig_text.delete("1.0", "end")
        self.orig_text.insert("1.0", original)
        self.trans_text.delete("1.0", "end")
        self.trans_text.insert("1.0", translation)

        # 记录历史（最近5条）
        self.history.append((original, translation))
        if len(self.history) > 5:
            self.history.pop(0)
        if self.history_visible:
            self.refresh_history()

        self.status_var.set(f"✓ 翻译完成  |  {len(original)} 字 → {len(translation)} 字")

    def _show_error(self, error_msg):
        self.status_var.set(f"✗ 翻译失败: {error_msg}")

    def on_close(self):
        self._do_save_config()
        self.root.destroy()
        os._exit(0)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = TranslateWindow()
    app.run()
