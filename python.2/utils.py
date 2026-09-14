# chat/utils.py
import os
import base64
import json
import logging
from datetime import datetime
from config import LOG_FILE, MAX_FILE_SIZE


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("logs/server.log"),
            logging.StreamHandler()
        ]
    )


def log_message(sender: str, recipient: str, content: str, msg_type: str = "broadcast"):
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sender": sender,
        "recipient": recipient,
        "type": msg_type,
        "content": content,
    }
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        logging.error(f"Failed to write log: {e}")


def file_to_base64(file_path: str) -> str:
    size = os.path.getsize(file_path)
    if size > MAX_FILE_SIZE:
        raise ValueError(f"File too large (max {MAX_FILE_SIZE // 1024 // 1024} MB)")
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def base64_to_file(base64_str: str, output_path: str):
    file_bytes = base64.b64decode(base64_str.encode("utf-8"))
    with open(output_path, "wb") as f:
        f.write(file_bytes)