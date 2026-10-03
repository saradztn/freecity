"""Street furniture placement and merged infrastructure geometry."""
from __future__ import annotations
import random
import math
from .mesh import Mesh
from .collision import CollisionMesh
from .road_graph import RoadGraph
from .props import add_hydrant, add_streetlamp, add_traffic_signal, add_road_sign, add_bus_shelter, add_mailbox, add_bench


def build_infrastructure(graph: RoadGraph, terrain, seed: int, *, lod: bool=False) -> tuple[Mesh, CollisionMesh, list[dict]]:
    mesh, coll = Mesh(), CollisionMesh()
    lights: list[dict] = []
    if lod:
        return mesh, coll, lights
    rng=random.Random(seed ^ 0x1199)
    types=("sodium","neutral_led","cool_led")
    # Lamps track road tangents and alternate offsets naturally on each side.
    for seg in graph.segments.values():
        if seg.kind in ("highway","ramp","roundabout","bridge","tunnel"):
            continue
        points=seg.sample_xy(graph,spacing=34.0)
        if len(points)<2:
            continue
        for i in range(1,len(points)-1):
            x,y,t=points[i]
            px,py=points[i-1][0],points[i-1][1]
            nx,ny=points[i+1][0],points[i+1][1]
            dx,dy=nx-px,ny-py
            length=math.hypot(dx,dy) or 1.0
            side=-1 if (i+len(seg.id))%2 else 1
            nx,ny=-dy/length,dx/length
            offset=seg.paved_width*.5+3.3
            lx,ly=x+nx*offset*side,y+ny*offset*side
            z=terrain.height(lx,ly)
            ltype=types[(i+len(seg.id))%len(types)]
            lights.append(add_streetlamp(mesh,coll,lx,ly,z,(dx/length,dy/length),ltype))

    # Traffic control is concentrated at actual multi-leg streets, not every node.
    for node_id,node in graph.nodes.items():
        roads=graph.adjacency(node_id)
        if len(roads)<3 or graph.intersection_type(node_id)=="roundabout":
            continue
        if any(r.kind in ("highway","ramp") for r in roads):
            continue
        z=terrain.height(node.x,node.y)
        for i,seg in enumerate(roads[:4]):
            outward=graph.endpoint_direction(seg,node_id)
            nx,ny=-outward[1],outward[0]
            side=1 if i%2 else -1
            x=node.x+outward[0]*7+nx*side*(seg.paved_width*.5+1.0)
            y=node.y+outward[1]*7+ny*side*(seg.paved_width*.5+1.0)
            add_traffic_signal(mesh,coll,x,y,terrain.height(x,y),(-outward[0],-outward[1]))
        # Stop/sign post on the minor approach of T-junctions.
        if graph.intersection_type(node_id)=="t_junction":
            seg=min(roads,key=lambda r:r.speed_kph)
            ox,oy=graph.endpoint_direction(seg,node_id)
            add_road_sign(mesh,coll,node.x+ox*5,node.y+oy*5,terrain.height(node.x+ox*5,node.y+oy*5))

    # Mailboxes, hydrants, drainage covers, bus stop and benches at district edges.
    for i,seg in enumerate(graph.segments.values()):
        if seg.kind not in ("residential","local","collector","boulevard"):
            continue
        samples=seg.sample_xy(graph,spacing=27.0)
        for j in range(1,len(samples)-1):
            x,y,t=samples[j]
            if (i+j)%3==0:
                px,py=samples[j-1][0],samples[j-1][1]
                nx,ny=samples[j+1][0],samples[j+1][1]
                d=math.hypot(nx-px,ny-py) or 1
                side=1 if (i+j)%2 else -1
                ox,oy=-(ny-py)/d,(nx-px)/d
                px,py=x+ox*side*(seg.paved_width*.5+2.7),y+oy*side*(seg.paved_width*.5+2.7)
                z=terrain.height(px,py)
                add_hydrant(mesh,coll,px,py,z)
                add_mailbox(mesh,px+ox*1.2,py+oy*1.2,z)
            if (i+j)%7==0:
                mesh.add_disk((x,y,terrain.height(x,y)+.025),.32,"metal",12)
                mesh.add_disk((x+.03,y+.03,terrain.height(x,y)+.04),.21,"painted_metal",12)
    # One bus shelter near the commercial boulevard; park benches at varied angles.
    add_bus_shelter(mesh,coll,-103,-82,terrain.height(-103,-82),angle=90)
    for x,y,angle in ((151,-14,10),(203,-16,90),(144,24,40),(210,23,-25)):
        add_bench(mesh,coll,x,y,terrain.height(x,y),angle)
    # Highway signage and guardrails are built in highways.py / bridges.py.
    return mesh,coll,lights
