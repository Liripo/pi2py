# pi2py

`pi2py` 是一个参考 [pi-agent](https://github.com/earendil-works/pi) TypeScript 源码实现的 Python 终端 Coding Agent 骨架。

- `agent core`：负责消息状态、工具调用循环和会话保存
- `LiteLLM`：统一接入 OpenAI、Anthropic、Gemini、OpenRouter、DeepSeek 等模型
- `Typer`：提供命令行入口和参数解析
- `prompt-toolkit`：提供交互式终端输入体验
- `Rich`：提供终端界面渲染
- `uv`：管理依赖、虚拟环境和项目脚本
- 内置工具：`read`、`write`、`edit`、`bash`、`grep`、`find`、`ls`

## 快速开始

```bash
uv sync
uv run pi2py -h
uv run pi2py -p "你好"
uv run pi2py
```

根据 LiteLLM 所选模型配置对应的 API Key，例如：

```bash
export OPENAI_API_KEY=...
uv run pi2py --model gpt-4o-mini -p "List files in this project"
```

## 使用示例

交互模式：

```bash
uv run pi2py --model gpt-4o-mini
```

单次文本输出：

```bash
uv run pi2py -p "Summarize README.md"
```

查看内置工具：

```bash
uv run pi2py tools
```

交互模式中可以直接执行 shell 命令：

```text
!dir
```

为避免误删根目录，bash 工具会阻止 `rm -rf /`。

## 架构说明

项目采用轻量分层结构：

- `src/pi2py/cli.py`：Typer CLI 入口，负责 print/json/interactive 三种运行方式
- `src/pi2py/core/agent.py`：Agent 主循环，负责向模型发送消息、执行工具调用、继续下一轮
- `src/pi2py/core/litellm_client.py`：LiteLLM 适配层，隔离具体模型供应商
- `src/pi2py/core/tools.py`：内置文件、搜索和命令执行工具
- `src/pi2py/core/session.py`：会话序列化与保存
- `src/pi2py/core/settings.py`：保存上次使用的模型等本地设置
- `tests/`：使用 Fake LLM 验证工具调用循环，不依赖真实网络

## 后续方向

- 支持恢复、分叉和导出历史会话
- 增加项目上下文文件加载，例如 `AGENTS.md` 或 `.pi2py/SYSTEM.md`
- 支持流式输出和更完整的事件协议
- 增加更细粒度的工具权限确认策略
- 扩展 slash commands，例如 `/compact`、`/export`
