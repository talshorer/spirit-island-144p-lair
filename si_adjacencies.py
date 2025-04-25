from __future__ import annotations

# from dataclasses import dataclass
# @dataclass
# class Land:
#     pass


class Edge:
    def __init__(self, lands: list[int], boundaries: list[int], parent: Board):
        self.lands = tuple(lands[::-1])
        self.boundaries = (0,) + tuple(sorted(boundaries)) + (7,)
        self.parent = parent
        self.neighbor = None

    def __contains__(self, landno):
        """Is this land number on this edge?"""
        return landno in self.lands

    def __matmul__(self, neighbor):
        # sorry for abusing dunders
        if neighbor is None:
            return

        self_pos = 1
        neighbor_pos = -2
        while True:
            try:
                self_next = self.boundaries[self_pos]
                neighbor_next = neighbor.boundaries[neighbor_pos]
            except IndexError:
                break
            yield (self.lands[self_pos - 1], neighbor.lands[neighbor_pos + 1])
            if self_next + neighbor_next > 6:
                neighbor_pos -= 1
            else:
                self_pos += 1


class Board:
    def __init__(self, name, letter):
        """
        Lands around the edge in clockwise order starting from 1.
        Boundaries in the same order, None for corners.
        """
        lands, boundaries, internal_adjacencies = GAME_BOARDS[letter]
        self.name = name

        c1, c2 = [i for i, x in enumerate(boundaries) if x is None]
        self.edges = [
            Edge(lands[: c1 + 1], boundaries[:c1], self),
            Edge(lands[c1:c2], boundaries[c1 + 1 : c2], self),
            Edge(lands[c2 - 1 :], boundaries[c2 + 1 :], self),
        ]
        self.internal_adjacencies = {i + 1: set() for i in range(8)}
        for i, val in enumerate(internal_adjacencies.split(",")):
            for n in val:
                self.internal_adjacencies[i + 1].add(int(n))
                self.internal_adjacencies[int(n)].add(i + 1)

    def get_corner(self, corner):
        """corner: str '1', '3', '6', '8'"""
        match corner:
            case "1" | "3":
                return int(corner)
            case "6":
                return self.edges[2].lands[-1]
            case "8":
                return self.edges[0].lands[-1]

    ##    def __getitem__(self, ix):
    ##        return self.edges[ix]

    def adjacent(self, land):
        for i in self.internal_adjacencies[land]:
            yield (self, i)

        yield from (
            (edge.neighbor.parent, j)
            for edge in self.edges
            for i, j in edge @ edge.neighbor
            if i == land
        )

        # yield the corner adjacencies

    def __iand__(self, neighbor):
        # sorry for really abusing dunders
        assert self.neighbor is None
        assert neighbor.neighbor is None
        self.neighbor = neighbor
        neighbor.neighbor = self

        return self


GAME_BOARDS = {
    "A": ((1, 6, 8, 7, 5, 4, 3), (5, 3, None, 4, None, 6, 5, 3), "2456,34,4,5,678,8,8"),
    "B": ((1, 6, 8, 7, 4, 3), (6, 3, None, 4, None, 6, 4), "2456,34,4,57,67,78,8"),
    "C": ((1, 6, 8, 7, 4, 3), (5, 3, None, 3, 1, None, 3), "256,345,4,57,67,78,8"),
    "D": ((1, 8, 7, 6, 4, 3), (1, None, 4, 1, None, 5, 2), "2578,345,4,56,67,7,8"),
    "E": ((1, 7, 8, 6, 4, 3), (4, 2, None, 2, None, 6, 3), "257,35,45,567,7,78,8"),
    "F": ((1, 6, 8, 7, 4, 3), (4, 1, None, 3, None, 5, 2), "256,345,4,578,68,8,8"),
    "G": ((1, 6, 8, 7, 4, 3), (4, 2, None, 3, None, 6, 4), "26,3456,4,57,678,8,8"),
    "H": ((1, 8, 7, 4, 3), (3, None, 5, 1, None, 3), "268,356,45,57,67,78,8"),
}


if __name__ == "__main__":

    def debug_edges(edge1, edge2):
        for i, j in edge1 @ edge2:
            print(f"{i} {j}")

    p, q, r = Board("🐑P", "H"), Board("🐑Q", "A"), Board("🐑R", "D")

    p.edges[1] &= q.edges[2]
    q.edges[1] &= r.edges[2]
    r.edges[1] &= p.edges[2]

    for i in range(1, 9):
        print(
            f'Neighbors of 🐑P{i}: {", ".join(f"{board.name}{number}" for board, number in p.adjacent(i))}'
        )
