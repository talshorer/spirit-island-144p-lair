from adjacency import gen_144p
import json5

map = gen_144p.Map144P(with_archipelago=False)
map.weave_from_file("config/turn6/weaves.json5")
adj = {
    land.key: list(land.links.keys())
    for board in map.boards.values()
    for land in board.lands.values()
}
with open("butwhytho.json5", "w") as f:
    json5.dumps(adj, f, indent=2, sort_keys=True, ensure_ascii=False)