import abc
import argparse
import functools
import itertools
import sys
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    Optional,
    Tuple,
    Type,
    TypeVar,
    cast,
)

import json5

from . import dijkstra
from .board_layout import Board, BoardEdge, Corner, Edge, Land, Layout

"""
For the 144p game specifically -

Generates the adjacency list of the map. Uses board_layout.py
"""


T = TypeVar("T")


class _MapMeta(type):
    @functools.cache
    def __call__(cls: Type[T], *args: Any, **kwargs: Any) -> T:
        return super(_MapMeta, cast(_MapMeta, cls)).__call__(*args, **kwargs)


def link_hub(p: Board, q: Board, r: Board, s: Board, t: Board, u: Board) -> None:
    # the left standard-3
    p.edges[Edge.CLOCK6].link(q.edges[Edge.CLOCK9])
    q.edges[Edge.CLOCK6].link(r.edges[Edge.CLOCK9])
    r.edges[Edge.CLOCK6].link(p.edges[Edge.CLOCK9])
    # the right standard-3
    s.edges[Edge.CLOCK6].link(t.edges[Edge.CLOCK9])
    t.edges[Edge.CLOCK6].link(u.edges[Edge.CLOCK9])
    u.edges[Edge.CLOCK6].link(s.edges[Edge.CLOCK9])
    # and link them
    q.edges[Edge.CLOCK3].link(s.edges[Edge.CLOCK3])


def link_spoke(p: Board, q: Board, r: Board, s: Board, t: Board, u: Board) -> None:
    # the left coastline
    p.edges[Edge.CLOCK9].link(q.edges[Edge.CLOCK3])
    q.edges[Edge.CLOCK9].link(r.edges[Edge.CLOCK3])
    # the right coastline
    s.edges[Edge.CLOCK9].link(t.edges[Edge.CLOCK3])
    t.edges[Edge.CLOCK9].link(u.edges[Edge.CLOCK3])
    # and link them
    r.edges[Edge.CLOCK9].link(s.edges[Edge.CLOCK6])


def link_rim(p: Board, q: Board, r: Board, s: Board, t: Board, u: Board) -> None:
    p.edges[Edge.CLOCK9].link(q.edges[Edge.CLOCK9])
    q.edges[Edge.CLOCK6].link(r.edges[Edge.CLOCK6])
    r.edges[Edge.CLOCK9].link(s.edges[Edge.CLOCK3])
    s.edges[Edge.CLOCK9].link(t.edges[Edge.CLOCK3])
    t.edges[Edge.CLOCK9].link(u.edges[Edge.CLOCK3])


class DreamLinker(abc.ABC, Generic[T]):
    @property
    @abc.abstractmethod
    def key(self) -> str:
        pass

    @abc.abstractmethod
    def get(self, board: Board, key: str) -> T:
        pass

    @abc.abstractmethod
    def extract_second(self, data: Any) -> Iterator[Tuple[str, str]]:
        pass

    @abc.abstractmethod
    def link(self, first: T, second: T) -> None:
        pass


class DreamEdgeLinker(DreamLinker):
    key = "edges"

    def get(self, board: Board, key: str) -> BoardEdge:
        edge = getattr(Edge, key.upper())
        return board.edges[edge]

    def extract_second(self, data: Any) -> Iterator[Tuple[str, str]]:
        yield (data["board"], data["edge"])

    def link(self, first: BoardEdge, second: BoardEdge) -> None:
        first.link(second)


class DreamCornerLinker(DreamLinker):
    key = "corners"

    def get(self, board: Board, key: str) -> Land:
        corner = getattr(Corner, key.upper())
        land_number = board.layout.get_corner(corner)
        return board.lands[land_number]

    def extract_second(self, data: Any) -> Iterator[Tuple[str, str]]:
        for item in data:
            yield item["board"], item["corner"]

    def link(self, first: Land, second: Land) -> None:
        first.link(second)


