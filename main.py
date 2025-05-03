import argparse
import copy
import csv
import dataclasses
import enum
import json
import multiprocessing
import os
import shutil
import sys
from typing import Any, List, Optional, Protocol, Self, Tuple, TypeVar

import action_log
import lair
import parse

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
    if (
        a.explorers.cnt == b.explorers.cnt
        and a.towns.cnt == b.towns.cnt
        and a.cities.cnt == b.cities.cnt
        and a.dahan.cnt == b.dahan.cnt
    ):
        return ""
    bstr = str(b)
    if (
        allow_clear
        and b.cities.cnt == 0
        and b.towns.cnt == 0
        and b.explorers.cnt == 0
        and b.dahan.cnt == 0
    ):
        bstr = "CLEAR"
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


def log_entry_tgt_pieces_to_text(entry: action_log.LogEntry) -> str:
    return " ".join(f"{cnt} {tgt}" for _, tgt, cnt in entry.pieces())


def log_entry_src_pieces_to_text(entry: action_log.LogEntry) -> str:
    return " ".join(f"{cnt} {src}" for src, _, cnt in entry.pieces())


def log_entry_to_text(entry: action_log.LogEntry) -> str:
    match entry.action:
        case action_log.Action.COMMENT:
            assert entry.text
            return entry.text
        case action_log.Action.GATHER:
            return f"gather {log_entry_src_pieces_to_text(entry)} from {entry.src_land} to {entry.tgt_land} ({entry.total_count()})"
        case action_log.Action.ADD:
            return f"add {log_entry_tgt_pieces_to_text(entry)} in {entry.tgt_land} ({entry.total_count()})"
        case action_log.Action.DESTROY:
            if entry.tgt_piece:
                response_log = f", MR adds {log_entry_tgt_pieces_to_text(entry)} in {entry.tgt_land}"
            else:
                response_log = ""
            return f"destroy {log_entry_src_pieces_to_text(entry)} in {entry.src_land}{response_log} ({entry.total_count()})"
        case action_log.Action.DOWNGRADE:
            return f"downgrade {log_entry_src_pieces_to_text(entry)} in {entry.src_land} ({entry.total_count()})"
        case action_log.Action.MANUAL:
            return ""
    raise LookupError(entry.action)


def cut_toplevel_log(line: str) -> str:
    return line.split(": ")[0]


