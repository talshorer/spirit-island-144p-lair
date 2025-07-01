import abc
import argparse
import dataclasses
import sys
from typing import (
    Any,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Self,
    Tuple,
    Type,
    TypeVar,
)

import json5

from adjacency import dijkstra

from .board_layout import Board, BoardEdge, Corner, Edge, Land, Layout

T = TypeVar("T")


class DeserializeNewBoardLinker(abc.ABC, Generic[T]):
    @property
    @abc.abstractmethod
    def key(self) -> str:
        pass

    @abc.abstractmethod
    def get(self, board: Board, key: str) -> T:
        pass

    @abc.abstractmethod
    def extract_first(self, data: Any) -> Iterator[Tuple[str, str]]:
        pass

    @abc.abstractmethod
    def extract_second(self, data: Any) -> Iterator[Tuple[str, str]]:
        pass

    @abc.abstractmethod
    def link(self, first: T, second: T) -> None:
        pass


class DeserializeNewBoardEdgeLinker(DeserializeNewBoardLinker):
    key = "edges"

    def get(self, board: Board, key: str) -> BoardEdge:
        assert key.islower()
        edge = getattr(Edge, key.upper())
        return board.edges[edge]

    def extract_first(self, data: Any) -> Iterator[Tuple[str, str]]:
        return data.items()

    def extract_second(self, data: Any) -> Iterator[Tuple[str, str]]:
        yield (data["board"], data["edge"])

    def link(self, first: BoardEdge, second: BoardEdge) -> None:
        first.link(second)


class DeserializeNewBoardCornerLinker(DeserializeNewBoardLinker):
    key = "corners"

    def get(self, board: Board, key: str) -> Land:
        assert key.islower()
        corner = getattr(Corner, key.upper())
        land_number = board.layout.get_corner(corner)
        return board.lands[land_number]

    def extract_first(self, data: Any) -> Iterator[Tuple[str, str]]:
        return data.items()

    def extract_second(self, data: Any) -> Iterator[Tuple[str, str]]:
        for item in data:
            yield item["board"], item["corner"]

    def link(self, first: Land, second: Land) -> None:
        first.link(second)


class DeserializeNewBoardArchipelagoLinker(DeserializeNewBoardLinker):
    key = "archipelago"

    def get(self, board: Board, key: str) -> Board:
        return board

    def extract_first(self, data: Any) -> Iterator[Tuple[str, str]]:
        for item in data:
            yield "", item

    def extract_second(self, data: Any) -> Iterator[Tuple[str, str]]:
        yield data, ""

    def link(self, first: Board, second: Board) -> None:
        first.link_archipelago(second)


@dataclasses.dataclass(frozen=True)
class MapConf:
    with_ocean: bool = True
    weave_file: Optional[str] = None

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> Self:
        return cls(with_ocean=not args.no_archipelago, weave_file=args.weaves)


class Map:
    def __init__(self, conf: MapConf) -> None:
        self._conf = conf
        self.boards: Dict[str, Board] = {}
        self._load()
        if conf.weave_file:
            self._weave(conf.weave_file)

    @classmethod
    def _from_args(cls, args: argparse.Namespace) -> Self:
        return cls(MapConf.from_args(args))

    def _load(self) -> None:
        pass

    def _weave(self, path: str) -> None:
        with open(path, encoding="utf-8") as f:
            data = json5.load(f)
        for weave in data:
            key1, key2 = weave.split(",")
            try:
                self.land(key1).link(self.land(key2), 0)
            except KeyError:
                pass

    def _deserialize_new_board_inner(
        self,
        board: Board,
        data: Dict[str, Any],
        linker_type: Type[DeserializeNewBoardLinker],
    ) -> None:
        linker = linker_type()
        if (it := data.get(linker.key)) is None:
            return
        for key, value in linker.extract_first(it):
            first = linker.get(board, key)
            for second_board, second_key in linker.extract_second(value):
                second = linker.get(self.boards[second_board], second_key)
                linker.link(first, second)

    def _deserialize_new_board(self, data: Dict[str, Any]) -> None:
        layout_name = data["layout"]
        layout = getattr(Layout, layout_name)
        board = Board(
            data.get("board", layout_name),
            layout,
            with_ocean=self._conf.with_ocean,
        )
        self.boards[board.name] = board

        self._deserialize_new_board_inner(board, data, DeserializeNewBoardEdgeLinker)
        self._deserialize_new_board_inner(board, data, DeserializeNewBoardCornerLinker)
        self._deserialize_new_board_inner(
            board, data, DeserializeNewBoardArchipelagoLinker
        )

    def _run_modifications(self, data: List[Dict[str, Any]]) -> None:
        for mod in data:
            match mod["power"]:
                case "cast_down":
                    self._cast_down(mod)
                case "deeps":
                    self._deeps(mod)
                case "dream":
                    self._dream(mod)
                case unknown:
                    raise ValueError(f"Unknown modification type {unknown}")

    def _cast_down(self, data: Dict[str, Any]) -> None:
        board = data["board"]
        self.boards[board].cast_down()
        del self.boards[board]
        for land in data.get("weave", ()):
            self.land(land).sink(deeps=False)

    def _deeps(self, data: Dict[str, Any]) -> None:
        self.land(data["land"]).sink(deeps=True)

    def _dream(self, data: Dict[str, Any]) -> None:
        self._deserialize_new_board(data)

    def land(self, key: str) -> Land:
        return self.boards[key[:-1]].lands[int(key[-1])]


def main(klass: Type[Map], parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--no-archipelago",
        action="store_true",
        help="Don't link archipelagos for distance calculation",
    )
    parser.add_argument(
        "--weaves",
        help="Path to weaves file",
    )
    subparsers = parser.add_subparsers(dest="sub", required=True)
    subparsers.add_parser("json5")
    path_subparser = subparsers.add_parser("path")
    path_subparser.add_argument("src")
    path_subparser.add_argument("dst")

    args = parser.parse_args()
    map = klass._from_args(args)

    match args.sub:
        case "json5":
            adj = {
                land.key: list(land.links.keys())
                for board in map.boards.values()
                for land in board.lands.values()
            }
            json5.dump(adj, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
            print()
        case "path":
            dist, prev = dijkstra.distances_from(map.land(args.src))
            print(
                dist[args.dst],
                " ".join(dijkstra.construct_path(prev, args.src, args.dst)),
            )


if __name__ == "__main__":

    @dataclasses.dataclass(frozen=True)
    class MapJson5Conf(MapConf):
        map_file: str = ""

        @classmethod
        def from_args(cls, args: argparse.Namespace) -> Self:
            sup = MapConf.from_args(args)
            return cls(**sup.__dict__, map_file=args.map)

    class MapJson5(Map):
        def __init__(self, conf: MapJson5Conf):
            super().__init__(conf)

        @classmethod
        def _from_args(cls, args: argparse.Namespace) -> Self:
            return cls(MapJson5Conf.from_args(args))

        def _load(self) -> None:
            assert isinstance(self._conf, MapJson5Conf)
            with open(self._conf.map_file, encoding="utf-8") as f:
                self._data = json5.load(f)
            for board_data in self._data["boards"]:
                self._deserialize_new_board(board_data)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--map",
        help="Path to map file",
    )
    main(MapJson5, parser)
