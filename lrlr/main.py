import argparse
import copy
import csv
import dataclasses
import enum
import itertools
import multiprocessing
import os
import shutil
import sys
import traceback
from typing import Any, Dict, List, Optional, Protocol, Self, Tuple, TypeVar, Union

import json5

from . import action_log, lair, parse

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
    a: lair.Land,
    b: lair.Land,
    args: argparse.Namespace,
) -> str:
    assert a.key == b.key
    if (
        a.explorers.cnt == b.explorers.cnt
        and a.towns.cnt == b.towns.cnt
        and a.cities.cnt == b.cities.cnt
        and a.dahan.cnt == b.dahan.cnt
    ):
        if not args.diff_all:
            return ""
        bstr = "UNCHANGED"
    else:
        bstr = b.stringify_pieces()
    return f"{a.display_name}: ({a.stringify_pieces()}) => ({bstr})"


class Comparable(Protocol):
    def __lt__(self: Self, other: Self) -> bool:
        pass


def score(lair_conf: lair.LairConf, thelair: lair.LairState) -> Comparable:
    cleared_lands = sum(
        int(land.total_invaders() == 0)
        for land in thelair.lands
        if land.land_type in lair_conf.terrain_priority
    )
    return (cleared_lands, thelair.r0.total_invaders(), thelair.wasted_invader_gathers)


def log_entry_tgt_pieces_to_text(entry: action_log.LogEntry) -> str:
    return lair.stringify_pieces((tgt, cnt) for _, tgt, cnt in entry.pieces())


def log_entry_src_pieces_to_text(entry: action_log.LogEntry) -> str:
    return lair.stringify_pieces((src, cnt) for src, _, cnt in entry.pieces())


def log_entry_to_text(entry: action_log.LogEntry) -> str:
    match entry.action:
        case action_log.Action.COMMENT:
            assert entry.text
            return entry.text
        case action_log.Action.GATHER:
            intermediate = "".join(
                f" to {land}" for land in (entry.intermediate_lands or [])
            )
            return f"gather {log_entry_src_pieces_to_text(entry)} from {entry.src_land}{intermediate} to {entry.tgt_land} (total {entry.total_count()})"
        case action_log.Action.ADD:
            return f"add {log_entry_tgt_pieces_to_text(entry)} in {entry.tgt_land} (total {entry.total_count()})"
        case action_log.Action.DESTROY:
            if entry.tgt_piece:
                response_log = f", MR adds {log_entry_tgt_pieces_to_text(entry)} in {entry.tgt_land}"
            else:
                response_log = ""
            return f"destroy {log_entry_src_pieces_to_text(entry)} in {entry.src_land}{response_log}"
        case action_log.Action.DOWNGRADE:
            return f"downgrade {log_entry_src_pieces_to_text(entry)} in {entry.src_land} (total {entry.total_count()})"
        case action_log.Action.MANUAL:
            if entry.tgt_land and any(entry.tgt_piece):
                tgt = f" +({log_entry_tgt_pieces_to_text(entry)}) in {entry.tgt_land}"
            else:
                tgt = ""
            if entry.src_land and any(entry.src_piece):
                src = f" -({log_entry_src_pieces_to_text(entry)}) in {entry.src_land}"
            else:
                src = ""
            if entry.text:
                text = " " + entry.text.split(" - ")[-1]
            else:
                text = ""
            return f"manual action:{text}{src}{tgt}"
    raise LookupError(entry.action)


def cut_toplevel_log(line: str) -> str:
    return line.split(": (")[0]


