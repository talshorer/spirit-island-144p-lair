from __future__ import annotations

import dataclasses
import enum
from typing import Callable, Dict, Iterator, List, Optional, Self, Set, Tuple, cast

"""
For a given list of boards (in the specified format) -

Generates an adjacency list of every land on that board.
"""


@dataclasses.dataclass
class LayoutEdge:
    lands: list[int]
    boundaries: list[int]


@dataclasses.dataclass
class LandLink:
    distance: int
    land: Land


class Land:
    def __init__(self, board: Board, num: int, coastal: bool) -> None:
        self.board = board
        self.num = num
        self.key = f"{board.name}{num}"
        self.links: Dict[str, LandLink] = {}
        self.terrain = board.layout.terrains[num]
        self.coastal = coastal

    def _link_one_way(self, other: Self, distance: int) -> None:
        if (link := self.links.get(other.key)) is not None:
            assert link.distance == distance
            return
        self.links[other.key] = LandLink(distance=distance, land=other)

    def link(self, other: Self, distance: int = 1) -> None:
        self._link_one_way(other, distance)
        other._link_one_way(self, distance)

    def sink(self, deeps: bool) -> None:
        for link in self.links.values():
            if deeps:
                link.land.coastal = True
                # we're coastal now, link archipelago!
                for board in self.board.archipelago_links.values():
                    for other in board.lands.values():
                        self.link(other, distance=2)
            del link.land.links[self.key]
        del self.board.lands[self.num]


class BoardEdge:
    def __init__(
        self,
        layout: LayoutEdge,
        position: Edge,
        parent: Board,
    ):
        self.lands = tuple(layout.lands[::-1])
        self.boundaries = (0,) + tuple(sorted(layout.boundaries)) + (7,)
        self.position = position
        self.parent = parent
        self.neighbor: Optional[Self] = None

    def _link_corners(self, neighbor: Self) -> None:
        for rotate, antirotate in (
            (clockwise, counterclockwise),
            (counterclockwise, clockwise),
        ):
            neighbor_corner = neighbor.parent.layout.get_corner(
                antirotate.to_corner(neighbor.position)
            )
            neighbor_corner_land = neighbor.parent.lands[neighbor_corner]
            rotated_position = rotate.to_edge(self.position)
            if rotated_position is None:
                continue
            other_neighbor = self.parent.edges[rotated_position].neighbor
            if other_neighbor is None:
                continue
            other_neighbor_corner = other_neighbor.parent.layout.get_corner(
                rotate.to_corner(other_neighbor.position)
            )
            other_neighbor_corner_land = other_neighbor.parent.lands[
                other_neighbor_corner
            ]
            other_neighbor_corner_land.link(neighbor_corner_land)

    def link(self, neighbor: Self) -> None:
        assert self.neighbor is None
        assert neighbor.neighbor is None
        self.neighbor = neighbor
        neighbor.neighbor = self
        assert self.neighbor

        self_pos = 1
        neighbor_pos = -2
        while True:
            try:
                self_next = self.boundaries[self_pos]
                neighbor_next = neighbor.boundaries[neighbor_pos]
            except IndexError:
                break
            self.parent.lands[self.lands[self_pos - 1]].link(
                neighbor.parent.lands[neighbor.lands[neighbor_pos + 1]]
            )
            if self_next + neighbor_next > 6:
                neighbor_pos -= 1
            else:
                self_pos += 1

        self._link_corners(neighbor)
        neighbor._link_corners(self)


class Edge(enum.Enum):
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
    # see Edge
    CLOCK1 = 1
    CLOCK5 = 3
    CLOCK7 = 5
    CLOCK11 = 7

    @classmethod
    def from_clock(cls, clock: int) -> Self:
        clock = (clock + 8) % 8
        return cls(clock)

    def clockwise_edge(self) -> Optional[Edge]:
        return Edge.from_clock(self.value + 1)

    def counterclockwise_edge(self) -> Optional[Edge]:
        return Edge.from_clock(self.value - 1)

    def clockwise_corner(self) -> Self:
        return self.from_clock(self.value + 2)

    def counterclockwise_corner(self) -> Self:
        return self.from_clock(self.value - 2)


RotateToEdge = Callable[[Edge | Corner], Optional[Edge]]
RotateToCorner = Callable[[Edge | Corner], Corner]


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


class Terrain(enum.Enum):
    Jungle = "J"
    Mountain = "M"
    Sands = "S"
    Wetlands = "W"


