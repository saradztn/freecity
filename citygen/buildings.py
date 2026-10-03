"""Archetype-driven building facades, roofs, entrances and collision shells."""
from __future__ import annotations
import math
import random
from .mesh import Mesh
from .collision import CollisionMesh
from .districts import BuildingPlacement
from .terrain import Terrain

ARCHETYPES = {
    "modern_tower": {"floors":(10,22),"size":(26,48),"facade":"stone_glass"},
    "glass_tower": {"floors":(14,30),"size":(28,48),"facade":"curtainwall"},
    "office_tower": {"floors":(8,22),"size":(26,48),"facade":"stone_glass"},
    "residential_tower": {"floors":(9,20),"size":(24,42),"facade":"brick_balcony"},
    "luxury_apartment": {"floors":(5,14),"size":(25,42),"facade":"brick_balcony"},
    "suburban_house": {"floors":(1,3),"size":(12,24),"facade":"siding"},
    "townhouse": {"floors":(2,4),"size":(13,25),"facade":"brick"},
    "motel": {"floors":(1,3),"size":(22,38),"facade":"painted_concrete"},
    "hotel": {"floors":(7,18),"size":(25,44),"facade":"stone_glass"},
    "shopping_center": {"floors":(1,3),"size":(32,65),"facade":"painted_concrete"},
    "strip_mall": {"floors":(1,2),"size":(24,58),"facade":"painted_concrete"},
    "restaurant": {"floors":(1,3),"size":(18,32),"facade":"brick"},
    "diner": {"floors":(1,2),"size":(16,30),"facade":"painted_metal"},
    "gas_station": {"floors":(1,2),"size":(20,42),"facade":"painted_metal"},
    "warehouse": {"floors":(1,3),"size":(30,70),"facade":"metal"},
    "factory": {"floors":(1,5),"size":(25,64),"facade":"industrial"},
    "hospital": {"floors":(3,12),"size":(28,58),"facade":"institutional"},
    "school": {"floors":(1,4),"size":(30,65),"facade":"institutional"},
    "police_station": {"floors":(2,7),"size":(20,42),"facade":"institutional"},
    "fire_station": {"floors":(1,4),"size":(20,42),"facade":"institutional"},
    "parking_garage": {"floors":(3,10),"size":(24,50),"facade":"concrete_open"},
    "industrial_building": {"floors":(1,6),"size":(22,58),"facade":"industrial"},
    "small_commercial": {"floors":(1,4),"size":(16,38),"facade":"brick"},
}

FACADE_MATERIAL = {
    "stone_glass":"stone", "curtainwall":"glass", "brick_balcony":"brick", "siding":"painted_concrete",
    "brick":"brick", "painted_concrete":"painted_concrete", "painted_metal":"painted_metal",
    "metal":"metal", "industrial":"metal", "institutional":"painted_concrete",
    "concrete_open":"concrete", "stucco":"painted_concrete",
}


def _wall_box(mesh: Mesh, x: float, y: float, z: float, w: float, d: float, h: float,
              material: str, roof: str="roof") -> None:
    mesh.add_box((x,y,z+h*.5),(w,d,h),material,roof)


def _window_material(rng: random.Random, night_bias: float=0.18) -> str:
    r=rng.random()
    if r<0.07:
        return "window_cool"
    if r<night_bias:
        return "window_warm"
    return "window_dark"


