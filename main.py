import argparse
import csv
import dataclasses
import os
import sys
from typing import Any, List, Optional, Self, Tuple, TypeVar, Protocol

import action_log
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


def landdiff(
    r: int | str,
    a: lair.Land,
    b: lair.Land,
    args: argparse.Namespace,
    allow_clear: bool = True,
) -> str:
    assert a.key == b.key
    bstr = str(b)
    if allow_clear and b.cities.cnt == b.towns.cnt == b.explorers.cnt == 0:
        if b.dahan.cnt == 0 or not args.dahan_diff:
            bstr = "CLEAR"
    if (
        a.explorers.cnt == b.explorers.cnt
        and a.towns.cnt == b.towns.cnt
        and a.cities.cnt == b.cities.cnt
        and a.dahan.cnt == b.dahan.cnt
    ):
        if args.strict_diff:
            return ""
        bstr = "UNCHANGED"
    if args.diff_range:
        range_ = f"({r}) "
    else:
        range_ = ""
    return f"{range_}{a.key}: {a} => {bstr}"


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


def log_entry_to_text(entry: action_log.LogEntry) -> str:
    match entry.action:
        case action_log.Action.COMMENT:
            assert entry.text
            return entry.text
        case action_log.Action.GATHER:
            return f"gather {entry.count} {entry.src_piece} from {entry.src_land} to {entry.tgt_land}"
        case action_log.Action.DESTROY:
            if entry.tgt_piece:
                response_log = (
                    f", MR adds {entry.count} {entry.tgt_piece} in {entry.tgt_land}"
                )
            else:
                response_log = ""
            return f"destroy {entry.count} {entry.src_piece} in {entry.src_land}{response_log}"
        case action_log.Action.DOWNGRADE:
            return f"downgrade {entry.count} {entry.src_piece} in {entry.src_land}"
    raise LookupError(entry.action)


def cut_toplevel_log(line: str) -> str:
    return line.split(": ")[0]


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
                self.toplevel = cut_toplevel_log(line)
            self.append(line.encode())
        self.commit(False)


@dataclasses.dataclass
class CatCafeRow:
    explorers_diff: int
    towns_diff: int
    cities_diff: int
    dahan_diff: int
    explorers_total: int
    towns_total: int
    cities_total: int
    dahan_total: int
    source: str
    action: str

    def to_csv(self) -> List[Any]:
        return [
            self.explorers_diff or None,
            self.towns_diff or None,
            self.cities_diff or None,
            self.dahan_diff or None,
            self.explorers_total,
            self.towns_total,
            self.cities_total,
            self.dahan_total,
            self.source or None,
            self.action or None,
        ]


