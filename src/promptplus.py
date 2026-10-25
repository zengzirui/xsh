import os
import sys
import json
import unicodedata
import readchar
from readchar import key

MAX_HISTORY = 100
DEFAULT_HISTORY_FILE = os.path.expanduser("~/.xsh_history")

HOME_KEYS = {key.HOME, "\x1b[1~", "\x1b[7~", "\x1bOH"}
END_KEYS = {key.END, "\x1b[4~", "\x1b[8~", "\x1bOF"}
BACKSPACE_KEYS = {key.BACKSPACE, "\x08", "\x7f"}
DELETE_KEYS = {key.DELETE, "\x1b[3~"}

class History:
    def __init__(self, file: str = ""):
        self.file = file
        self._history = []
        self.max_size = MAX_HISTORY
        if self.file: self.load()

    def append(self, cmd: str, cwd: str = ""):
        if not cmd: return
        self._history.append({"history": cmd, "cwd": cwd})
        if len(self._history) > self.max_size:
            self._history[:] = self._history[-self.max_size:]
        if self.file: self.save()

    def __len__(self): return len(self._history)
    def __getitem__(self, idx): return self._history[idx]
    def cmd_at(self, idx): return self._history[idx]["history"]

    def load(self):
        if not self.file or not os.path.exists(self.file): return
        try:
            with open(self.file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._history = [
                    {"history": item if isinstance(item, str) else item["history"], 
                     "cwd": "" if isinstance(item, str) else item.get("cwd", "")} 
                    for item in data
                ][-self.max_size:]
        except:
            self._history = []

    def save(self):
        if not self.file: return
        d = os.path.dirname(os.path.abspath(self.file))
        if d: os.makedirs(d, exist_ok=True)
        tmp = self.file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._history, f, ensure_ascii=False, indent=0)
        os.replace(tmp, self.file)

def char_width(c):
    if unicodedata.combining(c): return 0
    if unicodedata.east_asian_width(c) in ('W', 'F'): return 2
    return 1

def text_width(s):
    return sum(char_width(c) for c in s)

def redraw(buf, cursor, last_w):
    """
    💡 核心逻辑：纯局部覆盖，绝不使用 \r，绝不碰上一行！
    """
    buf_str = "".join(buf)
    buf_w = text_width(buf_str)
    
    out = ""
    
    # 1. 如果此时光标在中间，先把它移到输入区的末尾（为了下一步统一起点）
    cur_remaining = text_width("".join(buf[cursor:]))
    if cur_remaining > 0:
        out += f"\033[{cur_remaining}C"

    # 2. 把光标从输入区末尾，退回到输入区的起点
    if last_w > 0:
        out += f"\033[{last_w}D"

    # 3. 打印全新的输入内容
    out += buf_str

    # 4. 如果新内容比旧内容短（比如按了退格），擦掉尾部残存的旧字符
    # \033[K 只作用于光标右侧，绝不会跨越行首去删前面的提示符
    if buf_w < last_w:
        out += "\033[K"

    # 5. 把光标退回当前应该待的位置
    new_remaining = text_width("".join(buf[cursor:]))
    if new_remaining > 0:
        out += f"\033[{new_remaining}D"

    sys.stdout.write(out)
    sys.stdout.flush()
    
    # 返回新的输入区宽度
    return buf_w

def prompt(msg, hist: History, cwd: str = ""):
    buf = []
    cursor = 0
    hist_idx = None
    draft = []

    # 💡 首次进入时，只在当前光标位置打印一次提示符，不加任何回车符！
    sys.stdout.write(msg)
    sys.stdout.flush()
    
    last_w = 0

    while True:
        k = readchar.readkey()

        if k == key.UP:
            if len(hist) == 0: continue
            if hist_idx is None:
                draft = buf.copy()
                hist_idx = len(hist) - 1
                buf = list(hist.cmd_at(hist_idx))
            elif hist_idx - 1 >= 0:
                hist_idx -= 1
                buf = list(hist.cmd_at(hist_idx))
            else:
                continue
            cursor = len(buf)
            last_w = redraw(buf, cursor, last_w)
            continue

        elif k == key.DOWN:
            if hist_idx is None: continue
            elif hist_idx + 1 < len(hist):
                hist_idx += 1
                buf = list(hist.cmd_at(hist_idx))
            else:
                hist_idx = None
                buf = draft.copy()
            cursor = len(buf)
            last_w = redraw(buf, cursor, last_w)
            continue

        elif k == key.LEFT:
            if cursor > 0:
                cursor -= 1
                w = char_width(buf[cursor])
                if w > 0: 
                    # 💡 移动光标不重绘，直接原地理性退格，极度丝滑
                    sys.stdout.write(f"\033[{w}D")
                    sys.stdout.flush()
            continue

        elif k == key.RIGHT:
            if cursor < len(buf):
                w = char_width(buf[cursor])
                cursor += 1
                if w > 0: 
                    # 💡 移动光标不重绘，直接原地理性前进
                    sys.stdout.write(f"\033[{w}C")
                    sys.stdout.flush()
            continue

        elif k in HOME_KEYS:
            remaining = text_width("".join(buf[cursor:]))
            if remaining > 0:
                sys.stdout.write(f"\033[{remaining}D")
                sys.stdout.flush()
            cursor = 0
            continue

        elif k in END_KEYS:
            remaining = text_width("".join(buf[cursor:]))
            if remaining > 0:
                sys.stdout.write(f"\033[{remaining}C")
                sys.stdout.flush()
            cursor = len(buf)
            continue

        elif k == key.ENTER:
            line = "".join(buf)
            # 💡 回车时只发一个换行符，不管上一行有没有换行，这里都会强制另起一行
            sys.stdout.write("\n")
            sys.stdout.flush()
            hist.append(line, cwd=cwd)
            return line

        elif k in BACKSPACE_KEYS:
            if cursor > 0:
                buf.pop(cursor - 1)
                cursor -= 1
                last_w = redraw(buf, cursor, last_w)
            continue

        elif k in DELETE_KEYS:
            if cursor < len(buf):
                buf.pop(cursor)
                last_w = redraw(buf, cursor, last_w)
            continue

        elif k == "\x03":
            raise KeyboardInterrupt
        elif k == "\x04":
            raise EOFError

        elif len(k) == 1 and k.isprintable():
            buf.insert(cursor, k)
            cursor += 1
            last_w = redraw(buf, cursor, last_w)
            continue