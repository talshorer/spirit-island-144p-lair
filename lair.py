import dataclasses
from typing import List, TypeVar

T = TypeVar("T")


def perms(it: List[T]) -> List[List[T]]:
    if len(it) == 1:
        return [it]
    ret = []
    for i, x in enumerate(it):
        cp = it[:i] + it[i + 1 :]
        for p in perms(cp):
            ret.append([x] + p)
    return ret


@dataclasses.dataclass
class Invaders:
    cnt: int

    def __str__(self) -> str:
        return str(self.cnt)


@dataclasses.dataclass
class Range:
    explorers: Invaders
    towns: Invaders
    cities: Invaders

    def __init__(self, explorers: int, towns: int, cities: int):
        self.explorers = Invaders(explorers)
        self.towns = Invaders(towns)
        self.cities = Invaders(cities)

    def __str__(self) -> str:
        return f"(explorers={self.explorers}, towns={self.towns}, cities={self.cities})"


def xchg(src: Invaders, tgt: Invaders, cnt: int) -> int:
    actual = min(src.cnt, cnt)
    src.cnt -= actual
    tgt.cnt += actual
    return cnt - actual


class Lair:
    def __init__(self, r0: Range, r1: Range, r2: Range):
        self.r = [r0, r1, r2]
        self.total_gathers = 0
        self.wasted_damage = 0
        self.wasted_gathers = 0
        self.fear = 0

    def _lair1(self):
        r0, *_ = self.r
        downgrades = r0.explorers.cnt // 3
        left = xchg(r0.towns, r0.explorers, downgrades)
        xchg(r0.cities, r0.towns, left)

    def _lair2(self):
        r0, r1, _ = self.r
        gathers = xchg(r1.explorers, r0.explorers, 1)
        gathers = xchg(r1.towns, r0.towns, gathers)
        self.wasted_gathers += gathers
        self.total_gathers += 1 - gathers

    def _lair3(self):
        r0, r1, r2 = self.r
        gathers = r0.explorers.cnt // 6
        self.total_gathers += gathers
        gathers = xchg(r2.towns, r1.towns, gathers)
        gathers = xchg(r2.cities, r1.cities, gathers)
        gathers = xchg(r2.explorers, r1.explorers, gathers)
        gathers = xchg(r1.explorers, r0.explorers, gathers)
        gathers = xchg(r1.towns, r0.towns, gathers)
        gathers = xchg(r1.cities, r0.cities, gathers)
        self.wasted_gathers += gathers
        self.total_gathers -= gathers

    def lair(self):
        self._lair1()
        self._lair2()
        self._lair3()

    def call(self):
        r0, r1, r2 = self.r
        waste = xchg(r1.towns, r0.towns, 5)
        waste += xchg(r1.explorers, r0.explorers, 15)
        self.total_gathers += 20 - waste
        self.wasted_gathers += waste

    def blur(self):
        r0, r1, r2 = self.r
        dmg = max(0, r0.explorers.cnt - 6) + r0.towns.cnt * 2 + r0.cities.cnt * 3

        kill = min(dmg // 2, r1.towns.cnt)
        xchg(r1.towns, r0.explorers, kill)
        dmg -= kill * 2
        self.fear += kill

        kill = min(dmg // 3, r1.cities.cnt)
        xchg(r1.cities, r0.towns, kill)
        dmg -= kill * 3
        self.fear += kill * 2

        kill = min(dmg, r1.explorers.cnt)
        xchg(r1.explorers, Invaders(0), kill)
        dmg -= kill

        self.wasted_damage += dmg

    def blur2(self):
        self.blur()
        self.blur()


def main(actions: List[str]):
    res = []
    action_seqs = set(tuple(s) for s in perms(actions))
    for action_seq in action_seqs:
        action_seq += ("blur",)  # "ravage"
        # sunglasses is roughly Range(4, 7, 4) Range(7, 13, 5) // x3 of those
        # cookie is roughly Range(3, 22, 2) Range(5, 44, 6) // x3 of those
        lair = Lair(
            Range(108, 11, 3),
            Range(7 * 3, 29 * 3, 6 * 3),
            Range(12 * 3, 57 * 3, 11 * 3),
        )
        for action in action_seq:
            getattr(lair, action)()
        res.append((action_seq, lair))

    res.sort(key=lambda pair: pair[1].r[0].explorers.cnt)

    action_seq, lair = res[-1]
    print(
        " ".join(
            [
                f"{str(action_seq):<{58}}",
                str(lair.r[0]),
                f"wasted_damage={lair.wasted_damage}",
                f"wasted_gathers={lair.wasted_gathers}",
                f"fear={lair.fear}",
            ]
        )
    )


main(["lair", "lair", "blur", "blur", "call", "call"])
main(["lair", "lair", "blur2", "call", "call"])
