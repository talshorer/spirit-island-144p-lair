import dataclasses
from typing import Callable, List, Optional, Self


@dataclasses.dataclass
class Pieces:
    cnt: int

    def __str__(self) -> str:
        return str(self.cnt)


@dataclasses.dataclass
class Land:
    key: str
    explorers: Pieces
    towns: Pieces
    cities: Pieces
    dahan: Pieces
    gathers_to: Optional[Self]

    def __init__(
        self,
        key: str,
        explorers: int,
        towns: int,
        cities: int,
        dahan: int,
        gathers_to: Optional[Self],
    ):
        self.key = key
        self.explorers = Pieces(explorers)
        self.towns = Pieces(towns)
        self.cities = Pieces(cities)
        self.dahan = Pieces(dahan)
        self.gathers_to = gathers_to

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
    health: int
    fear: int
    response: Optional[Self]


Explorer = PieceType(lambda land: land.explorers, 1, 0, None)
Town = PieceType(lambda land: land.towns, 2, 1, Explorer)
City = PieceType(lambda land: land.cities, 3, 2, Town)
Dahan = PieceType(lambda land: land.dahan, 2, 0, None)


def xchg(src: Pieces, tgt: Pieces, cnt: int) -> int:
    actual = min(src.cnt, cnt)
    src.cnt -= actual
    tgt.cnt += actual
    return cnt - actual


class Lair:
    def __init__(self, r0: Land, r1: List[Land], r2: List[Land]):
        self.r0 = r0
        self.r1 = r1
        self.r2 = r2
        self.total_gathers = 0
        self.wasted_damage = 0
        self.wasted_downgrades = 0
        self.wasted_invader_gathers = 0
        self.wasted_dahan_gathers = 0
        self.fear = 0

    def _gather(self, tipe: PieceType, land: Land, cnt: int) -> int:
        assert land.gathers_to
        left = xchg(tipe.select(land), tipe.select(land.gathers_to), cnt)
        self.total_gathers += cnt - left
        return left

    def _lair1(self):
        r0 = self.r0
        downgrades = (r0.explorers.cnt + r0.dahan.cnt) // 3
        downgrades = xchg(r0.towns, r0.explorers, downgrades)
        downgrades = xchg(r0.cities, r0.towns, downgrades)
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

    def _lair3(self):
        r0 = self.r0
        gathers = (r0.explorers.cnt + r0.dahan.cnt) // 6

        # gather through lands with least dahan first
        for land in sorted(self.r2, key=lambda land: land.gathers_to.dahan.cnt):
            gathers = self._gather(Town, land, gathers)
            gathers = self._gather(City, land, gathers)
            gathers = self._gather(Explorer, land, gathers)

        for tipe in [Explorer, Town, City]:
            for land in self._r1_most_dahan():
                gathers = self._gather(tipe, land, gathers)

        self.wasted_invader_gathers += gathers

    def lair(self):
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
            response = tipe.response.select(respond_to)
        else:
            response = Pieces(0)
        kill = min(dmg // tipe.health, pieces.cnt)

        xchg(pieces, response, kill)
        self.fear += kill * tipe.fear
        return dmg - kill * tipe.health

    def ravage(self):
        r0 = self.r0
        dmg = max(0, r0.explorers.cnt - 6) + r0.towns.cnt * 2 + r0.cities.cnt * 3

        for land in self._r1_least_dahan():
            dmg = self._damage(land, Town, dmg)
            dmg = self._damage(land, City, dmg)
        for land in self._r1_least_dahan():
            dmg = self._damage(land, Explorer, dmg)

        self.wasted_damage += dmg

    def blur(self):
        self.ravage()

    def blur2(self):
        self.blur()
        self.blur()
