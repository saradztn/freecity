"""Road ribbons, shoulders, sidewalks and legible lane markings."""
from __future__ import annotations
import math
from .mesh import Mesh
from .collision import CollisionMesh
from .road_graph import RoadGraph, RoadSegment
from .math3d import Vec3, smoothstep


def _ground_z(segment: RoadSegment, t: float, x: float, y: float, terrain, graph: RoadGraph) -> float:
    if segment.alignment == "fixed":
        return float(segment.fixed_z or 0.0)
    if segment.alignment == "ramp":
        start, end = graph.nodes[segment.start], graph.nodes[segment.end]
        cut=float(segment.tags.get("cut_depth",4.5))
        def endpoint_z(node):
            z=float(node.elevation if node.elevation is not None else terrain.raw_height(node.x,node.y))
            if node.kind=="tunnel_portal":
                z-=cut
            return z
        z0,z1=endpoint_z(start),endpoint_z(end)
        s=t*t*(3.0-2.0*t)
        return z0+(z1-z0)*s
    if segment.alignment == "bridge":
        bed=max(terrain.raw_height(x,y),float(segment.tags.get("deck_min_z",0.8)))
        return bed+segment.bridge_clearance*(4.0*t*(1.0-t))
    if segment.kind == "tunnel":
        # Core tunnel floors stay below the ridge; tagged ramp-like portal
        # approaches provide the drivable grade transition into the opening.
        return terrain.raw_height(x,y)-float(segment.tags.get("cut_depth",4.5))+.16
    return terrain.raw_height(x,y)+0.16


def _ribbon_point(x: float, y: float, z: float, nx: float, ny: float, offset: float) -> Vec3:
    return (x+nx*offset,y+ny*offset,z)


def _add_segment_surface(mesh: Mesh, collision: CollisionMesh, segment: RoadSegment,
                         graph: RoadGraph, terrain, *, lod: bool=False) -> None:
    samples=segment.sample_xy(graph,spacing=13.0 if lod else 6.0)
    if len(samples)<2:return
    half=segment.paved_width*.5
    for i in range(len(samples)-1):
        x0,y0,t0=samples[i];x1,y1,t1=samples[i+1]
        dx,dy=x1-x0,y1-y0;length=math.hypot(dx,dy) or 1.0
        nx,ny=-dy/length,dx/length
        z0=_ground_z(segment,t0,x0,y0,terrain,graph);z1=_ground_z(segment,t1,x1,y1,terrain,graph)
        left0,right0=_ribbon_point(x0,y0,z0,nx,ny,half),_ribbon_point(x0,y0,z0,nx,ny,-half)
        left1,right1=_ribbon_point(x1,y1,z1,nx,ny,half),_ribbon_point(x1,y1,z1,nx,ny,-half)
        uv0=t0*segment.approximate_length(graph)/8.0;uv1=t1*segment.approximate_length(graph)/8.0
        mesh.add_quad((left0,right0,right1,left1),"asphalt",
                      ((0,uv0),(segment.paved_width/5.0,uv0),(segment.paved_width/5.0,uv1),(0,uv1)))
        collision.add_quad(left0,right0,right1,left1,surface=5)
        if segment.kind not in ("highway","ramp","bridge","tunnel"):
            sw=2.2
            for side in (-1,1):
                inner0=_ribbon_point(x0,y0,z0-.08,nx,ny,side*half)
                inner1=_ribbon_point(x1,y1,z1-.08,nx,ny,side*half)
                outer0=_ribbon_point(x0,y0,z0-.14,nx,ny,side*(half+sw))
                outer1=_ribbon_point(x1,y1,z1-.14,nx,ny,side*(half+sw))
                mesh.add_quad((inner0,outer0,outer1,inner1),"sidewalk",((0,uv0),(sw/3,uv0),(sw/3,uv1),(0,uv1)))
                collision.add_quad(inner0,outer0,outer1,inner1,surface=5)
                mesh.add_quad((outer0,outer1,(outer1[0],outer1[1],outer1[2]+.12),
                               (outer0[0],outer0[1],outer0[2]+.12)),"concrete")
                collision.add_quad(outer0,outer1,(outer1[0],outer1[1],outer1[2]+.12),
                                   (outer0[0],outer0[1],outer0[2]+.12),surface=5)
    if lod or segment.kind in ("highway","ramp","bridge","roundabout"):
        return
    _add_lane_markings(mesh,segment,graph,terrain,samples)


