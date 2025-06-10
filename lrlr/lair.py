from __future__ import annotations

import abc
import contextlib
import dataclasses
import itertools
from typing import Callable, Dict, Iterator, List, Optional, Tuple, Type

from adjacency import board_layout, dijkstra, gen_144p

from .action_log import Action, Actionlog, LogEntry


@dataclasses.dataclass
class Pieces:
    cnt: int
    tipe: PieceType

    def __str__(self) -> str:
        return str(self.cnt)


LAIR_KEY = "LAIR"


def stringify_pieces(it: Iterator[Tuple[str, int]]) -> str:
    return " ".join(f"{cnt} {piece}" for piece, cnt in it if cnt) or "CLEAR"


class Land:
    def __init__(
        self,
        key: str,  # example: 🌙R4
        display_name: str,  # example: 🌙R4 OR 🌙R4:Wetlands:
        land_type: str,  # example: M
        explorers: int,
        towns: int,
        cities: int,
        dahan: int,
        conf: LairConf,
    ):
        self.key = key
        self.display_name = display_name
        self.land_type = land_type
        self.explorers = Explorer.new(explorers)
        self.towns = Town.new(towns)
        self.cities = City.new(cities)
        self.dahan = Dahan.new(dahan)
        self.mr_explorers = Explorer.new()
        self.mr_towns = Town.new()
        self.conf = conf

    def mr(self) -> None:
        for tipe in (Explorer, Town, City):
            mr = tipe.select_mr(self)
            tipe.select(self).cnt += mr.cnt
            mr.cnt = 0

    def total_invaders(self) -> int:
        return self.explorers.cnt + self.towns.cnt + self.cities.cnt

    def stringify_pieces(self) -> str:
        return stringify_pieces(
            (tipe.name(self.conf.piece_names), tipe.select(self).cnt)
            for tipe in (
                Explorer,
                Town,
                City,
                Dahan,
            )
        )


@dataclasses.dataclass
class PieceNames:
    explorer: str
    town: str
    city: str
    dahan: str


piece_names_text = PieceNames(
    explorer="explorer",
    town="town",
    city="city",
    dahan="dahan",
)

piece_names_emoji = PieceNames(
    explorer=":InvaderExplorer:",
    town=":InvaderTown:",
    city=":InvaderCity:",
    dahan=":Dahan:",
)


class _PieceType(abc.ABC):
    @classmethod
    def new(cls, cnt: int = 0) -> Pieces:
        return Pieces(cnt=cnt, tipe=cls)

    health: int
    fear: int
    response: Optional[PieceType]

    @classmethod
    @abc.abstractmethod
    def select(cls, land: Land) -> Pieces:
        pass

    @classmethod
    @abc.abstractmethod
    def select_mr(cls, land: Land) -> Pieces:
        pass

    @classmethod
    @abc.abstractmethod
    def name(cls, pn: PieceNames) -> str:
        pass


PieceType = Type[_PieceType]


class Void(_PieceType):
    health = 0
    fear = 0
    response = None

    @classmethod
    def select(cls, land: Land) -> Pieces:
        return cls.new()

    @classmethod
    def select_mr(cls, land: Land) -> Pieces:
        return cls.new()

    @classmethod
    def name(cls, pn: PieceNames) -> str:
        return "void"


class Explorer(_PieceType):
    health = 1
    fear = 0
    response = None

    @classmethod
    def select(cls, land: Land) -> Pieces:
        return land.explorers

    @classmethod
    def select_mr(cls, land: Land) -> Pieces:
        return land.mr_explorers

    @classmethod
    def name(cls, pn: PieceNames) -> str:
        return pn.explorer


class Town(_PieceType):
    health = 2
    fear = 1
    response = Explorer

    @classmethod
    def select(cls, land: Land) -> Pieces:
        return land.towns

    @classmethod
    def select_mr(cls, land: Land) -> Pieces:
        return land.mr_towns

    @classmethod
    def name(cls, pn: PieceNames) -> str:
        return pn.town


