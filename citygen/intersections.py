"""Intersection surfacing, roundabout islands and pedestrian crossings."""
from __future__ import annotations
import math
from .mesh import Mesh
from .collision import CollisionMesh
from .road_graph import RoadGraph


def _collision_disk(collision: CollisionMesh, x: float, y: float, z: float, radius: float, sides: int=20) -> None:
    center=(x,y,z)
    for i in range(sides):
        a0=2*math.pi*i/sides
        a1=2*math.pi*(i+1)/sides
        p1=(x+radius*math.cos(a0),y+radius*math.sin(a0),z)
        p2=(x+radius*math.cos(a1),y+radius*math.sin(a1),z)
        collision.add_triangle(center,p1,p2,surface=5)


def add_intersections(mesh: Mesh, collision: CollisionMesh, graph: RoadGraph, ground_height) -> list[dict]:
    metadata=[]
    roundabout_done=False
    for node_id,node in graph.nodes.items():
        connected=graph.adjacency(node_id)
        degree=len(connected)
        kind=graph.intersection_type(node_id)
        if node.roundabout:
            if not roundabout_done:
                ring=[n for n in graph.nodes.values() if n.roundabout]
                cx=sum(n.x for n in ring)/len(ring)
                cy=sum(n.y for n in ring)/len(ring)
                z=ground_height(cx,cy)+.24
                radius=11.2
                mesh.add_disk((cx,cy,z),radius,"grass",24,color=(103,119,91,255))
                _collision_disk(collision,cx,cy,z,radius,24)
                # A short low curb gives the center island a legible edge.
                for i in range(24):
                    a0=2*math.pi*i/24;a1=2*math.pi*(i+1)/24
                    p0=(cx+radius*math.cos(a0),cy+radius*math.sin(a0),z-.08)
                    p1=(cx+radius*math.cos(a1),cy+radius*math.sin(a1),z-.08)
                    mesh.add_quad((p0,p1,(p1[0],p1[1],z+.12),(p0[0],p0[1],z+.12)),"concrete")
                    collision.add_quad(p0,p1,(p1[0],p1[1],z+.12),(p0[0],p0[1],z+.12),surface=5)
                roundabout_done=True
            continue
        if degree<2:
            continue
        radius=max((seg.paved_width*.5 for seg in connected),default=4.0)+2.4
        z=ground_height(node.x,node.y)+.20
        mesh.add_disk((node.x,node.y,z),radius,"asphalt",20)
        _collision_disk(collision,node.x,node.y,z,radius,20)
        metadata.append({"node":node_id,"type":kind,"x":round(node.x,3),"y":round(node.y,3),
                         "radius":round(radius,2),"degree":degree})
        if degree<3 or any(seg.kind in ("highway","ramp","bridge","tunnel") for seg in connected):
            continue
        # Four restrained off-white bars on each urban approach.
        for seg in connected:
            outward=graph.endpoint_direction(seg,node_id)
            nx,ny=-outward[1],outward[0]
            road_half=seg.road_width*.5-.2
            if road_half<2.5:
                continue
            base_distance=radius+1.2
            for bar in range(4):
                center_distance=base_distance+.95*bar
                cx=node.x+outward[0]*center_distance
                cy=node.y+outward[1]*center_distance
                p0=(cx-nx*road_half,cy-ny*road_half,z+.028)
                p1=(cx+nx*road_half,cy+ny*road_half,z+.028)
                p2=(p1[0]+outward[0]*.42,p1[1]+outward[1]*.42,z+.028)
                p3=(p0[0]+outward[0]*.42,p0[1]+outward[1]*.42,z+.028)
                mesh.add_quad((p0,p1,p2,p3),"road_marking",color=(208,207,198,255))
    return metadata
