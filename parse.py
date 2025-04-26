import csv
import dataclasses
import json
from typing import Dict, List


import lair
import layout


def to_int(s: str) -> int:
    if s == "":
        return 0
    return int(s)


@dataclasses.dataclass
class ParseConf:
    server_emojis: bool


def parse(
    csvpath: str,
    jsonpath: str,
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
    )
    r: List[List[lair.Land]] = [[], [], []]
    with open(csvpath) as f:
        it = iter(csv.reader(f))
        next(it)  # throw away header row
        last_weave = ""
        for row in it:
            (
                weaves,
                land_key,
                srng,
                cities,
                towns,
                explorers,
                dahan,
                tipe,
                gathers_to_land_key,
                _island_idx,
            ) = row
            if weaves == "Total":  # throw away all the stuff for humans
                break
            if weaves:
                last_weave = weaves.replace(" ", "")
            key = f"{last_weave}.{land_key}"
            rng = int(srng)
            if rng == 1:
                gathers_to = r0
            else:
                gathers_to = lands[f"{last_weave}.{gathers_to_land_key}"]
            land_type = tipe[0].upper()
            if parse_conf.server_emojis:
                land_type_key = f":Land{layout.Terrain(land_type).name}:"
            else:
                land_type_key = land_type
            land = lair.Land(
                key=key[:-5] + key[-2:].upper() + land_type_key,
                land_type=land_type,
                explorers=to_int(explorers),
                towns=to_int(towns),
                cities=to_int(cities),
                dahan=to_int(dahan),
                gathers_to=gathers_to,
            )
            lands[key] = land
            r[rng].append(land)
    assert not r[0]
    return lair.Lair(r0=r0, r1=r[1], r2=r[2], conf=lair_conf)
