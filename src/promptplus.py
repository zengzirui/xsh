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
        if self.file: 
            self.load()

    def append(self, cmd: str, cwd: str = ""):
        if not cmd: 
            return
        self._history.append({"history": cmd, "cwd": cwd})
        if len(self._history) > self.max_size:
            self._history[:] = self._history[-self.max_size:]
        if self.file: 
            self.save()

    def __len__(self): 
        return len(self._history)
        
    def __getitem__(self, idx): 
        return self._history[idx]
        
    def cmd_at(self, idx): 
        return self._history[idx]["history"]

    def load(self):
        if not self.file or not os.path.exists(self.file): 
            return
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
        if not self.file: 
            return
        d = os.path.dirname(os.path.abspath(self.file))
        if d: 
            os.makedirs(d, exist_ok=True)
        tmp = self.file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._history, f, ensure_ascii=False, indent=0)
        os.replace(tmp, self.file)

def char_width(c):
    if unicodedata.combining(c): 
        return 0
    if unicodedata.east_asian_width(c) in ('W', 'F'): 
        return 2
    return 1

def text_width(s):
    return sum(char_width(c) for c in s)

def redraw(buf, cursor, last_w, check_cmd_func=None):
    buf_str = "".join(buf)
    buf_w = text_width(buf_str)
    
    out = ""
    
    # 1. Move physical cursor to the end of input area
    cur_remaining = text_width("".join(buf[cursor:]))
    if cur_remaining > 0:
        out += f"\033[{cur_remaining}C"

    # 2. Move physical cursor back to the start of input area
    if last_w > 0:
        out += f"\033[{last_w}D"

    # 3. Print the text with syntax highlighting
    if check_cmd_func and buf_str:
        cmd_end = buf_str.find(" ")
        if cmd_end == -1:
            cmd_str = buf_str
            rest = ""
        else:
            cmd_str = buf_str[:cmd_end]
            rest = buf_str[cmd_end:]
            
        # Green for existing, Red for not existing
        color = "\033[32m" if check_cmd_func(cmd_str) else "\033[31m"
        out += color + cmd_str + "\033[0m" + rest
    else:
        out += buf_str

    # 4. Erase leftover characters
    if buf_w < last_w:
        out += "\033[K"

    # 5. Move cursor to the correct input position
    new_remaining = text_width("".join(buf[cursor:]))
    if new_remaining > 0:
        out += f"\033[{new_remaining}D"

    sys.stdout.write(out)
    sys.stdout.flush()
    
    return buf_w

def prompt(msg, hist: History, cwd: str = "", check_cmd_func=None):
    buf = []
    cursor = 0
    hist_idx = None
    draft = []
    is_pasting = False

    sys.stdout.write(msg)
    sys.stdout.flush()
    last_w = 0

    while True:
        k = readchar.readkey()

        # Handle Bracketed Paste Mode
        if k == "\x1b[200~":
            is_pasting = True
            continue
        elif k == "\x1b[201~":
            is_pasting = False
            last_w = redraw(buf, cursor, last_w, check_cmd_func)
            continue

        if is_pasting:
            if k in ("\r", "\n"):
                k = "\n"
            buf.insert(cursor, k)
            cursor += 1
            continue

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
            last_w = redraw(buf, cursor, last_w, check_cmd_func)
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
            last_w = redraw(buf, cursor, last_w, check_cmd_func)
            continue

        elif k == key.LEFT:
            if cursor > 0:
                cursor -= 1
                w = char_width(buf[cursor])
                if w > 0: 
                    sys.stdout.write(f"\033[{w}D")
                    sys.stdout.flush()
            continue

        elif k == key.RIGHT:
            if cursor < len(buf):
                w = char_width(buf[cursor])
                cursor += 1
                if w > 0: 
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
            sys.stdout.write("\n")
            sys.stdout.flush()
            hist.append(line, cwd=cwd)
            return line

        elif k in BACKSPACE_KEYS:
            if cursor > 0:
                buf.pop(cursor - 1)
                cursor -= 1
                last_w = redraw(buf, cursor, last_w, check_cmd_func)
            continue

        elif k in DELETE_KEYS:
            if cursor < len(buf):
                buf.pop(cursor)
                last_w = redraw(buf, cursor, last_w, check_cmd_func)
            continue

        elif k == "\x03":
            raise KeyboardInterrupt
        elif k == "\x04":
            raise EOFError

        elif len(k) == 1 and k.isprintable():
            buf.insert(cursor, k)
            cursor += 1
            last_w = redraw(buf, cursor, last_w, check_cmd_func)
            continue