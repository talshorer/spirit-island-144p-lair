import csv
import dataclasses
import json
from typing import Any, Dict, Iterator, List, Tuple, cast


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

    def parse_initial_lair(self) -> lair.Lair:
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

    def parse_all(self) -> Tuple[lair.Lair, Dict[str, lair.Land]]:
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
                else:
                    gathers_to = lands[gathers_to_land_key]
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
                r[rng].append(land)

        distant_lands: Dict[str, lair.Land] = {}
        for action in self.read_actions_csv():
            for key, mult in ((action.source_key, -1), (action.destination_key, 1)):
                if not key:
                    continue
                land_type = key[-1]
                key = key[:-1]
                if key in lands:
                    land = lands[key]
                    assert land_type == land.land_type
                    allow_negative = False
                else:
                    allow_negative = True
                    dland = distant_lands.get(key)
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
                            conf=self.lair_conf,
                        )
                        distant_lands[key] = land
                land.add_pieces(
                    mult * to_int(action.explorers),
                    mult * to_int(action.towns),
                    mult * to_int(action.cities),
                    mult * to_int(action.dahan),
                    allow_negative,
                )
        assert not r[0]
        return lair.Lair(r0=r0, r1=r[1], r2=r[2], conf=self.lair_conf), distant_lands
