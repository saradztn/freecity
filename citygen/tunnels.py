"""Cut-through tunnel apertures, retaining walls, portal frames and collision."""
from __future__ import annotations
import math
from .mesh import Mesh
from .road_graph import RoadGraph, RoadSegment
from .collision import CollisionMesh


def tunnel_hole_at(segment:RoadSegment,graph:RoadGraph,x:float,y:float,margin:float=5.4)->bool:
    if segment.kind!="tunnel":
        return False
    samples=segment.sample_xy(graph,spacing=3.0)
    best=(float("inf"),0.0)
    for i in range(len(samples)-1):
        ax,ay,ta=samples[i];bx,by,tb=samples[i+1]
        from .math3d import point_segment_distance_2d
        d,lt=point_segment_distance_2d((x,y),(ax,ay),(bx,by))
        t=ta+(tb-ta)*lt
        if d<best[0]:
            best=(d,t)
    return best[0]<margin and .025<best[1]<.975


def _floor(segment:RoadSegment,graph:RoadGraph,terrain,t:float,x:float,y:float)->float:
    if segment.alignment=="ramp":
        start,end=graph.nodes[segment.start],graph.nodes[segment.end]
        cut=float(segment.tags.get("cut_depth",4.5))
        def node_z(node):
            z=float(node.elevation if node.elevation is not None else terrain.raw_height(node.x,node.y))
            return z-cut if node.kind=="tunnel_portal" else z
        z0,z1=node_z(start),node_z(end)
        s=t*t*(3-2*t)
        return z0+(z1-z0)*s+.16
    return terrain.raw_height(x,y)-float(segment.tags.get("cut_depth",4.5))+.16


def add_tunnel(mesh:Mesh,collision:CollisionMesh,segment:RoadSegment,graph:RoadGraph,terrain)->None:
    # The two short portal approaches are open cuttings; only the middle edge
    # receives the roof and lined interior, preventing buried/raised fake roofs.
    if segment.alignment=="ramp":
        return
    samples=segment.sample_xy(graph,spacing=4.0)
    half=segment.road_width*.5+.75
    for index in range(len(samples)-1):
        x0,y0,t0=samples[index];x1,y1,t1=samples[index+1]
        dx,dy=x1-x0,y1-y0
        length=math.hypot(dx,dy) or 1.0
        nx,ny=-dy/length,dx/length
        floor0=_floor(segment,graph,terrain,t0,x0,y0)
        floor1=_floor(segment,graph,terrain,t1,x1,y1)
        eave0=terrain.raw_height(x0,y0)-.72
        eave1=terrain.raw_height(x1,y1)-.72
        crown0=terrain.raw_height(x0,y0)-.22
        crown1=terrain.raw_height(x1,y1)-.22
        for side in (-1,1):
            p0=(x0+nx*half*side,y0+ny*half*side,floor0)
            p1=(x1+nx*half*side,y1+ny*half*side,floor1)
            top0=(p0[0],p0[1],eave0);top1=(p1[0],p1[1],eave1)
            mesh.add_quad((p0,p1,top1,top0),"stone",((t0*6,0),(t1*6,0),(t1*6,1),(t0*6,1)))
            collision.add_quad(p0,p1,top1,top0,surface=26)
            # Sloped roof half, from crown to the adjacent eave.
            c0=(x0,y0,crown0);c1=(x1,y1,crown1)
            mesh.add_quad((c0,c1,top1,top0),"concrete")
            collision.add_quad(c0,c1,top1,top0,surface=5)
        if index%3==0:
            midx,midy=(x0+x1)*.5,(y0+y1)*.5
            midz=(floor0+floor1)*.5
            mesh.add_box((midx,midy,midz+3.45),(.8,1.2,.08),"emissive")
    # Portal posts and lintels frame a clear opening; collision follows the
    # vertical posts and lintel but never fills the vehicle aperture.
    for endpoint in (samples[0],samples[-1]):
        x,y,t=endpoint
        floor=_floor(segment,graph,terrain,t,x,y)
        roof=terrain.raw_height(x,y)-.22
        tangent=segment.xy(graph,min(1.0,t+.02)) if t<.5 else segment.xy(graph,max(0.0,t-.02))
        other=segment.xy(graph,min(1.0,t+.02)) if t<.5 else segment.xy(graph,max(0.0,t-.02))
        dx,dy=other[0]-x,other[1]-y
        length=math.hypot(dx,dy) or 1.0
        nx,ny=-dy/length,dx/length
        height=max(1.0,roof-floor)
        for side in (-1,1):
            px=x+nx*half*side;py=y+ny*half*side
            center=(px,py,(floor+roof)*.5);size=(.7,.7,height)
            mesh.add_box(center,size,"concrete")
            collision.add_box(center,size,surface=5)
        beam=(x,y,roof-.18);beam_size=(segment.road_width+2.0,.75,.38)
        mesh.add_box(beam,beam_size,"concrete")
        collision.add_box(beam,beam_size,surface=5)
