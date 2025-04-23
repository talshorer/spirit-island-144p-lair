import dataclasses
import itertools
from typing import Callable, List, Optional, Self, Tuple


@dataclasses.dataclass
class Pieces:
    cnt: int

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
        self.explorers = Pieces(explorers)
        self.towns = Pieces(towns)
        self.cities = Pieces(cities)
        self.dahan = Pieces(dahan)
        self.gathers_to = gathers_to
        self.mr_explorers = Pieces(0)
        self.mr_towns = Pieces(0)
        self.mr_cities = Pieces(0)

    def mr(self):
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


@dataclasses.dataclass
class PieceType:
    select: Callable[[Land], Pieces]
    select_mr: Callable[[Land], Pieces]
    health: int
    fear: int
    response: Optional[Self]
    name: str


Explorer = PieceType(
    select=lambda land: land.explorers,
    select_mr=lambda land: land.mr_explorers,
    health=1,
    fear=0,
    response=None,
    name="explorer",
)
Town = PieceType(
    select=lambda land: land.towns,
    select_mr=lambda land: land.mr_towns,
    health=2,
    fear=1,
    response=Explorer,
    name="town",
)
City = PieceType(
    select=lambda land: land.cities,
    select_mr=lambda land: land.mr_cities,
    health=3,
    fear=2,
    response=Town,
    name="city",
)
Dahan = PieceType(
    select=lambda land: land.dahan,
    select_mr=lambda land: Pieces(0),
    health=2,
    fear=0,
    response=None,
    name="dahan",
)


def xchg(src: Pieces, tgt: Pieces, cnt: int) -> int:
    actual = min(src.cnt, cnt)
    src.cnt -= actual
    tgt.cnt += actual
    return cnt - actual


class Lair:
    def __init__(
        self,
        r0: Land,
        r1: List[Land],
        r2: List[Land],
        land_priority: str,
    ):
        self.r0 = r0
        self.r1 = r1
        self.r2 = r2
        self.land_priority = land_priority
        self.total_gathers = 0
        self.wasted_damage = 0
        self.wasted_downgrades = 0
        self.wasted_invader_gathers = 0
        self.wasted_dahan_gathers = 0
        self.fear = 0
        self.log: List[str] = []

    def _gather(self, tipe: PieceType, land: Land, cnt: int) -> int:
        assert land.gathers_to
        left = xchg(tipe.select(land), tipe.select(land.gathers_to), cnt)
        self.total_gathers += cnt - left
        if cnt - left:
            self.log.append(
                f"  - gather {cnt-left} {tipe.name} from {land.key} to {land.gathers_to.key}"
            )
        return left

    def _downgrade(self, tipe: PieceType, land: Land, cnt: int) -> int:
        assert tipe.response
        left = xchg(tipe.select(land), tipe.response.select(land), cnt)
        if cnt - left:
            self.log.append(f"  - downgrade {cnt-left} {tipe.name} in {land.key}")
        return left

    def _lair1(self):
        r0 = self.r0
        downgrades = (r0.explorers.cnt + r0.dahan.cnt) // 3
        downgrades = self._downgrade(Town, r0, downgrades)
        downgrades = self._downgrade(City, r0, downgrades)
        self.wasted_downgrades += downgrades

    def _r1_least_dahan(self) -> List[Land]:
        return sorted(self.r1, key=lambda land: land.dahan.cnt)

    def _r1_most_dahan(self) -> List[Land]:
        return sorted(self.r1, key=lambda land: -land.dahan.cnt)

    def _lair2(self):
        gathers = 1
        for tipe in [Explorer, Town]:
            for land in self._r1_most_dahan():
                gathers = self._gather(tipe, land, gathers)
        self.wasted_invader_gathers += gathers

        gathers = 1
        for land in self._r1_most_dahan():
            gathers = self._gather(Dahan, land, gathers)
        self.wasted_dahan_gathers += gathers

    def _lair3_r2_gather_sort_key(self, land: Land) -> Tuple[int, int]:
        try:
            land_priority = self.land_priority.index(land.land_type)
        except ValueError:
            land_priority = len(self.land_priority)
        assert land.gathers_to
        return (land_priority, land.gathers_to.dahan.cnt)

    def _lair3(self):
        r0 = self.r0
        gathers = (r0.explorers.cnt + r0.dahan.cnt) // 6
        self.log.append(f"  - gathers: {gathers}")

        for land in sorted(self.r2, key=self._lair3_r2_gather_sort_key):
            gathers = self._gather(Town, land, gathers)
            gathers = self._gather(City, land, gathers)
            gathers = self._gather(Explorer, land, gathers)

        for tipe in [Explorer, Town, City]:
            for land in self._r1_most_dahan():
                gathers = self._gather(tipe, land, gathers)

        self.log.append(f"  - unused gathers left at end of slurp: {gathers}")
        self.wasted_invader_gathers += gathers

    def top_log(self, what: str):
        self.log.append(f"- {what} in {self.r0.key}")

    def lair(self):
        self.top_log("lair")
        self._lair1()
        self._lair2()
        self._lair3()

    def _call_one(
        self,
        it: Callable[[], List[Land]],
        tipe: PieceType,
        gathers: int,
    ):
        for land in it():
            gathers = self._gather(tipe, land, gathers)
        return gathers

    def call(self):
        self.top_log("call")
        self.wasted_invader_gathers += self._call_one(self._r1_most_dahan, Town, 5)
        self.wasted_invader_gathers += self._call_one(self._r1_most_dahan, Explorer, 15)
        self.wasted_dahan_gathers += self._call_one(self._r1_least_dahan, Dahan, 5)

    def _damage(self, land: Land, tipe: PieceType, dmg: int) -> int:
        assert land.gathers_to
        pieces = tipe.select(land)

        if tipe.response:
            if land.dahan.cnt:
                respond_to = land
            else:
                respond_to = land.gathers_to
            response = tipe.response.select_mr(respond_to)
        else:
            response = Pieces(0)
        kill = min(dmg // tipe.health, pieces.cnt)

        xchg(pieces, response, kill)
        if kill:
            self.log.append(f"  - destroy {kill} {tipe.name} in {land.key}")
            if tipe.response:
                self.log.append(
                    f"    - MR adds {kill} {tipe.response.name} in {respond_to.key}"
                )
        self.fear += kill * tipe.fear
        return dmg - kill * tipe.health

    def _ravage(self):
        r0 = self.r0
        dmg = max(0, r0.explorers.cnt - 6) + r0.towns.cnt * 2 + r0.cities.cnt * 3

        for land in self._r1_least_dahan():
            dmg = self._damage(land, Town, dmg)
            dmg = self._damage(land, City, dmg)
        for land in self._r1_least_dahan():
            dmg = self._damage(land, Explorer, dmg)

        self.log.append(f"  - unused damage left at end of ravage: {dmg}")
        self.wasted_damage += dmg

        for land in itertools.chain([self.r0], self.r1):
            land.mr()

    def ravage(self):
        self.top_log("ravage")
        self._ravage()

    def blur(self):
        self.top_log("blur")
        self._ravage()

    def blur2(self):
        self.blur()
        self.blur()

    def pull_r1_dahan(self, gathers: int):
        self.top_log(f"pull-r1-dahan({gathers})")
        self._call_one(self._r1_least_dahan, Dahan, gathers)
