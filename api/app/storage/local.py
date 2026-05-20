from pathlib import Path


class LocalStorageProvider:
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save_text(self, path: str, content: str) -> str:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

