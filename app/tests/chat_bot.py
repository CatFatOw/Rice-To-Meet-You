import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import SessionLocal
from repository.chatbot_repository import ChatbotRepository
from repository.heatmap_repository import HeatmapRepository


if __name__ == "__main__":
    db = SessionLocal()
    try:
        chatbot = ChatbotRepository(
            db,
            city="miami",
            date="2020-06-17",
        )
        for chunk in chatbot.ask_stream(
            "Recommend me 5 urban interventions on specific locations",
            max_tokens=6000,
        ):
            print(chunk, end="", flush=True)
        print()

        simulation = HeatmapRepository(db).get_simulated_points_by_date(
            from_date="2020-06-15",
            to_date="2020-06-18",
            city="miami",
            metric="local_temperature_c",
            mode="contextual",
        )
        chatbot.update_session_context_with_simulation(simulation["feedback"])

        for chunk in chatbot.ask_stream(
            "Which specific locations has seen a drop in local temperature?",
            max_tokens=4000,
        ):
            print(chunk, end="", flush=True)
        print()
    finally:
        db.close()
   