# utils.py
import os
import json
import logging
import hashlib
from datetime import datetime
from config import LOG_FILE, CHUNK_SIZE


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


def calculate_sha256(file_path: str) -> str:
    """Computes SHA-256 hash incrementally in chunks."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()


def verify_file_integrity(file_path: str, expected_hash: str) -> bool:
    """Verifies file hash against expected checksum."""
    if not os.path.exists(file_path):
        return False
    return calculate_sha256(file_path) == expected_hash