def cat_cafe(finallair: lair.Lair, parser: parse.Parser) -> None:
    w = csv.writer(sys.stdout)

    r0 = parser.parse_initial_lair()
    w.writerow(
        CatCafeRow(
            explorers_diff=r0.explorers.cnt,
            towns_diff=r0.towns.cnt,
            cities_diff=r0.cities.cnt,
            dahan_diff=r0.dahan.cnt,
            explorers_total=r0.explorers.cnt,
            towns_total=r0.towns.cnt,
            cities_total=r0.cities.cnt,
            dahan_total=r0.dahan.cnt,
            source="LAIR",
            action="From last phase",
        ).to_csv()
    )

    for action in parser.read_actions_csv():
        if "LAIR" not in action.destination_key:
            continue
        explorers_diff = parse.to_int(action.explorers)
        r0.explorers.cnt += explorers_diff
        towns_diff = parse.to_int(action.towns)
        r0.towns.cnt += towns_diff
        cities_diff = parse.to_int(action.cities)
        r0.cities.cnt += towns_diff
        dahan_diff = parse.to_int(action.dahan)
        r0.dahan.cnt += towns_diff
        w.writerow(
            CatCafeRow(
                explorers_diff=explorers_diff,
                towns_diff=towns_diff,
                cities_diff=cities_diff,
                dahan_diff=dahan_diff,
                explorers_total=r0.explorers.cnt,
                towns_total=r0.towns.cnt,
                cities_total=r0.cities.cnt,
                dahan_total=r0.dahan.cnt,
                source=action.source_key,
                action=action.action_name,
            ).to_csv()
        )

    toplevel: Optional[str] = ""
    for nest, entry in finallair.log.entries:
        if nest == 0:
            assert entry.action == action_log.Action.COMMENT
            toplevel = cut_toplevel_log(entry.text or "")

        row = CatCafeRow(
            explorers_diff=0,
            towns_diff=0,
            cities_diff=0,
            dahan_diff=0,
            explorers_total=0,
            towns_total=0,
            cities_total=0,
            dahan_total=0,
            source=entry.src_land or "",
            action="",
        )

        if entry.action is action_log.Action.DOWNGRADE:
            row.action = f"{toplevel} - downgrade"
        elif entry.action is action_log.Action.GATHER:
            row.action = f"{toplevel} - gather"
        elif entry.action is action_log.Action.DESTROY:
            row.action = f"{toplevel} - military response"
        else:
            continue

        def piece_diff(piece: lair.PieceType, name: Optional[str]) -> int:
            if parser.match_piece(piece, name or ""):
                return entry.count
            return 0

        row.explorers_diff -= piece_diff(lair.Explorer, entry.src_piece)
        row.towns_diff -= piece_diff(lair.Town, entry.src_piece)
        row.cities_diff -= piece_diff(lair.City, entry.src_piece)
        row.dahan_diff -= piece_diff(lair.Dahan, entry.src_piece)

        row.explorers_diff += piece_diff(lair.Explorer, entry.tgt_piece)
        row.towns_diff += piece_diff(lair.Town, entry.tgt_piece)
        row.cities_diff += piece_diff(lair.City, entry.tgt_piece)
        row.dahan_diff += piece_diff(lair.Dahan, entry.tgt_piece)

        r0.explorers.cnt += row.explorers_diff
        r0.towns.cnt += row.towns_diff
        r0.cities.cnt += row.cities_diff
        r0.dahan.cnt += row.dahan_diff

        row.explorers_total = r0.explorers.cnt
        row.towns_total = r0.towns.cnt
        row.cities_total = r0.cities.cnt
        row.dahan_total = r0.dahan.cnt

        w.writerow(row.to_csv())


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
        "--diff-range",
        action="store_true",
        help="Show range from lair in diff view",
    )
    parser.add_argument(
        "--dahan-diff",
        action="store_true",
        help="Don't show a land as clear if it has dahan",
    )
    parser.add_argument(
        "--distant-diff",
        action="store_true",
        help="Show distant lands in diff view",
    )
    parser.add_argument(
        "--strict-diff",
        action="store_true",
        help="Skip lands in diff view if they didn't change",
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
        "--ignore-lands",
        nargs="+",
        default=[],
        help="Lands to ignore",
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
    parser.add_argument(
        "--cat-cafe",
        action="store_true",
        help="Output cat-cafe-friendly csv",
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
        ignore_lands=args.ignore_lands,
    )
    parser = parse.Parser(
        csvpath="Turn4Start.csv",
        jsonpath="initial-lair.json",
        actionspath="Turn4Actions.csv",
        lair_conf=lair_conf,
        parse_conf=parse_conf,
    )
    for action_seq in action_seqs:
        action_seq += ("ravage",)
        thelair, _ = parser.parse_all()
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

        log = "\n".join(
            " " * (nest * 2) + "- " + log_entry_to_text(entry)
            for nest, entry in thelair.log.entries
        )
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
            all_diff = []
            orig_lair, distant_lands = parser.parse_all()
            all_diff.append(landdiff(0, orig_lair.r0, thelair.r0, args))
            for a, b in zip(orig_lair.r1, thelair.r1):
                all_diff.append(landdiff(1, a, b, args))
            for a, b in zip(orig_lair.r2, thelair.r2):
                all_diff.append(landdiff(2, a, b, args))
            if args.distant_diff:
                for b in distant_lands.values():
                    if not b.key:
                        b.key = "dead"
                    elif not b.key.endswith("X"):
                        b.key += "X"
                    a = lair.Land(
                        key=b.key,
                        land_type=b.land_type,
                        explorers=0,
                        towns=0,
                        cities=0,
                        dahan=0,
                        gathers_to=thelair.r0,  # whatever...
                        conf=lair_conf,
                    )
                    all_diff.append(landdiff("far", a, b, args, allow_clear=False))
            all_diff.sort()
            for line in all_diff:
                if line:
                    print(line)
        if args.cat_cafe:
            cat_cafe(thelair, parser)


if __name__ == "__main__":
    main()
