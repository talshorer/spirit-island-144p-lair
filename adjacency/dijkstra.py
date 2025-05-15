import dataclasses
from typing import Callable, Dict, List, Protocol, Self, Set, Tuple

from .board_layout import Land


@dataclasses.dataclass
class _Dist:
    key: str
    value: int
    land: Land

    def __lt__(self, other: Self) -> bool:
        return self.value.__lt__(other.value)


class Comparable(Protocol):
    def __lt__(self: Self, other: Self) -> bool:
        pass


def _default_tiebreaker(
    land: Land,
    dist: Dict[str, int],
    prev: Dict[str, str],
) -> Comparable:
    return 0


def distances_from(
    land: Land,
    tiebreaker: Callable[
        [
            Land,
            Dict[str, int],
            Dict[str, str],
        ],
        Comparable,
    ] = _default_tiebreaker,
) -> Tuple[Dict[str, int], Dict[str, str]]:
    visited: Set[str] = set()
    queue: Dict[str, Land] = {}
    dist: Dict[str, int] = {}
    prev: Dict[str, str] = {}
    priority: Dict[str, Comparable] = {}
    dist[land.key] = 0
    queue[land.key] = land
    priority[land.key] = tiebreaker(land, dist, prev)
    while queue:
        vertex = min(queue.values(), key=lambda v: dist[v.key])
        del queue[vertex.key]
        if vertex.key not in priority:
            priority[vertex.key] = tiebreaker(vertex, dist, prev)
        visited.add(vertex.key)
        base = dist[vertex.key]
        for key, link in vertex.links.items():
            if key in visited:
                continue
            queue[key] = link.land
            alt = base + link.distance
            if key in dist and alt > dist[key]:
                continue
            if (
                key in dist
                and alt == dist[key]
                and priority[vertex.key] > priority[prev[key]]
            ):
                continue
            dist[key] = alt
            prev[key] = vertex.key
    return dist, prev


def construct_path(prev: Dict[str, str], src: str, dst: str) -> List[str]:
    path = [dst]
    while dst != src:
        dst = prev[dst]
        path.append(dst)
    return path[::-1]
