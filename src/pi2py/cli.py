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

from pi2py import __version__
from pi2py.core.agent import Agent, AgentConfig
from pi2py.core.session import SessionStore

app = typer.Typer(
    no_args_is_help=False,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    prompt: Annotated[str | None, typer.Option("--print", "-p", help="运行单次提示词并打印回答。")] = None,
    mode: Annotated[Literal["text", "json"], typer.Option(help="--print 的输出模式。")] = "text",
    model: Annotated[str, typer.Option("--model", "-m", help="LiteLLM 模型名称。")] = "gpt-4o-mini",
    cwd: Annotated[Path, typer.Option("--cwd", help="工作区目录。")] = Path.cwd(),
    version: Annotated[
        bool | None,
        typer.Option("--version", "-v", callback=version_callback, is_eager=True, help="显示版本并退出。"),
    ] = None,
) -> None:
    load_dotenv()
    if ctx.invoked_subcommand is not None:
        return

    config = AgentConfig(model=model, cwd=cwd)
    agent = Agent(config, session_store=SessionStore.create_default(cwd))
    if prompt is not None:
        stdin = _read_stdin_if_piped()
        merged = f"{stdin}\n\n{prompt}" if stdin else prompt
        raise typer.Exit(asyncio.run(_run_print(agent, merged, mode)))
    asyncio.run(_run_interactive(agent))


@app.command()
def tools(
    model: Annotated[str, typer.Option("--model", "-m")] = "gpt-4o-mini",
    cwd: Annotated[Path, typer.Option("--cwd")] = Path.cwd(),
) -> None:
    agent = Agent(AgentConfig(model=model, cwd=cwd))
    for tool in agent.tools:
        typer.echo(f"{tool.name}: {tool.description}")


async def _run_print(agent: Agent, prompt: str, mode: str) -> int:
    try:
        if mode == "json":
            async for event in agent.run_events(prompt):
                print(json.dumps({"type": event.type, **event.data}, ensure_ascii=False), flush=True)
        else:
            print(await agent.run(prompt))
        return 0
    except Exception as exc:
        typer.echo(str(exc), err=True)
        return 1


async def _run_interactive(agent: Agent) -> None:
    completer = WordCompleter(["/help", "/quit", "/exit", "/tools", "/session", "/clear"], ignore_case=True)
    session: PromptSession[str] = PromptSession(completer=completer)
    typer.echo(f"pi2py {__version__}  model={agent.config.model}  cwd={agent.cwd}")
    typer.echo("输入 /help 查看命令，输入 /quit 退出。")

    while True:
        try:
            text = await session.prompt_async(HTML("<ansigreen>pi2py</ansigreen> > "))
        except (EOFError, KeyboardInterrupt):
            typer.echo()
            return
        text = text.strip()
        if not text:
            continue
        if await _handle_command(agent, text):
            continue
        async for event in agent.run_events(text):
            if event.type == "assistant_message" and event.data.get("content"):
                typer.echo(event.data["content"])
            elif event.type == "tool_result":
                name = event.data.get("name")
                content = str(event.data.get("content", ""))
                typer.echo(f"[tool:{name}] {content[:500]}")


async def _handle_command(agent: Agent, text: str) -> bool:
    if not text.startswith("/"):
        return False
    if text in {"/quit", "/exit"}:
        raise typer.Exit()
    if text == "/help":
        typer.echo("/tools, /session, /clear, /quit")
    elif text == "/tools":
        typer.echo(", ".join(tool.name for tool in agent.tools))
    elif text == "/session":
        typer.echo(f"id={agent.session.id} messages={len(agent.session.messages)}")
    elif text == "/clear":
        agent.session.messages = [agent.session.messages[0]]
        typer.echo("已清空当前会话上下文")
    else:
        typer.echo(f"未知命令：{text}")
    return True


def _read_stdin_if_piped() -> str:
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read().strip()


if __name__ == "__main__":
    app()
