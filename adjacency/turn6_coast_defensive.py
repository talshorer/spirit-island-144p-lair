import argparse
import collections
import json
import multiprocessing
import sys
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple

from . import dijkstra, gen_144p

map: Optional[gen_144p.Map144P] = None
dijstra_cache: Dict[str, Tuple[Dict[str, int], Dict[str, str]]] = {}


def ensure_map() -> None:
    global map
    if map is None:
        map = gen_144p.Map144P()


def tryone(
    lands: List[str],
    filter_coastal: bool = True,
    construct_paths: bool = False,
) -> Tuple[
    int,
    List[str],
    Dict[int, List[str]],
    Dict[str, int],
    Dict[str, List[str]],
]:
    ensure_map()
    assert map
    all_dist: Dict[str, int] = {}
    all_paths: Dict[str, List[str]] = {}
    for src in lands:
        if src not in dijstra_cache:
            dist, prev = dijkstra.distances_from(map.land(src))
            dijstra_cache[src] = (dist, prev)
        else:
            dist, prev = dijstra_cache[src]
        for k, v in dist.items():
            best = all_dist.get(k)
            if best is None or best > v:
                all_dist[k] = v
                if construct_paths:
                    all_paths[k] = dijkstra.construct_path(prev, src, k)
    by_dist: Dict[int, List[str]] = collections.defaultdict(list)
    for k, v in all_dist.items():
        land = map.land(k)
        if filter_coastal and not land.coastal:
            continue
        by_dist[v].append(f"{k}{land.terrain.value}")
    return (sorted(by_dist.keys())[-1], lands, by_dist, all_dist, all_paths)


def tryone_no_dist(lands: List[str]) -> Tuple[Optional[int], List[str]]:
    ensure_map()
    assert map
    try:
        for land in lands:
            map.land(land)
    except KeyError:
        return None, []
    score, lands, by_dist, all_dist, all_paths = tryone(lands)
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
    parser.add_argument(
        "--path-to",
        nargs="*",
        default=[],
        help="Show path from source lands to target lands",
    )
    parser.add_argument(
        "--coastal",
        action="store_true",
        help="Only show coastal lands in output",
    )
    args = parser.parse_args()

    if args.lands:
        (
            score,
            lands,
            by_dist,
            all_dist,
            all_paths,
        ) = tryone(args.lands, filter_coastal=args.coastal, construct_paths=True)
        if args.path_to:
            for land in args.path_to:
                print(all_dist[land], all_paths[land])
        else:
            for land in sorted(by_dist.keys()):
                print(land, by_dist[land])
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
            if score is not None
        ]
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
