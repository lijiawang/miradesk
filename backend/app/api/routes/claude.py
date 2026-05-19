import json
import subprocess

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.schemas.claude import ClaudeCLIRequest, ClaudeCLIResponse
from app.services.claude_cli import CommandNotAllowedError

router = APIRouter(prefix="/claude", tags=["claude"])


@router.post("/run", response_model=ClaudeCLIResponse)
async def run_claude_cli(
    payload: ClaudeCLIRequest,
    request: Request,
) -> ClaudeCLIResponse:
    claude_cli = request.app.state.claude_cli
    try:
        return await claude_cli.execute(payload)
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail=f"Claude CLI timed out after {payload.timeout} seconds",
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Claude CLI executable not found: {payload.cli_path or 'claude'}",
        )
    except CommandNotAllowedError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute Claude CLI: {exc}",
        )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def stream_claude_cli(
    payload: ClaudeCLIRequest,
    request: Request,
) -> StreamingResponse:
    claude_cli = request.app.state.claude_cli

    async def events():
        try:
            async for item in claude_cli.stream(payload):
                if await request.is_disconnected():
                    break
                event = item.pop("event", "message")
                yield _sse(event, item)
        except FileNotFoundError:
            yield _sse(
                "error",
                {"message": f"Claude CLI executable not found: {payload.cli_path or 'claude'}"},
            )
        except CommandNotAllowedError as exc:
            yield _sse("error", {"message": str(exc)})
        except Exception as exc:
            yield _sse("error", {"message": f"Failed to stream Claude CLI: {exc}"})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
