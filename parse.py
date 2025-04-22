import csv

try:
    from . import lair
except ImportError:
    # stupid vscode..
    import lair  # type: ignore


def to_int(s: str) -> int:
    if s == "":
        return 0
    return int(s)


def parse(path: str) -> lair.Lair:
    lands = {}
    r0 = lair.Land(
        key="lair",
        explorers=166,
        towns=26,
        cities=4,
        dahan=26,
        gathers_to=None,
    )
    r = [[], [], []]
    with open(path) as f:
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
                _tipe,
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
            land = lair.Land(
                key=key[:-5] + key[-2:].upper(),
                explorers=to_int(explorers),
                towns=to_int(towns),
                cities=to_int(cities),
                dahan=to_int(dahan),
                gathers_to=gathers_to,
            )
            lands[key] = land
            r[rng].append(land)
    return lair.Lair(r0=r0, r1=r[1], r2=r[2])
