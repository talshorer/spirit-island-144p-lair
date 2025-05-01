import collections
import csv
import dataclasses
import json
from typing import Any, Dict, Iterator, List, Tuple, cast

import action_log
import lair


def to_int(s: str) -> int:
    if s == "":
        return 0
    return int(s)


@dataclasses.dataclass
class ParseConf:
    server_emojis: bool
    ignore_lands: List[str]


@dataclasses.dataclass
class ActionCsvLands:
    near: Dict[str, lair.Land]
    distant: Dict[str, lair.Land]
    lair_conf: lair.LairConf


@dataclasses.dataclass
class CsvAction:
    source_key: str
    destination_key: str
    cities: str
    towns: str
    explorers: str
    dahan: str
    action_name: str
    action_id: str
    parent_action: str
    notes: str
    after_toplevel: str

    def run(self, lands: ActionCsvLands) -> None:
        for key, mult in ((self.source_key, -1), (self.destination_key, 1)):
            if not key:
                continue
            land_type = key[-1]
            key = key[:-1]
            if key in lands.near:
                land = lands.near[key]
                assert land_type == land.land_type
                allow_negative = False
            else:
                allow_negative = True
                dland = lands.distant.get(key)
                if dland is not None:
                    land = dland
                else:
                    land = lair.Land(
                        key=key,
                        land_type=land_type,
                        explorers=0,
                        towns=0,
                        cities=0,
                        dahan=0,
                        gathers_to=None,
                        conf=lands.lair_conf,
                    )
                    lands.distant[key] = land
            land.add_pieces(
                mult * to_int(self.explorers),
                mult * to_int(self.towns),
                mult * to_int(self.cities),
                mult * to_int(self.dahan),
                allow_negative,
            )


class DelayedActions:
    def __init__(
        self,
        near: Dict[str, lair.Land],
        lair_conf: lair.LairConf,
        log: action_log.Actionlog,
    ):
        self.actions: Dict[str, List[CsvAction]] = collections.defaultdict(lambda: [])
        self.by_id: Dict[str, CsvAction] = {}
        self.lair_conf = lair_conf
        self.lands = ActionCsvLands(near=near, distant={}, lair_conf=lair_conf)
        self.log = log

    def push(self, action: CsvAction) -> None:
        self.actions[action.after_toplevel].append(action)
        # when an action is split into multiple rows, we only want the first
        if action.action_id not in self.by_id:
            self.by_id[action.action_id] = action

    def progenitor(self, action: CsvAction) -> CsvAction:
        while action.parent_action:
            action = self.by_id[action.parent_action]
        return action

    def run(self, key: str) -> bool:
        if key not in self.actions:
            return False
        pieces = [
            self.lair_conf.piece_names.explorer,
            self.lair_conf.piece_names.town,
            self.lair_conf.piece_names.city,
            self.lair_conf.piece_names.dahan,
        ]
        for action in self.actions[key]:
            action.run(self.lands)
            self.log.entry(
                action_log.LogEntry(
                    action=action_log.Action.MANUAL,
                    text=self.progenitor(action).action_name,
                    src_land=action.source_key,
                    tgt_land=action.destination_key,
                    src_piece=pieces,
                    tgt_piece=pieces,
                    count=[
                        to_int(action.explorers),
                        to_int(action.towns),
                        to_int(action.cities),
                        to_int(action.dahan),
                    ],
                )
            )
        del self.actions[key]
        return True

    def run_all(self) -> None:
        for key in list(self.actions.keys()):
            self.run(key)


class Parser:
    def __init__(
        self,
        csvpath: str,
        jsonpath: str,
        actionspath: str,
        lair_conf: lair.LairConf,
        parse_conf: ParseConf,
    ):
        self.csvpath = csvpath
        self.jsonpath = jsonpath
        self.actionspath = actionspath
        self.lair_conf = lair_conf
        self.parse_conf = parse_conf

    def match_piece(self, piece: lair.PieceType, name: str) -> bool:
        return piece.name(self.lair_conf.piece_names) == name

    def parse_initial_lair(self) -> lair.Land:
        with open(self.jsonpath) as f:
            initial = json.load(f)
        if self.parse_conf.server_emojis:
            r0_key = ":IncarnaAspectLair:"
        else:
            r0_key = "lair"
        return lair.Land(
            key=r0_key,
            land_type="L",
            explorers=initial["explorers"],
            towns=initial["towns"],
            cities=initial["cities"],
            dahan=initial["dahan"],
            gathers_to=None,
            conf=self.lair_conf,
        )

    def read_actions_csv(self) -> Iterator[CsvAction]:
        with open(self.actionspath, encoding="utf-8") as f:
            it = iter(csv.reader(f))
            next(it)  # throw away header row
            yield from (CsvAction(*cast(Any, row)) for row in it)

    def parse_all(self) -> Tuple[
        lair.Lair,
        DelayedActions,
    ]:
        lands: Dict[str, lair.Land] = {}

        r0 = self.parse_initial_lair()
        lands["LAIR"] = r0

        r: List[List[lair.Land]] = [[], [], []]
        with open(self.csvpath, encoding="utf-8") as f:
            it = iter(csv.reader(f))
            next(it)  # throw away header row
            for row in it:
                (
                    key,
                    srng,
                    cities,
                    towns,
                    explorers,
                    dahan,
                    land_type,
                    gathers_to_land_key,
                ) = row
                rng = int(srng)
                if rng == 1:
                    gathers_to = r0
                elif rng >= 2:
                    gathers_to = lands[gathers_to_land_key]
                elif rng == 0:
                    gathers_to = None
                if key in self.parse_conf.ignore_lands:
                    continue
                land = lair.Land(
                    key=key,
                    land_type=land_type,
                    explorers=to_int(explorers),
                    towns=to_int(towns),
                    cities=to_int(cities),
                    dahan=to_int(dahan),
                    gathers_to=gathers_to,
                    conf=self.lair_conf,
                )
                lands[key] = land
                if rng:
                    r[rng].append(land)

        log = action_log.Actionlog()
        csv_actions = DelayedActions(lands, self.lair_conf, log)
        for action in self.read_actions_csv():
            csv_actions.push(action)
        csv_actions.run("")
        return (
            lair.Lair(r0=r0, r1=r[1], r2=r[2], conf=self.lair_conf, log=log),
            csv_actions,
        )
