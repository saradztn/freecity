"""Procedural island terrain, creek bed, terrain collision, and coast plane."""
from __future__ import annotations
import math
from .math3d import clamp, smoothstep
from .mesh import Mesh
from .collision import CollisionMesh
from .road_graph import RoadGraph
from .tunnels import tunnel_hole_at


class Terrain:
    def __init__(self, seed: int, graph: RoadGraph, *, step: float = 12.0, extent: float = 256.0):
        self.seed = seed
        self.graph = graph
        self.step = step
        self.extent = extent
        self._flat_pads: list[dict] = []
        self._road_samples: list[tuple[float, float, float, float, str]] = []
        for seg in graph.segments.values():
            if seg.alignment in ("fixed", "ramp", "bridge"):
                continue
            for x, y, t in seg.sample_xy(graph, spacing=8.0):
                self._road_samples.append((x, y, seg.road_width * .5, t, seg.id))

    def land_factor(self, x: float, y: float) -> float:
        # Organic, asymmetric island outline with broad bays rather than a
        # rectangular map boundary.
        angle = math.atan2(y, x)
        wobble = 0.025 * math.sin(angle * 5.0 + 0.7) + 0.018 * math.sin(angle * 9.0 - 1.1)
        # The 768 m tile footprint tapers to ocean before its outer tile
        # boundary while keeping all city blocks and local arterials on land.
        rx, ry = 330.0 * (1 + wobble), 315.0 * (1 - wobble * 0.45)
        d = math.sqrt((x / rx) ** 2 + (y / ry) ** 2)
        return 1.0 - smoothstep(0.91, 1.045, d)

    def inside_land(self, x: float, y: float) -> bool:
        return self.land_factor(x, y) > 0.015

    def raw_height(self, x: float, y: float) -> float:
        # Low coastal shelf, a western ridge and a shallow urban basin.
        ridge = 21.0 * math.exp(-(((x + 176.0) / 56.0) ** 2 + ((y + 47.0) / 58.0) ** 2))
        north_hill = 10.5 * math.exp(-(((x - 72.0) / 88.0) ** 2 + ((y - 174.0) / 62.0) ** 2))
        basin = -2.2 * math.exp(-((x / 130.0) ** 2 + (y / 125.0) ** 2))
        undulation = 1.2 * math.sin(x * 0.018 + self.seed * .001) * math.cos(y * 0.022)
        # A sinuous, shallow drainage channel through the southeast blocks.
        creek_y = -126.0 + 0.07 * (x - 130.0) + 5.0 * math.sin((x - 120.0) / 40.0)
        creek = 8.5 * math.exp(-((y - creek_y) / 15.0) ** 2) if 82.0 < x < 238.0 else 0.0
        inland = 3.0 + ridge + north_hill + basin + undulation - creek
        land = self.land_factor(x, y)
        # Interpolate to a rocky shelf at the shoreline; the water plane sits
        # below this so the island reads as a coastline, not a floating slab.
        return inland * land + (-3.0) * (1.0 - land)

    def add_flat_pad(self,x:float,y:float,width:float,depth:float,*,rotation:float=0.0,
                     elevation:float|None=None,blend_distance:float=4.0,name:str="pad") -> None:
        """Grade a buildable parcel flat and blend the cut/fill into nearby ground."""
        if width<=0 or depth<=0 or blend_distance<=0:
            raise ValueError("flat-pad dimensions and blend distance must be positive")
        self._flat_pads.append({"x":float(x),"y":float(y),"width":float(width),"depth":float(depth),
                                "rotation":math.radians(rotation),
                                "elevation":self.raw_height(x,y) if elevation is None else float(elevation),
                                "blend":float(blend_distance),"name":name})

    def _pad_influence(self,x:float,y:float)->tuple[float,float]|None:
        best=None
        for pad in self._flat_pads:
            dx,dy=x-pad["x"],y-pad["y"]
            c,s=math.cos(pad["rotation"]),math.sin(pad["rotation"])
            local_x=dx*c+dy*s
            local_y=-dx*s+dy*c
            outside=max(abs(local_x)-pad["width"]*.5,abs(local_y)-pad["depth"]*.5,0.0)
            weight=1.0-smoothstep(0.0,pad["blend"],outside)
            if best is None or weight>best[0]:
                best=(weight,pad["elevation"])
        return best

    def _inside_flat_pad(self,x:float,y:float)->bool:
        for pad in self._flat_pads:
            dx,dy=x-pad["x"],y-pad["y"]
            c,s=math.cos(pad["rotation"]),math.sin(pad["rotation"])
            if abs(dx*c+dy*s)<=pad["width"]*.5 and abs(-dx*s+dy*c)<=pad["depth"]*.5:
                return True
        return False

    def height(self, x: float, y: float, *, flatten_roads: bool = True) -> float:
        h = self.raw_height(x, y)
        if flatten_roads:
            closest_d = float("inf")
            target_z = h
            target_width = 0.0
            for rx, ry, half, t, seg_id in self._road_samples:
                d = math.hypot(x - rx, y - ry)
                if d < closest_d:
                    seg = self.graph.segments[seg_id]
                    if seg.alignment in ("fixed", "ramp", "bridge"):
                        continue
                    closest_d, target_z, target_width = d, self.raw_height(rx, ry) - 0.12, half
            if closest_d < target_width + 6.5:
                blend = 1.0 - smoothstep(target_width, target_width + 6.5, closest_d)
                h = h * (1.0 - blend) + target_z * blend
        influence=self._pad_influence(x,y)
        if influence:
            weight,elevation=influence
            h=h*(1.0-weight)+elevation*weight
        return h

    def mesh(self, *, lod: bool = False) -> tuple[Mesh, CollisionMesh]:
        visual, coll = Mesh(), CollisionMesh()
        step = 28.0 if lod else self.step
        x0, x1 = -self.extent, self.extent
        y0, y1 = -self.extent, self.extent
        xs = [x0 + i * step for i in range(int((x1 - x0) / step) + 1)]
        ys = [y0 + i * step for i in range(int((y1 - y0) / step) + 1)]
        if xs[-1] < x1:xs.append(x1)
        if ys[-1] < y1:ys.append(y1)
        # Keep the regular terrain grid inexpensive; height samples still use
        # the parcel grading field, while build-pad collision is supplied by
        # the building or parking footprint itself.
        for iy in range(len(ys) - 1):
            for ix in range(len(xs) - 1):
                x_a, x_b = xs[ix], xs[ix + 1]
                y_a, y_b = ys[iy], ys[iy + 1]
                cx, cy = (x_a + x_b) * .5, (y_a + y_b) * .5
                if not self.inside_land(cx, cy):
                    continue
                if any(tunnel_hole_at(seg, self.graph, cx, cy) for seg in self.graph.segments.values() if seg.kind == "tunnel"):
                    continue
                points = ((x_a, y_a, self.height(x_a, y_a)), (x_b, y_a, self.height(x_b, y_a)),
                          (x_b, y_b, self.height(x_b, y_b)), (x_a, y_b, self.height(x_a, y_b)))
                # Mottle turf with a restrained soil/dry-grass color variation.
                mat = "grass" if (int((cx + 400) // 24) + int((cy + 400) // 24)) % 9 else "soil"
                u0, u1, v0, v1 = x_a / 9.0, x_b / 9.0, y_a / 9.0, y_b / 9.0
                color = (231, 235, 227, 255) if mat == "grass" else (245, 239, 226, 255)
                visual.add_quad(points, mat, ((u0, v0), (u1, v0), (u1, v1), (u0, v1)), color=color)
                surface = 2 if mat == "grass" else 3
                if not self._inside_flat_pad(cx,cy):
                    coll.add_quad(*points, surface=surface)
        # Quiet water sheet below the land, tessellated into small patches so
        # each streamed DFF tile stays inside its own local bounds.
        water_z = -2.2
        water_step = 64.0
        for wx0 in range(-448,448,64):
            for wy0 in range(-448,448,64):
                wx1,wy1=wx0+water_step,wy0+water_step
                visual.add_quad(((wx0,wy0,water_z),(wx1,wy0,water_z),(wx1,wy1,water_z),(wx0,wy1,water_z)),
                                "water",((wx0/8,wy0/8),(wx1/8,wy0/8),(wx1/8,wy1/8),(wx0/8,wy1/8)))
        # Creek surface follows its centerline and is clipped to the east bank.
        for x in range(86, 239, 12):
            x2 = min(239, x + 12)
            def creek_y(px: float) -> float:
                return -126.0 + 0.07 * (px - 130.0) + 5.0 * math.sin((px - 120.0) / 40.0)
            y_a, y_b = creek_y(x), creek_y(x2)
            left = ((x, y_a - 8, 0.8), (x2, y_b - 8, 0.8), (x2, y_b + 8, 0.8), (x, y_a + 8, 0.8))
            visual.add_quad(left, "water", ((x/8, 0), (x2/8, 0), (x2/8, 1), (x/8, 1)))
        return visual, coll
