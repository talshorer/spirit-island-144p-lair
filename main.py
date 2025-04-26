import abc
import argparse
from typing import List, Self, Tuple, TypeVar, Protocol

import parse
import lair


SHOW_BEST = 1


T = TypeVar("T")


def perms(it: List[T]) -> List[List[T]]:
    if len(it) == 1:
        return [it]
    ret = []
    for i, x in enumerate(it):
        cp = it[:i] + it[i + 1 :]
        for p in perms(cp):
            ret.append([x] + p)
    return ret


def newlair(lair_conf: lair.LairConf, parse_conf: parse.ParseConf) -> lair.Lair:
    return parse.parse(
        csvpath="144Turn4WeaveShenans.csv",
        jsonpath="initial-lair.json",
        lair_conf=lair_conf,
        parse_conf=parse_conf,
    )


def cmplands(r: int, a: lair.Land, b: lair.Land, args: argparse.Namespace) -> None:
    assert a.key == b.key
    bstr = str(b)
    if b.cities.cnt == b.towns.cnt == b.explorers.cnt == 0:
        if b.dahan.cnt == 0 or not args.dahan_diff:
            bstr = "CLEAR"
    print(f"({r}) {a.key}: {a} => {bstr}")


class Comparable(Protocol):
    def __lt__(self: Self, other: Self) -> bool:
        pass


def score(thelair: lair.Lair) -> Comparable:
    cleared_lands = sum(
        int((land.explorers.cnt + land.towns.cnt + land.cities.cnt) == 0)
        for land in thelair.r2
        if land.land_type in thelair.conf.land_priority
    )
    return (thelair.r0.explorers.cnt, cleared_lands)


piece_names_text = lair.PieceNames(
    explorer="explorer",
    town="town",
    city="city",
    dahan="dahan",
)

piece_names_emoji = lair.PieceNames(
    explorer=":InvaderExplorer:",
    town=":InvaderTown:",
    city=":InvaderCity:",
    dahan=":Dahan:",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", action="store_true")
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--no-summary", action="store_true")
    parser.add_argument("--server-emojis", action="store_true")
    parser.add_argument("--dahan-diff", action="store_true")
    parser.add_argument("--pull-r1-dahan")
    parser.add_argument("--actions", nargs="+")
    parser.add_argument("--reckless-offensive", nargs="+", default=[])
    parser.add_argument("--best", type=int, default=1)
    parser.add_argument("--land-priority", default="")
    parser.add_argument("--reserve-gathers", type=int, default=0)
    parser.add_argument("--reserve-damage", type=int, default=0)
    args = parser.parse_args()
    res: List[Tuple[Tuple, lair.Lair]] = []
    action_seqs = set(tuple(s) for s in perms(args.actions))
    lair_conf = lair.LairConf(
        land_priority=args.land_priority,
        reserve_gathers=args.reserve_gathers,
        reserve_damage=args.reserve_damage,
        reckless_offensive=args.reckless_offensive,
        piece_names=piece_names_emoji if args.server_emojis else piece_names_text,
    )
    parse_conf = parse.ParseConf(
        server_emojis=args.server_emojis,
    )
    for action_seq in action_seqs:
        action_seq += ("ravage",)
        thelair = newlair(lair_conf, parse_conf)
        if args.pull_r1_dahan is not None:
            if args.pull_r1_dahan == "ALL":
                pull = 1 << 32
            else:
                pull = int(args.pull_r1_dahan)
            thelair.pull_r1_dahan(pull)
        for action in action_seq:
            getattr(thelair, action)()
        res.append((action_seq, thelair))

    res.sort(key=lambda pair: score(pair[1]))

    for action_seq, thelair in res[-args.best :]:
        if not args.no_summary:
            print(
                " ".join(
                    [
                        f"{str(action_seq):<{58}}",
                        str(thelair.r0),
                        f"wasted_damage={thelair.wasted_damage}",
                        f"total_gathers={thelair.total_gathers}",
                        f"wasted_invader_gathers={thelair.wasted_invader_gathers}",
                        f"wasted_dahan_gathers={thelair.wasted_dahan_gathers}",
                        f"wasted_downgrades={thelair.wasted_downgrades}",
                        f"fear={thelair.fear}",
                        f"score={score(thelair)}",
                    ]
                )
            )
        if args.log:
            print(thelair.log.collapse())
        if args.diff:
            orig_lair = newlair(lair_conf, parse_conf)
            cmplands(0, orig_lair.r0, thelair.r0, args)
            for a, b in zip(orig_lair.r1, thelair.r1):
                cmplands(1, a, b, args)
            for a, b in zip(orig_lair.r2, thelair.r2):
                cmplands(2, a, b, args)


if __name__ == "__main__":
    main()
