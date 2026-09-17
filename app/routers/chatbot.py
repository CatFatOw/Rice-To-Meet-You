"""Chat endpoints for the heat-mitigation assistant.

Two routes, both stateless on the server:

    POST /chat/session  -> opens a session for a city/date, returns the state
    POST /chat/ask      -> takes that state plus a question, returns the answer
                           and the updated state

The browser holds the conversation. Each response carries a `state` object that
must be sent back verbatim on the next call, plus a `transcript` for rendering.
Keep them separate: `state` is the Anthropic message list (the first element is
the whole briefing, which should never be drawn on screen), while `transcript`
is just the question/answer pairs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Adjust to wherever your session dependency actually lives.
from database import get_db
from repository.chatbot_repository import MAX_SESSION_MESSAGES, ChatbotRepository


router = APIRouter(prefix="/chat", tags=["chat"])

# The whole conversation round-trips through the browser on every turn, so cap
# it. A briefing runs a few tens of KB; this leaves room for ~20 exchanges.
MAX_STATE_CHARS = 400_000

# The API rejects a request carrying more than four cache breakpoints. Sessions
# accumulate one per context update, so trim before forwarding.
MAX_CACHE_BREAKPOINTS = 4


# ---------------------------------------------------------------------------
# Wire models
# ---------------------------------------------------------------------------

class SessionState(BaseModel):
    """Opaque round-trip payload. The client stores it and sends it back unchanged."""

    city: Optional[str] = None
    date: Optional[str] = None
    messages: List[Dict[str, Any]] = Field(default_factory=list)


class TranscriptEntry(BaseModel):
    """One renderable turn. The briefing and context updates are excluded."""

    role: str  # "user" | "assistant"
    text: str


class StartSessionRequest(BaseModel):
    city: str = Field(min_length=1)
    date: str = Field(min_length=1, description="ISO date, e.g. 2026-07-05")


class StartSessionResponse(BaseModel):
    state: SessionState
    transcript: List[TranscriptEntry]


class AskRequest(BaseModel):
    state: SessionState
    question: str = Field(min_length=1, max_length=4000)


class AskResponse(BaseModel):
    answer: str
    state: SessionState
    transcript: List[TranscriptEntry]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _block_text(content: Any) -> str:
    """Flatten a message's content to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def _is_context_block(text: str) -> bool:
    """Briefings and context updates are model input, not conversation."""
    stripped = text.lstrip()
    return stripped.startswith(("<briefing>", "<briefing-update>", "<simulation-result>"))


def _build_transcript(messages: List[Dict[str, Any]]) -> List[TranscriptEntry]:
    """Question/answer pairs only.

    Message 0 is the briefing. A user turn that follows a context update holds
    both the update and the question in one content list, so filtering is done
    per block rather than per message — otherwise the question would vanish
    from the transcript along with the update.
    """
    transcript: List[TranscriptEntry] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")

        if isinstance(content, list):
            parts = [
                str(block.get("text", ""))
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
        else:
            parts = [_block_text(content)]

        for part in parts:
            if not part.strip() or _is_context_block(part):
                continue
            transcript.append(TranscriptEntry(role=str(role), text=part))
    return transcript


def _enforce_cache_breakpoints(messages: List[Dict[str, Any]]) -> None:
    """Keep at most MAX_CACHE_BREAKPOINTS cache_control markers, in place.

    The briefing at index 0 always keeps its marker — it is the longest and
    hottest prefix. Beyond that the most recent markers are kept and older ones
    dropped, since a stale breakpoint mid-history buys nothing.
    """
    marked: List[Dict[str, Any]] = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("cache_control"):
                marked.append(block)

    if len(marked) <= MAX_CACHE_BREAKPOINTS:
        return

    keep = {id(marked[0])} | {id(block) for block in marked[-(MAX_CACHE_BREAKPOINTS - 1):]}
    for block in marked:
        if id(block) not in keep:
            block.pop("cache_control", None)


def _validate_state(state: SessionState) -> Dict[str, Any]:
    """Cheap guards before the repository's own validation in `resume`."""
    payload = state.model_dump()
    messages = payload.get("messages") or []

    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session has no messages — start a new chat",
        )
    if len(messages) > MAX_SESSION_MESSAGES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="session too long — start a new chat",
        )
    if sum(len(str(message)) for message in messages) > MAX_STATE_CHARS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="session payload too large — start a new chat",
        )

    _enforce_cache_breakpoints(messages)
    return payload


def _state_from(repository: ChatbotRepository) -> SessionState:
    snapshot = repository.to_state()
    return SessionState(
        city=snapshot.get("city"),
        date=snapshot.get("date"),
        messages=snapshot.get("messages") or [],
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

# Declared with `def` rather than `async def` on purpose: the repository uses
# the blocking Anthropic client and a sync SQLAlchemy Session, so FastAPI runs
# these in its worker threadpool instead of stalling the event loop.

@router.post("/session", response_model=StartSessionResponse)
def start_session(
    request: StartSessionRequest,
    db: Session = Depends(get_db),
) -> StartSessionResponse:
    """Build the briefing for a city/date and open a session on it.

    No model call is made here — the briefing is only assembled — so this
    returns as fast as the underlying queries allow. Nothing is persisted; the
    returned state is the session.
    """
    try:
        repository = ChatbotRepository(db, city=request.city, date=request.date)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

    state = _state_from(repository)
    return StartSessionResponse(
        state=state,
        transcript=_build_transcript(state.messages),
    )


@router.post("/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    db: Session = Depends(get_db),
) -> AskResponse:
    """Answer a question inside a client-held session.

    The state is rebuilt around this request's db session; the briefing is not
    re-queried and craftContext is not re-run. On any failure the state is not
    returned, so the client keeps its last good copy and can retry the same
    question without corrupting the history.
    """
    payload = _validate_state(request.state)

    try:
        repository = ChatbotRepository.resume(db, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

    try:
        answer = repository.ask(request.question)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    except Exception:
        # The model call failed after the question was appended. Roll it back so
        # the client's stored state stays valid if it retries with the old copy.
        repository._rollback_question()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="the assistant is unavailable right now — please try again",
        )

    state = _state_from(repository)
    return AskResponse(
        answer=answer,
        state=state,
        transcript=_build_transcript(state.messages),
    )   