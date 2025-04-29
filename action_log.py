import contextlib
import dataclasses
import enum
from typing import Iterator, List, Optional, Self, Tuple


class Action(enum.Enum):
    COMMENT = enum.auto()
    GATHER = enum.auto()
    ADD = enum.auto()
    DESTROY = enum.auto()
    DOWNGRADE = enum.auto()


@dataclasses.dataclass
class LogEntry:
    action: Action = Action.COMMENT
    text: Optional[str] = None
    src_land: Optional[str] = None
    src_piece: Optional[str] = None
    tgt_land: Optional[str] = None
    tgt_piece: Optional[str] = None
    count: int = 0


class Actionlog:
    def __init__(self) -> None:
        self._nest = 0
        self.entries: List[Tuple[int, LogEntry]] = []

    @contextlib.contextmanager
    def indent(self) -> Iterator[None]:
        self._nest += 1
        try:
            yield
        finally:
            self._nest -= 1

    def entry(self, entry: LogEntry) -> None:
        match entry.action:
            case Action.COMMENT:
                assert entry.text
            case Action.GATHER:
                assert entry.src_land
                assert entry.src_piece
                assert entry.tgt_land
                assert entry.count
            case Action.ADD:
                assert entry.tgt_land
                assert entry.tgt_piece
                assert entry.count
            case Action.DESTROY:
                assert entry.src_land
                assert entry.src_piece
                assert entry.count
            case Action.DOWNGRADE:
                assert entry.src_land
                assert entry.src_piece
                assert entry.tgt_piece
                assert entry.count
        self.entries.append((self._nest, entry))

    @contextlib.contextmanager
    def fork(self) -> Iterator[Self]:
        cls = type(self)
        fork = cls()
        fork._nest = self._nest + 1
        try:
            yield fork
        finally:
            self.entries.extend(fork.entries)