class Split:
    def __init__(
        self,
        force_commit_on_toplevel: bool,
    ) -> None:
        self.entries: List[bytes] = []
        self.toplevel = ""
        self.cur_length = 0
        self.count = 0
        self.files: List[bytes] = []
        self.force_commit_on_toplevel = force_commit_on_toplevel

    def commit(self, next_nest: int) -> None:
        if not self.entries:
            return

        upto = len(self.entries)
        if next_nest > 1:
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

        if next_nest > 0:
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
            self.commit(line.index(b"-") // 2)
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
                    self.commit(0)
            self.append(line.encode())
        self.commit(-1)

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
    thelair: lair.LairState,
    force_commit_on_toplevel: bool = False,
) -> None:
    if args.split:
        if args.split_header:
            split_header = f" {args.split_header}"
        else:
            split_header = ""
        Split(
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
    thelair: lair.LairState,
) -> None:
    all_diff = []
    orig_lair, _ = parser.parse_all()
    all_diff.append((landdiff(orig_lair.state.r0, thelair.r0, args), 0))
    for a, b in itertools.chain(
        zip(orig_lair.state.lands, thelair.lands),
        zip(orig_lair.state.unpathable, thelair.unpathable),
    ):
        dist = thelair.dist[a.key]
        all_diff.append((landdiff(a, b, args), dist))
    all_diff.sort(key=lambda tup: tup[args.diff_sort_range])
    all_diff_md = []
    last_toplevel: Union[None, str, int] = None
    toplevel: Union[str, int]
    for line, dist in all_diff:
        if not line:
            continue
        if args.filter not in line:
            continue
        if args.diff_sort_range:
            toplevel = dist
        else:
            toplevel = line[0]
        if toplevel != last_toplevel:
            all_diff_md.append(f"- {thelair.r0.key} {toplevel} diff")
            last_toplevel = toplevel
        all_diff_md.append(f"  - {line}")
    diffview = "\n".join(all_diff_md)
    print_or_split(
        raw=diffview,
        args=args,
        thelair=thelair,
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


def cat_cafe(finallair: lair.LairState, parser: parse.Parser) -> None:
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
            row.action = f"{toplevel} - gather ({entry.total_count()})"
        elif entry.action is action_log.Action.ADD:
            row.action = f"{toplevel} - add"
        elif entry.action is action_log.Action.DESTROY:
            row.action = f"{toplevel} - military response"
        elif entry.action is action_log.Action.MANUAL:
            row.action = entry.text or "UNKNOWN"
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


def output_actions_csv(thelair: lair.LairState, parser: parse.Parser) -> None:
    def to_str(v: int) -> str:
        return str(v) if v else ""

    _, delayed = parser.parse_all()
    last_action_id = delayed.max_action_id
    w = csv.writer(sys.stdout)
    w.writerow(
        (
            "Source",
            "Destination",
            "City",
            "Town",
            "Explorer",
            "Dahan",
            "Action Name",
            "Action ID",
            "Parent",
            "Notes",
            "After Toplevel",
        )
    )
    in_slurp: Optional[str] = None
    for nest, entry in thelair.log.entries:
        match entry.action:
            case action_log.Action.MANUAL:
                assert entry.csv_data
                w.writerow(entry.csv_data)
            case action_log.Action.COMMENT:
                if nest == 0:
                    for colour in ("blue", "orange"):
                        assert entry.text
                        if f"lair-{colour}-thresh3" in entry.text:
                            in_slurp = f"lair_{colour}"
                            break
                    else:
                        in_slurp = None
            case action_log.Action.GATHER:
                if in_slurp is None:
                    continue
                assert entry.src_land
                assert entry.tgt_land
                pieces = {key: 0 for key in dataclasses.astuple(lair.piece_names_text)}
                for src, _, cnt in entry.pieces():
                    pieces[src] += cnt
                last_action_id += 1
                # TODO get rid of this ugly hack and all "LAIRL" occurences everywhere
                destination_key = entry.tgt_land.replace(
                    thelair.r0.display_name,
                    "LAIRL",
                )
                w.writerow(
                    parse.CsvAction(
                        source_key=entry.src_land,
                        destination_key=destination_key,
                        cities=to_str(pieces[lair.piece_names_text.city]),
                        towns=to_str(pieces[lair.piece_names_text.town]),
                        explorers=to_str(pieces[lair.piece_names_text.explorer]),
                        dahan=to_str(pieces[lair.piece_names_text.dahan]),
                        action_name="Manual gather",
                        action_id=str(last_action_id),
                        parent_action="",
                        notes=f"generated by --output actions.csv: {entry.total_count()} gathers",
                        after_toplevel=in_slurp,
                    ).csv_data()
                )


_ravages_per_action = {
    "blur": 1,
    "blur2": 2,
}


ActionSeqResult = Tuple[Tuple[str, ...], lair.LairState, lair.LairState]


def run_action_seq(
    parser: parse.Parser,
    action_seq: Tuple[str, ...],
) -> ActionSeqResult:
    thelair, delayed = parser.parse_all()
    thelair.set_expected_ravages(
        1 + sum(_ravages_per_action.get(action, 0) for action in action_seq)
    )
    delayed.run("start")
    for action in action_seq:
        getattr(thelair, action)()
        delayed.run(action)
    preravage = copy.deepcopy(thelair.state)
    thelair.ravage()
    return action_seq, preravage, thelair.state


class Worker:
    def __init__(self, parser: parse.Parser):
        self.parser = parser

    def __call__(
        self,
        action_seq: Tuple[str, ...],
    ) -> ActionSeqResult:
        try:
            return run_action_seq(self.parser, action_seq)
        except Exception as e:
            # Log the exception and stack trace
            print(f"Exception in worker for action_seq {action_seq}: {e}")
            traceback.print_exc()
            raise  # Re-raise the exception to propagate it


class Output(enum.Enum):
    LOG = "log"
    DIFF = "diff"
    CAT_CAFE = "cat-cafe"
    ACTIONS_CSV = "actions.csv"


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
        "--filter",
        default="",
        help="Show only actions for a specific island",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Don't display final lair state summary",
    )
    parser.add_argument(
        "--postravage",
        action="store_true",
        help="Display postravage results instead of preravage",
    )
    parser.add_argument(
        "--diff-all",
        action="store_true",
        help="Show all lands in diffview even if they're unchanged",
    )
    parser.add_argument(
        "--best",
        type=int,
        default=1,
        metavar="N",
        help="Display N best solutions",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=32,
        help="Number of multiprocessing workers to run",
    )
    parser.add_argument(
        "--force-line",
        nargs="+",
        default=[],
        help="Force specific line instead of calculating best line",
        metavar="ACTION",
    )
    parser.add_argument(
        "--turn",
        type=int,
        default=5,
        help="Choose turn's config dir",
    )
    parser.add_argument(
        "--diff-sort-range",
        action="store_true",
        help="Sort diffview by range rather than by island",
    )
    return parser.parse_args()


