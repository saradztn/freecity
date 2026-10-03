"""Freeway deck, barriers, supports, and interchange signage."""
from __future__ import annotations
import math
from .mesh import Mesh
from .collision import CollisionMesh
from .road_graph import RoadGraph


def add_highway_details(mesh:Mesh,graph:RoadGraph,ground_height,collision:CollisionMesh|None=None)->list[dict]:
    signs=[]
    for seg in graph.segments.values():
        if seg.kind!="highway":
            continue
        samples=seg.sample_xy(graph,spacing=18.0)
        half=seg.paved_width*.5+.7
        deck=float(seg.fixed_z or 18.0)
        for i in range(len(samples)-1):
            x0,y0,t0=samples[i];x1,y1,t1=samples[i+1]
            dx,dy=x1-x0,y1-y0
            length=math.hypot(dx,dy) or 1.0
            nx,ny=-dy/length,dx/length
            for side in (-1,1):
                a=(x0+nx*half*side,y0+ny*half*side,deck+.25)
                b=(x1+nx*half*side,y1+ny*half*side,deck+.25)
                top_a=(a[0],a[1],a[2]+.85);top_b=(b[0],b[1],b[2]+.85)
                mesh.add_quad((a,b,top_b,top_a),"metal",((t0*8,0),(t1*8,0),(t1*8,1),(t0*8,1)))
                if collision:
                    collision.add_quad(a,b,top_b,top_a,surface=6)
                if i%2==0:
                    post_center=(a[0],a[1],deck+.67);post_size=(.16,.16,.84)
                    mesh.add_box(post_center,post_size,"painted_metal")
                    if collision:
                        collision.add_box(post_center,post_size,surface=6)
        for i in range(1,len(samples)-1):
            if i%3:
                continue
            x,y,_=samples[i]
            gz=ground_height(x,y)
            if deck-gz<4.5:
                continue
            center=(x,y,(deck+gz)*.5);size=(2.3,2.0,deck-gz)
            mesh.add_box(center,size,"concrete","concrete")
            if collision:
                collision.add_box(center,size,surface=5)
        # Large legible guide signs at the two interchange locations.
        for node_id,sign_x,direction in ((seg.start,-100,-1),(seg.end,125,1)):
            node=graph.nodes[node_id]
            if abs(node.x-sign_x)>80:
                continue
            sx,sy,sz=node.x,node.y,deck+2.0
            support=(sx,sy-13.0,sz-1.0);support_size=(.35,.35,4.8)
            frame=(sx,sy-13.0,sz+1.2);frame_size=(11.0,.45,2.2)
            mesh.add_box(support,support_size,"metal")
            mesh.add_box(frame,frame_size,"painted_metal","painted_metal")
            if collision:
                collision.add_box(support,support_size,surface=6)
                collision.add_box(frame,frame_size,surface=6)
            yface=sy-13.24
            points=((sx-5.2,yface,sz+.45),(sx+5.2,yface,sz+.45),
                    (sx+5.2,yface,sz+1.95),(sx-5.2,yface,sz+1.95))
            mesh.add_quad(points,"sign",color=(218,222,214,255))
            if collision:
                collision.add_quad(*points,surface=6)
            signs.append({"x":sx,"y":sy,"direction":direction,"name":seg.name})
    return signs


def bridge_barriers(mesh:Mesh,segment,graph:RoadGraph,ground_height,
                    collision:CollisionMesh|None=None,*,deck_offset:float=1.0)->None:
    samples=segment.sample_xy(graph,spacing=5.0)
    half=segment.paved_width*.5-.25
    for side in (-1,1):
        for i in range(len(samples)-1):
            x0,y0,t0=samples[i];x1,y1,t1=samples[i+1]
            dx,dy=x1-x0,y1-y0
            length=math.hypot(dx,dy) or 1.0
            nx,ny=-dy/length,dx/length
            minimum=float(segment.tags.get("deck_min_z",.8))
            z0=max(ground_height(x0,y0),minimum)+segment.bridge_clearance*4*t0*(1-t0)+deck_offset
            z1=max(ground_height(x1,y1),minimum)+segment.bridge_clearance*4*t1*(1-t1)+deck_offset
            a=(x0+nx*half*side,y0+ny*half*side,z0)
            b=(x1+nx*half*side,y1+ny*half*side,z1)
            top_a=(a[0],a[1],a[2]+.95);top_b=(b[0],b[1],b[2]+.95)
            mesh.add_quad((a,b,top_b,top_a),"concrete",((t0*7,0),(t1*7,0),(t1*7,1),(t0*7,1)))
            if collision:
                collision.add_quad(a,b,top_b,top_a,surface=5)
            if i%3==0:
                center=(a[0],a[1],a[2]+.43);size=(.18,.18,.86)
                mesh.add_box(center,size,"painted_metal")
                if collision:
                    collision.add_box(center,size,surface=6)
