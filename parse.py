import collections
import csv
import dataclasses
import json
from typing import Any, Dict, Iterator, List, Tuple, cast

import action_log
import lair
from adjacency.board_layout import Terrain
from adjacency.gen_144p import Map144P


def to_int(s: str) -> int:
    if s == "":
        return 0
    return int(s)


@dataclasses.dataclass
class ParseConf:
    server_emojis: bool
    ignore_lands: List[str]

    def land_display_name(self, key: str, land_type: str) -> str:
        if self.server_emojis:
            try:
                terrain = Terrain(land_type)
                return f"{key}:Land{terrain.name}:"
            except ValueError:
                pass
        return f"{key}{land_type}"


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
                        display_name=key,
                        land_type=land_type,
                        explorers=0,
                        towns=0,
                        cities=0,
                        dahan=0,
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
        parse_conf: ParseConf,
        log: action_log.Actionlog,
    ):
        self.actions: Dict[str, List[CsvAction]] = collections.defaultdict(lambda: [])
        self.by_id: Dict[str, CsvAction] = {}
        self.lair_conf = lair_conf
        self.parse_conf = parse_conf
        self.lands = ActionCsvLands(near=near, distant={}, lair_conf=lair_conf)
        self.log = log

    def push(self, action: CsvAction) -> None:
        self.actions[action.after_toplevel].append(action)
        # when an action is split into multiple rows, we only want the first
        if action.action_id not in self.by_id:
            self.by_id[action.action_id] = action

    def construct_action_text(self, action: CsvAction) -> str:
        actions = [action.action_name]
        while action.parent_action:
            action = self.by_id[action.parent_action]
            actions.append(action.action_name)
        return " - ".join(actions[::-1])

    def land_display_name(self, land: str) -> str:
        if not land:
            return ""
        return self.parse_conf.land_display_name(
            key=land[:-1],
            land_type=land[-1],
        )

    def run(self, key: str) -> None:
        if key not in self.actions:
            return
        pieces = [
            self.lair_conf.piece_names.explorer,
            self.lair_conf.piece_names.town,
            self.lair_conf.piece_names.city,
            self.lair_conf.piece_names.dahan,
        ]
        before = str(self.lands.near[lair.LAIR_KEY])
        with self.log.fork() as sublog:
            for action in self.actions[key]:
                action.run(self.lands)
                sublog.entry(
                    action_log.LogEntry(
                        action=action_log.Action.MANUAL,
                        text=self.construct_action_text(action),
                        src_land=self.land_display_name(action.source_key),
                        tgt_land=self.land_display_name(action.destination_key),
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
            after = str(self.lands.near[lair.LAIR_KEY])
            if key:
                self.log.entry(
                    action_log.LogEntry(
                        text=f"execute delayed actions for {key}: {before} => {after}"
                    )
                )
            else:
                sublog.entries = []
        del self.actions[key]


class Parser:
    def __init__(
        self,
        csvpath: str,
        jsonpath: str,
        actionspath: str,
        weaves: str,
        lair_conf: lair.LairConf,
        parse_conf: ParseConf,
    ):
        self.csvpath = csvpath
        self.jsonpath = jsonpath
        self.actionspath = actionspath
        self.weaves = weaves
        self.lair_conf = lair_conf
        self.parse_conf = parse_conf

    def match_piece(self, piece: lair.PieceType, name: str) -> bool:
        return piece.name(self.lair_conf.piece_names) == name

    def _parse_initial_lair(self) -> Tuple[lair.Land, str]:
        with open(self.jsonpath) as f:
            initial = json.load(f)
        if self.parse_conf.server_emojis:
            r0_key = ":IncarnaAspectLair:"
        else:
            r0_key = "lair"
        return (
            lair.Land(
                key=r0_key,
                display_name=r0_key,
                land_type="L",
                explorers=initial["explorers"],
                towns=initial["towns"],
                cities=initial["cities"],
                dahan=initial["dahan"],
                conf=self.lair_conf,
            ),
            initial["land"],
        )

    def parse_initial_lair(self) -> lair.Land:
        land, _ = self._parse_initial_lair()
        return land

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

        lands[lair.LAIR_KEY], src = self._parse_initial_lair()

        map = Map144P()
        with open(self.weaves) as f:
            weaves = json.load(f)
        for weave in weaves:
            first, second = weave.split(",")
            try:
                map.land(first).link(map.land(second), 0)
            except KeyError:
                pass

        with open(self.csvpath, encoding="utf-8") as f:
            it = iter(csv.reader(f))
            next(it)  # throw away header row
            for row in it:
                (
                    key,
                    cities,
                    towns,
                    explorers,
                    dahan,
                ) = row
                land_type = map.boards[key[:-1]].layout.terrains[int(key[-1])].value
                display_name = self.parse_conf.land_display_name(
                    key=key,
                    land_type=land_type,
                )
                if key in self.parse_conf.ignore_lands:
                    continue

                land = lair.Land(
                    key=key,
                    display_name=display_name,
                    land_type=land_type,
                    explorers=to_int(explorers),
                    towns=to_int(towns),
                    cities=to_int(cities),
                    dahan=to_int(dahan),
                    conf=self.lair_conf,
                )
                lands[key] = land

        log = action_log.Actionlog()
        csv_actions = DelayedActions(lands, self.lair_conf, self.parse_conf, log)
        for action in self.read_actions_csv():
            csv_actions.push(action)
        csv_actions.run("")

        return (
            lair.Lair(lands=lands, src=src, conf=self.lair_conf, log=log, map=map),
            csv_actions,
        )
