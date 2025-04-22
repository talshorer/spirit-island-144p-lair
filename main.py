import argparse
from typing import List, TypeVar

try:
    from . import parse
    from . import lair
except ImportError:
    # stupid vscode..
    import parse  # type: ignore
    import lair  # type: ignore


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


def newlair(land_priority: str) -> lair.Lair:
    return parse.parse("144Turn4WeaveShenans.csv", land_priority)


def cmplands(r: int, a: lair.Land, b: lair.Land):
    assert a.key == b.key
    if b.cities.cnt == b.towns.cnt == b.explorers.cnt == 0:
        b = "CLEAR"
    print(f"({r}) {a.key}: {a} => {b}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", action="store_true")
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--pull-r1-dahan")
    parser.add_argument("--actions", nargs="+")
    parser.add_argument("--best", type=int, default=1)
    parser.add_argument("--land-priority", default="")
    args = parser.parse_args()
    res = []
    action_seqs = set(tuple(s) for s in perms(args.actions))
    for action_seq in action_seqs:
        action_seq += ("ravage",)
        thelair = newlair(args.land_priority)
        if args.pull_r1_dahan is not None:
            if args.pull_r1_dahan == "ALL":
                pull = 1 << 32
            else:
                pull = int(args.pull_r1_dahan)
            thelair.pull_r1_dahan(pull)
        for action in action_seq:
            getattr(thelair, action)()
        res.append((action_seq, thelair))

    res.sort(key=lambda pair: pair[1].r0.explorers.cnt)

    for action_seq, thelair in res[-args.best :]:
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
                ]
            )
        )
        if args.log:
            print("\n".join(thelair.log))
        if args.diff:
            orig_lair = newlair(args.land_priority)
            cmplands(0, orig_lair.r0, thelair.r0)
            for a, b in zip(orig_lair.r1, thelair.r1):
                cmplands(1, a, b)
            for a, b in zip(orig_lair.r2, thelair.r2):
                cmplands(2, a, b)


if __name__ == "__main__":
    main()
