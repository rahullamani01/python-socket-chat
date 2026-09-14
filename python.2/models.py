
from dataclasses import dataclass, asdict
from typing import Optional, List
from datetime import datetime


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
class FileMessage(BaseMessage):
    sender: str
    filename: str
    file_data: str
    type: str = "file"


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