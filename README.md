xsh (X Shell)

[English](#english) | [中文](#中文)

> A modern, human-friendly, hacker-grade interactive shell built with Python for Windows.
> 一个用 Python 编写、现代化、人性化的极客级交互式shell


<img width="1482" height="852" alt="image" src="https://github.com/user-attachments/assets/8c153c92-9eea-401f-adce-c65484b6623d" />
---

## English

### ✨ Features

*   **🛠 Hand-crafted Line Editor (`promptplus.py`)**:
    Discarded bloated 3rd-party libraries that often cause cursor misalignment or overwrite terminal history. Hand-crafted from scratch based on `readchar`, featuring perfect persistent history, arrow-key navigation, precise CJK (Chinese/Japanese/Korean) double-width character calculation, and absolute protection against accidentally erasing previous output.
*   **⚡ Multi-threaded Hybrid Pipeline (`|`)**:
    True pipeline concurrency using `ThreadPoolExecutor` and `Queue`. Seamlessly mix external system commands (like `git`, `ping`) with internal Python functions.
*   **🧠 Structured Object Passing**:
    Passes real Python objects (Dict/List) through the pipeline internally. Automatically downgrades to plain text streams when passing to external `.exe` processes.
*   **🎨 Code-drawn Prompt (`Prompt` class)**:
    Completely ditches the bulky `starship.exe` black box. Uses `rich` to render the **Catppuccin gradient Powerline blocks** entirely in code, with status-linked feedback (the prompt `❯` turns red when the last command fails).
*   **🔍 Geek-level Argument Parsing**:
    Hand-crafted `parse_args` that perfectly handles quoted strings with spaces (`"hello world"`) and natively supports `#` comments.
*   **📦 Modern Engineering**:
    Managed with `uv`, includes PyInstaller build configuration, and an extremely clean architecture.

### 🚀 Quick Start

#### 1. Clone the repository
```bash
git clone https://github.com/yourusername/xsh.git
cd xsh

#### 2. Install dependencies (requires `uv`)
```bash
uv sync
```

#### 3. Run xsh
```bash
uv run python src/xsh.py
```

### ⌨️ How to Extend (Custom Commands)

Use the `@command` decorator in `xsh.py` to register your Python function as a shell command:

```python
from src.xsh import command

@command
def hello(name, sh):
    """Say hello to someone"""
    sh.out(f"Hello, {name}!\n")
    return 0
```

Run it inside `xsh`:
```text
❯ hello World
Hello, World!
```

### 📂 Project Structure

```text
xsh/
├── src/
│   ├── xsh.py          # Core dispatcher, pipeline concurrency, Prompt rendering
│   ├── promptplus.py   # Hand-crafted terminal input & history engine
│   └── errors/         # Custom exceptions
├── make/
│   └── xsh.spec        # PyInstaller build configuration
├── pyproject.toml      # uv dependency management
├── .gitattributes      # Strict line-ending control
└── README.md
```

### ⚠️ Status

Currently in **Beta**. The core architecture (concurrent pipeline, input engine, UI rendering) is complete and stable. However, daily base commands (like `ls`, `cat`, `grep`) are still under development. Issues and PRs are highly welcome!

### 📄 License

[MIT](LICENSE)

---

## 中文

### ✨ 核心特性

*   **🛠 纯血自研行编辑器 (`promptplus.py`)**：
    抛弃了笨重且经常出现光标错位、覆盖上一行输出的第三方库。基于 `readchar` 从底层手搓，完美支持**历史记录持久化**、**上下翻页**、**中文字符双宽精准计算**、**绝不误删历史输出**。
*   **⚡ 多线程混合并发管道 (`|`)**：
    基于 `ThreadPoolExecutor` 和 `Queue` 实现真正的流水线并发。完美兼容外部系统命令（如 `git`, `ping`）与内部 Python 函数混排。
*   **🧠 结构化对象传递**：
    管道内部传递的是真正的 Python 对象（Dict/List），一旦碰触到外部 `.exe` 进程，自动降级为纯文本流。
*   **🎨 纯代码手绘提示符 (`Prompt` 类)**：
    彻底抛弃庞大的 `starship.exe` 黑盒。利用 `rich` 库纯代码拼接，实现了 **Catppuccin 渐变 Powerline 色块**，且支持状态联动（上一条命令报错时，提示符 `❯` 自动变红）。
*   **🔍 极客级参数解析**：
    手搓 `parse_args`，完美处理带空格的引号（`"hello world"`），并原生支持 `#` 注释符号。
*   **📦 现代工程化**：
    使用 `uv` 管理环境，内置 PyInstaller 打包配置，结构极度清晰。

### 🚀 快速开始

#### 1. 克隆仓库
```bash
git clone https://github.com/yourusername/xsh.git
cd xsh
```

#### 2. 安装依赖 (推荐使用 uv)
```bash
uv sync
```

#### 3. 启动 xsh
```bash
uv run python src/xsh.py
```

### ⌨️ 如何扩展你自己的命令？

在 `xsh.py` 中，使用 `@command` 装饰器即可一键注册你的 Python 函数为 Shell 命令：

```python
from src.xsh import command

@command
def hello(name, sh):
    """向某人打招呼"""
    sh.out(f"Hello, {name}!\n")
    return 0
```

启动 `xsh` 后直接输入：
```text
❯ hello World
Hello, World!
```

### 📂 项目结构

```text
xsh/
├── src/
│   ├── xsh.py          # Shell 核心调度、并发管道、Prompt 渲染
│   ├── promptplus.py   # 纯血自研的终端输入与历史记录引擎
│   └── errors/         # 自定义异常类
├── make/
│   └── xsh.spec        # PyInstaller 打包配置
├── pyproject.toml      # uv 依赖管理
├── .gitattributes      # 严格的行尾换行符控制
└── README.md
```

### ⚠️ 当前状态

当前版本为 **Beta**。核心架构（并发管道、输入引擎、UI 渲染）已经完备且稳定，但日常基础命令（如 `ls`, `cat`, `grep`）仍在持续开发中。欢迎提交 Issue 或 PR！

### 📄 许可证

[MIT](LICENSE)
