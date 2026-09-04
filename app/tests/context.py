import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.chat_bot import createContext


if __name__ == "__main__":
	context_id = createContext("miami", "2020-06-15")
	print(context_id)
