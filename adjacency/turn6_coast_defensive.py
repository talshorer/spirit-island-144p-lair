import argparse
import collections
import json
import multiprocessing
import sys
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple

from . import dijkstra, gen_144p

map: Optional[gen_144p.Map144P] = None
dijstra_cache: Dict[str, Dict[str, int]] = {}


def tryone(lands: List[str]) -> Tuple[int, List[str], Dict[int, List[str]]]:
    global map
    if map is None:
        map = gen_144p.Map144P()
    all_dist: Dict[str, int] = {}
    for land in lands:
        if land not in dijstra_cache:
            dist, _ = dijkstra.distances_from(map.land(land))
            dijstra_cache[land] = dist
        else:
            dist = dijstra_cache[land]
        for k, v in dist.items():
            prev = all_dist.get(k)
            if prev is None or prev > v:
                all_dist[k] = v
    by_dist: Dict[int, List[str]] = collections.defaultdict(list)
    for k, v in all_dist.items():
        if not map.land(k).coastal:
            continue
        by_dist[v].append(k)
    return (sorted(by_dist.keys())[-1], lands, by_dist)


def tryone_no_dist(lands: List[str]) -> Tuple[int, List[str]]:
    score, lands, by_dist = tryone(lands)
    return score, lands


def diags(data: Any) -> Iterator[Tuple[str, str]]:
    yield from (
        (f"{a}R", f"{b}S")
        for a, b in zip(
            data,
            data[2:] + data[:2],
        )
    )
    yield from (
        (f"{a}S", f"{b}R")
        for a, b in zip(
            data,
            data[2:] + data[:2],
        )
    )
    yield from (
        (f"{a}S", f"{b}S")
        for a, b in zip(
            data[:3],
            data[3:],
        )
    )
    yield from (
        (f"{a}R", f"{b}R")
        for a, b in zip(
            data[:3],
            data[3:],
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lands",
        nargs="*",
        default=[],
        help="Lands from which to measure distance",
    )
    args = parser.parse_args()

    if args.lands:
        _, _, by_dist = tryone(args.lands)
        for k2 in sorted(by_dist.keys()):
            print(k2, by_dist[k2])
        return

    map = gen_144p.Map144P()
    blue_diags = list(diags(map.data["blue"]["spokes"]))
    orange_diags = list(diags(map.data["orange"]["spokes"]))
    res = []
    total_tasks = len(blue_diags) * len(orange_diags) * 8 * 8 * 8 * 8
    start = time.monotonic()
    try:
        with multiprocessing.Pool(32) as pool:
            for idx, sol in enumerate(
                pool.imap_unordered(
                    tryone_no_dist,
                    (
                        [f"{bd[0]}{l1}", f"{bd[1]}{l2}", f"{od[0]}{l3}", f"{od[1]}{l4}"]
                        for bd in blue_diags
                        for od in orange_diags
                        for l1 in range(1, 9)
                        for l2 in range(1, 9)
                        for l3 in range(1, 9)
                        for l4 in range(1, 9)
                    ),
                )
            ):
                res.append(sol)
                duration = time.monotonic() - start
                sys.stderr.write(f"\r{duration:.3f} {idx / total_tasks:.3%}")
    finally:
        sys.stderr.write("\n")
        out = [
            {
                "score": score,
                "lands": lands,
            }
            for score, lands in res
        ]
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
