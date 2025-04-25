from __future__ import annotations

import contextlib
import dataclasses
import itertools
from typing import Callable, Iterator, List, Optional, Self, Tuple, cast


@dataclasses.dataclass
class Pieces:
    cnt: int
    tipe: PieceType

    def __str__(self) -> str:
        return str(self.cnt)


class Land:
    def __init__(
        self,
        key: str,
        land_type: str,
        explorers: int,
        towns: int,
        cities: int,
        dahan: int,
        gathers_to: Optional[Self],
    ):
        self.key = key
        self.land_type = land_type
        self.explorers = Explorer.new(explorers)
        self.towns = Town.new(towns)
        self.cities = City.new(cities)
        self.dahan = Dahan.new(dahan)
        self.gathers_to = gathers_to
        self.mr_explorers = Explorer.new()
        self.mr_towns = Town.new()

    def mr(self) -> None:
        for tipe in (Explorer, Town, City):
            mr = tipe.select_mr(self)
            tipe.select(self).cnt += mr.cnt
            mr.cnt = 0

    def __str__(self) -> str:
        pieces = ", ".join(
            [
                f"explorers={self.explorers}",
                f"towns={self.towns}",
                f"cities={self.cities}",
                f"dahan={self.dahan}",
            ]
        )
        return f"({pieces})"


PieceSelect = Callable[[Land], Pieces]


@dataclasses.dataclass
class PieceType:
    select: PieceSelect
    select_mr: PieceSelect
    health: int
    fear: int
    response: Optional[Self]
    name: str

    def new(self, cnt: int = 0) -> Pieces:
        return Pieces(cnt=cnt, tipe=self)


Void: PieceType
Void = PieceType(
    select=cast(PieceSelect, lambda land: Void.new()),
    select_mr=cast(PieceSelect, lambda land: Void.new()),
    health=0,
    fear=0,
    response=None,
    name="void",
)
Explorer = PieceType(
    select=cast(PieceSelect, lambda land: land.explorers),
    select_mr=cast(PieceSelect, lambda land: land.mr_explorers),
    health=1,
    fear=0,
    response=None,
    name="explorer",
)
Town = PieceType(
    select=cast(PieceSelect, lambda land: land.towns),
    select_mr=cast(PieceSelect, lambda land: land.mr_towns),
    health=2,
    fear=1,
    response=Explorer,
    name="town",
)
City = PieceType(
    select=cast(PieceSelect, lambda land: land.cities),
    select_mr=cast(PieceSelect, lambda land: Void.new()),
    health=3,
    fear=2,
    response=Town,
    name="city",
)
Dahan = PieceType(
    select=cast(PieceSelect, lambda land: land.dahan),
    select_mr=cast(PieceSelect, lambda land: Void.new()),
    health=2,
    fear=0,
    response=None,
    name="dahan",
)


@dataclasses.dataclass
class LairConf:
    land_priority: str
    reserve_gathers: int
    reckless_offensive: List[str]


ConvertLand = Callable[[Land], Land]


