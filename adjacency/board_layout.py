from __future__ import annotations

import dataclasses
import enum
from typing import Any, Callable, Dict, Optional, Self, Set, cast

import json5

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
    def __init__(self, board: Board, num: int) -> None:
        self.board = board
        self.num = num
        self.key = f"{board.name}{num}"
        self.links: Dict[str, LandLink] = {}
        self.terrain = board.layout.terrains[num] if num else Terrain.Ocean
        self.coastal = self._is_ocean()

    def _is_ocean(self) -> bool:
        return self.terrain is Terrain.Ocean

    def _link_one_way(self, other: Self, distance: int) -> None:
        if other._is_ocean():
            self.coastal = True
        if (link := self.links.get(other.key)) is not None:
            if distance == 0:
                link.distance = 0  # force a weave
            else:
                assert link.distance in (0, distance)  # don't override a previous weave
            return
        self.links[other.key] = LandLink(distance=distance, land=other)

    def link(self, other: Self, distance: int = 1) -> None:
        self._link_one_way(other, distance)
        other._link_one_way(self, distance)

    def sink(self, deeps: bool) -> None:
        for link in self.links.values():
            other = link.land
            if deeps and link.distance == 1:
                if (ocean := self.board.lands.get(0)) is not None:
                    other.link(ocean)
                else:
                    other.coastal = True
                for board in self.board.archipelago_links.values():
                    for across in board.lands.values():
                        if across.coastal:
                            other.link(across, distance=2)
            del other.links[self.key]
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
            cur: BoardEdge = self
            while True:
                rotated_position = rotate.to_edge(cur.position)
                if rotated_position is None:
                    break
                other_neighbor = cur.parent.edges[rotated_position].neighbor
                if other_neighbor is None:
                    break
                other_neighbor_corner = other_neighbor.parent.layout.get_corner(
                    rotate.to_corner(other_neighbor.position)
                )
                other_neighbor_corner_land = other_neighbor.parent.lands[
                    other_neighbor_corner
                ]
                if other_neighbor_corner_land is neighbor_corner_land:
                    break
                other_neighbor_corner_land.link(neighbor_corner_land)
                cur = other_neighbor

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
    Ocean = "O"


with open("config/board_layout.json5", encoding="utf-8") as f:
    _layout_data = json5.load(f)


class Layout(enum.Enum):
    A = _layout_data["A"]
    B = _layout_data["B"]
    C = _layout_data["C"]
    D = _layout_data["D"]
    E = _layout_data["E"]
    F = _layout_data["F"]
    G = _layout_data["G"]
    H = _layout_data["H"]

    def __init__(
        self,
        data: Any,
    ):
        lands = data["envelope"]
        boundaries = data["boundaries"]
        c1 = len(boundaries[0])
        c2 = c1 + len(boundaries[1])
        self.edges = {
            Edge.CLOCK3: LayoutEdge(lands[: c1 + 1], boundaries[0]),
            Edge.CLOCK6: LayoutEdge(lands[c1 : c2 + 1], boundaries[1]),
            Edge.CLOCK9: LayoutEdge(lands[c2:], boundaries[2]),
        }
        self.internal_adjacencies: Dict[int, Set[int]] = {i: set() for i in range(1, 9)}
        for i, j in data["internal_adjacencies"]:
            self.internal_adjacencies[i].add(j)
            self.internal_adjacencies[j].add(i)
        self.terrains = {i + 1: Terrain(ch) for i, ch in enumerate(data["terrains"])}

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
        with_ocean: bool = True,
    ):
        self.name = name
        self.layout = layout
        self.edges = {
            pos: BoardEdge(edge, pos, self) for pos, edge in layout.edges.items()
        }
        first = 0 if with_ocean else 1
        self.lands = {i: Land(board=self, num=i) for i in range(first, 8 + 1)}
        for n, adj_set in self.layout.internal_adjacencies.items():
            for neigh in adj_set:
                self.lands[n]._link_one_way(self.lands[neigh], 1)
        for n in range(1, 3 + 1):
            land = self.lands[n]
            if with_ocean:
                land.link(self.lands[0])
            else:
                land.coastal = True
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
