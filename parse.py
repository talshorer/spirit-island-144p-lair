import csv
import dataclasses
import json
from typing import Dict, List


import lair


def to_int(s: str) -> int:
    if s == "":
        return 0
    return int(s)


@dataclasses.dataclass
class ParseConf:
    server_emojis: bool
    ignore_lands: List[str]


def parse(
    csvpath: str,
    jsonpath: str,
    actionspath: str,
    lair_conf: lair.LairConf,
    parse_conf: ParseConf,
) -> lair.Lair:
    lands: Dict[str, lair.Land] = {}
    with open(jsonpath) as f:
        initial = json.load(f)
    if parse_conf.server_emojis:
        r0_key = ":IncarnaAspectLair:"
    else:
        r0_key = "lair"
    r0 = lair.Land(
        key=r0_key,
        land_type="L",
        explorers=initial["explorers"],
        towns=initial["towns"],
        cities=initial["cities"],
        dahan=initial["dahan"],
        gathers_to=None,
        conf=lair_conf,
    )
    lands["LAIR"] = r0

    r: List[List[lair.Land]] = [[], [], []]
    with open(csvpath, encoding="utf-8") as f:
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
            if key in parse_conf.ignore_lands:
                continue
            land = lair.Land(
                key=key,
                land_type=land_type,
                explorers=to_int(explorers),
                towns=to_int(towns),
                cities=to_int(cities),
                dahan=to_int(dahan),
                gathers_to=gathers_to,
                conf=lair_conf,
            )
            lands[key] = land
            r[rng].append(land)

    # lands not in TurnNStart.csv
    # I'm keeping track of them so that we can potentially update the code to produce
    #    a log with the sources of invaders to doublecheck things
    distant_lands: Dict[str, lair.Land] = {}
    with open(actionspath, encoding="utf-8") as f:
        it = iter(csv.reader(f))
        next(it)  # throw away header row
        for row in it:
            (
                source_key,
                destination_key,
                cities,
                towns,
                explorers,
                dahan,
                _action_name,
                _action_id,
                _parent_action,
                _notes,
            ) = row

            for key, mult in ((source_key, -1), (destination_key, 1)):
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
                    land = distant_lands.get(key)
                    if land is None:
                        land = lair.Land(
                            key=key,
                            land_type=land_type,
                            explorers=0,
                            towns=0,
                            cities=0,
                            dahan=0,
                            gathers_to=None,
                            conf=lair_conf,
                        )
                        distant_lands[key] = land
                land.add_pieces(
                    mult * to_int(explorers),
                    mult * to_int(towns),
                    mult * to_int(cities),
                    mult * to_int(dahan),
                    allow_negative,
                )
    assert not r[0]
    return lair.Lair(r0=r0, r1=r[1], r2=r[2], conf=lair_conf)
