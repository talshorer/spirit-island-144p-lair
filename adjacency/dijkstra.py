import dataclasses
from typing import Dict, Self, Set, Tuple

from .board_layout import Land


@dataclasses.dataclass
class _Dist:
    key: str
    value: int
    land: Land

    def __lt__(self, other: Self) -> bool:
        return self.value.__lt__(other.value)


def distances_from(land: Land) -> Tuple[Dict[str, int], Dict[str, str]]:
    visited: Set[str] = set()
    queue: Dict[str, Land] = {}
    dist: Dict[str, int] = {}
    prev: Dict[str, str] = {}
    dist[land.key] = 0
    queue[land.key] = land
    while queue:
        vertex = min(queue.values(), key=lambda v: dist[v.key])
        del queue[vertex.key]
        visited.add(vertex.key)
        base = dist[vertex.key]
        for key, link in vertex.links.items():
            if key in visited:
                continue
            queue[key] = link.land
            alt = base + link.distance
            if key not in dist or alt < dist[key]:
                dist[key] = alt
                prev[key] = vertex.key
    return dist, prev
