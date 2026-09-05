import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import SessionLocal
from repository.chatbot_repository import ChatbotRepository


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
            max_tokens=4000,
        ):
            print(chunk, end="", flush=True)
        print()
    finally:
        db.close()
   