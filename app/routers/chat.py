from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from ..deps import current_user, default_connection
from ..models import OdooConnection, User
from ..schemas import ChatRequest, StakeholderRequest
from ..services import claude
from ..services.context_builder import build_project_pack
from ..services.odoo import creds_from, post_chatter

router = APIRouter(prefix="/ai", tags=["ai"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/chat/stream")
def chat_stream(
    req: ChatRequest,
    user: User = Depends(current_user),
    conn: OdooConnection = Depends(default_connection),
):
    c = creds_from(conn)
    pack = build_project_pack(c, req.project_id)

    async def iter_sse():
        yield "event: start\ndata: {}\n\n"
        collected: list[str] = []
        async for delta in claude.stream(
            feature="chat",
            user_message=req.message,
            project_context=pack,
            user_id=user.id,
        ):
            collected.append(delta)
            # Escape newlines for SSE; client joins on the data boundary.
            safe = delta.replace("\r", "").replace("\n", "\\n")
            yield f"data: {safe}\n\n"

        if req.post_to_chatter:
            try:
                body = "".join(collected)
                post_chatter(
                    c,
                    model="project.project",
                    res_id=req.project_id,
                    subject="Claude answer",
                    body_html=f"<p><b>Q:</b> {req.message}</p><pre>{body}</pre>",
                )
            except Exception as e:
                yield f"event: chatter_error\ndata: {e}\n\n"

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(iter_sse(), media_type="text/event-stream")


@router.post("/stakeholder")
def stakeholder(
    req: StakeholderRequest,
    user: User = Depends(current_user),
    conn: OdooConnection = Depends(default_connection),
):
    c = creds_from(conn)
    pack = build_project_pack(c, req.project_id)
    if req.tone not in {"exec", "customer", "internal"}:
        raise HTTPException(400, "tone must be one of exec, customer, internal")
    user_msg = (
        f"Tone: {req.tone}\n"
        f"Highlights the author wants included: {req.highlights or '(none)'}\n"
        "Return STRICT JSON only."
    )
    return claude.call_json(
        feature="stakeholder",
        user_message=user_msg,
        project_context=pack,
        user_id=user.id,
    )
