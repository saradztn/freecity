"""Directed, elevation-aware road graph and deterministic vertical-slice layout."""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Any
from .math3d import Vec2, bezier2, distance2, point_segment_distance_2d


@dataclass
class RoadNode:
    id: str
    x: float
    y: float
    kind: str = "junction"
    boundary: bool = False
    roundabout: bool = False
    elevation: float | None = None
    connections: list[str] = field(default_factory=list)


@dataclass
class RoadSegment:
    id: str
    start: str
    end: str
    kind: str = "local"
    lanes: int = 2  # total lanes; on two-way roads this is split around a centreline
    direction: str = "both"  # both | forward | reverse
    speed_kph: int = 35
    shoulder: float = 0.5
    median: float = 0.0
    controls: tuple[Vec2, Vec2] | None = None
    alignment: str = "terrain"  # terrain | fixed | ramp | bridge
    fixed_z: float | None = None
    bridge_clearance: float = 0.0
    name: str = ""
    allow_uturn: bool = False
    tags: dict[str, Any] = field(default_factory=dict)

    @property
    def lane_width(self) -> float:
        return 3.5 if self.kind not in ("residential", "ramp") else 3.25

    @property
    def paved_width(self) -> float:
        return max(4.0, self.lanes * self.lane_width + self.median + self.shoulder * 2.0)

    @property
    def road_width(self) -> float:
        return max(3.5, self.lanes * self.lane_width + self.median)

    def xy(self, graph: "RoadGraph", t: float) -> Vec2:
        a, b = graph.nodes[self.start], graph.nodes[self.end]
        p0, p3 = (a.x, a.y), (b.x, b.y)
        if self.controls:
            return bezier2(p0, self.controls[0], self.controls[1], p3, t)
        return (p0[0] + (p3[0] - p0[0]) * t, p0[1] + (p3[1] - p0[1]) * t)

    def approximate_length(self, graph: "RoadGraph", steps: int = 16) -> float:
        points = [self.xy(graph, i / steps) for i in range(steps + 1)]
        return sum(distance2(points[i], points[i + 1]) for i in range(steps))

    def sample_xy(self, graph: "RoadGraph", spacing: float = 8.0) -> list[tuple[float, float, float]]:
        count = max(2, int(math.ceil(self.approximate_length(graph) / spacing)))
        return [(self.xy(graph, i / count)[0], self.xy(graph, i / count)[1], i / count) for i in range(count + 1)]


class RoadGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, RoadNode] = {}
        self.segments: dict[str, RoadSegment] = {}
        self._next_node = 0
        self._next_segment = 0

    def add_node(self, x: float, y: float, *, kind: str = "junction", boundary: bool = False,
                 roundabout: bool = False, elevation: float | None = None, node_id: str | None = None) -> str:
        node_id = node_id or f"n{self._next_node:03d}"
        self._next_node += 1
        if node_id in self.nodes:
            raise ValueError(f"duplicate road node: {node_id}")
        self.nodes[node_id] = RoadNode(node_id, float(x), float(y), kind, boundary, roundabout, elevation)
        return node_id

    def add_segment(self, start: str, end: str, *, segment_id: str | None = None, kind: str = "local",
                    lanes: int = 2, direction: str = "both", speed_kph: int = 35,
                    shoulder: float | None = None, median: float = 0.0,
                    controls: tuple[Vec2, Vec2] | None = None, alignment: str = "terrain",
                    fixed_z: float | None = None, bridge_clearance: float = 0.0,
                    name: str = "", allow_uturn: bool = False, tags: dict[str, Any] | None = None) -> str:
        if start not in self.nodes or end not in self.nodes or start == end:
            raise ValueError(f"invalid road edge {start}->{end}")
        segment_id = segment_id or f"r{self._next_segment:03d}"
        self._next_segment += 1
        if segment_id in self.segments:
            raise ValueError(f"duplicate road segment: {segment_id}")
        if direction not in ("both", "forward", "reverse"):
            raise ValueError(f"invalid direction {direction}")
        if lanes < 1 or lanes > 8:
            raise ValueError(f"invalid lane count {lanes}")
        if shoulder is None:
            shoulder = 1.4 if kind == "highway" else (0.15 if kind == "ramp" else 0.55)
        road = RoadSegment(segment_id, start, end, kind, lanes, direction, speed_kph,
                           float(shoulder), float(median), controls, alignment, fixed_z,
                           bridge_clearance, name, allow_uturn, tags or {})
        self.segments[segment_id] = road
        self.nodes[start].connections.append(segment_id)
        self.nodes[end].connections.append(segment_id)
        return segment_id

    def adjacency(self, node_id: str) -> list[RoadSegment]:
        return [self.segments[sid] for sid in self.nodes[node_id].connections]

    def endpoint_direction(self, seg: RoadSegment, node_id: str) -> tuple[float, float]:
        """Unit direction pointing away from a junction along a segment."""
        if node_id == seg.start:
            a, b = seg.xy(self, 0.0), seg.xy(self, 0.035)
            dx, dy = b[0] - a[0], b[1] - a[1]
        else:
            a, b = seg.xy(self, 1.0), seg.xy(self, 0.965)
            dx, dy = a[0] - b[0], a[1] - b[1]
        n = math.hypot(dx, dy) or 1.0
        return dx / n, dy / n

    def edge_allows(self, seg: RoadSegment, from_node: str, to_node: str) -> bool:
        if seg.direction == "both":
            return True
        return (seg.direction == "forward" and from_node == seg.start and to_node == seg.end) or \
               (seg.direction == "reverse" and from_node == seg.end and to_node == seg.start)

    def road_distance(self, x: float, y: float, *, exclude: set[str] | None = None) -> tuple[float, RoadSegment | None, float]:
        best = (float("inf"), None, 0.0)
        exclude = exclude or set()
        p = (x, y)
        for seg in self.segments.values():
            if seg.id in exclude:
                continue
            samples = seg.sample_xy(self, spacing=8.0)
            for i in range(len(samples) - 1):
                d, local_t = point_segment_distance_2d(p, samples[i][:2], samples[i + 1][:2])
                if d < best[0]:
                    global_t = samples[i][2] + (samples[i + 1][2] - samples[i][2]) * local_t
                    best = (d, seg, global_t)
        return best

    def intersection_type(self, node_id: str) -> str:
        node = self.nodes[node_id]
        degree = len(node.connections)
        if node.roundabout:
            return "roundabout"
        if degree <= 1:
            return "boundary" if node.boundary else "culdesac"
        if degree == 2:
            return "merge" if any(self.segments[s].kind in ("ramp", "highway") for s in node.connections) else "continuation"
        if degree == 3:
            return "t_junction"
        return "four_way" if degree == 4 else "multi_way"

    def directed_turns(self) -> list[dict[str, str]]:
        turns: list[dict[str, str]] = []
        for node_id, node in self.nodes.items():
            incoming: list[tuple[RoadSegment, str]] = []
            outgoing: list[tuple[RoadSegment, str]] = []
            for seg in self.adjacency(node_id):
                other = seg.end if seg.start == node_id else seg.start
                if self.edge_allows(seg, other, node_id):
                    incoming.append((seg, other))
                if self.edge_allows(seg, node_id, other):
                    outgoing.append((seg, other))
            for in_seg, previous in incoming:
                in_dir = self.endpoint_direction(in_seg, node_id)
                for out_seg, nxt in outgoing:
                    if out_seg.id == in_seg.id and not in_seg.allow_uturn:
                        continue
                    out_dir = self.endpoint_direction(out_seg, node_id)
                    cross_z = in_dir[0] * out_dir[1] - in_dir[1] * out_dir[0]
                    dot = in_dir[0] * out_dir[0] + in_dir[1] * out_dir[1]
                    turn = "straight" if dot < -0.65 else ("left" if cross_z > 0 else "right")
                    turns.append({"node": node_id, "from": in_seg.id, "to": out_seg.id, "turn": turn})
        return turns

    def connected_components(self) -> list[list[str]]:
        unseen = set(self.nodes)
        components: list[list[str]] = []
        while unseen:
            root = min(unseen)
            stack = [root]
            unseen.remove(root)
            group = []
            while stack:
                current = stack.pop()
                group.append(current)
                for seg in self.adjacency(current):
                    nxt = seg.end if seg.start == current else seg.start
                    if nxt in unseen:
                        unseen.remove(nxt)
                        stack.append(nxt)
            components.append(group)
        return components

    def to_dict(self) -> dict[str, object]:
        nodes = []
        for n in self.nodes.values():
            nodes.append({"id": n.id, "x": round(n.x, 3), "y": round(n.y, 3), "kind": n.kind,
                          "boundary": n.boundary, "roundabout": n.roundabout,
                          "intersection": self.intersection_type(n.id),
                          "connections": list(n.connections)})
        roads = []
        for s in self.segments.values():
            a, b = self.nodes[s.start], self.nodes[s.end]
            lane_dirs = []
            for lane_index in range(s.lanes):
                if s.direction == "both" and s.lanes > 1:
                    lane_dirs.append("forward" if lane_index < s.lanes // 2 else "reverse")
                else:
                    lane_dirs.append("forward" if s.direction != "reverse" else "reverse")
            roads.append({"id": s.id, "from": s.start, "to": s.end, "kind": s.kind,
                          "name": s.name, "lanes": s.lanes, "lane_width": s.lane_width,
                          "road_width": round(s.road_width, 2), "paved_width": round(s.paved_width, 2),
                          "lane_directions": lane_dirs, "direction": s.direction,
                          "speed_kph": s.speed_kph, "alignment": s.alignment,
                          "fixed_z": s.fixed_z, "bridge_clearance": s.bridge_clearance,
                          "start_xy": [a.x, a.y], "end_xy": [b.x, b.y],
                          "controls": [list(p) for p in s.controls] if s.controls else None,
                          "length": round(s.approximate_length(self), 2), "tags": s.tags})
        return {"schema": 1, "nodes": nodes, "segments": roads, "turns": self.directed_turns()}


def build_vertical_slice_graph() -> RoadGraph:
    """A connected, mildly irregular road network for the Northpoint slice."""
    g=RoadGraph()
    n:dict[str,str]={}
    xs=(-220.0,-200.0,-170.0,-110.0,10.0,130.0,230.0)
    rows={
        "south":    [-180.0,-180.0,-180.0,-180.0,-180.0,-180.0,-180.0],
        "arterial": [-75.0,-70.0,-62.0,-55.0,-45.0,-38.0,-28.0],
        "mid":      [40.0,44.0,48.0,54.0,58.0,50.0,38.0],
        "north":    [150.0,148.0,145.0,142.0,150.0,165.0,180.0],
    }
    for row_name,ys in rows.items():
        for i,(x,y) in enumerate(zip(xs,ys)):
            boundary=i in (0,len(xs)-1)
            nid=g.add_node(x,y,boundary=boundary,kind="boundary" if boundary else "junction")
            n[f"{row_name}_{i}"]=nid

    # The low southern grid is a local two-way street with two short one-way
    # links, keeping the traffic data meaningful without making a rigid grid.
    for i in range(len(xs)-1):
        a=(xs[i],rows["south"][i]);b=(xs[i+1],rows["south"][i+1])
        g.add_segment(n[f"south_{i}"],n[f"south_{i+1}"],kind="residential",lanes=2,
                      direction="forward" if i==1 else ("reverse" if i==4 else "both"),
                      speed_kph=30,controls=((a[0]+(b[0]-a[0])*.33,a[1]+1.4),
                                             (a[0]+(b[0]-a[0])*.68,b[1]-.8)),
                      name="Mariner Street")

    # A four-lane, curved arterial. Its western ridge crossing is cut down to
    # a short ramp/tunnel/ramp sequence with a terrain aperture.
    for i in range(len(xs)-1):
        a=(xs[i],rows["arterial"][i]);b=(xs[i+1],rows["arterial"][i+1])
        if i==1:
            entry=g.add_node(-192.0,-68.0,kind="tunnel_portal")
            exit=g.add_node(-178.0,-64.0,kind="tunnel_portal")
            approach_tags={"tunnel":True,"tunnel_approach":True,"cut_depth":4.5}
            g.add_segment(n["arterial_1"],entry,kind="tunnel",lanes=2,speed_kph=25,
                          alignment="ramp",name="West Ridge Tunnel Entrance",tags=approach_tags)
            g.add_segment(entry,exit,kind="tunnel",lanes=2,speed_kph=30,
                          name="West Ridge Tunnel",tags={"tunnel":True,"cut_depth":4.5})
            g.add_segment(exit,n["arterial_2"],kind="tunnel",lanes=2,speed_kph=25,
                          alignment="ramp",name="West Ridge Tunnel Exit",tags=approach_tags)
            continue
        controls=((a[0]+(b[0]-a[0])*.34,(a[1]+b[1])*.5-1.6),
                  (a[0]+(b[0]-a[0])*.68,(a[1]+b[1])*.5+1.1))
        g.add_segment(n[f"arterial_{i}"],n[f"arterial_{i+1}"],kind="boulevard",lanes=4,
                      direction="reverse" if i==4 else "both",speed_kph=50,median=1.0,
                      controls=controls,name="Harbor Boulevard")

    # The elevated mid-town collector bends around the civic/park blocks.
    for i in range(len(xs)-1):
        a=(xs[i],rows["mid"][i]);b=(xs[i+1],rows["mid"][i+1])
        controls=((a[0]+(b[0]-a[0])*.32,(a[1]+b[1])*.5+1.7),
                  (a[0]+(b[0]-a[0])*.70,(a[1]+b[1])*.5-1.1))
        g.add_segment(n[f"mid_{i}"],n[f"mid_{i+1}"],kind="local",lanes=2,
                      direction="forward" if i==4 else "both",speed_kph=35,
                      controls=controls,name="Cedar Avenue")

    # North ridge service street: staggered, but all nodes remain attached to
    # the road graph and terminate at explicit map-edge connectors.
    for i in range(len(xs)-1):
        a=(xs[i],rows["north"][i]);b=(xs[i+1],rows["north"][i+1])
        controls=((a[0]+(b[0]-a[0])*.31,(a[1]+b[1])*.5+1.4),
                  (a[0]+(b[0]-a[0])*.69,(a[1]+b[1])*.5-1.0))
        g.add_segment(n[f"north_{i}"],n[f"north_{i+1}"],kind="local",lanes=2,
                      speed_kph=35,controls=controls,name="Foundry Road")

    # North-south local links use the same x columns in every row; this avoids
    # unintended diagonals through building parcels.
    for col in range(len(xs)):
        if col==5:
            # Creek crossing: two level approaches and one raised deck.
            south=n["south_5"];arterial=n["arterial_5"]
            b1=g.add_node(130,-145,kind="bridge_approach")
            b2=g.add_node(130,-105,kind="bridge_approach")
            g.add_segment(south,b1,kind="collector",lanes=2,speed_kph=40,name="River Road")
            g.add_segment(b1,b2,kind="bridge",lanes=2,speed_kph=35,
                          alignment="bridge",bridge_clearance=5.0,name="Northpoint Bridge",
                          tags={"bridge":True,"deck_min_z":0.8})
            g.add_segment(b2,arterial,kind="collector",lanes=2,speed_kph=40,name="River Road")
        else:
            g.add_segment(n[f"south_{col}"],n[f"arterial_{col}"],
                          kind="collector" if col in (3,4) else "local",lanes=2,
                          direction="reverse" if col==2 else "both",
                          speed_kph=40 if col in (3,4) else 30,
                          controls=((xs[col]-1.0,rows["south"][col]+(rows["arterial"][col]-rows["south"][col])*.34),
                                    (xs[col]+1.0,rows["south"][col]+(rows["arterial"][col]-rows["south"][col])*.68)),
                          name="River Street" if col==4 else "Local Street")

        g.add_segment(n[f"arterial_{col}"],n[f"mid_{col}"],
                      kind="collector" if col in (3,4,5) else "local",lanes=2,
                      speed_kph=40 if col in (3,4,5) else 30,
                      controls=((xs[col]+(2.0 if col%2 else -1.0),rows["arterial"][col]+(rows["mid"][col]-rows["arterial"][col])*.34),
                                (xs[col]-(1.0 if col%2 else -2.0),rows["arterial"][col]+(rows["mid"][col]-rows["arterial"][col])*.68)),
                      name="Pioneer Avenue" if col==4 else "Local Street")

    # The two eastern mid/north approaches feed the circle rather than crossing
    # its center; the remaining north-south links close the western grid.
    for col in range(5):
        g.add_segment(n[f"mid_{col}"],n[f"north_{col}"],kind="local",lanes=2,
                      speed_kph=35,
                      controls=((xs[col]-1.0,rows["mid"][col]+(rows["north"][col]-rows["mid"][col])*.34),
                                (xs[col]+1.0,rows["mid"][col]+(rows["north"][col]-rows["mid"][col])*.68)),
                      name="Local Street")

    # Compact US-style (counter-clockwise) roundabout with four real graph arms.
    cx,cy,radius=180.0,90.0,14.0
    ring=[]
    for i in range(8):
        angle=2*math.pi*i/8
        ring.append(g.add_node(cx+radius*math.cos(angle),cy+radius*math.sin(angle),
                               kind="roundabout",roundabout=True))
    for i in range(8):
        j=(i+1)%8
        p0=(cx+radius*math.cos(2*math.pi*i/8),cy+radius*math.sin(2*math.pi*i/8))
        p1=(cx+radius*math.cos(2*math.pi*j/8),cy+radius*math.sin(2*math.pi*j/8))
        c1=(p0[0]*.72+cx*.28,p0[1]*.72+cy*.28)
        c2=(p1[0]*.72+cx*.28,p1[1]*.72+cy*.28)
        g.add_segment(ring[i],ring[j],kind="roundabout",lanes=1,direction="forward",
                      speed_kph=20,shoulder=.1,controls=(c1,c2),name="Northpoint Circle")
    arms=(
        (n["mid_5"],ring[2],((151,51),(155,73)),"East Park Drive"),
        (n["north_5"],ring[0],((151,159),(163,128)),"East Park Drive"),
        (n["north_6"],ring[7],((223,150),(205,121)),"Foundry Road"),
        (n["mid_6"],ring[4],((229,39),(207,65)),"East Park Drive"),
    )
    for start,end,controls,name in arms:
        g.add_segment(start,end,kind="local",lanes=2,speed_kph=30,controls=controls,name=name)

    # Grade-separated I-14 comprises three connected freeway sections and two
    # one-way ramps, with explicit design elevation and merge-node metadata.
    h0=g.add_node(-245,210,kind="highway_boundary",boundary=True,elevation=18)
    h1=g.add_node(-70,210,kind="merge",elevation=18)
    h2=g.add_node(70,210,kind="merge",elevation=18)
    h3=g.add_node(245,210,kind="highway_boundary",boundary=True,elevation=18)
    highway_nodes=(h0,h1,h2,h3)
    highway_controls=(((-195,214),(-128,215)),((-34,216),(34,207)),((128,204),(196,210)))
    for i,(start,end) in enumerate(zip(highway_nodes,highway_nodes[1:])):
        g.add_segment(start,end,kind="highway",lanes=6,direction="both",speed_kph=100,
                      shoulder=2.0,median=3.0,alignment="fixed",fixed_z=18.0,
                      controls=highway_controls[i],name="I-14 Northpoint Freeway",
                      tags={"elevated":True,"highway":True,"segment":i})
    g.add_segment(h1,n["north_3"],kind="ramp",lanes=1,direction="forward",speed_kph=35,
                  alignment="ramp",fixed_z=18.0,controls=((-74,197),(-96,174)),
                  name="Freeway Exit 3A",tags={"ramp":"exit","highway":True})
    g.add_segment(n["north_5"],h2,kind="ramp",lanes=1,direction="forward",speed_kph=35,
                  alignment="ramp",fixed_z=18.0,controls=((121,176),(96,194)),
                  name="Freeway Entrance 3B",tags={"ramp":"entrance","highway":True})
    return g
