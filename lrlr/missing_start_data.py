import argparse

from . import lair, parse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--turn",
        type=int,
        help="Choose turn's config dir",
    )
    parser.add_argument(
        "--range",
        type=int,
        help="Find missing lands up to given range",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    lair_conf = lair.LairConf(
        allow_missing_r1=True,
    )
    parse_conf = parse.ParseConf(
        directory=f"config/turn{args.turn}",
    )
    parser = parse.Parser(
        lair_conf=lair_conf,
        parse_conf=parse_conf,
    )

    thelair, delayed = parser.parse_all()
    missing = []
    for land, dist in thelair.state.dist.items():
        if dist > args.range:
            continue
        if land in delayed.lands.near:
            continue
        missing.append(land)
    if missing:
        toprint = ", ".join(missing)
    else:
        toprint = "nothing!"
    print(f"missing {toprint}")


if __name__ == "__main__":
    main()
