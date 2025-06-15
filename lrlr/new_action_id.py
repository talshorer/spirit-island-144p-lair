import argparse

from . import lair, parse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--turn",
        type=int,
        help="Choose turn's config dir",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    lair_conf = lair.LairConf()
    parse_conf = parse.ParseConf(
        directory=f"config/turn{args.turn}",
    )
    parser = parse.Parser(
        lair_conf=lair_conf,
        parse_conf=parse_conf,
    )
    used = set()
    for action in parser.read_actions_csv():
        used.add(int(action.action_id))
    for i in range(len(used) + 1):
        if i not in used:
            print(i)
            break
    else:
        raise ValueError("Failed to find free action id")


if __name__ == "__main__":
    main()
