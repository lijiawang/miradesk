import asyncio
from collections.abc import AsyncIterator
import json
import logging
import os
import pty
import re
import select
import shlex
import subprocess
import termios
import time
from typing import Any

from app.core.config import Settings
from app.core.utils import truncate
from app.schemas.claude import ClaudeCLIRequest, ClaudeCLIResponse, ClaudeSlashCommand

logger = logging.getLogger("uvicorn.error")

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\a]*(?:\a|\x1b\\)|\x1b[()][A-Za-z]")
CURSOR_RIGHT_RE = re.compile(r"\x1b\[(\d*)C")


class CommandNotAllowedError(ValueError):
    pass


class ClaudeCLIService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_command(
        self,
        cli_path: str | None,
        command: str,
        args: dict[str, Any] | None,
    ) -> tuple[list[str], str | None]:
        command = command.strip()
        if command not in self.settings.command_allowlist:
            allowed = ", ".join(self.settings.command_allowlist)
            raise CommandNotAllowedError(
                f"Claude command '{command}' is not allowed. Allowed: {allowed}"
            )

        cmd = [cli_path or self.settings.default_cli_path, command]
        stdin_text: str | None = None
        safe_args = dict(args or {})

        for text_key in ("message", "input", "stdin"):
            if text_key in safe_args and safe_args[text_key] is not None:
                value = safe_args.pop(text_key)
                stdin_text = (
                    value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                )
                break

        for key, value in safe_args.items():
            key_norm = str(key).replace("_", "-")
            if key_norm == "model":
                continue
            if isinstance(value, bool):
                if value:
                    cmd.append(f"--{key_norm}")
                continue
            if value is None:
                continue
            cmd.extend((f"--{key_norm}", str(value)))

        return cmd, stdin_text

    async def discover_slash_commands(
        self,
        cli_path: str | None = None,
        timeout: float = 3.0,
    ) -> tuple[list[ClaudeSlashCommand], str, str | None]:
        try:
            output = await asyncio.to_thread(
                self._capture_interactive_slash_menu,
                cli_path or self.settings.default_cli_path,
                timeout,
            )
            commands = self._parse_slash_menu(output)
            if commands:
                return commands, "claude", None
            return [], "claude", "Claude slash menu returned no parseable commands"
        except Exception as exc:
            logger.warning("Failed to discover Claude slash commands: %s", exc)
            return [], "claude", str(exc)

    def _capture_interactive_slash_menu(self, cli_path: str, timeout: float) -> str:
        master_fd, slave_fd = pty.openpty()
        termios.tcsetwinsize(slave_fd, (100, 100))
        env = {
            **os.environ,
            "TERM": "xterm-256color",
            "COLUMNS": "100",
            "LINES": "100",
            "NO_COLOR": "1",
        }
        process = subprocess.Popen(
            [cli_path],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=str(self.settings.workspace_path),
            env=env,
            close_fds=True,
            text=False,
        )
        os.close(slave_fd)
        chunks: list[bytes] = []
        deadline = time.monotonic() + timeout
        slash_at = time.monotonic() + 0.8
        sent_slash = False

        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master_fd], [], [], 0.1)
                if ready:
                    try:
                        chunk = os.read(master_fd, 8192)
                    except OSError:
                        break
                    if not chunk:
                        break
                    chunks.append(chunk)

                if not sent_slash and time.monotonic() >= slash_at and time.monotonic() < deadline - 0.8:
                    os.write(master_fd, b"/")
                    sent_slash = True

            for key in (b"\x03", b"\x03"):
                if process.poll() is not None:
                    break
                try:
                    os.write(master_fd, key)
                except OSError:
                    break
                time.sleep(0.1)

            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=0.6)
                except subprocess.TimeoutExpired:
                    process.kill()
        finally:
            os.close(master_fd)

        return b"".join(chunks).decode("utf-8", errors="replace")

    def _parse_slash_menu(self, output: str) -> list[ClaudeSlashCommand]:
        text = CURSOR_RIGHT_RE.sub(lambda match: " " * int(match.group(1) or "1"), output)
        text = ANSI_RE.sub("", text)
        text = text.replace("\r", "\n").replace("\xa0", " ")
        details: dict[str, str] = {}
        current_name: str | None = None

        for raw_line in text.splitlines():
            line = re.sub(r"[^\S\n]+", " ", raw_line).strip()
            match = re.match(r"^(?P<name>/[A-Za-z0-9][\w:./-]*)(?:\s+(?P<detail>.+))?$", line)
            if match:
                name = match.group("name")
                if name in details:
                    current_name = name
                    continue
                detail = (match.group("detail") or "").strip()
                if not detail or detail == name:
                    current_name = None
                    continue
                details[name] = detail
                current_name = name
                continue

            if not current_name or not line:
                continue

            if any(token in line for token in ("Claude Code", "Tips for", "What's new", "Press Ctrl-C")):
                current_name = None
                continue
            if set(line) <= {"─", "╭", "╮", "╰", "╯", "│", " "}:
                current_name = None
                continue
            if line.startswith(("❯", "?", "●", "⏵")):
                current_name = None
                continue

            details[current_name] = f"{details[current_name]} {line}"

        return [
            ClaudeSlashCommand(
                name=name,
                title=title,
                detail=detail,
                source="claude",
            )
            for name, detail in details.items()
            for title in [name.lstrip("/").replace(":", " ").replace("-", " ").title()]
        ]

    async def execute(self, request: ClaudeCLIRequest) -> ClaudeCLIResponse:
        cmd, stdin_text = self.build_command(
            request.cli_path,
            request.command,
            request.args,
        )

        try:
            cmd_preview = shlex.join(cmd)
        except Exception:
            cmd_preview = " ".join(cmd)

        logger.warning("Claude CLI cmd: %s", cmd_preview)
        if stdin_text:
            logger.warning("Claude CLI stdin preview: %s", truncate(stdin_text))
        else:
            logger.warning("Claude CLI stdin: <empty>")

        def _run() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                cmd,
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=request.timeout,
                check=False,
            )

        result = await asyncio.to_thread(_run)
        return ClaudeCLIResponse(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr if result.returncode != 0 else None,
            return_code=result.returncode,
        )

    async def stream(self, request: ClaudeCLIRequest) -> AsyncIterator[dict[str, Any]]:
        cmd, stdin_text = self.build_command(
            request.cli_path,
            request.command,
            request.args,
        )

        try:
            cmd_preview = shlex.join(cmd)
        except Exception:
            cmd_preview = " ".join(cmd)

        logger.warning("Claude CLI stream cmd: %s", cmd_preview)
        if stdin_text:
            logger.warning("Claude CLI stream stdin preview: %s", truncate(stdin_text))
        else:
            logger.warning("Claude CLI stream stdin: <empty>")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if process.stdin is not None:
            try:
                if stdin_text is not None:
                    process.stdin.write(stdin_text.encode("utf-8"))
                    await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError, RuntimeError) as exc:
                logger.warning("Claude CLI stdin closed early: %s", exc)
            finally:
                process.stdin.close()
                try:
                    await process.stdin.wait_closed()
                except (BrokenPipeError, ConnectionResetError, RuntimeError):
                    pass

        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

        async def pump_stream(name: str, stream: asyncio.StreamReader | None) -> None:
            if stream is None:
                return
            while True:
                chunk = await stream.read(1024)
                if not chunk:
                    break
                await queue.put((name, chunk.decode("utf-8", errors="replace")))

        pump_tasks = [
            asyncio.create_task(pump_stream("stdout", process.stdout)),
            asyncio.create_task(pump_stream("stderr", process.stderr)),
        ]
        wait_task = asyncio.create_task(process.wait())
        deadline = asyncio.get_running_loop().time() + request.timeout

        try:
            while True:
                finished = wait_task.done() and all(task.done() for task in pump_tasks)
                if finished and queue.empty():
                    break

                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    process.kill()
                    await process.wait()
                    yield {
                        "event": "error",
                        "message": f"Claude CLI timed out after {request.timeout} seconds",
                    }
                    return

                try:
                    stream_name, text = await asyncio.wait_for(
                        queue.get(),
                        timeout=min(0.2, remaining),
                    )
                except TimeoutError:
                    continue

                yield {
                    "event": "chunk",
                    "stream": stream_name,
                    "text": text,
                }

            return_code = await wait_task
            yield {
                "event": "done",
                "success": return_code == 0,
                "return_code": return_code,
            }
        except asyncio.CancelledError:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        finally:
            for task in pump_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*pump_tasks, return_exceptions=True)