def _front_windows(mesh: Mesh, rng: random.Random, x: float, y: float, base_z: float,
                   width: float, height: float, floors: int, *, facade: str,
                   low: bool=False, balconies: bool=False, door: bool=False) -> None:
    cols=max(2,min(8,int(width/(4.2 if floors>4 else 3.6))))
    floor_h=height/max(1,floors)
    gap_x=width/(cols+1)
    win_w=min(2.3,gap_x*.62) if floors>4 else min(1.75,gap_x*.62)
    win_h=min(floor_h*.62,1.75 if floors<5 else 2.05)
    wallmat=FACADE_MATERIAL.get(facade,"painted_concrete")
    if low:
        floor_indices=sorted(set((0,max(0,floors//2),max(0,floors-1))))
    else:
        floor_indices=list(range(floors))
    sides=(("front",-1),("back",1))
    for face,ysign in sides:
        yy=y+ysign*(1e-2+0.5)  # caller uses building depth-independent front/back surface below
        del yy
    # front/rear y coordinates are assigned by caller via attribute below


def _add_windows_on_wall(mesh: Mesh, rng: random.Random, *, axis: str, fixed: float, start: float,
                         base_z: float, span: float, height: float, floors: int, facade: str,
                         low: bool=False, balconies: bool=False, door: bool=False, flip: bool=False,
                         seed_offset: int=0) -> None:
    cols=max(2,min(9,int(span/(4.2 if floors>4 else 3.5))))
    floor_h=height/max(1,floors)
    gap=span/(cols+1)
    win_w=min(2.35,gap*.62) if floors>4 else min(1.8,gap*.60)
    win_h=min(floor_h*.60,2.0 if floors>4 else 1.65)
    mat_wall=FACADE_MATERIAL.get(facade,"painted_concrete")
    floors_to_build=list(range(floors)) if not low else sorted(set((0,floors//2,max(0,floors-1))))
    for floor in floors_to_build:
        zc=base_z+floor*floor_h+floor_h*.56
        for col in range(cols):
            center=start-span*.5+(col+1)*gap
            if floor==0 and door and col==cols//2:
                # recessed entrance and transom; the collision shell remains a
                # simple building volume, so no deceptive walk-through hole.
                if axis=="y":
                    p0=(center-.62,fixed,base_z+.03);p1=(center+.62,fixed,base_z+.03)
                    p2=(center+.62,fixed,base_z+floor_h*.92);p3=(center-.62,fixed,base_z+floor_h*.92)
                else:
                    p0=(fixed,center-.62,base_z+.03);p1=(fixed,center+.62,base_z+.03)
                    p2=(fixed,center+.62,base_z+floor_h*.92);p3=(fixed,center-.62,base_z+floor_h*.92)
                mesh.add_quad((p0,p1,p2,p3),"metal",color=(230,231,221,255))
                continue
            material=_window_material(rng,0.18)
            half=win_w*.5
            if axis=="y":
                points=((center-half,fixed,zc-win_h*.5),(center+half,fixed,zc-win_h*.5),
                        (center+half,fixed,zc+win_h*.5),(center-half,fixed,zc+win_h*.5))
            else:
                points=((fixed,center-half,zc-win_h*.5),(fixed,center+half,zc-win_h*.5),
                        (fixed,center+half,zc+win_h*.5),(fixed,center-half,zc+win_h*.5))
            # Interior pane is a dark, slightly reflective material. Thin metal
            # frames avoid the flat printed-card effect of a single facade map.
            if flip:
                points=(points[1],points[0],points[3],points[2])
            uv_shift=rng.uniform(0.0,64.0)
            window_uvs=((uv_shift,0),(uv_shift+1,0),(uv_shift+1,1),(uv_shift,1))
            mesh.add_quad(points,material,window_uvs,color=(235,238,234,255))
            frame=.055
            def add_frame(frame_points):
                if flip:
                    frame_points=(frame_points[1],frame_points[0],frame_points[3],frame_points[2])
                mesh.add_quad(frame_points,"metal")
            if not low:
                if axis=="y":
                    outward=1 if flip else -1
                    fy=fixed+outward*.015
                    fy_top=fixed+outward*.018
                    add_frame(((center-half-frame,fy,zc-win_h*.5-frame),(center-half,fy,zc-win_h*.5-frame),
                               (center-half,fy,zc+win_h*.5+frame),(center-half-frame,fy,zc+win_h*.5+frame)))
                    add_frame(((center+half,fy,zc-win_h*.5-frame),(center+half+frame,fy,zc-win_h*.5-frame),
                               (center+half+frame,fy,zc+win_h*.5+frame),(center+half,fy,zc+win_h*.5+frame)))
                    add_frame(((center-half-frame,fy_top,zc+win_h*.5),(center+half+frame,fy_top,zc+win_h*.5),
                               (center+half+frame,fy_top,zc+win_h*.5+frame),(center-half-frame,fy_top,zc+win_h*.5+frame)))
                else:
                    outward=-1 if flip else 1
                    fx=fixed+outward*.015
                    add_frame(((fx,center-half-frame,zc-win_h*.5-frame),(fx,center-half,zc-win_h*.5-frame),
                               (fx,center-half,zc+win_h*.5+frame),(fx,center-half-frame,zc+win_h*.5+frame)))
                    add_frame(((fx,center+half,zc-win_h*.5-frame),(fx,center+half+frame,zc-win_h*.5-frame),
                               (fx,center+half+frame,zc+win_h*.5+frame),(fx,center+half,zc+win_h*.5+frame)))
                if balconies and floor>0:
                    bx=center
                    mesh.add_box((bx,fixed-.7,zc-win_h*.1),(win_w+1.0,.72,.09),"concrete")
                    mesh.add_box((bx,fixed-1.02,zc+win_h*.28),(win_w+1.0,.07,.65),"painted_metal")


def _add_roof_details(mesh: Mesh, placement: BuildingPlacement, ztop: float, rng: random.Random,
                      material: str, low: bool=False) -> None:
    x,y,w,d=placement.x,placement.y,placement.width,placement.depth
    mesh.add_box((x,y,ztop+.45),(w+.7,d+.7,.9),"concrete","roof")
    if low:
        if placement.archetype in ("glass_tower","modern_tower","office_tower"):
            mesh.add_box((x,y,ztop+2.0),(w*.26,d*.24,2.2),material,"roof")
        return
    # Varied parapets, HVAC units and roof equipment; all are subtle, not toy-like.
    n=1+int(placement.width//22)
    for i in range(min(n,3)):
        hx=x+rng.uniform(-w*.26,w*.26)
        hy=y+rng.uniform(-d*.25,d*.25)
        hw=rng.uniform(1.5,3.8); hd=rng.uniform(1.2,2.9); hh=rng.uniform(.8,1.7)
        mesh.add_box((hx,hy,ztop+.9+hh*.5),(hw,hd,hh),"painted_metal","painted_metal")
        mesh.add_box((hx,hy,ztop+.9+hh+.05),(hw*.62,hd*.62,.08),"metal")
    if placement.archetype in ("glass_tower","office_tower","modern_tower") and rng.random()<.65:
        mesh.add_cylinder((x+w*.18,y-d*.1,ztop+.9),.12,rng.uniform(4,10),"metal",8,top_radius=.08)


def _add_pitched_roof(mesh: Mesh, p: BuildingPlacement, base_z: float, roof_height: float=3.0) -> None:
    x,y,w,d=p.x,p.y,p.width,p.depth
    eave=base_z+p.height
    ridge_z=eave+roof_height
    front,back=y-d*.5,y+d*.5
    # Two complete sloping planes plus gable triangles.
    mesh.add_quad(((x-w*.5,front,eave),(x,front,ridge_z),(x,back,ridge_z),(x-w*.5,back,eave)),"roof")
    mesh.add_quad(((x,front,ridge_z),(x+w*.5,front,eave),(x+w*.5,back,eave),(x,back,ridge_z)),"roof")
    mesh.add_triangle(((x-w*.5,front,eave),(x+w*.5,front,eave),(x,front,ridge_z)),"brick")
    mesh.add_triangle(((x+w*.5,back,eave),(x-w*.5,back,eave),(x,back,ridge_z)),"brick")
    mesh.add_box((x,y,eave+roof_height*.45),(w*.08,d*.9,.18),"painted_metal")


def build_building(placement: BuildingPlacement, terrain: Terrain, *, lod: bool=False) -> tuple[Mesh, CollisionMesh]:
    if placement.archetype not in ARCHETYPES:
        raise ValueError(f"unknown building archetype {placement.archetype}")
    mesh,coll=Mesh(),CollisionMesh()
    rng=random.Random(placement.seed)
    x,y=placement.x,placement.y
    w,d,h=placement.width,placement.depth,placement.height
    base_z=terrain.height(x,y)
    facade=placement.facade
    wall=FACADE_MATERIAL.get(facade,"painted_concrete")
    floors=max(1,placement.floors)
    roof_z=base_z+h

    # Subtle step-backs on taller towers break the single-box silhouette.
    if placement.archetype in ("glass_tower","office_tower","modern_tower") and not lod and floors>12:
        lower_h=h*.66
        _wall_box(mesh,x,y,base_z,w,d,lower_h,wall,"roof")
        _wall_box(mesh,x,y,base_z+lower_h,w*.90,d*.90,h-lower_h,wall,"roof")
    elif placement.archetype=="factory" and not lod:
        _wall_box(mesh,x,y,base_z,w,d*.72,h,wall,"roof")
        # Small saw-tooth clerestory volumes along the rear half.
        for i in range(3):
            sx=x-w*.32+i*w*.32
            mesh.add_box((sx,y+d*.2,base_z+h+.75),(w*.20,d*.44,1.5),"painted_metal","roof")
    elif placement.archetype=="parking_garage":
        if lod:
            _wall_box(mesh,x,y,base_z,w,d,h,"concrete","roof")
        else:
            # Open-air decks: slabs, corner piers and exposed parking bays.
            levels=max(2,floors)
            mesh.add_box((x,y,base_z+.22),(w,d,.44),"concrete")
            for level in range(1,levels+1):
                z=base_z+level*(h/levels)
                mesh.add_box((x,y,z),(w+.4,d+.4,.32),"concrete")
                for px in (-w*.42,w*.42):
                    for py in (-d*.42,d*.42):
                        mesh.add_box((x+px,y+py,base_z+(level-.5)*(h/levels)),(1.1,1.1,h/levels),"concrete")
                mesh.add_box((x,y-d*.5+.35,z+.22),(w*.82,.20,.44),"painted_metal")
    elif placement.archetype in ("gas_station","diner"):
        _wall_box(mesh,x,y,base_z,w,d,h,wall,"roof")
        if placement.archetype=="gas_station":
            canopy_z=base_z+h+2.4
            mesh.add_box((x,y+d*.5+4.0,canopy_z),(w*.9,8.0,.7),"painted_metal","roof")
            for sx in (-w*.3,w*.3):
                for sy in (d*.5+1.1,d*.5+6.8):
                    mesh.add_box((x+sx,y+sy,base_z+h+1.2),(.35,.35,2.4),"metal")
            for sx in (-w*.22,0,w*.22):
                mesh.add_box((x+sx,y+d*.5+4.0,base_z+1.1),(1.1,1.5,2.2),"painted_metal")
        else:
            # Diner awning and a restrained sign band.
            mesh.add_box((x,y-d*.5-.7,base_z+h*.82),(w*.9,1.0,.42),"painted_metal")
    else:
        _wall_box(mesh,x,y,base_z,w,d,h,wall,"roof")

    # Collision is a conservative watertight shell. Entries/windows are visual
    # detail only; the exported COL bounds remain predictable for vehicles.
    coll.add_box((x,y,base_z+h*.5),(max(2.0,w-.2),max(2.0,d-.2),max(2.0,h)),surface=5)

    # Facades: a material-specific skin with framed repeated bays. Low LOD keeps
    # silhouettes and broad glazing bands, not the near geometry.
    if placement.archetype not in ("parking_garage",):
        depth_front=y-d*.5-.035
        depth_back=y+d*.5+.035
        left=x-w*.5-.035
        right=x+w*.5+.035
        balconies=placement.archetype in ("luxury_apartment","residential_tower","hotel")
        entry=placement.archetype not in ("warehouse","factory","gas_station")
        for face_y in (depth_front,depth_back):
            _add_windows_on_wall(mesh,rng,axis="y",fixed=face_y,start=x,base_z=base_z+.15,
                                 span=w*.86,height=h*.92,floors=floors,facade=facade,
                                 low=lod,balconies=balconies and not lod and face_y==depth_front,
                                 door=entry and face_y==depth_front,flip=(face_y==depth_back))
        for face_x in (left,right):
            _add_windows_on_wall(mesh,rng,axis="x",fixed=face_x,start=y,base_z=base_z+.15,
                                 span=d*.84,height=h*.92,floors=floors,facade=facade,
                                 low=lod,balconies=False,door=False,flip=(face_x==left),seed_offset=3)

    if placement.archetype in ("suburban_house","townhouse"):
        _add_pitched_roof(mesh,placement,base_z,roof_height=2.4 if placement.archetype=="suburban_house" else 1.8)
        # Porch, steps, and front door canopy.
        mesh.add_box((x,y-d*.5-1.3,base_z+.22),(w*.52,2.4,.44),"concrete")
        mesh.add_box((x,y-d*.5-2.0,base_z+h*.48),(w*.36,.38,.16),"wood")
        if not lod:
            for px in (-w*.18,w*.18):
                mesh.add_box((x+px,y-d*.5-2.0,base_z+h*.28),(.13,.13,h*.42),"wood")
    else:
        _add_roof_details(mesh,placement,roof_z,rng,wall,lod)

    # Signs/awnings are attached to a small number of commercial/public facades.
    if placement.archetype in ("motel","restaurant","diner","gas_station","strip_mall","small_commercial"):
        if not lod:
            sign_z=base_z+min(h*.75,4.2)
            sign_w=min(w*.68,8.0)
            sign_y=y-d*.5-.22
            mesh.add_box((x,sign_y,sign_z),(sign_w,.32,1.25),"painted_metal")
            mesh.add_quad(((x-sign_w*.46,sign_y-.18,sign_z-.48),(x+sign_w*.46,sign_y-.18,sign_z-.48),
                           (x+sign_w*.46,sign_y-.18,sign_z+.48),(x-sign_w*.46,sign_y-.18,sign_z+.48)),"sign")
    # Rooftop antennas on a small stable fraction of tall buildings.
    if not lod and floors>8 and rng.random()<.4:
        mesh.add_cylinder((x-w*.22,y,roof_z+1.0),.045,rng.uniform(3.5,7.5),"metal",6,top_radius=.035)
    angle=math.radians(placement.rotation)
    if abs(angle)>1e-7:
        c,s=math.cos(angle),math.sin(angle)
        for vertex in mesh.vertices:
            px,py,pz=vertex.position
            dx,dy=px-x,py-y
            vertex.position=(x+dx*c-dy*s,y+dx*s+dy*c,pz)
            nx,ny,nz=vertex.normal
            vertex.normal=(nx*c-ny*s,nx*s+ny*c,nz)
        coll.vertices=[(x+(px-x)*c-(py-y)*s,y+(px-x)*s+(py-y)*c,pz)
                       for px,py,pz in coll.vertices]
        coll._lookup={(round(px*128),round(py*128),round(pz*128)):i
                      for i,(px,py,pz) in enumerate(coll.vertices)}
    return mesh,coll
