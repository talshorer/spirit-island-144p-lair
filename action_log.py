import contextlib
from typing import Iterator, List, Self


class Actionlog:
    def __init__(self) -> None:
        self._indent = 0
        self._entries: List[str] = []

    @contextlib.contextmanager
    def indent(self) -> Iterator[None]:
        self._indent += 1
        try:
            yield
        finally:
            self._indent -= 1

    def entry(self, entry: str) -> None:
        self._entries.append((" " * self._indent * 2) + "- " + entry)

    @contextlib.contextmanager
    def fork(self) -> Iterator[Self]:
        cls = type(self)
        fork = cls()
        fork._indent = self._indent + 1
        try:
            yield fork
        finally:
            self._entries.extend(fork._entries)

    def collapse(self) -> str:
        return "\n".join(self._entries)
