import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import SessionLocal
from repository.chatbot_repository import ChatbotRepository


if __name__ == "__main__":
	db = SessionLocal()
	try:
		context_id = ChatbotRepository(db).createContext("miami", "2020-06-15")
		print(context_id)
	finally:
		db.close()