class Split:
    def __init__(
        self,
        may_break_second_level: bool,
        force_commit_on_toplevel: bool,
    ) -> None:
        self.entries: List[bytes] = []
        self.toplevel = ""
        self.cur_length = 0
        self.count = 0
        self.files: List[bytes] = []
        self.may_break_second_level = may_break_second_level
        self.force_commit_on_toplevel = force_commit_on_toplevel

    def commit(self, needs_cont: bool) -> None:
        if not self.entries:
            return

        upto = len(self.entries)
        if not self.may_break_second_level:
            # don't break a second-level bullet in the middle
            for i in range(len(self.entries) - 1, 0, -1):
                if self.entries[i].startswith(b"  -"):
                    upto = i
                    break
        self.files.append(b"\n".join(self.entries[:upto]))
        leftover = self.entries[upto:]

        self.count += 1
        self.cur_length = 0
        self.entries = []

        if needs_cont:
            self.append(f"{self.toplevel} - cont.".encode())
        for entry in leftover:
            self.append(entry)

    def space_emojis(self, line: bytes) -> bytes:
        idx = 0
        while True:
            try:
                start = line.index(b":", idx)
            except ValueError:
                return line
            if start < len(line) - 1 and line[start + 1] != ord(b" "):
                end = line.index(b":", start + 1) + 1
                before = b" " if start > 0 and line[start - 1] != ord(b" ") else b""
                after = b" " if end < len(line) and line[end] != ord(b" ") else b""
                line = line[:start] + before + line[start:end] + after + line[end:]
                idx = end
            else:
                idx = start + 1

    def append(self, line: bytes) -> None:
        line = self.space_emojis(line)
        real_length = len(line) + 1 + (line.count(b":") // 2 * DISCORD_EMOJI_COST)
        if self.cur_length + real_length > DISCORD_MESSAGE_LIMIT:
            self.commit(True)
        self.cur_length += real_length
        self.entries.append(line)

    def run(
        self,
        log: str,
        directory: str,
        header_prefix: str,
        header_suffix: str,
    ) -> None:
        shutil.rmtree(directory, ignore_errors=True)
        os.makedirs(directory, exist_ok=True)

        for line in log.splitlines():
            if line.startswith("-"):
                self.toplevel = cut_toplevel_log(line)
                if self.force_commit_on_toplevel:
                    self.commit(False)
            self.append(line.encode())
        self.commit(False)

        for i, content in enumerate(self.files):
            with open(
                os.path.join(directory, f"msg{(i + 1):02}.md"),
                "wb",
            ) as f:
                f.write(
                    f"{header_prefix} [{i + 1}/{len(self.files)}]{header_suffix}\n".encode()
                )
                f.write(content)


def print_or_split(
    raw: str,
    args: argparse.Namespace,
    thelair: lair.Lair,
    may_break_second_level: bool = False,
    force_commit_on_toplevel: bool = False,
) -> None:
    if args.split:
        if args.split_header:
            split_header = f" {args.split_header}"
        else:
            split_header = ""
        Split(
            may_break_second_level=may_break_second_level,
            force_commit_on_toplevel=force_commit_on_toplevel,
        ).run(
            raw,
            args.split,
            thelair.r0.key,
            split_header,
        )
    else:
        print(raw)


def process_diffview(
    parser: parse.Parser,
    args: argparse.Namespace,
    thelair: lair.Lair,
) -> None:
    all_diff = []
    orig_lair, _ = parser.parse_all()
    all_diff.append(landdiff(0, orig_lair.r0, thelair.r0, args))
    for a, b in zip(orig_lair.r1, thelair.r1):
        all_diff.append(landdiff(1, a, b, args))
    for a, b in zip(orig_lair.r2, thelair.r2):
        all_diff.append(landdiff(2, a, b, args))
    all_diff.sort()
    all_diff_md = []
    last_islet = ""
    for line in all_diff:
        if not line:
            continue
        islet = line[0]
        if islet != last_islet:
            all_diff_md.append(f"- {thelair.r0.key} diff: {islet}")
            last_islet = islet
        all_diff_md.append(f"  - {line}")
    diffview = "\n".join(all_diff_md)
    print_or_split(
        raw=diffview,
        args=args,
        thelair=thelair,
        may_break_second_level=True,
        force_commit_on_toplevel=True,
    )


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

    toplevel: Optional[str] = ""
    for nest, entry in finallair.log.entries:
        if nest == 0:
            assert entry.action in (
                action_log.Action.COMMENT,
                action_log.Action.MANUAL,
            )
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
        elif entry.action is action_log.Action.ADD:
            row.action = f"{toplevel} - add"
        elif entry.action is action_log.Action.DESTROY:
            row.action = f"{toplevel} - military response"
        elif entry.action is action_log.Action.MANUAL:
            row.action = toplevel or "UNKNWON"
        else:
            continue

        def is_lair(key: Optional[str]) -> bool:
            return key in (r0.key, "LAIRL")

        src_mult = tgt_mult = 0
        if is_lair(entry.src_land):
            src_mult = 1
        if is_lair(entry.tgt_land):
            tgt_mult = 1
        if src_mult == tgt_mult == 0:
            continue

        def piece_diff(piece: lair.PieceType, name: Optional[str], cnt: int) -> int:
            if parser.match_piece(piece, name or ""):
                return cnt
            return 0

        for src, tgt, cnt in entry.pieces():
            row.explorers_diff -= piece_diff(lair.Explorer, src, cnt) * src_mult
            row.towns_diff -= piece_diff(lair.Town, src, cnt) * src_mult
            row.cities_diff -= piece_diff(lair.City, src, cnt) * src_mult
            row.dahan_diff -= piece_diff(lair.Dahan, src, cnt) * src_mult

            row.explorers_diff += piece_diff(lair.Explorer, tgt, cnt) * tgt_mult
            row.towns_diff += piece_diff(lair.Town, tgt, cnt) * tgt_mult
            row.cities_diff += piece_diff(lair.City, tgt, cnt) * tgt_mult
            row.dahan_diff += piece_diff(lair.Dahan, tgt, cnt) * tgt_mult

        r0.explorers.cnt += row.explorers_diff
        r0.towns.cnt += row.towns_diff
        r0.cities.cnt += row.cities_diff
        r0.dahan.cnt += row.dahan_diff

        row.explorers_total = r0.explorers.cnt
        row.towns_total = r0.towns.cnt
        row.cities_total = r0.cities.cnt
        row.dahan_total = r0.dahan.cnt

        w.writerow(row.to_csv())


ActionSeqResult = Tuple[Tuple[str, ...], lair.Lair, lair.Lair]


def run_action_seq(
    parser: parse.Parser,
    args: argparse.Namespace,
    action_seq: Tuple[str, ...],
) -> ActionSeqResult:
    thelair, delayed = parser.parse_all()
    for action in action_seq:
        getattr(thelair, action)()
        before_delayed = str(thelair.r0)
        if delayed.run(action):
            after_delayed = str(thelair.r0)
            thelair.log.entry(
                action_log.LogEntry(
                    text=f"_execute delayed actions for {action}_ {before_delayed} => {after_delayed}"
                )
            )
    preravage = copy.deepcopy(thelair)
    thelair.ravage()
    return action_seq, preravage, thelair


class Worker:
    def __init__(
        self,
        parser: parse.Parser,
        args: argparse.Namespace,
    ):
        self.parser = parser
        self.args = args

    def __call__(
        self,
        action_seq: Tuple[str, ...],
    ) -> ActionSeqResult:
        return run_action_seq(self.parser, self.args, action_seq)


class Output(enum.Enum):
    LOG = "log"
    DIFF = "diff"
    CAT_CAFE = "cat-cafe"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        metavar="|".join([repr(output.value) for output in Output]),
        type=Output,
        help="Output action log in markdown format to stdout",
    )
    parser.add_argument(
        "--split",
        help="Output to multiple files, split into discord message length",
        metavar="DIRECTORY",
    )
    parser.add_argument(
        "--split-header",
        help="Append a marker to each split file header",
        metavar="HEADER",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Display final lair state summary",
    )
    parser.add_argument(
        "--postravage",
        action="store_true",
        help="Display postravage results instead of preravage",
    )
    parser.add_argument(
        "--diff-range",
        action="store_true",
        help="Show range from lair in diff view",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=32,
        help="Number of multiprocessing workers to run",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with open("config/turn4/input.json") as f:
        input = json.load(f)
    res: List[ActionSeqResult] = []
    action_seqs = set(
        tuple(s) for s in perms(input["actions"] + ["lair_blue", "lair_orange"])
    )
    server_emojis = args.split
    lair_conf = lair.LairConf(
        land_priority=input.get("land_priority", ""),
        reserve_gathers_blue=input.get("reserve_gathers_blue", 0),
        reserve_gathers_orange=input.get("reserve_gathers_orange", 0),
        reckless_offensive=input.get("reckless_offensive", []),
        piece_names=piece_names_emoji if server_emojis else piece_names_text,
    )
    parse_conf = parse.ParseConf(
        server_emojis=server_emojis,
        ignore_lands=input.get("ignore_lands", []),
    )
    parser = parse.Parser(
        csvpath="config/turn4/start.csv",
        jsonpath="config/turn4/initial_lair.json",
        actionspath="config/turn4/actions.csv",
        lair_conf=lair_conf,
        parse_conf=parse_conf,
    )

    worker = Worker(parser, args)
    with multiprocessing.Pool(args.workers) as pool:
        res = pool.map(worker, action_seqs)
    res.sort(key=lambda pair: score(pair[2]))  # score by postravage state

    action_seq, preravage, postravage = res[-1]
    if args.postravage:
        thelair = postravage
    else:
        thelair = preravage
    if args.summary:
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

    match args.output:
        case Output.LOG:
            log = "\n".join(
                " " * (nest * 2) + "- " + line
                for nest, entry in thelair.log.entries
                for line in (log_entry_to_text(entry),)
                if line
            )
            print_or_split(
                raw=log,
                args=args,
                thelair=thelair,
            )

        case Output.DIFF:
            process_diffview(parser, args, thelair)

        case Output.CAT_CAFE:
            cat_cafe(thelair, parser)


if __name__ == "__main__":
    main()
