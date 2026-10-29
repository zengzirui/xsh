import loguru
import datetime
import os
import inspect
import pathlib
import sys
import subprocess
import threading
import concurrent.futures
from queue import Queue
from rich.console import Console
from rich.markup import escape
from rich.text import Text
import locale
import shutil

import promptplus

sys_encoding = locale.getpreferredencoding(False)

class SentinelValue:
    def __bool__(self):
        return False

donot_have_sentinel = SentinelValue()

try:
    from errors.commanderror import *
except ImportError:
    class XsError(Exception): pass

# ---------------- Path & Logging Initialization ----------------
if getattr(sys, "frozen", False):
    PROJECTDIR = pathlib.Path(sys.executable).parent
else:
    PROJECTDIR = pathlib.Path(__file__).resolve().parent.parent

pathlib.Path(PROJECTDIR / "logs").mkdir(exist_ok=True)
datedir = datetime.datetime.now().strftime("%Y-%m-%d")
datefile = datetime.datetime.now().strftime("%Hh%Mm%Ss")
pathlib.Path(PROJECTDIR / "logs" / datedir).mkdir(exist_ok=True)
logfile = (PROJECTDIR / "logs" / datedir / f"{datefile}.xshlog").open("a+", encoding="utf-8")

loguru.logger.remove()
loguru.logger.add(logfile, format="{time} {level} {message}", level="DEBUG")

console = Console()
_sh_ = None

def get_sh():
    return _sh_

# ---------------- Custom Argument Parser ----------------
def parse_args(cmd_str):
    """Custom parser: splits by spaces, ignores spaces inside quotes, supports # comments"""
    cmd_str = cmd_str.split("#")[0]
    args = []
    current_arg = ""
    in_quotes = False
    for char in cmd_str:
        if char in ('"', "'"):
            in_quotes = not in_quotes
        elif char == ' ' and not in_quotes:
            if current_arg:
                args.append(current_arg)
                current_arg = ""
        else:
            current_arg += char
    if current_arg:
        args.append(current_arg)
    return args

# ---------------- Command Registration Decorator ----------------
def command(arg=None, help=""):
    def decorator(func):
        cmd = Command(func, help)
        if isinstance(arg, list):
            cmd.kvargs = arg
        sh = get_sh()
        sh.commands[func.__name__] = cmd
        return cmd
    
    if callable(arg):
        return decorator(arg)
    return decorator

# ---------------- Command Class ----------------
class Command:
    def __init__(self, func, help_text=""):
        self.name = func.__name__
        self.description = func.__doc__
        self.func = func
        self.help = help_text
        self.cmdargs = {}

        for name in inspect.signature(func).parameters:
            if name not in ('sh', 'stdin'):
                self.cmdargs[name] = None

    def lexArgs(self, string):
        args = {}
        commandlist = parse_args(string)[1:]
        positional = []
        idx = 0
        no_look = False
        
        for arg in commandlist:
            if not no_look:
                if arg.startswith("-"):
                    if idx + 1 < len(commandlist) and not commandlist[idx+1].startswith("-"):
                        no_look = True
                        args[arg.lstrip("-")] = commandlist[idx+1]
                    else:
                        args[arg.lstrip("-")] = True
                else:
                    positional.append(arg)
            else:
                no_look = False
            idx += 1
            
        if hasattr(self, 'kvargs'):
            positionalnames = [name for name in self.cmdargs if name not in self.kvargs]
        else:
            positionalnames = list(self.cmdargs.keys())

        for name, val in zip(positionalnames, positional):
            args[name] = val
        return args

    def __call__(self, argstr, sh_instance, stdin_data=None):
        args = self.lexArgs(argstr)
        
        if 'stdin' in inspect.signature(self.func).parameters:
            args['stdin'] = stdin_data
        if 'sh' in inspect.signature(self.func).parameters:
            args['sh'] = sh_instance
            
        missing = []
        for name, param in inspect.signature(self.func).parameters.items():
            if name in ('sh', 'stdin'):
                continue
            if param.default is inspect.Parameter.empty and name not in args:
                missing.append(name)
                
        if missing:
            raise XsError(f"{self.name}: Missing required arguments {missing}")
            
        return self.func(**args)

