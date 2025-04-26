from layout import Board, EdgePosition, Layout


def link_hub(p: Board, q: Board, r: Board, s: Board, t: Board, u: Board) -> None:
    # the left standard-3
    p.edges[EdgePosition.CLOCK6].link(q.edges[EdgePosition.CLOCK9])
    q.edges[EdgePosition.CLOCK6].link(r.edges[EdgePosition.CLOCK9])
    r.edges[EdgePosition.CLOCK6].link(p.edges[EdgePosition.CLOCK9])
    # the right standard-3
    s.edges[EdgePosition.CLOCK6].link(t.edges[EdgePosition.CLOCK9])
    t.edges[EdgePosition.CLOCK6].link(u.edges[EdgePosition.CLOCK9])
    u.edges[EdgePosition.CLOCK6].link(s.edges[EdgePosition.CLOCK9])
    # and link them
    q.edges[EdgePosition.CLOCK3].link(s.edges[EdgePosition.CLOCK3])


def link_spoke(p: Board, q: Board, r: Board, s: Board, t: Board, u: Board) -> None:
    # the left coastline
    p.edges[EdgePosition.CLOCK9].link(q.edges[EdgePosition.CLOCK3])
    q.edges[EdgePosition.CLOCK9].link(r.edges[EdgePosition.CLOCK3])
    # the right coastline
    s.edges[EdgePosition.CLOCK9].link(t.edges[EdgePosition.CLOCK3])
    t.edges[EdgePosition.CLOCK9].link(u.edges[EdgePosition.CLOCK3])
    # and link them
    r.edges[EdgePosition.CLOCK9].link(s.edges[EdgePosition.CLOCK6])


def link_rim(p: Board, q: Board, r: Board, s: Board, t: Board, u: Board) -> None:
    p.edges[EdgePosition.CLOCK9].link(q.edges[EdgePosition.CLOCK9])
    q.edges[EdgePosition.CLOCK6].link(r.edges[EdgePosition.CLOCK6])
    r.edges[EdgePosition.CLOCK9].link(s.edges[EdgePosition.CLOCK3])
    s.edges[EdgePosition.CLOCK9].link(t.edges[EdgePosition.CLOCK3])
    t.edges[EdgePosition.CLOCK9].link(u.edges[EdgePosition.CLOCK3])


if __name__ == "__main__":
    p = Board("🌵P", Layout.E)
    q = Board("🌵Q", Layout.H)
    r = Board("🌵R", Layout.G)
    s = Board("🌵S", Layout.H)
    t = Board("🌵T", Layout.D)
    u = Board("🌵U", Layout.F)
    link_rim(p, q, r, s, t, u)

    for board in [p, q, r, s, t, u]:
        for i in range(1, 9):
            adjacencies = ", ".join(
                f"{parent.name}{number}{parent.layout.terrains[number].value}"
                for parent, number in board.adjacent(i)
            )
            print(
                f"Neighbors of {board.name}{i}{board.layout.terrains[i].value}: {adjacencies}"
            )