class City(_PieceType):
    health = 3
    fear = 2
    response = Town

    @classmethod
    def select(cls, land: Land) -> Pieces:
        return land.cities

    @classmethod
    def select_mr(cls, land: Land) -> Pieces:
        return Void.new()

    @classmethod
    def name(cls, pn: PieceNames) -> str:
        return pn.city


class Dahan(_PieceType):
    health = 2
    fear = 0
    response = None

    @classmethod
    def select(cls, land: Land) -> Pieces:
        return land.dahan

    @classmethod
    def select_mr(cls, land: Land) -> Pieces:
        return Void.new()

    @classmethod
    def name(cls, pn: PieceNames) -> str:
        return pn.dahan


@dataclasses.dataclass
class LairInnateConf:
    reserve_gathers: int = 0
    max_range: int = 0


@dataclasses.dataclass
class LairConf:
    terrain_priority: str = ""
    blue: LairInnateConf = dataclasses.field(default_factory=LairInnateConf)
    orange: LairInnateConf = dataclasses.field(default_factory=LairInnateConf)
    leave_behind: Dict[str, Dict[str, int]] = dataclasses.field(default_factory=dict)
    piece_names: PieceNames = dataclasses.field(
        default_factory=lambda: piece_names_text
    )
    ignore_lands: List[str] = dataclasses.field(default_factory=list)
    priority_lands: List[str] = dataclasses.field(default_factory=list)
    display_name_range: bool = False
    allow_missing_r1: bool = False

    def _terrain_priority(self, land_type: str) -> int:
        try:
            return self.terrain_priority.index(land_type)
        except ValueError:
            return len(self.terrain_priority)

    def land_priority(self, land: Optional[Land], terrain: str, coastal: bool) -> int:
        if land and land.key in self.priority_lands:
            return -1

        priority = self._terrain_priority(terrain)
        if coastal:
            priority = min(priority, self._terrain_priority("C"))
        return priority


ConvertLand = Callable[[Land], Land]


@dataclasses.dataclass
class LairState:
    r0: Land
    lands: List[Land]
    unpathable: List[Land]
    log: Actionlog
    dist: Dict[str, int]
    total_gathers: int = 0
    wasted_damage: int = 0
    wasted_downgrades: int = 0
    wasted_invader_gathers: int = 0
    wasted_dahan_gathers: int = 0
    fear: int = 0


def construct_distance_map(
    conf: LairConf,
    lands: Dict[str, Land],
    map: gen_144p.Map144P,
    src: str,
) -> Tuple[Dict[str, int], Dict[str, str]]:
    def tiebreaker(
        land: board_layout.Land,
        dist: Dict[str, int],
        prev: Dict[str, str],
    ) -> dijkstra.Comparable:
        priority = conf.land_priority(None, land.terrain.value, land.coastal)
        key = land.key
        while dist[key] > 1 and key in prev:
            key = prev[key]
        if dist[key] == 1:
            if key not in lands:
                assert conf.allow_missing_r1
                r1_dahan = 0
            else:
                r1_dahan = lands[key].dahan.cnt
        else:
            r1_dahan = 0  # it's the lair..

        prev_land = land.key
        ignored = False
        while prev_land != src:
            if prev_land in conf.ignore_lands:
                ignored = True
                break
            prev_land = prev[prev_land]

        return (ignored, -priority, r1_dahan)

    return dijkstra.distances_from(map.land(src), tiebreaker)


