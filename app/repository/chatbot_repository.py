import json
import os
import uuid
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

import anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from repository.final_visitor_repository import VisitorRepository
from repository.heatmap_repository import HeatmapRepository
from services.craft_context import MODEL_RULES, craftContext, craftSimulationSection
from services.simulation_services import SimulationFeedback


DateLike = Union[str, date_type, datetime]

CHAT_MODEL = "claude-sonnet-5"
CHAT_MAX_TOKENS = 1500
MAX_SESSION_MESSAGES = 41  # briefing + 20 question/answer pairs

AGENT_INSTRUCTIONS = """You are a heat-mitigation planning assistant for city staff.
The briefing in the first user message is authoritative: its ΔT_max ceilings,
intensities and composed cooling figures were produced by the simulator. Quote those
numbers rather than re-deriving them. Use the model rules below only to reason about
what-if changes the user proposes, and say plainly when a what-if needs a fresh
simulation run instead of arithmetic."""

# Static prefix: cached once, reused for every turn of every session.
CHAT_SYSTEM = [
    {
        "type": "text",
        "text": AGENT_INSTRUCTIONS + "\n\n" + MODEL_RULES,
        "cache_control": {"type": "ephemeral"},
    }
]


class ChatbotRepository:
    def __init__(
        self,
        db: Session,
        city: Optional[str] = None,
        date: Optional[DateLike] = None,
    ):
        self.db = db
        self.city = city
        self.date = date
        self.messages: List[Dict[str, Any]] = []
        self._client: Optional[anthropic.Anthropic] = None

        if city is not None and date is not None:
            self.startSessionByCityDate(city, date)

    @property
    def client(self) -> anthropic.Anthropic:
        """Lazily built so constructing the repository never requires an API key."""
        if self._client is None:
            self._client = anthropic.Anthropic(api_key="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")
        return self._client

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime, date_type)):
            return value.isoformat()
        return value

    @staticmethod
    def _coerce_date(value: DateLike) -> date_type:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date_type):
            return value
        return date_type.fromisoformat(str(value).strip()[:10])

    @staticmethod
    def _context_to_text(context: Union[str, Dict[str, Any]]) -> str:
        """Accept a raw briefing string or a dict wrapping one."""
        if isinstance(context, str):
            return context
        if isinstance(context, dict):
            for key in ("promptContext", "context", "text"):
                value = context.get(key)
                if isinstance(value, (str, dict)):
                    return ChatbotRepository._context_to_text(value)
            return json.dumps(context, indent=2, default=str)
        return str(context)

    @staticmethod
    def craftCurrentScenarios(city: str, date: DateLike) -> Dict[str, Any]:
        return {"city": city, "date": date}

    async def upload_chatbot_context(
        self,
        context: str | dict[str, Any],
    ) -> str:
        context_data = {"text": context} if isinstance(context, str) else context
        statement = text("""
            INSERT INTO chatbot_context (context_id, context)
            VALUES (CAST(:context_id AS UUID), CAST(:context AS JSONB))
            RETURNING context_id
        """)
        context_id = uuid.uuid4()
        params = {
            "context_id": str(context_id),
            "context": json.dumps(context_data),
        }

        if isinstance(self.db, AsyncSession):
            result = await self.db.execute(statement, params)
            await self.db.commit()
        else:
            result = self.db.execute(statement, params)
            self.db.commit()

        return str(result.scalar_one())

    def buildPromptContext(
        self,
        city: Optional[str] = None,
        date: Optional[DateLike] = None,
    ) -> Dict[str, Any]:
        """Gather scenarios, heat-risk rows and weather, and craft the briefing.

        Falls back to the instance's city/date. Pure read path — nothing is written.
        """
        city = city if city is not None else self.city
        date = date if date is not None else self.date
        if city is None or date is None:
            raise ValueError("city and date are required (pass them or set them on the instance)")

        query_date = self._coerce_date(date)
        current_scenarios = self.craftCurrentScenarios(city, date)

        visitor_repository = VisitorRepository(self.db)
        heatmap_repository = HeatmapRepository(self.db)
        visitor_rows = visitor_repository.queryVisitorRowsWithGeometryByCityDate(
            city,
            query_date,
            sorted=True,
            limit=10,
        )
        top_heat_risk_destinations = [
            {
                key: self._json_safe(value)
                for key, value in row._mapping.items()
            }
            for row in visitor_rows
        ]

        context = {
            **current_scenarios,
            "currentScenarios": current_scenarios,
            "topHeatRiskDestinations": top_heat_risk_destinations,
            "allMetricsByCityDate": heatmap_repository.getAllMetricsByCityDate(
                weather_date=query_date,
                market_code=city,
            ),
        }
        prompt_context = craftContext(
            current_scenarios,
            top_heat_risk_destinations,
            context["allMetricsByCityDate"],
        )
        return {"context": context, "promptContext": prompt_context}

    def startSessionByCityDate(
        self,
        city: Optional[str] = None,
        date: Optional[DateLike] = None,
    ) -> List[Dict[str, Any]]:
        """Build the briefing for a city/date and open a session on it, no DB write.

        Also records the pair on the instance, so later calls can omit the arguments.
        """
        city = city if city is not None else self.city
        date = date if date is not None else self.date
        built = self.buildPromptContext(city, date)
        self.city = city
        self.date = date
        return self.start_session(built["promptContext"])

    def start_session(self, context: Union[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Open a chat session seeded with a briefing. Replaces any session in progress.

        The briefing goes in the first user message (not the system prompt) because it
        changes per city/date; the cache breakpoint sits on that block so the prefix
        stays hot for the rest of the conversation.
        """
        briefing = self._context_to_text(context).strip()
        if not briefing:
            raise ValueError("start_session requires a non-empty context")

        self.messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"<briefing>\n{briefing}\n</briefing>",
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ]
        return self.messages

    def ask(self, question: str, max_tokens: int = CHAT_MAX_TOKENS) -> str:
        """Send a question in the current session. Requires a started session."""
        if not self.messages:
            raise RuntimeError(
                "no active session — construct with city/date or call startSessionByCityDate()"
            )
        if not question or not question.strip():
            raise ValueError("question must not be empty")

        self._append_question(question)

        response = self.client.messages.create(
            model=CHAT_MODEL,
            max_tokens=max_tokens,
            system=CHAT_SYSTEM,
            messages=self.messages,
        )
        answer = "".join(block.text for block in response.content if block.type == "text")
        self.messages.append({"role": "assistant", "content": answer})
        return answer

    def ask_stream(self, question: str, max_tokens: int = CHAT_MAX_TOKENS):
        """Yield answer text as it arrives. History is committed only once the stream ends.

        The caller MUST drain the generator; abandoning it half way leaves the user
        message in ``self.messages`` with no assistant reply after it, which the API
        rejects on the next turn.
        """
        if not self.messages:
            raise RuntimeError(
                "no active session — construct with city/date or call startSessionByCityDate()"
            )
        if not question or not question.strip():
            raise ValueError("question must not be empty")

        self._append_question(question)
        chunks = []
        try:
            with self.client.messages.stream(
                model=CHAT_MODEL,
                max_tokens=max_tokens,
                system=CHAT_SYSTEM,
                messages=self.messages,
            ) as stream:
                for delta in stream.text_stream:
                    chunks.append(delta)
                    yield delta
            self.messages.append({"role": "assistant", "content": "".join(chunks)})
        except BaseException:
            # Roll the half-finished turn back so the session stays usable.
            self._rollback_question()
            raise

    def _append_question(self, question: str) -> None:
        last = self.messages[-1]
        if last["role"] == "user" and isinstance(last["content"], list):
            last["content"].append({"type": "text", "text": question.strip()})
        else:
            self.messages.append({"role": "user", "content": question.strip()})

    def update_session_context_with_simulation(
        self,
        feedback: SimulationFeedback,
    ) -> List[Dict[str, Any]]:
        """Append authoritative simulator results to the active chat session."""
        return self.update_session_context(context=craftSimulationSection(feedback))

    def update_session_context(
        self,
        city: Optional[str] = None,
        date: Optional[DateLike] = None,
        context: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Fold a rebuilt briefing into the running session, keeping the history.

        The new briefing is appended as a fresh user turn rather than written over
        the one at index 0. Editing index 0 in place would invalidate the cache
        breakpoint for the whole conversation, and would leave earlier answers
        citing figures no longer present anywhere in the transcript.

        Pass ``context`` to reuse a briefing you already built; otherwise it is
        rebuilt from city/date. With no active session this falls through to
        ``startSessionByCityDate``.
        """
        if not self.messages:
            if context is not None:
                self.city = city if city is not None else self.city
                self.date = date if date is not None else self.date
                return self.start_session(context)
            return self.startSessionByCityDate(city, date)

        if self.messages[-1]["role"] == "user":
            raise RuntimeError(
                "cannot update context mid-turn — the last user message has no answer"
            )

        if context is None:
            context = self.buildPromptContext(city, date)["promptContext"]
        briefing = self._context_to_text(context).strip()
        if not briefing:
            raise ValueError("update_session_context requires a non-empty context")

        self.city = city if city is not None else self.city
        self.date = date if date is not None else self.date

        self.messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "<briefing-update>\n"
                            "The simulator has been re-run. The figures below supersede "
                            "the earlier briefing; use these for any further answers.\n"
                            f"{briefing}\n"
                            "</briefing-update>"
                        ),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        )
        return self.messages

    def _rollback_question(self) -> None:
        last = self.messages[-1]
        if last["role"] != "user":
            return
        if isinstance(last["content"], list) and len(last["content"]) > 1:
            last["content"].pop()
        else:
            self.messages.pop()

    @classmethod
    def resume(cls, db: Session, state: Dict[str, Any]) -> "ChatbotRepository":
        """Rebuild a repository around a fresh db session from client-held state.

        Skips the constructor's auto-start: the briefing already lives in
        ``state["messages"][0]``, so nothing is re-queried and craftContext is not
        re-run. The state comes back from the browser, so it is validated here.
        """
        if not isinstance(state, dict):
            raise ValueError("session state must be an object")

        messages = state.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("session has no messages — start a new chat")
        if messages[0].get("role") != "user":
            raise ValueError("malformed session: first message must carry the briefing")
        if len(messages) > MAX_SESSION_MESSAGES:
            raise ValueError("session too long — start a new chat")
        if messages[-1].get("role") == "user":
            raise ValueError("malformed session: last turn has no answer")

        repo = cls(db)
        repo.city = state.get("city")
        repo.date = state.get("date")
        repo.messages = messages
        return repo

    def to_state(self) -> Dict[str, Any]:
        """JSON-serializable snapshot of the conversation. Never includes ``db``."""
        return {
            "city": self.city,
            "date": self._json_safe(self.date),
            "messages": self.messages,
        }

    def trim_history(self, keep_turns: int = 12) -> None:
        """Drop the oldest turns, never the briefing at index 0.

        The kept slice is realigned to start on a user turn, otherwise the briefing
        would be followed by a second user message and the API would reject it.
        """
        history = self.messages[1:]
        if len(history) <= keep_turns:
            return
        kept = history[-keep_turns:]
        while kept and kept[0]["role"] != "user":
            kept = kept[1:]
        self.messages = [self.messages[0]] + kept

    def end_session(self) -> None:
        """Clear the conversation. city/date stay set so a session can be reopened."""
        self.messages = []