class Map144P(metaclass=_MapMeta):
    def __init__(
        self,
        with_ocean: bool = True,
        weave_file: Optional[str] = None,
    ) -> None:
        self._with_ocean = with_ocean
        with open("config/144p_board_layout.json5", encoding="utf-8") as f:
            self.data = json5.load(f)
        self.boards: Dict[str, Board] = {}
        self._load_continent("blue")
        self._load_continent("orange")
        self._connect_continents()
        self._run_modifications()
        if weave_file:
            self._weave(weave_file)

    def _load_continent(self, name: str) -> None:
        data = self.data[name]

        for islet in data["rim"]:
            self._load_islet(islet, link_rim)
        for islet in data["spokes"]:
            self._load_islet(islet, link_spoke)
        for islet in data["hub"]:
            self._load_islet(islet, link_hub)

        rim_ahead = iter(itertools.cycle(data["rim"]))
        next(rim_ahead)
        for rim1, rim2, spoke in zip(
            data["rim"],  # 🧀
            rim_ahead,  # 🌙
            data["spokes"],  # 🐍
        ):
            rim1p = self.boards[f"{rim1}P"]
            spokep = self.boards[f"{spoke}P"]
            rim2u = self.boards[f"{rim2}U"]
            rim1p.edges[Edge.CLOCK6].link(spokep.edges[Edge.CLOCK3])
            spokep.edges[Edge.CLOCK6].link(rim2u.edges[Edge.CLOCK9])

            rim2s = self.boards[f"{rim2}S"]
            spokeu = self.boards[f"{spoke}U"]
            spokeu.edges[Edge.CLOCK9].link(rim2s.edges[Edge.CLOCK6])

        for spoke1, spoke2, hub in zip(
            data["spokes"][0::2],  # 🐍
            data["spokes"][1::2],  # ♾️
            data["hub"],  # 🏝️
        ):
            spoke1s = self.boards[f"{spoke1}S"]
            hubp = self.boards[f"{hub}P"]
            spoke1s.edges[Edge.CLOCK3].link(hubp.edges[Edge.CLOCK3])

            spoke2s = self.boards[f"{spoke2}S"]
            hubt = self.boards[f"{hub}T"]
            spoke2s.edges[Edge.CLOCK3].link(hubt.edges[Edge.CLOCK3])

        for i in range(3):
            hub1 = data["hub"][(i + 0) % 3]  # 🏝️
            hub2 = data["hub"][(i + 1) % 3]  # 💖
            hub1u = self.boards[f"{hub1}U"]
            hub2r = self.boards[f"{hub2}R"]
            hub1u.edges[Edge.CLOCK3].link(hub2r.edges[Edge.CLOCK3])

        for i in range(6):
            spoke = data["spokes"][i]  # 🐍
            hub1 = data["hub"][((i + 5) // 2) % 3]  # 😎
            hub2 = data["hub"][((i + 1) // 2) % 3]  # 🏝️
            rim = data["rim"][i]  # 🧀

            hub1_letter = "U" if (i % 2 == 0) else "Q"
            hub1_board = self.boards[f"{hub1}{hub1_letter}"]
            if self._with_ocean:
                for spoke_letter in "PQR":
                    self.boards[f"{spoke}{spoke_letter}"].link_archipelago(hub1_board)
                self.boards[f"{rim}Q"].link_archipelago(hub1_board)

                hub2_letter = "T" if (i % 2 == 0) else "P"
                hub2_board = self.boards[f"{hub2}{hub2_letter}"]
                for spoke_letter in "STU":
                    self.boards[f"{spoke}{spoke_letter}"].link_archipelago(hub2_board)

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
        layout = getattr(Layout, self.data["boards"][name])
        board = Board(name, layout, with_ocean=self._with_ocean)
        self.boards[name] = board
        return board

    def _connect_continents(self) -> None:
        if not self._with_ocean:
            return

        for rim1, rim2 in zip(
            self.data["blue"]["rim"],  # 🧀
            self.data["orange"]["rim"],  # 🍌
        ):
            for letter in "PRSTU":
                rim1_board = self.boards[f"{rim1}{letter}"]
                rim2_board = self.boards[f"{rim2}{letter}"]
                rim1_board.link_archipelago(rim2_board)

    def _run_modifications(self) -> None:
        for mod in self.data["modifications"]:
            match mod["power"]:
                case "cast_down":
                    self._cast_down(mod)
                case "deeps":
                    self._deeps(mod)
                case "dream":
                    self._dream(mod)
                case unknown:
                    raise ValueError(f"Unknown modification type {unknown}")

    def _cast_down(self, data: Dict[str, Any]) -> None:
        board = data["board"]
        self.boards[board].cast_down()
        del self.boards[board]
        for land in data.get("weave", ()):
            self.land(land).sink(deeps=False)

    def _deeps(self, data: Dict[str, Any]) -> None:
        self.land(data["land"]).sink(deeps=True)

    def _dream_inner(
        self,
        board: Board,
        data: Dict[str, Any],
        linker_type: Type[DreamLinker],
    ) -> None:
        linker = linker_type()
        if (it := data.get(linker.key)) is None:
            return
        for key, value in it.items():
            assert key.islower()
            first = linker.get(board, key)
            for second_board, second_key in linker.extract_second(value):
                second = linker.get(self.boards[second_board], second_key)
                linker.link(first, second)

    def _dream(self, data: Dict[str, Any]) -> None:
        layout = getattr(Layout, data["layout"])
        board = Board(data["board"], layout, with_ocean=self._with_ocean)
        self.boards[board.name] = board

        self._dream_inner(board, data, DreamEdgeLinker)
        self._dream_inner(board, data, DreamCornerLinker)

    def land(self, key: str) -> Land:
        return self.boards[key[:-1]].lands[int(key[-1])]

    def _weave(self, path: str) -> None:
        with open(path, encoding="utf-8") as f:
            data = json5.load(f)
        for weave in data:
            key1, key2 = weave.split(",")
            try:
                self.land(key1).link(self.land(key2), 0)
            except KeyError:
                pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-archipelago",
        action="store_true",
        help="Don't link archipelagos for distance calculation",
    )
    parser.add_argument(
        "--weaves",
        help="Path to weaves file",
    )
    subparsers = parser.add_subparsers(dest="sub", required=True)
    subparsers.add_parser("json5")
    path_subparser = subparsers.add_parser("path")
    path_subparser.add_argument("src")
    path_subparser.add_argument("dst")
    args = parser.parse_args()

    map = Map144P(with_ocean=not args.no_archipelago, weave_file=args.weaves)

    match args.sub:
        case "json5":
            adj = {
                land.key: list(land.links.keys())
                for board in map.boards.values()
                for land in board.lands.values()
            }
            json5.dump(adj, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
            print()
        case "path":
            dist, prev = dijkstra.distances_from(map.land(args.src))
            print(
                dist[args.dst],
                " ".join(dijkstra.construct_path(prev, args.src, args.dst)),
            )


if __name__ == "__main__":
    main()