class Lair:
    def __init__(
        self,
        r0: Land,
        r1: List[Land],
        r2: List[Land],
        conf: LairConf,
    ):
        self.r0 = r0
        self.r1 = r1
        self.r2 = r2
        self.conf = conf
        self.total_gathers = 0
        self.wasted_damage = 0
        self.wasted_downgrades = 0
        self.wasted_invader_gathers = 0
        self.wasted_dahan_gathers = 0
        self.reserve_gathers = conf.reserve_gathers
        self.fear = 0
        self.log: List[str] = []

    def _xchg(
        self,
        src_land: Land,
        src_tipe: PieceType,
        tgt: Pieces,
        cnt: int,
    ) -> int:
        if any(land_key in src_land.key for land_key in self.conf.reckless_offensive):
            leave = 2
        else:
            leave = 0
        src = src_tipe.select(src_land)
        actual = min(max(src.cnt - leave, 0), cnt)
        src.cnt -= actual
        tgt.cnt += actual
        return cnt - actual

    def _gather(self, tipe: PieceType, land: Land, cnt: int) -> int:
        assert land.gathers_to
        left = self._xchg(land, tipe, tipe.select(land.gathers_to), cnt)
        self.total_gathers += cnt - left
        if cnt - left:
            self.log.append(
                f"  - gather {cnt-left} {tipe.name} from {land.key} to {land.gathers_to.key}"
            )
        return left

    def _downgrade(self, tipe: PieceType, land: Land, cnt: int) -> int:
        assert tipe.response
        left = self._xchg(land, tipe, tipe.response.select(land), cnt)
        if cnt - left:
            self.log.append(f"  - downgrade {cnt-left} {tipe.name} in {land.key}")
        return left

    def _lair1(self) -> None:
        r0 = self.r0
        downgrades = (r0.explorers.cnt + r0.dahan.cnt) // 3
        downgrades = self._downgrade(Town, r0, downgrades)
        downgrades = self._downgrade(City, r0, downgrades)
        self.wasted_downgrades += downgrades

    def _r1_least_dahan(self) -> List[Land]:
        return sorted(self.r1, key=lambda land: land.dahan.cnt)

    def _r1_most_dahan(self) -> List[Land]:
        return sorted(self.r1, key=lambda land: -land.dahan.cnt)

    def _lair2(self) -> None:
        gathers = 1
        for tipe in [Explorer, Town]:
            for land in self._r1_most_dahan():
                gathers = self._gather(tipe, land, gathers)
        self.wasted_invader_gathers += gathers

        gathers = 1
        for land in self._r1_most_dahan():
            gathers = self._gather(Dahan, land, gathers)
        self.wasted_dahan_gathers += gathers

    def _least_dahan_land_priority_key(
        self,
        convert: ConvertLand,
    ) -> Callable[[Land], Tuple[int, int]]:
        def key(land: Land) -> Tuple[int, int]:
            try:
                land_priority = self.conf.land_priority.index(land.land_type)
            except ValueError:
                land_priority = len(self.conf.land_priority)
            land = convert(land)
            assert land
            return (land_priority, land.dahan.cnt)

        return key

    def _lair3(self) -> None:
        r0 = self.r0
        gathers = (r0.explorers.cnt + r0.dahan.cnt) // 6
        self.log.append(f"  - gathers: {gathers}")
        if self.reserve_gathers:
            reserve = min(gathers, self.reserve_gathers)
            self.log.append(f"    - reserved {reserve} gathers")
            gathers -= reserve
            self.reserve_gathers -= reserve

        for land in sorted(
            self.r2,
            key=self._least_dahan_land_priority_key(
                cast(ConvertLand, lambda land: land.gathers_to)
            ),
        ):
            gathers = self._gather(Town, land, gathers)
            gathers = self._gather(City, land, gathers)
            gathers = self._gather(Explorer, land, gathers)

        for tipe in [Explorer, Town, City]:
            for land in self._r1_most_dahan():
                gathers = self._gather(tipe, land, gathers)

        self.log.append(f"  - unused gathers left at end of slurp: {gathers}")
        self.wasted_invader_gathers += gathers

    @contextlib.contextmanager
    def _top_log(self, what: str) -> Iterator[None]:
        oldlog = self.log
        self.log = []
        before = str(self.r0)
        yield
        oldlog.append(f"- {what} in {self.r0.key}: {before} => {self.r0}")
        oldlog.extend(self.log)
        self.log = oldlog

    def lair(self) -> None:
        with self._top_log("lair"):
            self._lair1()
            self._lair2()
            self._lair3()

    def _call_one(
        self,
        it: Callable[[], List[Land]],
        tipe: PieceType,
        gathers: int,
    ) -> int:
        for land in it():
            gathers = self._gather(tipe, land, gathers)
        return gathers

    def call(self) -> None:
        with self._top_log("call"):
            self.wasted_invader_gathers += self._call_one(self._r1_most_dahan, Town, 5)
            self.wasted_invader_gathers += self._call_one(
                self._r1_most_dahan, Explorer, 15
            )
            self.wasted_dahan_gathers += self._call_one(self._r1_least_dahan, Dahan, 5)

    def _damage(self, land: Land, tipe: PieceType, dmg: int) -> int:
        assert land.gathers_to

        if tipe.response:
            if land.dahan.cnt:
                respond_to = land
            else:
                respond_to = land.gathers_to
            response = tipe.response.select_mr(respond_to)
        else:
            response = Void.new()
        kill = min(dmg // tipe.health, tipe.select(land).cnt)

        self._xchg(land, tipe, response, kill)
        if kill:
            self.log.append(f"  - destroy {kill} {tipe.name} in {land.key}")
            if tipe.response:
                self.log.append(
                    f"    - MR adds {kill} {tipe.response.name} in {respond_to.key}"
                )
        self.fear += kill * tipe.fear
        return dmg - kill * tipe.health

    def _ravage(self) -> None:
        r0 = self.r0
        dmg = max(0, r0.explorers.cnt - 6) + r0.towns.cnt * 2 + r0.cities.cnt * 3

        lands = sorted(
            self.r1,
            key=self._least_dahan_land_priority_key(
                cast(ConvertLand, lambda land: land)
            ),
        )
        for land in lands:
            dmg = self._damage(land, Town, dmg)
            dmg = self._damage(land, City, dmg)
        for land in lands:
            dmg = self._damage(land, Explorer, dmg)

        self.log.append(f"  - unused damage left at end of ravage: {dmg}")
        self.wasted_damage += dmg

        for land in itertools.chain([self.r0], self.r1):
            land.mr()

    def ravage(self) -> None:
        with self._top_log("ravage"):
            self._ravage()

    def blur(self) -> None:
        with self._top_log("blur"):
            self._ravage()

    def blur2(self) -> None:
        self.blur()
        self.blur()

    def pull_r1_dahan(self, gathers: int) -> None:
        with self._top_log(f"pull-r1-dahan({gathers})"):
            self._call_one(self._r1_least_dahan, Dahan, gathers)
