# models.py
from dataclasses import dataclass, asdict
from typing import Optional, List


@dataclass
class BaseMessage:
    type: str

    def to_dict(self):
        return asdict(self)


@dataclass
class NickRequest(BaseMessage):
    type: str = "nick_request"


@dataclass
class Nick(BaseMessage):
    username: str
    type: str = "nick"


@dataclass
class Welcome(BaseMessage):
    text: str
    type: str = "welcome"


@dataclass
class SystemMessage(BaseMessage):
    text: str
    type: str = "system"


@dataclass
class ChatMessage(BaseMessage):
    sender: str
    text: str
    type: str = "chat"


@dataclass
class PrivateMessage(BaseMessage):
    from_user: str
    text: str
    type: str = "pm"


@dataclass
class PrivateMessageSelf(BaseMessage):
    to: str
    text: str
    type: str = "pm_self"


@dataclass
class FileOffer(BaseMessage):
    file_id: str
    sender: str
    filename: str
    file_size: int
    sha256: str
    type: str = "file_offer"


@dataclass
class FileResponse(BaseMessage):
    file_id: str
    accepted: bool
    type: str = "file_response"


@dataclass
class FileChunk(BaseMessage):
    file_id: str
    chunk_index: int
    data_b64: str
    type: str = "file_chunk"


@dataclass
class FileComplete(BaseMessage):
    file_id: str
    type: str = "file_complete"


@dataclass
class UsersList(BaseMessage):
    users: List[str]
    type: str = "users"


@dataclass
class ErrorMessage(BaseMessage):
    text: str
    type: str = "error"


@dataclass
class QuitMessage(BaseMessage):
    type: str = "quit"


@dataclass
class HistoryMessage(BaseMessage):
    messages: List[dict]
    type: str = "history"