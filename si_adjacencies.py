from __future__ import annotations

import dataclasses
import enum
from typing import List


@dataclasses.dataclass
class LayoutEdge:
    lands: list[int]
    boundaries: list[int]


class Edge:
    def __init__(self, layout: LayoutEdge, parent: Board):
        self.lands = tuple(layout.lands[::-1])
        self.boundaries = (0,) + tuple(sorted(layout.boundaries)) + (7,)
        self.parent = parent
        self.neighbor = None

    def cross_adjacencies(self):
        assert self.neighbor

        self_pos = 1
        neighbor_pos = -2
        while True:
            try:
                self_next = self.boundaries[self_pos]
                neighbor_next = self.neighbor.boundaries[neighbor_pos]
            except IndexError:
                break
            yield (self.lands[self_pos - 1], self.neighbor.lands[neighbor_pos + 1])
            if self_next + neighbor_next > 6:
                neighbor_pos -= 1
            else:
                self_pos += 1

    def link(self, neighbor):
        # sorry for really abusing dunders
        assert self.neighbor is None
        assert neighbor.neighbor is None
        self.neighbor = neighbor
        neighbor.neighbor = self


class EdgePosition(enum.Enum):
    # the ocean is 12 o'clock
    CLOCK3 = enum.auto()
    CLOCK6 = enum.auto()
    CLOCK9 = enum.auto()


class Corner(enum.Enum):
    # the ocean is 12 o'clock
    CLOCK1 = enum.auto()
    CLOCK5 = enum.auto()
    CLOCK7 = enum.auto()
    CLOCK11 = enum.auto()


class Layout(enum.Enum):

    A = ([1, 6, 8, 7, 5, 4, 3], [5, 3, None, 4, None, 6, 5, 3], "2456,34,4,5,678,8,8")
    B = ([1, 6, 8, 7, 4, 3], [6, 3, None, 4, None, 6, 4], "2456,34,4,57,67,78,8")
    C = ([1, 6, 8, 7, 4, 3], [5, 3, None, 3, 1, None, 3], "256,345,4,57,67,78,8")
    D = ([1, 8, 7, 6, 4, 3], [1, None, 4, 1, None, 5, 2], "2578,345,4,56,67,7,8")
    E = ([1, 7, 8, 6, 4, 3], [4, 2, None, 2, None, 6, 3], "257,35,45,567,7,78,8")
    F = ([1, 6, 8, 7, 4, 3], [4, 1, None, 3, None, 5, 2], "256,345,4,578,68,8,8")
    G = ([1, 6, 8, 7, 4, 3], [4, 2, None, 3, None, 6, 4], "26,3456,4,57,678,8,8")
    H = ([1, 8, 7, 4, 3], [3, None, 5, 1, None, 3], "268,356,45,57,67,78,8")

    def __init__(
        self,
        lands: List[int],
        boundaries: List[int],
        internal_adjacencies: str,
    ):
        """
        Lands around the edge in clockwise order starting from 1.
        Boundaries in the same order, None for corners.
        """

        c1, c2 = [i for i, x in enumerate(boundaries) if x is None]
        self.edges = {
            EdgePosition.CLOCK3: LayoutEdge(lands[: c1 + 1], boundaries[:c1]),
            EdgePosition.CLOCK6: LayoutEdge(lands[c1:c2], boundaries[c1 + 1 : c2]),
            EdgePosition.CLOCK9: LayoutEdge(lands[c2 - 1 :], boundaries[c2 + 1 :]),
        }
        self.internal_adjacencies = {i + 1: set() for i in range(8)}
        for i, val in enumerate(internal_adjacencies.split(",")):
            for n in val:
                self.internal_adjacencies[i + 1].add(int(n))
                self.internal_adjacencies[int(n)].add(i + 1)

    def get_corner(self, corner: Corner) -> int:
        match corner:
            case Corner.CLOCK1:
                return 1
            case Corner.CLOCK11:
                return 3
            case Corner.CLOCK5:
                return self.edges[EdgePosition.CLOCK3].lands[-1]
            case Corner.CLOCK7:
                return self.edges[EdgePosition.CLOCK9].lands[-1]


class Board:
    def __init__(
        self,
        name: str,
        layout: Layout,
    ):
        self.name = name
        self.layout = layout
        self.edges = {pos: Edge(edge, self) for pos, edge in layout.edges.items()}

    def adjacent(self, land):
        for i in self.layout.internal_adjacencies[land]:
            yield (self, i)

        yield from (
            (edge.neighbor.parent, j)
            for edge in self.edges.values()
            if edge.neighbor
            for i, j in edge.cross_adjacencies()
            if i == land
        )

        # TODO corner adjacencies


if __name__ == "__main__":

    def debug_edges(edge1, edge2):
        for i, j in edge1 @ edge2:
            print(f"{i} {j}")

    p = Board("🐑P", Layout.H)
    q = Board("🐑Q", Layout.A)
    r = Board("🐑R", Layout.D)

    p.edges[EdgePosition.CLOCK6].link(q.edges[EdgePosition.CLOCK9])
    q.edges[EdgePosition.CLOCK6].link(r.edges[EdgePosition.CLOCK9])
    r.edges[EdgePosition.CLOCK6].link(p.edges[EdgePosition.CLOCK9])

    for i in range(1, 9):
        print(
            f'Neighbors of 🐑P{i}: {", ".join(f"{board.name}{number}" for board, number in p.adjacent(i))}'
        )
