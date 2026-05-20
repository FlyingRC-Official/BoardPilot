from typing import Protocol


class StorageProvider(Protocol):
    def save_text(self, path: str, content: str) -> str:
        ...

    def save_bytes(self, path: str, content: bytes) -> str:
        ...
