import itertools
import json
from typing import Any, Callable, Dict, List

from layout import Board, EdgePosition, Layout


def link_hub(p: Board, q: Board, r: Board, s: Board, t: Board, u: Board) -> None:
    # the left standard-3
    p.edges[EdgePosition.CLOCK6].link(q.edges[EdgePosition.CLOCK9])
    q.edges[EdgePosition.CLOCK6].link(r.edges[EdgePosition.CLOCK9])
    r.edges[EdgePosition.CLOCK6].link(p.edges[EdgePosition.CLOCK9])
    # the right standard-3
    s.edges[EdgePosition.CLOCK6].link(t.edges[EdgePosition.CLOCK9])
    t.edges[EdgePosition.CLOCK6].link(u.edges[EdgePosition.CLOCK9])
    u.edges[EdgePosition.CLOCK6].link(s.edges[EdgePosition.CLOCK9])
    # and link them
    q.edges[EdgePosition.CLOCK3].link(s.edges[EdgePosition.CLOCK3])


def link_spoke(p: Board, q: Board, r: Board, s: Board, t: Board, u: Board) -> None:
    # the left coastline
    p.edges[EdgePosition.CLOCK9].link(q.edges[EdgePosition.CLOCK3])
    q.edges[EdgePosition.CLOCK9].link(r.edges[EdgePosition.CLOCK3])
    # the right coastline
    s.edges[EdgePosition.CLOCK9].link(t.edges[EdgePosition.CLOCK3])
    t.edges[EdgePosition.CLOCK9].link(u.edges[EdgePosition.CLOCK3])
    # and link them
    r.edges[EdgePosition.CLOCK9].link(s.edges[EdgePosition.CLOCK6])


def link_rim(p: Board, q: Board, r: Board, s: Board, t: Board, u: Board) -> None:
    p.edges[EdgePosition.CLOCK9].link(q.edges[EdgePosition.CLOCK9])
    q.edges[EdgePosition.CLOCK6].link(r.edges[EdgePosition.CLOCK6])
    r.edges[EdgePosition.CLOCK9].link(s.edges[EdgePosition.CLOCK3])
    s.edges[EdgePosition.CLOCK9].link(t.edges[EdgePosition.CLOCK3])
    t.edges[EdgePosition.CLOCK9].link(u.edges[EdgePosition.CLOCK3])


class Loader:
    def __init__(
        self,
        data: Dict[str, Any],
    ):
        self._data = data
        self.boards: Dict[str, Board] = {}
        self._load_continent("blue")
        self._load_continent("orange")

    def _load_continent(self, name: str) -> None:
        for islet in self._data[name]["rim"]:
            self._load_islet(islet, link_rim)
        for islet in self._data[name]["spokes"]:
            self._load_islet(islet, link_spoke)
        for islet in self._data[name]["hub"]:
            self._load_islet(islet, link_hub)

        rim_ahead = iter(itertools.cycle(self._data[name]["rim"]))
        next(rim_ahead)
        for rim1, rim2, spoke in zip(
            self._data[name]["rim"],  # 🧀
            rim_ahead,  # 🌙
            self._data[name]["spokes"],  # 🐍
        ):
            rim1p = self.boards[f"{rim1}P"]
            spokep = self.boards[f"{spoke}P"]
            rim2u = self.boards[f"{rim2}U"]
            rim1p.edges[EdgePosition.CLOCK6].link(spokep.edges[EdgePosition.CLOCK3])
            spokep.edges[EdgePosition.CLOCK6].link(rim2u.edges[EdgePosition.CLOCK9])

            rim2s = self.boards[f"{rim2}S"]
            spokeu = self.boards[f"{spoke}U"]
            spokeu.edges[EdgePosition.CLOCK9].link(rim2s.edges[EdgePosition.CLOCK6])

        for spoke1, spoke2, hub in zip(
            self._data[name]["spokes"][0::2],  # 🐍
            self._data[name]["spokes"][1::2],  # ♾️
            self._data[name]["hub"],  # 🏝️
        ):
            spoke1s = self.boards[f"{spoke1}S"]
            hubp = self.boards[f"{hub}P"]
            spoke1s.edges[EdgePosition.CLOCK3].link(hubp.edges[EdgePosition.CLOCK3])

            spoke2s = self.boards[f"{spoke2}S"]
            hubt = self.boards[f"{hub}T"]
            spoke2s.edges[EdgePosition.CLOCK3].link(hubt.edges[EdgePosition.CLOCK3])

    def _load_islet(
        self,
        name: str,
        link: Callable[
            [
                Board,
                Board,
                Board,
                Board,
                Board,
                Board,
            ],
            None,
        ],
    ) -> None:
        p = self._load_board(name, "P")
        q = self._load_board(name, "Q")
        r = self._load_board(name, "R")
        s = self._load_board(name, "S")
        t = self._load_board(name, "T")
        u = self._load_board(name, "U")
        link(p, q, r, s, t, u)

    def _load_board(self, islet: str, letter: str) -> Board:
        name = f"{islet}{letter}"
        if islet in self._data["missing"]:
            layout = Layout.A
        else:
            layout = getattr(Layout, self._data["boards"][name])
        board = Board(name, layout)
        self.boards[name] = board
        return board


def main() -> None:
    with open("board-layout.json") as f:
        data = json.load(f)
    boards = Loader(data).boards
    for name in [
        "🌱P",
        "🌱Q",
        "🌱R",
        "🌱S",
        "🌱T",
        "🌱U",
    ]:
        board = boards[name]
        for i in range(1, 9):
            adjacencies = ", ".join(
                f"{parent.name}{number}{parent.layout.terrains[number].value}"
                for parent, number in board.adjacent(i)
            )
            print(
                f"Neighbors of {board.name}{i}{board.layout.terrains[i].value}: {adjacencies}"
            )


if __name__ == "__main__":
    main()
