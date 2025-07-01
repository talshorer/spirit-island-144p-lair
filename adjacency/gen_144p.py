import argparse
import functools
import itertools
from typing import Callable

import json5

from . import anymap
from .board_layout import Board, Edge, Layout

"""
For the 144p game specifically -

Generates the adjacency list of the map. Uses board_layout.py
"""


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


@functools.cache
class Map144P(anymap.Map):
    def _load(self) -> None:
        with open("config/144p_board_layout.json5", encoding="utf-8") as f:
            self._data = json5.load(f)
        self._load_continent("blue")
        self._load_continent("orange")
        self._connect_continents()
        self._run_modifications(self._data["modifications"])

    def _load_continent(self, name: str) -> None:
        data = self._data[name]

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
            if self._conf.with_ocean:
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
        layout = getattr(Layout, self._data["boards"][name])
        board = Board(name, layout, with_ocean=self._conf.with_ocean)
        self.boards[name] = board
        return board

    def _connect_continents(self) -> None:
        if not self._conf.with_ocean:
            return

        for rim1, rim2 in zip(
            self._data["blue"]["rim"],  # 🧀
            self._data["orange"]["rim"],  # 🍌
        ):
            for letter in "PRSTU":
                rim1_board = self.boards[f"{rim1}{letter}"]
                rim2_board = self.boards[f"{rim2}{letter}"]
                rim1_board.link_archipelago(rim2_board)


if __name__ == "__main__":
    anymap.main(Map144P, argparse.ArgumentParser())
