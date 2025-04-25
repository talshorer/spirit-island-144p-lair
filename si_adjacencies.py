from __future__ import annotations

import dataclasses
import enum
from typing import Callable, Dict, Iterator, List, Optional, Self, Set, Tuple, cast


@dataclasses.dataclass
class LayoutEdge:
    lands: list[int]
    boundaries: list[int]


class Edge:
    def __init__(
        self,
        layout: LayoutEdge,
        position: EdgePosition,
        parent: Board,
    ):
        self.lands = tuple(layout.lands[::-1])
        self.boundaries = (0,) + tuple(sorted(layout.boundaries)) + (7,)
        self.position = position
        self.parent = parent
        self.neighbor: Optional[Self] = None

    def cross_adjacencies(self) -> Iterator[Tuple[int, int]]:
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

    def link(self, neighbor: Self) -> None:
        # sorry for really abusing dunders
        assert self.neighbor is None
        assert neighbor.neighbor is None
        self.neighbor = neighbor
        neighbor.neighbor = self


class EdgePosition(enum.Enum):
    # for naming, the ocean is 12 o'clock
    # for values, we pretend the clock is split in 8 to ease corner calc
    CLOCK3 = 2
    CLOCK6 = 4
    CLOCK9 = 6

    @classmethod
    def from_clock(cls, clock: int) -> Optional[Self]:
        clock = (clock + 8) % 8
        if clock in cls:
            return cls(clock)
        return None

    def clockwise_edge(self) -> Optional[Self]:
        return self.from_clock(self.value + 2)

    def counterclockwise_edge(self) -> Optional[Self]:
        return self.from_clock(self.value - 2)

    def clockwise_corner(self) -> Corner:
        return Corner.from_clock(self.value + 1)

    def counterclockwise_corner(self) -> Corner:
        return Corner.from_clock(self.value - 1)


class Corner(enum.Enum):
    # see EdgePosition
    CLOCK1 = 1
    CLOCK5 = 3
    CLOCK7 = 5
    CLOCK11 = 7

    @classmethod
    def from_clock(cls, clock: int) -> Self:
        clock = (clock + 8) % 8
        return cls(clock)

    def clockwise_edge(self) -> Optional[EdgePosition]:
        return EdgePosition.from_clock(self.value + 1)

    def counterclockwise_edge(self) -> Optional[EdgePosition]:
        return EdgePosition.from_clock(self.value - 1)

    def clockwise_corner(self) -> Self:
        return self.from_clock(self.value + 2)

    def counterclockwise_corner(self) -> Self:
        return self.from_clock(self.value - 2)


RotateToEdge = Callable[[EdgePosition | Corner], Optional[EdgePosition]]
RotateToCorner = Callable[[EdgePosition | Corner], Corner]


@dataclasses.dataclass
class Rotate:
    to_edge: RotateToEdge
    to_corner: RotateToCorner


clockwise = Rotate(
    cast(RotateToEdge, lambda item: item.clockwise_edge()),
    cast(RotateToCorner, lambda item: item.clockwise_corner()),
)
counterclockwise = Rotate(
    cast(RotateToEdge, lambda item: item.counterclockwise_edge()),
    cast(RotateToCorner, lambda item: item.counterclockwise_corner()),
)


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
        self.internal_adjacencies: Dict[int, Set[int]] = {
            i + 1: set() for i in range(8)
        }
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
                return self.edges[EdgePosition.CLOCK6].lands[-1]


class Board:
    def __init__(
        self,
        name: str,
        layout: Layout,
    ):
        self.name = name
        self.layout = layout
        self.edges = {pos: Edge(edge, pos, self) for pos, edge in layout.edges.items()}

    def _edge_opt(self, pos: Optional[EdgePosition]):
        if pos is None:
            return None
        return self.edges[pos]

    def _corner_adjacency(
        self,
        corner: Corner,
        rotate: Rotate,
    ) -> Optional[Tuple[Board, int]]:
        edge: Optional[Edge] = self._edge_opt(rotate.to_edge(corner))  # own board edge
        if edge is None or edge.neighbor is None:
            return None
        edge = edge.neighbor  # neighbor's touching edge
        edge = edge.parent._edge_opt(
            rotate.to_edge(edge.position)
        )  # neighbor's rotated edge
        if edge is None or edge.neighbor is None:
            return None
        edge = edge.neighbor  # corner neighbor edge
        # wait, are we in standard-3 configuration?
        standard3check = edge.parent._edge_opt(rotate.to_edge(edge.position))
        if (
            standard3check is not None
            and standard3check.neighbor is not None
            and standard3check.neighbor.parent == self
        ):
            return None
        land = edge.parent.layout.get_corner(rotate.to_corner(edge.position))
        return edge.parent, land

    def adjacent(self, land: int) -> Iterator[Tuple[Board, int]]:
        for i in self.layout.internal_adjacencies[land]:
            yield (self, i)

        yield from (
            (edge.neighbor.parent, j)
            for edge in self.edges.values()
            if edge.neighbor
            for i, j in edge.cross_adjacencies()
            if i == land
        )

        yield from (
            adjacency
            for adjacency in (
                self._corner_adjacency(corner, rotate)
                for corner in Corner
                for rotate in (clockwise, counterclockwise)
                if self.layout.get_corner(corner) == land
            )
            if adjacency is not None
        )


def link_hub(p: Board, q: Board, r: Board, s: Board, t: Board, u: Board):
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


def link_spoke(p: Board, q: Board, r: Board, s: Board, t: Board, u: Board):
    # the left coastline
    p.edges[EdgePosition.CLOCK9].link(q.edges[EdgePosition.CLOCK3])
    q.edges[EdgePosition.CLOCK9].link(r.edges[EdgePosition.CLOCK3])
    # the right coastline
    s.edges[EdgePosition.CLOCK9].link(t.edges[EdgePosition.CLOCK3])
    t.edges[EdgePosition.CLOCK9].link(u.edges[EdgePosition.CLOCK3])
    # and link them
    r.edges[EdgePosition.CLOCK9].link(s.edges[EdgePosition.CLOCK6])


def link_rim(p: Board, q: Board, r: Board, s: Board, t: Board, u: Board):
    p.edges[EdgePosition.CLOCK9].link(q.edges[EdgePosition.CLOCK9])
    q.edges[EdgePosition.CLOCK6].link(r.edges[EdgePosition.CLOCK6])
    r.edges[EdgePosition.CLOCK9].link(s.edges[EdgePosition.CLOCK3])
    s.edges[EdgePosition.CLOCK9].link(t.edges[EdgePosition.CLOCK3])
    t.edges[EdgePosition.CLOCK9].link(u.edges[EdgePosition.CLOCK3])


if __name__ == "__main__":
    p = Board("🌵P", Layout.E)
    q = Board("🌵Q", Layout.H)
    r = Board("🌵R", Layout.G)
    s = Board("🌵S", Layout.H)
    t = Board("🌵T", Layout.D)
    u = Board("🌵U", Layout.F)
    link_rim(p, q, r, s, t, u)

    for board in [p, q, r, s, t, u]:
        for i in range(1, 9):
            adjacencies = ", ".join(
                f"{parent.name}{number}" for parent, number in board.adjacent(i)
            )
            print(f"Neighbors of {board.name}{i}: {adjacencies}")
