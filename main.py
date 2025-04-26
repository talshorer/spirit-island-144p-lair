import abc
import argparse
import os
from typing import List, Self, Tuple, TypeVar, Protocol

import parse
import lair


DISCORD_MESSAGE_LIMIT = 1900  # actually 2000, but we leave some space for a header
DISCORD_EMOJI_COST = 21

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


class LogSplit:
    def __init__(self) -> None:
        self.entries: List[bytes] = []
        self.toplevel = ""
        self.cur_length = 0
        self.count = 0
        self.files: List[bytes] = []

    def commit(self, needs_cont: bool) -> None:
        if not self.entries:
            return

        # don't break a second-level bullet in the middle
        for i in range(len(self.entries) - 1, 0, -1):
            if self.entries[i].startswith(b"  -"):
                break
        else:
            i = len(self.entries)
        self.files.append(b"\n".join(self.entries[:i]))
        leftover = self.entries[i:]

        self.count += 1
        self.cur_length = 0
        self.entries = []

        if needs_cont:
            self.append(f"{self.toplevel} - cont.".encode())
        for entry in leftover:
            self.append(entry)

    def append(self, line: bytes) -> None:
        real_length = len(line) + 1 + (line.count(b":") // 2 * DISCORD_EMOJI_COST)
        if self.cur_length + real_length > DISCORD_MESSAGE_LIMIT:
            self.commit(True)
        self.cur_length += real_length
        self.entries.append(line)

    def run(self, log: str) -> None:
        for line in log.splitlines():
            if line.startswith("-"):
                self.toplevel = line.split(": ")[0]
            self.append(line.encode())
        self.commit(False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log",
        action="store_true",
        help="Output action log in markdown format to stdout",
    )
    parser.add_argument(
        "--log-split",
        help="Output action log to multiple files, split into discord message length",
        metavar="DIRECTORY",
    )
    parser.add_argument(
        "--log-split-header",
        help="Append a marker to each split log header",
        metavar="HEADER",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Don't display final lair state summary",
    )
    parser.add_argument(
        "--server-emojis",
        action="store_true",
        help="Use Spirit Island Discord server emojis where applicable",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Show each land's initial and final state",
    )
    parser.add_argument(
        "--dahan-diff",
        action="store_true",
        help="Don't show a land as clear if it has dahan",
    )
    parser.add_argument(
        "--pull-r1-dahan",
        help='Pull N (or "ALL") range-1 Dahan before any lair action',
        metavar="COUNT",
    )
    parser.add_argument(
        "--actions",
        nargs="+",
        help="Available actions for the lair. Specify an action multiple times if it's available multiple times",
        metavar="ACTION",
    )
    parser.add_argument(
        "--reckless-offensive",
        nargs="+",
        default=[],
        help="Reserve a list of lands to be qualified for Reckless Offensive event",
        metavar="LAND",
    )
    parser.add_argument(
        "--best",
        type=int,
        default=1,
        help="Show best N results instead of just one",
        metavar="COUNT",
    )
    parser.add_argument(
        "--land-priority",
        default="",
        help="Priority list of land types to clear",
        metavar="LAND-TYPES",
    )
    parser.add_argument(
        "--reserve-gathers",
        type=int,
        default=0,
        help="Reserve first N lair gathers for other actions",
        metavar="COUNT",
    )
    parser.add_argument(
        "--reserve-damage",
        type=int,
        default=0,
        help="Reserve first N lair damage for other actions",
        metavar="COUNT",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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
        log = thelair.log.collapse()
        if args.log:
            print(log)
        if args.log_split:
            if args.log_split_header:
                log_split_header = f" {args.log_split_header}"
            else:
                log_split_header = ""
            ls = LogSplit()
            ls.run(log)
            for i, content in enumerate(ls.files):
                os.makedirs(args.log_split, exist_ok=True)
                with open(os.path.join(args.log_split, f"msg{i:02}.md"), "wb") as f:
                    f.write(
                        f"{thelair.r0.key} [{i+1}/{len(ls.files)}]{log_split_header}\n".encode()
                    )
                    f.write(content)
        if args.diff:
            orig_lair = newlair(lair_conf, parse_conf)
            cmplands(0, orig_lair.r0, thelair.r0, args)
            for a, b in zip(orig_lair.r1, thelair.r1):
                cmplands(1, a, b, args)
            for a, b in zip(orig_lair.r2, thelair.r2):
                cmplands(2, a, b, args)


if __name__ == "__main__":
    main()
