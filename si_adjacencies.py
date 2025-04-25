class Edge:
    def __init__(self, lands: list[int], boundaries: list[int]):
        self.lands = tuple(lands[::-1])
        self.boundaries = (0,)+tuple(sorted(boundaries))+(7,)

    def __matmul__(self, neighbor):
        # sorry for abusing dunders
        self_pos = 1
        neighbor_pos = -2
        while True:
            try:
                self_next = self.boundaries[self_pos]
                neighbor_next = neighbor.boundaries[neighbor_pos]
            except IndexError:
                break
            yield (self.lands[self_pos-1], neighbor.lands[neighbor_pos+1])
            if self_next + neighbor_next > 6:
                neighbor_pos -= 1
            else:
                self_pos += 1


class Board:
    def __init__(self, lands, boundaries, adjacencies):
        '''
        Lands around the edge in clockwise order starting from 1.
        Boundaries in the same order, None for corners.
        '''
        c1, c2 = [i for i,x in enumerate(boundaries) if x is None]
        self.edges = [
            Edge(lands[:c1+1], boundaries[:c1]),
            Edge(lands[c1:c2], boundaries[c1+1:c2]),
            Edge(lands[c2-1:], boundaries[c2+1:]),
        ]
        self.adjacencies = {i+1: set() for i in range(8)}
        for i, val in enumerate(adjacencies.split(',')):
            for n in val:
                self.adjacencies[i+1].add(int(n))
                self.adjacencies[int(n)].add(i+1)

    def get_corner(self, corner):
        '''corner: str '1', '3', '6', '8' '''
        match corner:
            case '1' | '3':
                return int(corner)
            case '6':
                return self.edges[2].lands[-1]
            case '8':
                return self.edges[0].lands[-1]

    def __getitem__(self, ix):
        return self.edges[ix]


GAME_BOARDS = {
    'A': Board((1,6,8,7,5,4,3), (5,3,None,4,None,6,5,3),
               '2456,34,4,5,678,8,8'),
    'B': Board((1,6,8,7,4,3), (6,3,None,4,None,6,4),
               '2456,34,4,57,67,78,8'),
    'C': Board((1,6,8,7,4,3), (5,3,None,3,1,None,3),
               '256,345,4,57,67,78,8'),
    'D': Board((1,8,7,6,4,3), (1,None,4,1,None,5,2),
               '2578,345,4,56,67,7,8'),
    'E': Board((1,7,8,6,4,3), (4,2,None,2,None,6,3),
               '257,35,45,567,7,78,8'),
    'F': Board((1,6,8,7,4,3), (4,1,None,3,None,5,2),
               '256,345,4,578,68,8,8'),
    'G': Board((1,6,8,7,4,3), (4,2,None,3,None,6,4),
               '26,3456,4,57,678,8,8'),
    'H': Board((1,8,7,4,3), (3,None,5,1,None,3),
               '268,356,45,57,67,78,8'),
}


class Island:
    names = 'PQRSTU'

    possible_shapes = {
        # (edge-edge adjacencies, corner-corner adjacencies)
        # edge 1 is the one touching land 1, edge 3 touches land 3, edge 2 is inland
        # corners are labeled 1 3 6 and 8 by common land numbers that are that corner
        'hub': ('P2Q3,Q2R3,R2P3,T2U3,U2S3,S2T3,Q1S1'.split(','),
                'T3Q1,R3S1'.split(',')),
        'spokes': ('P3Q1,Q3R1,R3S2,S3T1,T3U1'.split(','),
                   'T8R6'.split(',')),
        'rim': ('P3Q3,Q2R2,R3S1,S3T1,T3U1'.split(','),
                'S8Q8,P3R8'.split(','))
    }

    def __init__(self, board_makeup, shape):
        '''
        board_makeup: string of the form 'AEBBFD', if board P is A, board Q is E, etc
        shape: hub, spokes, or rim
        '''
        self.boards = [GAME_BOARDS[x] for x in board_makeup]
        assert shape in ('hub', 'spokes', 'rim')
        self.shape = self.possible_shapes[shape]

    def all_adjacencies(self):
        for name, board in zip(self.names, self.boards):
            # internal adjacencies
            for land1 in board.adjacencies:
                for land2 in board.adjacencies[land1]:
                    if land1 < land2:
                        yield (f'{name}{land1}', f'{name}{land2}')

        for b1_name, e1, b2_name, e2 in self.shape[0]:
            # cross-board edge adjacencies
            b1 = self.boards[self.names.index(b1_name)]
            b2 = self.boards[self.names.index(b2_name)]
            e1, e2 = int(e1)-1, int(e2)-1
            for land1, land2 in b1.edges[e1] @ b2.edges[e2]:
                yield (f'{b1_name}{land1}', f'{b2_name}{land2}')

        for b1_name, c1, b2_name, c2 in self.shape[1]:
            # corner adjacencies
            b1 = self.boards[self.names.index(b1_name)]
            b2 = self.boards[self.names.index(b2_name)]
            yield (f'{b1_name}{b1.get_corner(c1)}', f'{b2_name}{b2.get_corner(c2)}')
            

    def check_adjacency(self, land1, land2):
        raise NotImplementedError


