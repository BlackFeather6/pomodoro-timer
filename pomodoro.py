"""
番茄钟桌面应用 - Pomodoro Timer

一个功能完整的桌面番茄钟应用，基于 Python tkinter 构建。
"""

import tkinter as tk
from tkinter import ttk, messagebox
import time
import json
import os
import platform
import winsound
from datetime import datetime, date
from threading import Thread


# ============================================================
# 配置
# ============================================================
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pomodoro_config.json")
STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pomodoro_stats.json")
TASKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pomodoro_tasks.json")

DEFAULT_CONFIG = {
    "work_time": 25 * 60,
    "short_break": 5 * 60,
    "long_break": 15 * 60,
    "pomodoros_before_long_break": 4,
    "auto_start_break": False,
    "auto_start_work": False,
    "sound_enabled": True,
    "always_on_top": False,
    "theme": "light",
    "window_x": None,
    "window_y": None,
}

DEFAULT_TASKS = []

DEFAULT_STATS = {
    "total_pomodoros": 0,
    "total_work_seconds": 0,
    "today_pomodoros": 0,
    "today_date": str(date.today()),
    "daily_history": {},
}


# ============================================================
# 数据持久化
# ============================================================
def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 合并默认值，确保新字段存在
                if isinstance(data, dict) and isinstance(default, dict):
                    for k, v in default.items():
                        data.setdefault(k, v)
                return data
    except Exception:
        pass
    return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存失败: {e}")


# ============================================================
# 音频播放 (非阻塞)
# ============================================================
def play_sound_async():
    """在后台线程播放系统提示音"""
    def _play():
        try:
            if platform.system() == "Windows":
                winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
            else:
                print("\a")  # 终端响铃
        except Exception:
            print("\a")
    Thread(target=_play, daemon=True).start()


