# config.py
HOST = "127.0.0.1"
PORT = 65433
HEADER_SIZE = 4
MAX_MESSAGE_SIZE = 10 * 1024 * 1024   # 10 MB maximum for general JSON frames
CHUNK_SIZE = 64 * 1024                # 64 KB binary chunks for flat RAM usage
HISTORY_LIMIT = 50
LOG_FILE = "logs/chat_history.jsonl"