# ---------------- Prompt Class (Catppuccin) ----------------
class Prompt:
    def __init__(self):
        self.console = Console(force_terminal=True, color_system="truecolor")
        self.C = {
            "red": "#f38ba8", "peach": "#fab387", "yellow": "#f9e2af",
            "green": "#a6e3a1", "sapphire": "#74c7ec", "lavender": "#b4befe",
            "crust": "#11111b",
        }
        self.left_round = ""
        self.right_round = ""
        self.arrow = ""

    def _get_git_branch(self) -> str:
        try:
            with open(".git/HEAD", "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content.startswith("ref: refs/heads/"):
                    return content.replace("ref: refs/heads/", "")
                return content[:7]
        except FileNotFoundError:
            return ""

    def _check_python(self):
        if os.path.exists("pyproject.toml") or os.path.exists(".venv") or any(f.endswith('.py') for f in os.listdir('.')):
            return f"v{sys.version_info.major}.{sys.version_info.minor}"
        return ""

    def render(self, status: int, duration: float = 0.0) -> str:
        text = Text()
        
        user = os.environ.get("USERNAME") or os.environ.get("USER") or "admin"
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        if cwd.startswith(home):
            cwd = "~" + cwd[len(home):]
        parts = cwd.replace("\\", "/").split("/")
        if len(parts) > 3:
            cwd = "…/" + "/".join(parts[-2:])
            
        git_branch = self._get_git_branch()
        py_ver = self._check_python()
        conda_env = os.environ.get("CONDA_DEFAULT_ENV")
        now = datetime.datetime.now().strftime("%H:%M")

        text.append(self.left_round, style=self.C["red"])
        text.append(f"  {user} ", style=f"bold {self.C['crust']} on {self.C['red']}")
        
        text.append(self.arrow, style=f"{self.C['red']} on {self.C['peach']}")
        text.append(f" {cwd} ", style=f"bold {self.C['crust']} on {self.C['peach']}")
        
        text.append(self.arrow, style=f"{self.C['peach']} on {self.C['yellow']}")
        if git_branch:
            text.append(f"  {git_branch} ", style=f"bold {self.C['crust']} on {self.C['yellow']}")
            
        text.append(self.arrow, style=f"{self.C['yellow']} on {self.C['green']}")
        if py_ver:
            text.append(f"  {py_ver} ", style=f"bold {self.C['crust']} on {self.C['green']}")
            
        text.append(self.arrow, style=f"{self.C['green']} on {self.C['sapphire']}")
        if conda_env:
            text.append(f"  {conda_env} ", style=f"bold {self.C['crust']} on {self.C['sapphire']}")
            
        text.append(self.arrow, style=f"{self.C['sapphire']} on {self.C['lavender']}")
        text.append(f"  {now} ", style=f"bold {self.C['crust']} on {self.C['lavender']}")
        text.append(self.right_round, style=self.C['lavender'])

        char_color = self.C["green"] if status == 0 else self.C["red"]
        text.append(" ❯ ", style=f"bold {char_color}")

        with self.console.capture() as capture:
            self.console.print(text, end="")
        return capture.get()

# ---------------- Shell Core Class ----------------
class Xsh:
    def __init__(self):
        self.log = loguru.logger
        self.commands = {}
        self._local = threading.local()
        self.status = 0
        self.prompt_engine = Prompt()

    def out(self, data, on_stdout: str | SentinelValue = donot_have_sentinel, not_data_str: str | SentinelValue = donot_have_sentinel):
        target = getattr(self._local, "target", None)
        if target:
            if getattr(self._local, "afterisext", False) == True:
                target(not_data_str if not_data_str is not donot_have_sentinel else str(data))
            else:
                target(data)
        if not target:
            sys.stdout.write(on_stdout if on_stdout is not donot_have_sentinel else str(data))
            sys.stdout.flush()

    def check_command_exists(self, name: str) -> bool:
        """Check if command exists internally or externally"""
        if name in self.commands:
            return True
        if shutil.which(name):
            return True
        return False

    def load_rc(self):
        rc_paths = [
            pathlib.Path(os.path.expanduser("~/.xshrc")), 
            pathlib.Path(".xshrc")                        
        ]
        
        for rc_path in rc_paths:
            if not rc_path.exists():
                self.log.debug(f"Skipped rc file (not found): {rc_path.absolute()}")
                continue
                
            self.log.info(f"Loading rc file: {rc_path.absolute()}")
            loguru.logger.complete()
            
            try:
                with open(rc_path, "r", encoding="utf-8-sig") as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                            
                        if line.startswith("export "):
                            var_def = line[7:].strip()
                            if "=" in var_def:
                                k, v = var_def.split("=", 1)
                                os.environ[k.strip()] = v.strip("'\"")
                                continue
                        
                        try:
                            self.run_command(line)
                        except Exception as e:
                            self.log.exception(f"[xshrc Error] Failed at line {line_num}: {line}")
            except Exception as e:
                self.log.exception(f"[Read Error] {rc_path}")

    def run_command(self, command: str):
        if "|" in command:
            commandlist = [c.strip() for c in command.split("|") if c.strip()]
            qs = [Queue() for _ in commandlist]
            
            def worker(i):
                try:
                    name = commandlist[i].split()[0]
                    is_last = (i == len(commandlist) - 1)
                    in_q = qs[i-1] if i > 0 else None
                    out_q = qs[i] if not is_last else None
                    self._local.afterisext = False
                    
                    if name in self.commands:
                        if not is_last:
                            next_name = commandlist[i+1].split()[0]
                            if next_name not in self.commands:
                                self._local.afterisext = True
                    
                        if is_last:
                            self._local.target = lambda x: (sys.stdout.write(str(x)), sys.stdout.flush())
                        else:
                            self._local.target = out_q.put
                            
                        stdin_stream = iter(in_q.get, None) if in_q else None
                        self.commands[name](commandlist[i], sh_instance=self, stdin_data=stdin_stream)
                        
                        if not is_last:
                            out_q.put(None)
                    else:
                        try:
                            p_stdin = subprocess.PIPE if in_q else None
                            p_stdout = None if is_last else subprocess.PIPE
                            
                            parts = parse_args(commandlist[i])
                            
                            p = subprocess.Popen(
                                parts, 
                                shell=False, 
                                stdin=p_stdin, 
                                stdout=p_stdout, 
                                text=True, 
                                encoding=sys_encoding, 
                                errors='replace'
                            )
                            
                            if in_q:
                                def feed():
                                    for x in iter(in_q.get, None):
                                        try:
                                            p.stdin.write(str(x))
                                            p.stdin.flush()
                                        except: 
                                            break
                                    try: 
                                        p.stdin.close()
                                    except: 
                                        pass
                                threading.Thread(target=feed, daemon=True).start()
                                
                            if not is_last:
                                def read_out():
                                    for line in iter(lambda: p.stdout.readline(), ''):
                                        out_q.put(line)
                                threading.Thread(target=read_out, daemon=True).start()
                                
                            p.wait() 
                                
                        except FileNotFoundError:
                            self.log.error(f"Command not found: {commandlist[i]}")
                            print(f"Command not found: {commandlist[i]}")  # English UI
                        except Exception as e:
                            self.log.exception(f"[External Command Crash] {commandlist[i]}")
                            print(f"[External Command Crash] {commandlist[i]}")  # English UI
                        
                except Exception as e:
                    self.log.exception(f"[Thread Crash] {commandlist[i]}")
                finally:
                    if not is_last: 
                        out_q.put(None)
            
            with concurrent.futures.ThreadPoolExecutor() as e:
                for i in range(len(commandlist)):
                    e.submit(worker, i)
                    
        else:
            self.log.info(f"Running command: {command}")
            tokens = command.split()
            if tokens:
                name = tokens[0]
                if name in self.commands:
                    return self.commands[name](command, sh_instance=self)
                else:
                    try:
                        parts = parse_args(command)
                        res = subprocess.run(parts, shell=False, encoding=sys_encoding).returncode
                    except FileNotFoundError:
                        self.log.error(f"Command not found: {name}")
                        print(f"Command not found: {name}")  # English UI
                        res = 1
                    except Exception as e:
                        self.log.exception(f"[External Command Crash] {command}")
                        print(f"[External Command Crash] {command}")  # English UI
                        res = 1
                    return res
            return 0

    def run(self):
        global _sh_
        _sh_ = self
        
        self.load_rc()
        
        his = promptplus.History(os.path.expanduser("~/.xsh_history"))

        while True:
            try:
                prompt_str = self.prompt_engine.render(self.status)
                
                command = promptplus.prompt(
                    prompt_str, 
                    his, 
                    os.getcwd(), 
                    check_cmd_func=self.check_command_exists
                )
                
                if command.strip():
                    self.status = self.run_command(command)
                else:
                    self.status = 0
                    
            except FileNotFoundError:
                self.log.error("FileNotFoundError in run loop")
            except KeyboardInterrupt:
                sys.stdout.write("\033[0m\n")
                sys.stdout.flush()
                continue
            except EOFError:
                sys.stdout.write("\033[0m\n")
                sys.stdout.flush()
                break
            except Exception as e:
                self.log.exception("[Fatal Crash in Main Loop]")
                print(f"\n[Internal System Error, please check logs]")  # English UI
                sys.stdout.flush()

# ---------------- Built-in Commands ----------------
xsh = Xsh()
_sh_ = xsh

@command
def pwd(sh: Xsh):
    sh.out(escape(os.getcwd()))
    return 0

@command
def cat(stdin, sh):
    if stdin:
        for chunk in stdin:
            sh.out(chunk + "\n")
    return 0

@command
def echo(stdin, sh: Xsh, string=""):
    sh.out(string + "\n")
    return 0

@command
def kk(sh):
    sh.out((1, 11))
    return 0

@command
def upper(stdin, sh: Xsh):
    if stdin:
        for chunk in stdin:
            sh.out(chunk.upper())
    return 0

@command
def cd(path):
    if path.endswith(":"):
        path += "\\"
    path = os.path.expanduser(path)
    try:
        os.chdir(path)
    except FileNotFoundError:
        print(f"cd: No such file or directory '{path}'")  # English UI
    return 0

@command
def exit():
    os._exit(0)

if __name__ == "__main__":
    xsh.run()