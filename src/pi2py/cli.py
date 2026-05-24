from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated, Literal

import typer
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pi2py import __version__
from pi2py.core.agent import Agent, AgentConfig
from pi2py.core.session import SessionStore
from pi2py.core.settings import DEFAULT_MODEL, SettingsStore
from pi2py.core.tools import run_bash_command

app = typer.Typer(
    no_args_is_help=False,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _console(*, stderr: bool = False) -> Console:
    return Console(highlight=False, stderr=stderr)


def version_callback(value: bool) -> None:
    if value:
        _console().print(__version__)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    prompt: Annotated[str | None, typer.Option("--print", "-p", help="运行单次提示词并打印回答。")] = None,
    mode: Annotated[Literal["text", "json"], typer.Option(help="--print 的输出模式。")] = "text",
    model: Annotated[str | None, typer.Option("--model", "-m", help="LiteLLM 模型名称。")] = None,
    cwd: Annotated[Path, typer.Option("--cwd", help="工作区目录。")] = Path.cwd(),
    version: Annotated[
        bool | None,
        typer.Option("--version", "-v", callback=version_callback, is_eager=True, help="显示版本并退出。"),
    ] = None,
) -> None:
    load_dotenv()
    if ctx.invoked_subcommand is not None:
        return

    settings_store = SettingsStore()
    settings = settings_store.load()
    selected_model = model or settings.model or DEFAULT_MODEL
    if model:
        settings_store.save_model(model)

    agent = Agent(
        AgentConfig(model=selected_model, cwd=cwd),
        session_store=SessionStore.create_default(cwd),
    )
    if prompt is not None:
        stdin = _read_stdin_if_piped()
        merged = f"{stdin}\n\n{prompt}" if stdin else prompt
        raise typer.Exit(asyncio.run(_run_print(agent, merged, mode)))
    asyncio.run(_run_interactive(agent))


@app.command()
def tools(
    model: Annotated[str | None, typer.Option("--model", "-m", help="LiteLLM 模型名称。")] = None,
    cwd: Annotated[Path, typer.Option("--cwd", help="工作区目录。")] = Path.cwd(),
) -> None:
    selected_model = model or SettingsStore().load().model
    agent = Agent(AgentConfig(model=selected_model, cwd=cwd))
    _print_tools(agent)


async def _run_print(agent: Agent, prompt: str, mode: str) -> int:
    try:
        if mode == "json":
            async for event in agent.run_events(prompt):
                print(json.dumps({"type": event.type, **event.data}, ensure_ascii=False), flush=True)
        else:
            _console().print(await agent.run(prompt))
        return 0
    except Exception as exc:
        _console(stderr=True).print(f"[red]{exc}[/red]")
        return 1


async def _run_interactive(agent: Agent) -> None:
    completer = WordCompleter(
        ["/help", "/model", "/tools", "/session", "/clear", "/quit", "/exit", "!"],
        ignore_case=True,
    )
    session: PromptSession[str] = PromptSession(completer=completer)
    _print_banner(agent)

    while True:
        try:
            prompt = HTML(
                f"<ansiblue>pi2py</ansiblue> "
                f"<ansibrightblack>{agent.config.model}</ansibrightblack> "
                "<ansigreen>›</ansigreen> "
            )
            text = await session.prompt_async(prompt)
        except (EOFError, KeyboardInterrupt):
            _console().print()
            return
        text = text.strip()
        if not text:
            continue
        if text.startswith("!"):
            await _run_shell_input(agent, text[1:].strip())
            continue
        if await _handle_command(agent, text):
            continue
        async for event in agent.run_events(text):
            if event.type == "assistant_message" and event.data.get("content"):
                _console().print(event.data["content"])
            elif event.type == "tool_result":
                name = event.data.get("name")
                content = str(event.data.get("content", ""))
                _console().print(Panel(content[:500], title=f"tool: {name}", border_style="dim"))


async def _run_shell_input(agent: Agent, command: str) -> None:
    if not command:
        _console().print("[yellow]请输入要执行的命令，例如 !dir[/yellow]")
        return
    try:
        result = await run_bash_command(agent.cwd, command)
    except ValueError as exc:
        _console().print(f"[red]{exc}[/red]")
        return
    _console().print(Panel(result, title=f"! {command}", border_style="cyan"))


async def _handle_command(agent: Agent, text: str) -> bool:
    if not text.startswith("/"):
        return False
    if text in {"/quit", "/exit"}:
        raise typer.Exit()
    if text == "/help":
        _print_interactive_help()
    elif text.startswith("/model"):
        _handle_model_command(agent, text)
    elif text == "/tools":
        _print_tools(agent)
    elif text == "/session":
        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan")
        table.add_column()
        table.add_row("会话", agent.session.id)
        table.add_row("消息数", str(len(agent.session.messages)))
        _console().print(Panel(table, title="Session", border_style="cyan"))
    elif text == "/clear":
        agent.session.messages = [agent.session.messages[0]]
        _console().print("[green]已清空当前会话上下文[/green]")
    else:
        _console().print(f"[red]未知命令: {text}[/red]")
    return True


def _handle_model_command(agent: Agent, text: str) -> None:
    parts = text.split(maxsplit=1)
    if len(parts) == 1:
        _console().print(f"[cyan]当前模型:[/cyan] {agent.config.model}")
        _console().print("用法: /model deepseek/deepseek-chat")
        return

    model = parts[1].strip()
    if not model:
        _console().print("[red]模型名称不能为空[/red]")
        return

    agent.config.model = model
    SettingsStore().save_model(model)
    _console().print(f"[green]已切换并记住模型:[/green] {model}")


def _print_banner(agent: Agent) -> None:
    title = Text()
    title.append("▣ ", style="bold cyan")
    title.append("pi2py", style="bold white")
    title.append("  Python 终端 Coding Agent", style="dim")

    body = Table.grid(padding=(0, 2))
    body.add_column(style="cyan", no_wrap=True)
    body.add_column()
    body.add_row("version", __version__)
    body.add_row("model", agent.config.model)
    body.add_row("cwd", str(agent.cwd))
    body.add_row("commands", "/help  /model  /tools  !command  /session  /clear  /quit")
    _console().print(Panel(body, title=title, border_style="cyan", padding=(1, 2)))


def _print_interactive_help() -> None:
    table = Table(title="pi2py commands", border_style="cyan", show_lines=False)
    table.add_column("命令", style="green", no_wrap=True)
    table.add_column("说明")
    table.add_row("/model [name]", "查看或切换模型，并记住本次选择")
    table.add_row("/tools", "查看当前可用工具")
    table.add_row("!command", "直接执行 bash 命令；仅阻止 rm -rf /")
    table.add_row("/session", "查看当前会话信息")
    table.add_row("/clear", "清空当前上下文")
    table.add_row("/quit", "退出")
    _console().print(table)


def _print_tools(agent: Agent) -> None:
    table = Table(title="▣ pi2py tools", border_style="cyan", show_lines=False)
    table.add_column("工具", style="green", no_wrap=True)
    table.add_column("说明")
    for tool in agent.tools:
        table.add_row(tool.name, tool.description)

    meta = Table.grid(padding=(0, 2))
    meta.add_column(style="cyan")
    meta.add_column()
    meta.add_row("model", agent.config.model)
    meta.add_row("cwd", str(agent.cwd))

    _console().print(Panel(meta, title="Runtime", border_style="cyan"))
    _console().print(table)


def _read_stdin_if_piped() -> str:
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read().strip()


if __name__ == "__main__":
    app()
