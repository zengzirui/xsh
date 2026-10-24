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
from collections import OrderedDict as Odict
import locale
import shlex
sys_encoding=locale.getpreferredencoding(False)
class SentinelValue:
    def __bool__(self):
        return False
donot_have_sentinel=SentinelValue()

# 假设你在 errors 文件夹下有这个异常类，如果没有，这里给你兜个底
try:
    from errors.commanderror import *
except ImportError:
    class XsError(Exception): pass

# ---------------- 路径与日志初始化 ----------------
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

# ---------------- 命令注册装饰器 ----------------
def command(arg):
    sh = get_sh()
    if type(arg) is not list:
        cmd = Command(arg)
        sh.commands[arg.__name__] = cmd
        return cmd
    else:
        def decorator(func):
            cmd = Command(func)
            cmd.kvargs = arg
            sh.commands[func.__name__] = cmd
            return cmd
        return decorator

# ---------------- 命令类 ----------------
class Command:
    def __init__(self, func):
        self.name = func.__name__
        self.description = func.__doc__
        self.func = func
        self.cmdargs = {}

        
        # 核心修复：只把需要用户输入的参数放进 cmdargs
        for name in inspect.signature(func).parameters:
            if name not in ('sh', 'stdin'):
                self.cmdargs[name] = None

    def lexArgs(self, string):
        args = {}
        commandlist = string.split()[1:]
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
            
        # 💡 直接现场检查：遍历函数签名，找出没默认值且用户没传的参数
        missing = []
        for name, param in inspect.signature(self.func).parameters.items():
            if name in ('sh', 'stdin'):
                continue
            if param.default is inspect.Parameter.empty and name not in args:
                missing.append(name)
                
        if missing:
            raise XsError(f"{self.name}: 缺少必填参数 {missing}")
            
        return self.func(**args)

class Xsh:
    def __init__(self):
        self.log = loguru.logger
        self.commands = {}
        self._local = threading.local()
        self.status = 0

    def out(self, data, on_stdout: str | SentinelValue = donot_have_sentinel, not_data_str: str | SentinelValue = donot_have_sentinel):
        """内部命令调用的输出口"""
        target = getattr(self._local, "target", None)
        
        # 1. 在管道中
        if target:
            if getattr(self._local, "afterisext", False):
                # 下一个是外部命令，强制降级
                if not_data_str is not donot_have_sentinel:
                    target(not_data_str)
                else:
                    target(str(data))
            else:
                # 下一个是内部命令，直接传对象
                target(data)
        # 2. 单条命令（没有 target）
        else:
            if on_stdout is not donot_have_sentinel:
                sys.stdout.write(on_stdout)
            else:
                sys.stdout.write(str(data))
            sys.stdout.flush()

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
                    
                    if name in self.commands:
                        # --- 内部命令 ---
                        self._local.afterisext = False
                        
                        # 💡 核心：安全地判断下一个是不是外部命令
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
                        # --- 外部命令 ---
                        try:
                            import shlex
                            p_stdin = subprocess.PIPE if in_q else None
                            p_stdout = None if is_last else subprocess.PIPE
                            
                            parts = shlex.split(commandlist[i])
                            p = subprocess.Popen(
                                parts, 
                                shell=False, 
                                stdin=p_stdin, 
                                stdout=p_stdout, 
                                text=True, 
                                encoding=sys_encoding, 
                                errors='replace'
                            )
                            
                            # 喂数据
                            if in_q:
                                def feed():
                                    for x in iter(in_q.get, None):
                                        try:
                                            p.stdin.write(str(x))
                                            p.stdin.flush()
                                        except: 
                                            break
                                    try: p.stdin.close()
                                    except: pass
                                threading.Thread(target=feed, daemon=True).start()
                                
                            # 读数据
                            if not is_last:
                                def read_out():
                                    for line in iter(lambda: p.stdout.readline(), ''):
                                        out_q.put(line)
                                    out_q.put(None)
                                threading.Thread(target=read_out, daemon=True).start()
                                
                            # 💡 核心：无论是不是最后一个，都必须等进程结束，防止僵尸进程
                            p.wait() 
                                
                        except FileNotFoundError:
                            print(f"command not found: {commandlist[i]}")
                            if not is_last: out_q.put(None)
                        except Exception as e:
                            print(f"[外部命令崩溃] {e}")
                            if not is_last: out_q.put(None)

                except Exception as e:
                    print(f"\n[线程崩溃] {commandlist[i]} : {e}")
                    import traceback
                    traceback.print_exc()
                    if not is_last: out_q.put(None)
            
            with concurrent.futures.ThreadPoolExecutor() as e:
                for i in range(len(commandlist)):
                    e.submit(worker, i) # 现在不需要传多余的参数了
                    
        else:
            # 单条命令
            self.log.info(f"Running command: {command}")
            tokens = command.split()
            if tokens:
                name = tokens[0]
                if name in self.commands:
                    return self.commands[name](command, sh_instance=self)
                else:
                    try:
                        parts = shlex.split(command)
                        # 单条命令也建议加上防止 cmd 退出的隔离
                        p = subprocess.Popen(parts, shell=False)
                        p.communicate()
                    except FileNotFoundError:
                        print(f"command not found: {name}")
            return 0

    def run(self):
        global _sh_
        _sh_ = self
        while True:
            try:
                command = console.input(f"xs [blue]{escape(os.getcwd())}[/blue]> ")
                self.status = self.run_command(command)
            except FileNotFoundError:
                print("command not found")
            except KeyboardInterrupt:
                print()
                continue # 💡 之前说好的直接 continue，不退出
            except EOFError:
                pass
            except XsError as e:
                print(f"Error: {e}")

# ---------------- 内置命令实现 ----------------
xsh = Xsh()
_sh_=xsh

@command
def pwd(sh: Xsh):
    sh.out(escape(os.getcwd()))
@command
def cat(stdin, sh):
    if stdin:
        for chunk in stdin:
            sh.out(type(chunk))
            sh.out(str(chunk)+"\n")
@command
def echo(stdin,sh: Xsh,string):
    sh.out(string+"\n")
@command
def kk(sh):
    sh.out((1,11))
@command
def upper(stdin, sh: Xsh):
    # 接收管道流，转大写后继续往下流
    if stdin:
        for chunk in stdin:
            sh.out(chunk.upper())

@command
def cd(path):
    if path.endswith(":"):
        path += "\\"
    os.chdir(path)

@command
def exit():
    os._exit(0)

if __name__ == "__main__":

    xsh.run()