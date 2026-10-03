"""Small bridge deck fascia, supports, barriers, and collision."""
from __future__ import annotations
import math
from .mesh import Mesh
from .collision import CollisionMesh
from .road_graph import RoadGraph, RoadSegment


def add_bridge(mesh:Mesh,collision:CollisionMesh,segment:RoadSegment,graph:RoadGraph,ground_height)->None:
    samples=segment.sample_xy(graph,spacing=8.0)
    half=segment.paved_width*.5
    def deck_z(t:float,x:float,y:float)->float:
        bed=max(ground_height(x,y),float(segment.tags.get("deck_min_z",.8)))
        return bed+segment.bridge_clearance*(4.0*t*(1.0-t))
    for side in (-1,1):
        for i in range(len(samples)-1):
            x0,y0,t0=samples[i];x1,y1,t1=samples[i+1]
            dx,dy=x1-x0,y1-y0
            length=math.hypot(dx,dy) or 1.0
            nx,ny=-dy/length,dx/length
            a=(x0+nx*half*side,y0+ny*half*side,deck_z(t0,x0,y0)-.2)
            b=(x1+nx*half*side,y1+ny*half*side,deck_z(t1,x1,y1)-.2)
            c=(b[0],b[1],b[2]-1.0);d=(a[0],a[1],a[2]-1.0)
            mesh.add_quad((a,b,c,d),"concrete",((t0*6,0),(t1*6,0),(t1*6,1),(t0*6,1)))
            collision.add_quad(a,b,c,d,surface=5)
    # Two support bents on either side of the channel, not through its bed.
    for sample_index in (max(1,len(samples)//2-1),min(len(samples)-2,len(samples)//2+1)):
        x,y,t=samples[sample_index]
        dx,dy=segment.xy(graph,min(1,t+.01))[0]-segment.xy(graph,max(0,t-.01))[0], \
              segment.xy(graph,min(1,t+.01))[1]-segment.xy(graph,max(0,t-.01))[1]
        length=math.hypot(dx,dy) or 1.0
        nx,ny=-dy/length,dx/length
        deck=deck_z(t,x,y)-.55
        for side in (-1,1):
            px=x+nx*side*(half-1.2);py=y+ny*side*(half-1.2)
            gz=ground_height(px,py)
            if deck-gz>1.0:
                center=(px,py,(deck+gz)*.5);size=(1.25,1.5,deck-gz)
                mesh.add_box(center,size,"stone","concrete")
                collision.add_box(center,size,surface=26)
    from .highways import bridge_barriers
    bridge_barriers(mesh,segment,graph,ground_height,collision,deck_offset=1.3)