def lair_innate_conf(data: Optional[Dict[str, Any]]) -> lair.LairInnateConf:
    if data is None:
        data = {}
    return lair.LairInnateConf(
        reserve_gathers=data.get("reserve_gathers", 0),
        max_range=data.get("max_range", 0),
    )


def main() -> None:
    args = parse_args()
    config_dir = f"config/turn{args.turn}"
    with open(os.path.join(config_dir, "input.json5"), encoding="utf-8") as f:
        input = json5.load(f)
    res: List[ActionSeqResult] = []
    if args.force_line:
        action_seqs = set([tuple(args.force_line)])
    else:
        action_seqs = set(
            tuple(s) for s in perms(input["actions"] + ["lair_blue", "lair_orange"])
        )
    server_emojis = args.split
    log_prestart = args.output in (
        Output.CAT_CAFE,
        Output.ACTIONS_CSV,
    )
    display_name_range = args.output is not Output.ACTIONS_CSV
    force_no_summary = args.output is Output.ACTIONS_CSV
    lair_conf = lair.LairConf(
        terrain_priority=input.get("terrain_priority", ""),
        blue=lair_innate_conf(input.get("blue_lair")),
        orange=lair_innate_conf(input.get("orange_lair")),
        leave_behind=input.get("leave_behind", {}),
        piece_names=(
            lair.piece_names_emoji if server_emojis else lair.piece_names_text
        ),
        ignore_lands=input.get("ignore_lands", []),
        priority_lands=input.get("priority_lands", []),
        display_name_range=display_name_range,
    )
    parse_conf = parse.ParseConf(
        directory=config_dir,
        server_emojis=server_emojis,
        log_prestart=log_prestart,
    )
    parser = parse.Parser(
        lair_conf=lair_conf,
        parse_conf=parse_conf,
    )

    worker = Worker(parser)
    with multiprocessing.Pool(args.workers) as pool:
        res = pool.map(worker, action_seqs)
    res.sort(key=lambda pair: score(lair_conf, pair[2]))  # score by postravage state

    for action_seq, preravage, postravage in res[-args.best :]:
        if args.postravage:
            thelair = postravage
        else:
            thelair = preravage
        if not args.no_summary and not force_no_summary:
            print(
                " ".join(
                    [
                        f"{str(action_seq):<{58}}",
                        f"({thelair.r0.stringify_pieces()})",
                        f"wasted_damage={thelair.wasted_damage}",
                        f"total_gathers={thelair.total_gathers}",
                        f"wasted_invader_gathers={thelair.wasted_invader_gathers}",
                        f"wasted_dahan_gathers={thelair.wasted_dahan_gathers}",
                        f"wasted_downgrades={thelair.wasted_downgrades}",
                        f"fear={thelair.fear}",
                        f"score={score(lair_conf, thelair)}",
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
                    if (nest == 0) or (args.filter in line)
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

            case Output.ACTIONS_CSV:
                output_actions_csv(thelair, parser)


if __name__ == "__main__":
    main()