class Layout(enum.Enum):
    A = (
        [1, 6, 8, 7, 5, 4, 3],
        [5, 3, None, 4, None, 6, 5, 3],
        "2456,34,4,5,678,8,8",
        "MWJSWMSJ",
    )
    B = (
        [1, 6, 8, 7, 4, 3],
        [6, 3, None, 4, None, 6, 4],
        "2456,34,4,57,67,78,8",
        "WMSJSWMJ",
    )
    C = (
        [1, 6, 8, 7, 4, 3],
        [5, 3, None, 3, 1, None, 3],
        "256,345,4,57,67,78,8",
        "JSMJWSMW",
    )
    D = (
        [1, 8, 7, 6, 4, 3],
        [1, None, 4, 1, None, 5, 2],
        "2578,345,4,56,67,7,8",
        "WJWSMJSM",
    )
    E = (
        [1, 7, 8, 6, 4, 3],
        [4, 2, None, 2, None, 6, 3],
        "257,35,45,567,7,78,8",
        "SMJWMSJW",
    )
    F = (
        [1, 6, 8, 7, 4, 3],
        [4, 1, None, 3, None, 5, 2],
        "256,345,4,578,68,8,8",
        "SJWMJMWS",
    )
    G = (
        [1, 6, 8, 7, 4, 3],
        [4, 2, None, 3, None, 6, 4],
        "26,3456,4,57,678,8,8",
        "MWSWSJJM",
    )
    H = ([1, 8, 7, 4, 3], [3, None, 5, 1, None, 3], "268,356,45,57,67,78,8", "JSMMJWWS")

    def __init__(
        self,
        lands: List[int],
        boundaries: List[int],
        internal_adjacencies: str,
        terrains: str,
    ):
        """
        Lands around the edge in clockwise order starting from 1.
        Boundaries in the same order, None for corners.
        """

        c1, c2 = [i for i, x in enumerate(boundaries) if x is None]
        self.edges = {
            Edge.CLOCK3: LayoutEdge(lands[: c1 + 1], boundaries[:c1]),
            Edge.CLOCK6: LayoutEdge(lands[c1:c2], boundaries[c1 + 1 : c2]),
            Edge.CLOCK9: LayoutEdge(lands[c2 - 1 :], boundaries[c2 + 1 :]),
        }
        self.internal_adjacencies: Dict[int, Set[int]] = {
            i + 1: set() for i in range(8)
        }
        for i, val in enumerate(internal_adjacencies.split(",")):
            for n in val:
                self.internal_adjacencies[i + 1].add(int(n))
                self.internal_adjacencies[int(n)].add(i + 1)
        self.terrains = {i + 1: Terrain(ch) for i, ch in enumerate(terrains)}

    def get_corner(self, corner: Corner) -> int:
        match corner:
            case Corner.CLOCK1:
                return 1
            case Corner.CLOCK11:
                return 3
            case Corner.CLOCK5:
                return self.edges[Edge.CLOCK3].lands[-1]
            case Corner.CLOCK7:
                return self.edges[Edge.CLOCK6].lands[-1]


class Board:
    def __init__(
        self,
        name: str,
        layout: Layout,
    ):
        self.name = name
        self.layout = layout
        self.edges = {
            pos: BoardEdge(edge, pos, self) for pos, edge in layout.edges.items()
        }
        self.lands = {i: Land(board=self, num=i, coastal=(i <= 3)) for i in range(1, 9)}
        for n, adj_set in self.layout.internal_adjacencies.items():
            for neigh in adj_set:
                self.lands[n]._link_one_way(self.lands[neigh], 1)
        self.archipelago_links: Dict[str, Self] = {}

    def _link_archipelago_one_way(self, other: Self) -> None:
        assert other.name not in self.archipelago_links
        self.archipelago_links[other.name] = other

    def link_archipelago(self, other: Self) -> None:
        self._link_archipelago_one_way(other)
        other._link_archipelago_one_way(self)
        for self_land in self.lands.values():
            if not self_land.coastal:
                continue
            for other_land in other.lands.values():
                if not other_land.coastal:
                    continue
                self_land.link(other=other_land, distance=2)

    def cast_down(self) -> None:
        for land in list(self.lands.values()):
            land.sink(deeps=False)

        for other in self.archipelago_links.values():
            del other.archipelago_links[self.name]
