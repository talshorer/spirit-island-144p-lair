import contextlib
import dataclasses
import enum
from typing import Iterator, List, Optional, Self, Tuple, TypeVar, Union

T = TypeVar("T")


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
    tgt_land: Optional[str] = None
    src_piece: Union[str | List[str]] = ""
    tgt_piece: Union[str | List[str]] = ""
    count: Union[int | List[int]] = 0

    @staticmethod
    def _listify_one(v: Union[T | List[T]]) -> List[T]:
        if isinstance(v, list):
            return v
        return [v]

    def _listify_pieces(self) -> None:
        self.src_piece = self._listify_one(self.src_piece)
        self.tgt_piece = self._listify_one(self.tgt_piece)
        self.count = self._listify_one(self.count)

    def pieces(self) -> Iterator[Tuple[str, str, int]]:
        "for src, tgt, cnt in entry.pieces():"
        if isinstance(self.src_piece, str):
            assert isinstance(self.tgt_piece, str)
            assert isinstance(self.count, int)
            yield (self.src_piece, self.tgt_piece, self.count)
        elif isinstance(self.src_piece, list):
            assert isinstance(self.tgt_piece, list)
            assert isinstance(self.count, list)
            assert len(self.src_piece) == len(self.tgt_piece) == len(self.count)
            yield from zip(self.src_piece, self.tgt_piece, self.count)

    def total_count(self) -> int:
        if isinstance(self.count, int):
            return self.count
        return sum(self.count)


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

    def _can_merge(self, entry: LogEntry) -> bool:
        if not self.entries:
            return False
        last_nest, last_entry = self.entries[-1]
        return (
            self._nest == last_nest
            and entry.action == last_entry.action
            and entry.text == last_entry.text
            and entry.src_land == last_entry.src_land
            and entry.tgt_land == last_entry.tgt_land
        )

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
        if self._can_merge(entry):
            _, last_entry = self.entries[-1]
            last_entry._listify_pieces()

            assert isinstance(last_entry.src_piece, list)
            assert isinstance(entry.src_piece, str), entry
            last_entry.src_piece.append(entry.src_piece)

            assert isinstance(last_entry.tgt_piece, list)
            assert isinstance(entry.tgt_piece, str), entry
            last_entry.tgt_piece.append(entry.tgt_piece)

            assert isinstance(last_entry.count, list)
            assert isinstance(entry.count, int)
            last_entry.count.append(entry.count)
        else:
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
