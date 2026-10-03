"""Species-level vegetation variants with distinct silhouettes and cheap LOD."""
from __future__ import annotations
import math
import random
from .mesh import Mesh
from .collision import CollisionMesh
from .road_graph import RoadGraph
from .terrain import Terrain


TREE_ZONES = [
    (-204, 48, -118, 139, 14, "oak"),
    (142, -15, 220, 28, 12, "oak"),

    (138, 153, 220, 199, 5, "pine"),
    (-214, -174, -116, -78, 4, "palm"),
]


def _palm(mesh: Mesh, coll: CollisionMesh, x: float, y: float, z: float, rng: random.Random, lod: bool=False) -> None:
    height=rng.uniform(8.0,12.0)
    bend=rng.uniform(-1.0,1.0)
    mesh.add_cylinder((x,y,z),.26,height*.62,"wood",8,top_radius=.12)
    coll.add_box((x,y,z+height*.28),(.45,.45,height*.56),surface=20)
    top=(x+bend,y+0.4,z+height*.62)
    count=4 if lod else 9
    for i in range(count):
        a=2*math.pi*i/count+rng.uniform(-.16,.16)
        length=rng.uniform(3.1,4.8)
        dx,dy=math.cos(a),math.sin(a)
        side=(-dy,dx)
        end=(top[0]+dx*length,top[1]+dy*length,top[2]-rng.uniform(1.0,2.0))
        width=.55 if not lod else .8
        points=((top[0]-side[0]*width,top[1]-side[1]*width,top[2]),
                (top[0]+side[0]*width,top[1]+side[1]*width,top[2]),
                (end[0]+side[0]*.08,end[1]+side[1]*.08,end[2]),
                (end[0]-side[0]*.08,end[1]-side[1]*.08,end[2]))
        mesh.add_quad(points,"leaves",color=(235,242,222,255))


def _oak(mesh: Mesh, coll: CollisionMesh, x: float, y: float, z: float, rng: random.Random, lod: bool=False) -> None:
    height=rng.uniform(7.0,10.0)
    mesh.add_cylinder((x,y,z),.36,height*.52,"wood",9,top_radius=.13)
    coll.add_box((x,y,z+height*.25),(.62,.62,height*.5),surface=20)
    rings=1 if lod else 2
    clusters=2 if lod else 6
    for i in range(clusters):
        angle=2*math.pi*i/clusters+rng.uniform(-.25,.25)
        offset=rng.uniform(.15,1.25)
        center=(x+math.cos(angle)*offset,y+math.sin(angle)*offset,z+height*rng.uniform(.62,.86))
        radii=(rng.uniform(1.5,2.3),rng.uniform(1.4,2.1),rng.uniform(1.4,2.0))
        color=(rng.randint(218,246),rng.randint(225,248),rng.randint(208,235),255)
        mesh.add_ellipsoid(center,radii,"leaves",rings=4 if not lod else 2,sides=7 if not lod else 5,color=color)


def _pine(mesh: Mesh, coll: CollisionMesh, x: float, y: float, z: float, rng: random.Random, lod: bool=False) -> None:
    height=rng.uniform(8.0,12.0)
    mesh.add_cylinder((x,y,z),.27,height*.78,"wood",8,top_radius=.10)
    coll.add_box((x,y,z+height*.35),(.48,.48,height*.7),surface=20)
    levels=2 if lod else 5
    for level in range(levels):
        frac=.33+level*(.48/max(1,levels-1))
        radius=(1.9*(1.0-frac*.4))*rng.uniform(.85,1.15)
        base=z+height*frac
        tip=z+height*min(.98,frac+.3)
        sides=7 if not lod else 5
        for i in range(sides):
            a=2*math.pi*i/sides
            a2=2*math.pi*(i+1)/sides
            p0=(x+radius*math.cos(a),y+radius*math.sin(a),base)
            p1=(x+radius*math.cos(a2),y+radius*math.sin(a2),base)
            p2=(x,y,tip)
            mesh.add_triangle((p0,p1,p2),"leaves",color=(225,236,222,255))


def build_vegetation(seed: int, graph: RoadGraph, terrain: Terrain, *, lod: bool=False,
                     blocked_areas: list[tuple[float,float,float,float]] | None=None) -> tuple[Mesh,CollisionMesh,list[dict]]:
    mesh,coll=Mesh(),CollisionMesh()
    rng=random.Random(seed ^ 0x71A3)
    records=[]
    blocked_areas=blocked_areas or []
    tree_id=0
    for xmin,ymin,xmax,ymax,count,species in TREE_ZONES:
        attempts=count if lod else count*3
        placed=0
        for _ in range(attempts):
            if placed>=count:
                break
            x=rng.uniform(xmin,xmax);y=rng.uniform(ymin,ymax)
            if species=="oak" and -68<x<128 and -65<y<148:
                continue
            if any(ax<=x<=bx and ay<=y<=by for ax,ay,bx,by in blocked_areas):
                continue
            road_dist,seg,_=graph.road_distance(x,y)
            if seg and road_dist < seg.paved_width*.5+5.0:
                continue
            # Keep trees clear of the park's curving main/secondary paths and
            # of the tidal creek crossing beyond the downtown edge.
            if 142<x<220 and -18<y<30:
                t=(x-140)/82
                main_y=-18+48*(.43+.11*math.sin(t*math.pi*2))
                cross_x=156+7*math.sin(max(0,min(1,(y+13)/38))*math.pi)
                if abs(y-main_y)<3.3 or abs(x-cross_x)<2.5:
                    continue
            if 106<x<233 and -145<y<-108:
                continue
            z=terrain.height(x,y)
            local_species=species
            if species=="oak" and rng.random()<.18:
                local_species="pine"
            if local_species=="palm":
                _palm(mesh,coll,x,y,z,rng,lod)
            elif local_species=="pine":
                _pine(mesh,coll,x,y,z,rng,lod)
            else:
                _oak(mesh,coll,x,y,z,rng,lod)
            records.append({"id":f"tree_{tree_id:03d}","species":local_species,
                            "x":round(x,2),"y":round(y,2),"z":round(z,2),
                            "seed":seed+tree_id*73})
            tree_id+=1;placed+=1
    # Low ornamental shrubs stay inside the park planting beds, off its paths.
    if not lod:
        for i in range(18):
            x=rng.uniform(141,217);y=rng.uniform(-14,26)
            t=(x-140)/82
            main_y=-18+48*(.43+.11*math.sin(t*math.pi*2))
            cross_x=156+7*math.sin(max(0,min(1,(y+13)/38))*math.pi)
            if abs(y-main_y)<4.0 or abs(x-cross_x)<3.0:
                continue
            mesh.add_ellipsoid((x,y,terrain.height(x,y)+.46),(.65,.48,.55),"leaves",rings=3,sides=6,
                               color=(228,235,218,255))
    return mesh,coll,records


def build_vegetation_lod(instances:list[dict])->Mesh:
    """Build matching low-detail silhouettes from the accepted high-tier trees."""
    mesh=Mesh()
    for record in instances:
        rng=random.Random(int(record.get("seed",0)) ^ 0x2A31)
        x,y,z=float(record["x"]),float(record["y"]),float(record["z"])
        species=record.get("species","oak")
        if species=="palm":
            _palm(mesh,CollisionMesh(),x,y,z,rng,lod=True)
        elif species=="pine":
            _pine(mesh,CollisionMesh(),x,y,z,rng,lod=True)
        else:
            _oak(mesh,CollisionMesh(),x,y,z,rng,lod=True)
    return mesh
