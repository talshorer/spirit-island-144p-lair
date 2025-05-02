import argparse
import collections
from typing import Dict, List

from . import dijkstra, gen_144p


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lands",
        nargs="*",
        default=[],
        help="Lands from which to measure distance",
    )

    args = parser.parse_args()
    map = gen_144p.Map144P()
    all_dist: Dict[str, int] = {}
    for land in args.lands:
        dist, _ = dijkstra.distances_from(map.land(land))
        for k, v in dist.items():
            prev = all_dist.get(k)
            if prev is None or prev > v:
                all_dist[k] = v
    by_dist: Dict[int, List[str]] = collections.defaultdict(list)
    for k, v in all_dist.items():
        if not map.land(k).coastal:
            continue
        by_dist[v].append(k)
    for k2 in sorted(by_dist.keys()):
        print(k2, by_dist[k2])


if __name__ == "__main__":
    main()