class Lair:
    def __init__(
        self,
        lands: Dict[str, Land],
        src: str,
        conf: LairConf,
        log: Actionlog,
        map: gen_144p.Map144P,
    ):
        self.map = map
        self.conf = conf
        self.uncommitted: List[LogEntry] = []
        self.expected_ravages_left = 0

        dist, prev = construct_distance_map(conf, lands, map, src)
        self.gathers_to = {
            key: lands.get(prev[key])
            for key in lands.keys()
            if key in prev and dist[key] != 0
        }
        r0 = lands[LAIR_KEY]
        self.r1 = []
        r2 = []
        unpathable = []
        for key, land in lands.items():
            if key == LAIR_KEY or key not in prev or dist[key] == 0:
                continue
            if conf.display_name_range:
                land.display_name += f" [{dist[key]}]"
            if dist[key] == 1:
                # gathers_to itself, only let pieces that wouldn't die to ravage through
                self.gathers_to[key] = land
                self.r1.append(land)
                r2.append(land)
            elif self._r1_gathers_to(land, dist) is not None:
                r2.append(land)
            else:
                unpathable.append(land)

        self.state = LairState(
            r0=r0,
            lands=r2,
            unpathable=unpathable,
            log=log,
            dist=dist,
        )
        self.gather_cost = {
            key: self._calc_gather_cost(lands[key]) for key in self.gathers_to.keys()
        }

    def set_expected_ravages(self, ravages: int) -> None:
        self.expected_ravages_left = ravages

    def _calc_gather_cost(self, land: Land) -> int:
        return self.state.dist[land.key] - 1

    def _r1_gathers_to(
        self,
        land: Land,
        dist: Dict[str, int],
    ) -> Optional[Land]:
        while dist[land.key] > 1:
            prev_land = self.gathers_to[land.key]
            if prev_land is None:
                return None
            land = prev_land
        return land

    def _commit_log(self) -> None:
        self.uncommitted.sort(key=lambda entry: entry.src_land or "")
        for entry in self.uncommitted:
            self.state.log.entry(entry)
        self.uncommitted = []

    def _noncommit_entry(self, entry: LogEntry) -> None:
        self.uncommitted.append(entry)

    def _xchg(
        self,
        src_land: Land,
        src_tipe: PieceType,
        tgt: Pieces,
        cnt: int,
    ) -> int:
        leave = self.conf.leave_behind.get(src_land.key, {}).get(
            src_tipe.name(piece_names_text), 0
        )
        src = src_tipe.select(src_land)
        actual = min(max(src.cnt - leave, 0), cnt)
        src.cnt -= actual
        tgt.cnt += actual
        return actual

    def _gather(self, tipe: PieceType, land: Land, cnt: int, force: bool = True) -> int:
        if land.key in self.conf.ignore_lands:
            return 0
        cost = self.gather_cost[land.key]
        intermediate_lands: List[str] = []

        last: Optional[Land] = land
        assert last
        for _ in range(cost - 1):
            last = self.gathers_to[last.key]
            assert last
            intermediate_lands.append(last.display_name)
        gathers_to = self.gathers_to[last.key]
        assert gathers_to
        assert self.state.dist.get(gathers_to.key) == 1

        if force or (
            tipe.health > self.expected_ravages_left and gathers_to.dahan.cnt > 0
        ):
            if cost:
                intermediate_lands.append(gathers_to.display_name)
            gathers_to = self.state.r0
            cost += 1
            assert gathers_to

        if cost == 0:
            return 0

        gathered = self._xchg(land, tipe, tipe.select(gathers_to), cnt // cost)
        actual = gathered * cost
        self.state.total_gathers += actual
        if actual:
            piece_name = tipe.name(self.conf.piece_names)
            self._noncommit_entry(
                LogEntry(
                    action=Action.GATHER,
                    src_land=land.display_name,
                    src_piece=piece_name,
                    intermediate_lands=intermediate_lands,
                    tgt_land=gathers_to.display_name,
                    tgt_piece=piece_name,
                    count=gathered,
                    mult=cost,
                )
            )
        return actual

    def _slurp(self, tipe: PieceType, land: Land, cnt: int) -> int:
        return self._gather(tipe, land, cnt, force=False)

    def _downgrade(self, tipe: PieceType, land: Land, cnt: int) -> int:
        assert tipe.response
        actual = self._xchg(land, tipe, tipe.response.select(land), cnt)
        if actual:
            self._noncommit_entry(
                LogEntry(
                    action=Action.DOWNGRADE,
                    src_land=land.display_name,
                    src_piece=tipe.name(self.conf.piece_names),
                    tgt_land=land.display_name,
                    tgt_piece=tipe.response.name(self.conf.piece_names),
                    count=actual,
                )
            )
        return actual

    def _lair1(self) -> None:
        r0 = self.state.r0
        downgrades = (r0.explorers.cnt + r0.dahan.cnt) // 3
        self.state.log.entry(LogEntry(text=f"available downgrades: {downgrades}"))
        downgrades -= self._downgrade(Town, r0, downgrades)
        downgrades -= self._downgrade(City, r0, downgrades)
        self.state.wasted_downgrades += downgrades

    def _r1_least_dahan(self) -> List[Land]:
        return sorted(self.r1, key=lambda land: land.dahan.cnt)

    def _r1_most_dahan(self) -> List[Land]:
        return sorted(self.r1, key=lambda land: -land.dahan.cnt)

    def _lair2(self) -> None:
        gathers = 1
        for tipe in (Explorer, Town):
            for land in self._r1_most_dahan():
                gathers -= self._gather(tipe, land, gathers)
        self.state.wasted_invader_gathers += gathers

        gathers = 1
        for land in self._r1_most_dahan():
            gathers -= self._gather(Dahan, land, gathers)
        self.state.wasted_dahan_gathers += gathers

    def _reserve(self, reserve: int, what: str, cnt: int) -> int:
        if reserve:
            to_reserve = min(cnt, reserve)
            self.state.log.entry(LogEntry(text=f"reserved {to_reserve} {what}"))
            return to_reserve
        return 0

    def _least_r1_dahan_land_priority_key(
        self,
        land: Land,
    ) -> Tuple[int, int, int, int]:
        try:
            coastal = self.map.land(land.key).coastal
        except KeyError:
            coastal = False
        land_priority = self.conf.land_priority(land, land.land_type, coastal)

        dist = self.state.dist[land.key]
        r1_land = self._r1_gathers_to(land, self.state.dist)
        assert r1_land

        ignored = land.key in self.conf.ignore_lands

        return (
            ignored,
            # swap `dist` and `land_priority` order to change sorting.
            # REVISIT make this a toggle?
            dist,
            land_priority,
            r1_land.dahan.cnt,
        )

    def _lair3(self, conf: LairInnateConf) -> None:
        r0 = self.state.r0
        gathers = (r0.explorers.cnt + r0.dahan.cnt) // 6
        self.state.log.entry(LogEntry(text=f"available gathers: {gathers}"))
        with self.state.log.indent():
            gathers -= self._reserve(conf.reserve_gathers, "gathers", gathers)

        for land in sorted(
            self.state.lands,
            key=self._least_r1_dahan_land_priority_key,
        ):
            if self.state.dist[land.key] > conf.max_range:
                continue
            gathers -= self._slurp(City, land, gathers)
            gathers -= self._slurp(Town, land, gathers)
            gathers -= self._slurp(Explorer, land, gathers)
        self._commit_log()

        for land in self._r1_most_dahan():
            gathers -= self._gather(Explorer, land, gathers)
        self._commit_log()

        self.state.log.entry(
            LogEntry(text=f"unused gathers left at end of slurp: {gathers}")
        )
        self.state.wasted_invader_gathers += gathers

    @contextlib.contextmanager
    def _top_log(self, what: str) -> Iterator[None]:
        oldlog = self.state.log
        with self.state.log.fork() as newlog:
            self.state.log = newlog
            before = self.state.r0.stringify_pieces()
            yield
            self._commit_log()
            after = self.state.r0.stringify_pieces()
            oldlog.entry(
                LogEntry(text=f"{what} in {self.state.r0.key}: ({before}) => ({after})")
            )
        self.state.log = oldlog

    def _lair_all(self, colour: str, conf: LairInnateConf) -> None:
        with self._top_log(f"lair-{colour}-thresh1"):
            self._lair1()
        with self._top_log(f"lair-{colour}-thresh2"):
            self._lair2()
        with self._top_log(f"lair-{colour}-thresh3"):
            self._lair3(conf)

    def lair_blue(self) -> None:
        self._lair_all("blue", self.conf.blue)

    def lair_orange(self) -> None:
        self._lair_all("orange", self.conf.orange)

    def _call_one(
        self,
        it: Callable[[], List[Land]],
        tipe: PieceType,
        gathers: int,
    ) -> int:
        for land in it():
            gathers -= self._gather(tipe, land, gathers)
        return gathers

    def call(self) -> None:
        with self._top_log("call"):
            wasted_invaders_gathers = self._call_one(self._r1_most_dahan, Town, 5)
            wasted_invaders_gathers += self._call_one(self._r1_most_dahan, Explorer, 15)
            self.state.wasted_invader_gathers += wasted_invaders_gathers
            self.state.log.entry(
                LogEntry(
                    text=f"unused gathers left at end of call: {wasted_invaders_gathers}"
                )
            )
            self.state.wasted_dahan_gathers += self._call_one(
                self._r1_least_dahan, Dahan, 5
            )

    def _damage(self, land: Land, tipe: PieceType, dmg: int) -> int:
        assert land.key in self.gathers_to

        respond_to: Optional[Land] = None
        if tipe.response:
            if land.dahan.cnt:
                respond_to = land
            else:
                if self.state.dist[land.key] == 1:
                    respond_to = self.state.r0
                else:
                    respond_to = self.gathers_to[land.key]
            assert respond_to
            response = tipe.response.select_mr(respond_to)
        else:
            response = Void.new()

        kill = self._xchg(land, tipe, response, dmg // tipe.health)
        if kill:
            self._noncommit_entry(
                LogEntry(
                    action=Action.DESTROY,
                    src_land=land.display_name,
                    src_piece=tipe.name(self.conf.piece_names),
                    tgt_land=respond_to.display_name if respond_to else "",
                    tgt_piece=(
                        tipe.response.name(self.conf.piece_names)
                        if tipe.response
                        else ""
                    ),
                    count=kill,
                )
            )
        self.state.fear += kill * tipe.fear
        return kill * tipe.health

    def _ravage(self) -> None:
        self.expected_ravages_left -= 1

        r0 = self.state.r0
        dmg = max(0, r0.explorers.cnt - 6) + r0.towns.cnt * 2 + r0.cities.cnt * 3
        fear_before = self.state.fear

        lands = sorted(
            self.r1,
            key=self._least_r1_dahan_land_priority_key,
        )
        for land in lands:
            dmg -= self._damage(land, Town, dmg)
            dmg -= self._damage(land, City, dmg)
        for land in lands:
            dmg -= self._damage(land, Explorer, dmg)

        self._commit_log()
        self.state.log.entry(
            LogEntry(text=f"unused damage left at end of ravage: {dmg}")
        )
        self.state.log.entry(
            LogEntry(text=f"fear caused by ravage: {self.state.fear - fear_before}")
        )
        self.state.wasted_damage += dmg

        for land in itertools.chain([self.state.r0], self.r1):
            land.mr()

    def ravage(self) -> None:
        with self._top_log("ravage"):
            self._ravage()

    def _add(self, land: Land, tipe: PieceType, cnt: int) -> None:
        tipe.select(land).cnt += cnt
        self.state.log.entry(
            LogEntry(
                action=Action.ADD,
                tgt_land=land.display_name,
                tgt_piece=tipe.name(self.conf.piece_names),
                count=cnt,
            )
        )

    def _build(self, land: Land) -> None:
        if all(tipe.select(land).cnt == 0 for tipe in (Explorer, Town, City)):
            return

        tipe: PieceType
        if land.towns.cnt > land.cities.cnt:
            tipe = City
        else:
            tipe = Town
        self._add(land, tipe, 1)

    def blur(self) -> None:
        with self._top_log("blur"):
            if self.state.r0.dahan.cnt > 0:
                self._add(self.state.r0, Dahan, 1)
            self._build(self.state.r0)
            self._ravage()

    def blur2(self) -> None:
        self.blur()
        self.blur()
