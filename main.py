from typing import List, TypeVar

try:
    from . import parse
except ImportError:
    # stupid vscode..
    import parse  # type: ignore


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


def main(actions: List[str]):
    res = []
    action_seqs = set(tuple(s) for s in perms(actions))
    for action_seq in action_seqs:
        action_seq += ("ravage",)
        thelair = parse.parse("144Turn4WeaveShenans.csv")
        for action in action_seq:
            getattr(thelair, action)()
        res.append((action_seq, thelair))

    res.sort(key=lambda pair: pair[1].r0.explorers.cnt)

    action_seq, thelair = res[-1]
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


main(["lair", "lair", "blur", "blur", "call", "call"])
main(["lair", "lair", "blur2", "call", "call"])