# ============================================================
# 主应用
# ============================================================
class PomodoroApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("番茄钟")
        self.root.minsize(400, 500)
        self.root.geometry("480x620")

        # 加载配置
        self.config = load_json(CONFIG_FILE, DEFAULT_CONFIG)
        self.stats = load_json(STATS_FILE, DEFAULT_STATS)
        self.tasks = load_json(TASKS_FILE, DEFAULT_TASKS)

        # 状态变量
        self.mode = "work"          # work | short_break | long_break
        self.time_left = self.config["work_time"]
        self.is_running = False
        self.is_paused = False
        self.pomodoro_count = 0     # 当前连续完成的番茄数
        self.session_start_time = None
        self._timer_id = None

        # 检查每日统计重置
        self._check_daily_reset()

        # UI
        self._setup_styles()
        self._build_ui()
        self._apply_theme()
        self._restore_window_position()
        self._update_display()

        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- 每日统计 ----------
    def _check_daily_reset(self):
        today = str(date.today())
        if self.stats.get("today_date") != today:
            self.stats["today_date"] = today
            self.stats["today_pomodoros"] = 0
            save_json(STATS_FILE, self.stats)

    # ---------- 样式 ----------
    def _setup_styles(self):
        style = ttk.Style()
        self._style = style
        # 不同主题下使用不同颜色
        self.colors = {
            "light": {
                "bg": "#f5f5f5",
                "fg": "#333333",
                "card": "#ffffff",
                "accent": "#e74c3c",
                "accent2": "#2ecc71",
                "accent3": "#f39c12",
                "timer": "#2c3e50",
                "btn_bg": "#e74c3c",
                "btn_fg": "#ffffff",
                "secondary_btn": "#ecf0f1",
                "secondary_fg": "#333333",
                "border": "#dddddd",
                "text_secondary": "#888888",
            },
            "dark": {
                "bg": "#1e1e1e",
                "fg": "#e0e0e0",
                "card": "#2d2d2d",
                "accent": "#e74c3c",
                "accent2": "#2ecc71",
                "accent3": "#f39c12",
                "timer": "#ffffff",
                "btn_bg": "#e74c3c",
                "btn_fg": "#ffffff",
                "secondary_btn": "#3d3d3d",
                "secondary_fg": "#e0e0e0",
                "border": "#444444",
                "text_secondary": "#999999",
            }
        }
        self._current_colors = self.colors.get(self.config.get("theme", "light"), self.colors["light"])

    def _apply_theme(self):
        c = self._current_colors
        self.root.configure(bg=c["bg"])
        # 主框架
        for widget in [self.main_frame, self.timer_frame, self.control_frame,
                       self.top_frame, self.task_frame, self.stats_frame]:
            try:
                widget.configure(bg=c["bg"])
            except:
                pass

        # 更新计时器标签
        try:
            self.timer_label.configure(bg=c["bg"], fg=c["timer"])
        except:
            pass
        try:
            self.mode_label.configure(bg=c["bg"], fg=c["accent"] if self.mode == "work" else c["accent2"])
        except:
            pass
        try:
            self.pomo_label.configure(bg=c["bg"], fg=c["text_secondary"])
        except:
            pass

        # stats
        try:
            self.stats_pomo_label.configure(bg=c["bg"], fg=c["fg"])
            self.stats_today_label.configure(bg=c["bg"], fg=c["text_secondary"])
        except:
            pass

        # 任务列表
        try:
            self.task_listbox.configure(
                bg=c["card"] if c["card"] else "#ffffff",
                fg=c["fg"],
                selectbackground=c["accent"],
                selectforeground="#ffffff",
                relief="flat",
                highlightthickness=1,
                highlightbackground=c["border"],
                highlightcolor=c["border"],
            )
        except:
            pass

        # 任务输入框
        try:
            self.task_entry.configure(bg=c["card"], fg=c["fg"],
                                       insertbackground=c["fg"],
                                       relief="flat",
                                       highlightthickness=1,
                                       highlightbackground=c["border"],
                                       highlightcolor=c["accent"])
        except:
            pass

    # ---------- UI 构建 ----------
    def _build_ui(self):
        c = self._current_colors
        bg = c["bg"]

        self.main_frame = tk.Frame(self.root, bg=bg)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=15)

        # ========== 顶部：模式 + 番茄计数 ==========
        self.top_frame = tk.Frame(self.main_frame, bg=bg)
        self.top_frame.pack(fill="x", pady=(0, 10))

        self.mode_label = tk.Label(
            self.top_frame,
            text="工作时间",
            font=("Segoe UI", 14, "bold"),
            bg=bg,
            fg=c["accent"],
        )
        self.mode_label.pack(side="left")

        self.pomo_label = tk.Label(
            self.top_frame,
            text="🍅 0",
            font=("Segoe UI", 11),
            bg=bg,
            fg=c["text_secondary"],
        )
        self.pomo_label.pack(side="right")

        # ========== 计时器显示 ==========
        self.timer_frame = tk.Frame(self.main_frame, bg=bg)
        self.timer_frame.pack(fill="x", pady=10)

        self.canvas = tk.Canvas(
            self.timer_frame,
            width=260,
            height=260,
            bg=bg,
            highlightthickness=0,
        )
        self.canvas.pack()

        self.timer_label = tk.Label(
            self.timer_frame,
            text="25:00",
            font=("Segoe UI", 56, "bold"),
            bg=bg,
            fg=c["timer"],
        )
        self.timer_label.place(relx=0.5, rely=0.5, anchor="center")

        # 绑定 canvas 尺寸更新
        self.canvas.bind("<Configure>", self._draw_progress)

        # ========== 控制按钮 ==========
        self.control_frame = tk.Frame(self.main_frame, bg=bg)
        self.control_frame.pack(fill="x", pady=15)

        self._create_button(self.control_frame, "▶ 开始", self._toggle_start,
                           c["btn_bg"], c["btn_fg"], 0, 0, padx=(0, 5))
        self._create_button(self.control_frame, "⏸ 暂停", self._toggle_pause,
                           c["secondary_btn"], c["secondary_fg"], 0, 1, padx=(5, 5))
        self._create_button(self.control_frame, "↺ 重置", self._reset,
                           c["secondary_btn"], c["secondary_fg"], 0, 2, padx=(5, 0))

        self.control_frame.columnconfigure(0, weight=1)
        self.control_frame.columnconfigure(1, weight=1)
        self.control_frame.columnconfigure(2, weight=1)

        # ========== 信息统计 ==========
        self.stats_frame = tk.Frame(self.main_frame, bg=bg)
        self.stats_frame.pack(fill="x", pady=5)

        self.stats_pomo_label = tk.Label(
            self.stats_frame,
            text="今日番茄: 0 个",
            font=("Segoe UI", 11),
            bg=bg,
            fg=c["fg"],
        )
        self.stats_pomo_label.pack(side="left", padx=(0, 15))

        self.stats_today_label = tk.Label(
            self.stats_frame,
            text="总番茄: 0 个",
            font=("Segoe UI", 11),
            bg=bg,
            fg=c["text_secondary"],
        )
        self.stats_today_label.pack(side="left")

        # ========== 任务列表 ==========
        self.task_frame = tk.Frame(self.main_frame, bg=bg)
        self.task_frame.pack(fill="both", expand=True, pady=(15, 5))

        task_header_frame = tk.Frame(self.task_frame, bg=bg)
        task_header_frame.pack(fill="x", pady=(0, 5))

        tk.Label(
            task_header_frame,
            text="📋 任务列表",
            font=("Segoe UI", 12, "bold"),
            bg=bg,
            fg=c["fg"],
        ).pack(side="left")

        self._create_small_button(task_header_frame, "清空", self._clear_tasks,
                                  c["text_secondary"], "#ffffff", side="right", padx=(5, 0))
        self._create_small_button(task_header_frame, "完成 ✓", self._complete_task,
                                  c["accent2"], "#ffffff", side="right", padx=(5, 0))
        self._create_small_button(task_header_frame, "删除 ✕", self._delete_task,
                                  c["accent"], "#ffffff", side="right", padx=(5, 0))

        # 任务输入行
        input_frame = tk.Frame(self.task_frame, bg=bg)
        input_frame.pack(fill="x", pady=(0, 5))

        self.task_entry = tk.Entry(
            input_frame,
            font=("Segoe UI", 11),
            bg=c["card"],
            fg=c["fg"],
            insertbackground=c["fg"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=c["border"],
            highlightcolor=c["accent"],
        )
        self.task_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.task_entry.bind("<Return>", lambda e: self._add_task())

        self._create_small_button(input_frame, "添加", self._add_task,
                                  c["accent"], "#ffffff", side="right", padx=(5, 0))

        # 任务列表
        list_frame = tk.Frame(self.task_frame, bg=c["card"], highlightbackground=c["border"], highlightthickness=1)
        list_frame.pack(fill="both", expand=True)

        self.task_listbox = tk.Listbox(
            list_frame,
            font=("Segoe UI", 11),
            bg=c["card"],
            fg=c["fg"],
            selectbackground=c["accent"],
            selectforeground="#ffffff",
            relief="flat",
            highlightthickness=0,
            borderwidth=0,
            activestyle="none",
            height=6,
        )
        self.task_listbox.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.task_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.task_listbox.configure(yscrollcommand=scrollbar.set)

        # ========== 底部：设置按钮 ==========
        bottom_frame = tk.Frame(self.main_frame, bg=bg)
        bottom_frame.pack(fill="x", pady=(5, 0))

        self._create_small_button(bottom_frame, "⚙ 设置", self._open_settings,
                                  c["text_secondary"], bg, side="left")
        self._create_small_button(bottom_frame, "📊 统计", self._open_stats,
                                  c["text_secondary"], bg, side="right")

        # 填充任务数据
        self._refresh_task_list()

    def _create_button(self, parent, text, command, bg, fg, row, col, padx=(5, 5)):
        btn = tk.Button(
            parent,
            text=text,
            font=("Segoe UI", 11, "bold"),
            bg=bg,
            fg=fg,
            relief="flat",
            activebackground=bg,
            activeforeground=fg,
            cursor="hand2",
            command=command,
            bd=0,
            padx=8,
            pady=6,
        )
        btn.grid(row=row, column=col, sticky="ew", padx=padx, ipady=2)
        btn.bind("<Enter>", lambda e, b=btn, c=bg: self._on_btn_hover(b, c, True))
        btn.bind("<Leave>", lambda e, b=btn, c=bg: self._on_btn_hover(b, c, False))
        return btn

    def _create_small_button(self, parent, text, command, bg, fg, side="left", padx=(0, 0)):
        btn = tk.Button(
            parent,
            text=text,
            font=("Segoe UI", 10),
            bg=bg,
            fg=fg,
            relief="flat",
            activebackground=bg,
            activeforeground=fg,
            cursor="hand2",
            command=command,
            bd=0,
            padx=6,
            pady=2,
        )
        btn.pack(side=side, padx=padx)
        return btn

    def _on_btn_hover(self, btn, color, enter):
        try:
            if enter:
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                factor = 0.85
                r, g, b = int(r * factor), int(g * factor), int(b * factor)
                hover = f"#{r:02x}{g:02x}{b:02x}"
            else:
                hover = color
            btn.configure(bg=hover)
        except:
            btn.configure(bg=color if not enter else color)

    # ---------- 计时器逻辑 ----------
    def _draw_progress(self, event=None):
        self.canvas.delete("progress")
        w = self.canvas.winfo_width() or 260
        h = self.canvas.winfo_height() or 260
        cx, cy = w // 2, h // 2
        r = min(cx, cy) - 15

        # 计算进度
        total = self._get_total_time()
        progress = 1.0 - (self.time_left / total) if total > 0 else 0

        c = self._current_colors
        accent = c["accent"] if self.mode == "work" else (c["accent2"] if self.mode == "short_break" else c["accent3"])

        # 背景圆环
        self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            outline=c["border"],
            width=6,
            tags="progress",
        )

        # 进度弧
        if progress > 0:
            start_angle = 90
            extent = -360 * progress
            self.canvas.create_arc(
                cx - r, cy - r, cx + r, cy + r,
                start=start_angle,
                extent=extent,
                outline=accent,
                width=6,
                style="arc",
                tags="progress",
            )

    def _get_total_time(self):
        if self.mode == "work":
            return self.config["work_time"]
        elif self.mode == "short_break":
            return self.config["short_break"]
        else:
            return self.config["long_break"]

    def _update_display(self):
        minutes = self.time_left // 60
        seconds = self.time_left % 60
        self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}")

        # 窗口标题更新
        if self.is_running and not self.is_paused:
            mode_text = "🍅 工作中" if self.mode == "work" else "☕ 休息中"
            self.root.title(f"{mode_text} - {minutes:02d}:{seconds:02d}")
        else:
            self.root.title("番茄钟")

        # 更新进度环
        self._draw_progress()

        # 更新番茄计数
        self.pomo_label.config(text=f"🍅 {self.pomodoro_count}")

        # 更新统计显示
        today = self.stats.get("today_pomodoros", 0)
        total = self.stats.get("total_pomodoros", 0)
        self.stats_pomo_label.config(text=f"今日: {today} 个")
        self.stats_today_label.config(text=f"总计: {total} 个")

    def _toggle_start(self):
        if not self.is_running:
            self._start()
        else:
            self._pause()

    def _start(self):
        if self.time_left <= 0:
            self._reset()

        self.is_running = True
        self.is_paused = False
        self.session_start_time = time.time()

        # 更新按钮颜色
        for child in self.control_frame.winfo_children():
            if isinstance(child, tk.Button) and "暂停" in child.cget("text"):
                child.configure(bg=self._current_colors["accent"], fg="#ffffff")

        self._tick()

    def _pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            # 暂停状态
            for child in self.control_frame.winfo_children():
                if isinstance(child, tk.Button) and "暂停" in child.cget("text"):
                    child.configure(text="▶ 继续")
                    child.configure(bg=self._current_colors["accent"], fg="#ffffff")
            if self._timer_id:
                self.root.after_cancel(self._timer_id)
                self._timer_id = None
        else:
            # 继续
            for child in self.control_frame.winfo_children():
                if isinstance(child, tk.Button) and "继续" in child.cget("text"):
                    child.configure(text="⏸ 暂停")
                    child.configure(bg=self._current_colors["secondary_btn"], fg=self._current_colors["secondary_fg"])
            self._tick()

    def _toggle_pause(self):
        if not self.is_running:
            return
        self._pause()

    def _reset(self):
        if self._timer_id:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None

        self.is_running = False
        self.is_paused = False

        # 重置计时
        if self.mode == "work":
            self.time_left = self.config["work_time"]
        elif self.mode == "short_break":
            self.time_left = self.config["short_break"]
        else:
            self.time_left = self.config["long_break"]

        # 恢复按钮文字
        for child in self.control_frame.winfo_children():
            if isinstance(child, tk.Button):
                if "暂停" in child.cget("text") or "继续" in child.cget("text"):
                    child.configure(text="⏸ 暂停", bg=self._current_colors["secondary_btn"], fg=self._current_colors["secondary_fg"])

        self._update_display()

    def _tick(self):
        if not self.is_running or self.is_paused:
            return

        now = time.time()
        elapsed = now - self.session_start_time
        total = self._get_total_time()
        self.time_left = max(0, total - int(elapsed))

        self._update_display()

        if self.time_left <= 0:
            self._on_timer_complete()
            return

        self._timer_id = self.root.after(200, self._tick)

    def _on_timer_complete(self):
        self._timer_id = None
        self.is_running = False

        # 播放提示音
        if self.config.get("sound_enabled", True):
            play_sound_async()

        if self.mode == "work":
            # 完成一个番茄
            self.pomodoro_count += 1
            self.stats["total_pomodoros"] = self.stats.get("total_pomodoros", 0) + 1
            self.stats["today_pomodoros"] = self.stats.get("today_pomodoros", 0) + 1
            save_json(STATS_FILE, self.stats)

            # 弹出提醒
            self._show_notification("🍅 番茄完成！", f"已完成 {self.pomodoro_count} 个番茄，该休息一下了！")

            # 决定短休息还是长休息
            if self.pomodoro_count % self.config["pomodoros_before_long_break"] == 0:
                self._switch_mode("long_break")
            else:
                self._switch_mode("short_break")

            if self.config.get("auto_start_break", False):
                self._start()
        else:
            # 休息结束
            self._show_notification("☕ 休息结束", "休息时间到，开始新的番茄吧！")
            self._switch_mode("work")

            if self.config.get("auto_start_work", False):
                self._start()

        self._update_display()

    def _switch_mode(self, new_mode):
        self.mode = new_mode
        c = self._current_colors

        if new_mode == "work":
            self.time_left = self.config["work_time"]
            self.mode_label.config(text="工作时间", fg=c["accent"])
        elif new_mode == "short_break":
            self.time_left = self.config["short_break"]
            self.mode_label.config(text="短休息", fg=c["accent2"])
        elif new_mode == "long_break":
            self.time_left = self.config["long_break"]
            self.mode_label.config(text="长休息 🎉", fg=c["accent3"])

    def _show_notification(self, title, message):
        """显示通知（尝试不同方式）"""
        try:
            if platform.system() == "Windows":
                from plyer import notification
                notification.notify(title=title, message=message, app_name="番茄钟", timeout=5)
                return
        except ImportError:
            pass

        try:
            self.root.attributes("-topmost", True)
            self.root.attributes("-topmost", self.config.get("always_on_top", False))
        except:
            pass

    # ---------- 任务管理 ----------
    def _add_task(self):
        task = self.task_entry.get().strip()
        if task:
            self.tasks.append({"text": task, "done": False, "created": str(datetime.now())})
            save_json(TASKS_FILE, self.tasks)
            self._refresh_task_list()
            self.task_entry.delete(0, tk.END)

    def _delete_task(self):
        sel = self.task_listbox.curselection()
        if sel:
            idx = sel[0]
            del self.tasks[idx]
            save_json(TASKS_FILE, self.tasks)
            self._refresh_task_list()

    def _complete_task(self):
        sel = self.task_listbox.curselection()
        if sel:
            idx = sel[0]
            self.tasks[idx]["done"] = not self.tasks[idx]["done"]
            save_json(TASKS_FILE, self.tasks)
            self._refresh_task_list()

    def _clear_tasks(self):
        if self.tasks and messagebox.askyesno("清空任务", "确定要清空所有任务吗？"):
            self.tasks = []
            save_json(TASKS_FILE, self.tasks)
            self._refresh_task_list()

    def _refresh_task_list(self):
        self.task_listbox.delete(0, tk.END)
        for task in self.tasks:
            text = task.get("text", "")
            done = task.get("done", False)
            display = f"{'✓ ' if done else '  '}{text}"
            self.task_listbox.insert(tk.END, display)
            if done:
                self.task_listbox.itemconfig(tk.END, fg=self._current_colors.get("text_secondary", "#888888"))

    # ---------- 设置窗口 ----------
    def _open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("设置")
        win.geometry("420x450")
        win.configure(bg=self._current_colors["bg"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        # 映射标签文本和配置键
        fields = [
            ("工作时间 (分钟)", "work_time", 1, 60),
            ("短休息 (分钟)", "short_break", 1, 30),
            ("长休息 (分钟)", "long_break", 1, 60),
            ("长休息前番茄数", "pomodoros_before_long_break", 1, 20),
        ]

        entries = {}
        row = 0
        for label, key, min_v, max_v in fields:
            tk.Label(win, text=label, font=("Segoe UI", 11),
                     bg=win.cget("bg"), fg=self._current_colors["fg"]).grid(
                row=row, column=0, sticky="w", padx=20, pady=(15 if row == 0 else 8))

            var = tk.StringVar(value=str(self.config[key] // 60 if key.endswith("time") else self.config[key]))
            entry = tk.Spinbox(win, from_=min_v, to=max_v, textvariable=var,
                               font=("Segoe UI", 11), width=8,
                               bg=self._current_colors["card"], fg=self._current_colors["fg"],
                               relief="flat", buttonbackground=self._current_colors["secondary_btn"])
            entry.grid(row=row, column=1, sticky="e", padx=20, pady=(15 if row == 0 else 8), ipady=2)
            entries[key] = (var, min_v, max_v)
            row += 1

        # 开关选项
        checkboxes = [
            ("自动开始休息", "auto_start_break"),
            ("自动开始工作", "auto_start_work"),
            ("启用提示音", "sound_enabled"),
            ("窗口置顶", "always_on_top"),
        ]

        cb_vars = {}
        for label, key in checkboxes:
            var = tk.BooleanVar(value=self.config.get(key, False))
            cb = tk.Checkbutton(win, text=label, variable=var,
                                font=("Segoe UI", 11),
                                bg=win.cget("bg"), fg=self._current_colors["fg"],
                                selectcolor=self._current_colors["card"],
                                activebackground=win.cget("bg"),
                                activeforeground=self._current_colors["fg"],
                                relief="flat")
            cb.grid(row=row, column=0, columnspan=2, sticky="w", padx=20, pady=5)
            cb_vars[key] = var
            row += 1

        # 主题选择
        tk.Label(win, text="主题", font=("Segoe UI", 11),
                 bg=win.cget("bg"), fg=self._current_colors["fg"]).grid(
            row=row, column=0, sticky="w", padx=20, pady=(8, 20))

        theme_var = tk.StringVar(value=self.config.get("theme", "light"))
        theme_combo = ttk.Combobox(win, textvariable=theme_var, values=["light", "dark"],
                                    state="readonly", font=("Segoe UI", 11), width=8)
        theme_combo.grid(row=row, column=1, sticky="e", padx=20, pady=(8, 20))
        row += 1

        def save_settings():
            try:
                for key, (var, min_v, max_v) in entries.items():
                    val = int(var.get())
                    val = max(min_v, min(max_v, val))
                    if key.endswith("time"):
                        self.config[key] = val * 60
                    else:
                        self.config[key] = val

                for key, var in cb_vars.items():
                    self.config[key] = var.get()

                self.config["theme"] = theme_var.get()

                save_json(CONFIG_FILE, self.config)

                # 应用主题
                self._current_colors = self.colors.get(self.config["theme"], self.colors["light"])
                self._apply_theme()

                # 如果当前没有运行，重置计时
                if not self.is_running:
                    self._reset()

                self._update_display()

                # 置顶
                self.root.attributes("-topmost", self.config.get("always_on_top", False))

                win.destroy()
            except ValueError:
                messagebox.showerror("输入错误", "请输入有效的数字")

        # 按钮
        btn_frame = tk.Frame(win, bg=win.cget("bg"))
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(0, 15))

        tk.Button(btn_frame, text="保存", command=save_settings,
                  font=("Segoe UI", 11, "bold"), bg=self._current_colors["accent"],
                  fg="#ffffff", relief="flat", padx=20, pady=4, bd=0,
                  activebackground=self._current_colors["accent"],
                  activeforeground="#ffffff", cursor="hand2").pack(side="left", padx=5)

        tk.Button(btn_frame, text="取消", command=win.destroy,
                  font=("Segoe UI", 11), bg=self._current_colors["secondary_btn"],
                  fg=self._current_colors["secondary_fg"], relief="flat", padx=15, pady=4, bd=0,
                  activebackground=self._current_colors["secondary_btn"],
                  activeforeground=self._current_colors["secondary_fg"], cursor="hand2").pack(side="left", padx=5)

    # ---------- 统计窗口 ----------
    def _open_stats(self):
        win = tk.Toplevel(self.root)
        win.title("统计")
        win.geometry("400x350")
        win.configure(bg=self._current_colors["bg"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        bg = self._current_colors["bg"]
        fg = self._current_colors["fg"]
        card = self._current_colors["card"]
        sec = self._current_colors["text_secondary"]

        # 统计卡片
        data = [
            ("总番茄数", f"{self.stats.get('total_pomodoros', 0)} 个"),
            ("今日番茄", f"{self.stats.get('today_pomodoros', 0)} 个"),
            ("总工作时间", f"{self._format_seconds(self.stats.get('total_work_seconds', 0))}"),
        ]

        for i, (label, value) in enumerate(data):
            frame = tk.Frame(win, bg=card, highlightbackground=self._current_colors["border"], highlightthickness=1)
            frame.pack(fill="x", padx=25, pady=(20 if i == 0 else 8))

            tk.Label(frame, text=label, font=("Segoe UI", 11),
                     bg=card, fg=sec).pack(side="left", padx=15, pady=12)
            tk.Label(frame, text=value, font=("Segoe UI", 16, "bold"),
                     bg=card, fg=fg).pack(side="right", padx=15, pady=12)

        # 每日历史 (最近7天)
        daily = self.stats.get("daily_history", {})
        if daily:
            tk.Label(win, text="近7天记录", font=("Segoe UI", 11, "bold"),
                     bg=bg, fg=fg).pack(pady=(20, 5))

            history_frame = tk.Frame(win, bg=bg)
            history_frame.pack(fill="x", padx=25)

            sorted_dates = sorted(daily.keys(), reverse=True)[:7]
            for d in sorted_dates:
                count = daily[d]
                tk.Label(history_frame, text=d, font=("Segoe UI", 10),
                         bg=bg, fg=sec).pack(side="left", padx=(0, 8))
                bar_w = min(count * 30, 200)
                bar = tk.Frame(history_frame, bg=self._current_colors["accent"], height=16, width=max(bar_w, 2))
                bar.pack(side="left", pady=2)
                tk.Label(history_frame, text=f"{count}个", font=("Segoe UI", 10),
                         bg=bg, fg=fg).pack(side="left", padx=5)

        # 关闭按钮
        tk.Button(win, text="关闭", command=win.destroy,
                  font=("Segoe UI", 11), bg=self._current_colors["secondary_btn"],
                  fg=self._current_colors["secondary_fg"], relief="flat", padx=20, pady=4, bd=0,
                  cursor="hand2").pack(pady=20)

    def _format_seconds(self, secs):
        hours = secs // 3600
        mins = (secs % 3600) // 60
        if hours > 0:
            return f"{hours}小时{mins}分钟"
        return f"{mins}分钟"

    # ---------- 窗口状态 ----------
    def _restore_window_position(self):
        x = self.config.get("window_x")
        y = self.config.get("window_y")
        if x is not None and y is not None:
            self.root.geometry(f"+{x}+{y}")

    def _on_close(self):
        # 保存窗口位置
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.config["window_x"] = x
        self.config["window_y"] = y
        save_json(CONFIG_FILE, self.config)

        # 停止计时器
        if self._timer_id:
            self.root.after_cancel(self._timer_id)

        self.root.destroy()

    def run(self):
        self.root.attributes("-topmost", self.config.get("always_on_top", False))
        self.root.mainloop()


# ============================================================
# 程序入口
# ============================================================
def main():
    app = PomodoroApp()
    app.run()


if __name__ == "__main__":
    main()
