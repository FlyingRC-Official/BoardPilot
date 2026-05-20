import re
from html import unescape
from html.parser import HTMLParser


class _VisibleTextParser(HTMLParser):
    block_tags = {
        "article",
        "blockquote",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "p",
        "section",
        "td",
        "th",
        "title",
        "tr",
    }
    skip_tags = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.skip_tags:
            self.skip_depth += 1
            return
        if tag == "li":
            self._break()
            self.parts.append("- ")
        elif tag in self.block_tags:
            self._break()

    def handle_endtag(self, tag: str) -> None:
        if tag in self.skip_tags and self.skip_depth:
            self.skip_depth -= 1
            return
        if tag in self.block_tags:
            self._break()

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        text = re.sub(r"\s+", " ", unescape(data)).strip()
        if not text:
            return
        if self.parts and not self.parts[-1].endswith(("\n", " ", "- ")):
            self.parts.append(" ")
        self.parts.append(text)

    def _break(self) -> None:
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")


def parse_webpage_snapshot(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
