"""Compute BFS layers / layout for the intro page animation (docs/intro/data/bfs_data.json).

Needs DuckDB and the locally rebuilt MaleCNS edges.parquet (see README). Run, then rebuild the page:
    python scripts/build_intro_bfs_data.py
    python scripts/build_intro_html.py
"""
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import duckdb  # noqa: E402
from flycall_data.streaming_bfs import _hash_priority  # noqa: E402

SUB = ROOT / "data/connectome/derived/malecns_v1.0/subgraphs"
SIGNS = ROOT / "data/connectome/derived/malecns_v1.0/neuron_signs_v1.0.parquet"
EDGES_ALL = ROOT / "data/connectome/derived/malecns_v1.0/edges.parquet"


def layout(node_ids, edges, seed, rng):
    adj = defaultdict(set)
    for s, t, *_ in edges:
        adj[s].add(t)
        adj[t].add(s)
    layer = {seed: 0}
    parent = {seed: None}
    frontier = [seed]
    while frontier:
        nxt = []
        for u in sorted(frontier, key=_hash_priority):
            for v in sorted(adj[u], key=_hash_priority):
                if v not in layer:
                    layer[v] = layer[u] + 1
                    parent[v] = u
                    nxt.append(v)
        frontier = nxt
    assert len(layer) == len(node_ids), (len(layer), len(node_ids))
    order = sorted(node_ids, key=lambda n: (layer[n], _hash_priority(n)))
    angle = {seed: 0.0}
    maxl = max(layer.values())
    for L in range(1, maxl + 1):
        members = [n for n in order if layer[n] == L]
        members.sort(key=lambda n: (angle[parent[n]], _hash_priority(n)))
        k = len(members)
        offset = rng.random() * 0.2
        for i, n in enumerate(members):
            angle[n] = (2 * math.pi * (i + 0.5) / k + offset) % (2 * math.pi)
    radius = {}
    for n in node_ids:
        L = layer[n]
        radius[n] = 0.0 if L == 0 else (0.26 + 0.07 * rng.random()) if L == 1 else (0.55 + 0.4 * rng.random())
    return order, layer, parent, angle, radius


def pack(name, node_ids, edges, seed, signs=None, glu=None, inputs=(), outputs=(), ghosts=None):
    rng = random.Random(20261114)
    order, layer, parent, angle, radius = layout(node_ids, edges, seed, rng)
    idx = {n: i for i, n in enumerate(order)}
    nodes = []
    for n in order:
        x = 0.5 + 0.47 * radius[n] * math.cos(angle[n])
        y = 0.5 + 0.47 * radius[n] * math.sin(angle[n])
        nodes.append([round(x, 4), round(y, 4), layer[n], -1 if parent[n] is None else idx[parent[n]],
                      0 if signs is None else signs[n], 1 if glu and n in glu else 0,
                      1 if n in inputs else (2 if n in outputs else 0)])
    e = [[idx[s], idx[t]] for s, t, *_ in edges]
    layers = defaultdict(int)
    for n in order:
        layers[layer[n]] += 1
    return {"name": name, "seed": seed, "nodes": nodes, "edges": e, "layer_counts": dict(layers), "ghosts": ghosts or {}}


con = duckdb.connect()
# G0
g0e = con.execute(f"select source_id, target_id from '{SUB / 'engineering-demo-v1.0/edges.parquet'}'").fetchall()
g0n = [r[0] for r in con.execute(f"select node_id from '{SUB / 'engineering-demo-v1.0/nodes.parquet'}'").fetchall()]
g0m = json.loads((SUB / "engineering-demo-v1.0/manifest.json").read_text(encoding="utf-8"))
io = json.loads((ROOT / ".scratch/1999-connectome-demo/m1-3/engineering-demo-io-v1.0-20261016/io_manifest.json").read_text(encoding="utf-8"))
seed0 = 274013289
print("G0 io keys", [k for k in io if "node" in k][:6])
inp0 = set(io["io_selection"]["input_node_ids"])
out0 = set(io["io_selection"]["output_node_ids"])
G0 = pack("G0", g0n, g0e, seed0, inputs=inp0, outputs=out0)

# signed
g2 = json.loads((SUB / "signed-quota-v1.0/graph_definition_G2_glu_inhibitory.json").read_text())
g2p = json.loads((SUB / "signed-quota-v1.0/graph_definition_G2_glu_excitatory.json").read_text())
s_inh = {int(a): int(b) for a, b in g2["node_signs"]}
s_exc = {int(a): int(b) for a, b in g2p["node_signs"]}
glu = {n for n in g2["node_ids"] if s_inh[n] != s_exc[n]}
# layer-1 candidates of the signed seed in the FULL graph (to show skipped unsigned neighbours)
nb = con.execute(f"""select distinct n from (
  select target_id as n from '{EDGES_ALL}' where source_id = 810979
  union select source_id as n from '{EDGES_ALL}' where target_id = 810979) where n <> 810979""").fetchall()
nb = {r[0] for r in nb}
cols = [c[0] for c in con.execute(f"describe select * from '{SIGNS}'").fetchall()]
print("sign cols", cols)
idcol = "body"
signed = {r[0] for r in con.execute(f"select {idcol} from '{SIGNS}' where sign_glu_inhibitory in (1,-1)").fetchall()}
ghost1 = len([n for n in nb if n not in signed])
S = pack("SIGNED", g2["node_ids"], [tuple(e) for e in g2["edges"]], 810979, signs=s_inh, glu=glu,
         inputs=set(g2["input_node_ids"]), outputs=set(g2["output_node_ids"]), ghosts={"1": ghost1, "2": 6325})
print("G0 layers", G0["layer_counts"], "| signed layers", S["layer_counts"], "glu", len(glu), "layer1 neighbours", len(nb), "unsigned", ghost1)
print("G0 io", len(inp0), len(out0))
out = {"G0": G0, "SIGNED": S}
dst = ROOT / "docs/intro/data/bfs_data.json"
dst.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
print("bytes", dst.stat().st_size)