def _add_lane_markings(mesh:Mesh,segment:RoadSegment,graph:RoadGraph,terrain,samples)->None:
    total=segment.approximate_length(graph)
    if total<18:return
    start_node,end_node=graph.nodes[segment.start],graph.nodes[segment.end]
    trim0=10.0 if len(start_node.connections)>=3 else 1.0
    trim1=10.0 if len(end_node.connections)>=3 else 1.0
    offsets=[]
    if segment.lanes>=2 and segment.direction=="both":
        offsets.extend(((-.18,(222,184,86,255),False),(.18,(222,184,86,255),False)))
        for k in range(1,segment.lanes-1):
            lateral=-segment.road_width*.5+k*segment.lane_width
            if abs(lateral)>.65:offsets.append((lateral,(218,218,211,235),True))
    elif segment.lanes>1:
        for k in range(1,segment.lanes):
            offsets.append((-segment.road_width*.5+k*segment.lane_width,(218,218,211,235),True))
    edge=segment.road_width*.5-.27
    offsets.extend(((-edge,(205,205,197,210),False),(edge,(205,205,197,210),False)))
    for lateral,color,dashed in offsets:
        if dashed:
            cursor=trim0
            while cursor+3.0<total-trim1:
                _draw_center_strip(mesh,segment,graph,terrain,samples,cursor,cursor+3.0,lateral,.105,color)
                cursor+=8.0
        else:
            _draw_center_strip(mesh,segment,graph,terrain,samples,trim0,total-trim1,lateral,.11,color)


def _position_on_samples(samples,wanted_distance:float):
    acc=0.0
    for i in range(len(samples)-1):
        a,b=samples[i],samples[i+1]
        d=math.hypot(b[0]-a[0],b[1]-a[1])
        if acc+d>=wanted_distance:
            t=0.0 if d==0 else (wanted_distance-acc)/d
            return (a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,
                    a[2]+(b[2]-a[2])*t,(b[0]-a[0])/max(d,1e-9),(b[1]-a[1])/max(d,1e-9))
        acc+=d
    a,b=samples[-2],samples[-1];d=math.hypot(b[0]-a[0],b[1]-a[1]) or 1.0
    return (b[0],b[1],b[2],(b[0]-a[0])/d,(b[1]-a[1])/d)


def _draw_center_strip(mesh:Mesh,segment:RoadSegment,graph:RoadGraph,terrain,samples,
                       d0:float,d1:float,lateral:float,width:float,color)->None:
    if d1<=d0:return
    x0,y0,t0,tx0,ty0=_position_on_samples(samples,max(0.0,d0))
    x1,y1,t1,tx1,ty1=_position_on_samples(samples,d1)
    n0=(-ty0,tx0);n1=(-ty1,tx1)
    z0=_ground_z(segment,t0,x0,y0,terrain,graph)+.035
    z1=_ground_z(segment,t1,x1,y1,terrain,graph)+.035
    points=((x0+n0[0]*(lateral-width*.5),y0+n0[1]*(lateral-width*.5),z0),
            (x0+n0[0]*(lateral+width*.5),y0+n0[1]*(lateral+width*.5),z0),
            (x1+n1[0]*(lateral+width*.5),y1+n1[1]*(lateral+width*.5),z1),
            (x1+n1[0]*(lateral-width*.5),y1+n1[1]*(lateral-width*.5),z1))
    mesh.add_quad(points,"road_marking",color=color)


def build_roads(graph:RoadGraph,terrain,*,lod:bool=False)->tuple[Mesh,CollisionMesh]:
    visual,collision=Mesh(),CollisionMesh()
    for seg in graph.segments.values():
        _add_segment_surface(visual,collision,seg,graph,terrain,lod=lod)
    return visual,collision
