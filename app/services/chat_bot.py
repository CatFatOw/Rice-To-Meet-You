import asyncio
import uuid
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Any, Dict, Union

from database import SessionLocal
from repository.final_visitor_repository import VisitorRepository
from repository.heatmap_repository import HeatmapRepository
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.craft_context import craftContext


DateLike = Union[str, date_type, datetime]


def _json_safe(value: Any) -> Any:
	if isinstance(value, Decimal):
		return float(value)
	if isinstance(value, (datetime, date_type)):
		return value.isoformat()
	return value


def _coerce_date(value: DateLike) -> date_type:
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, date_type):
		return value
	return date_type.fromisoformat(str(value).strip()[:10])


async def upload_chatbot_context(
	db: Any,
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

	if isinstance(db, AsyncSession):
		result = await db.execute(statement, params)
		await db.commit()
	else:
		result = db.execute(statement, params)
		db.commit()

	return str(result.scalar_one())


def craftCurrentScenarios(city: str, date: DateLike) -> Dict[str, Any]:
	"""Return the current scenario context placeholder for a city and date."""
	return {"city": city, "date": date}


def createContext(city: str, date: DateLike) -> Dict[str, Any]:
	"""Build the context used by the chat bot for a city and date."""
	query_date = _coerce_date(date)
	current_scenarios = craftCurrentScenarios(city, date)
	db = SessionLocal()
	try:
		visitor_repository = VisitorRepository(db)
		heatmap_repository = HeatmapRepository(db)

		visitor_rows = visitor_repository.queryVisitorRowsWithGeometryByCityDate(
			city,
			query_date,
			sorted=True,
			limit=10,
		)
		top_heat_risk_destinations = [
			{
				key: _json_safe(value)
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
		return {"context_id": asyncio.run(upload_chatbot_context(db, prompt_context))}
	finally:
		db.close()
