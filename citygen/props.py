"""Low-cost authored prop primitives used by infrastructure and city dressing."""
from __future__ import annotations
import math
from .mesh import Mesh
from .collision import CollisionMesh


def add_hydrant(mesh: Mesh, collision: CollisionMesh, x: float, y: float, z: float, color=(170, 48, 35)) -> None:
    mesh.add_cylinder((x,y,z),0.25,0.75,"painted_metal",8,top_radius=0.18)
    mesh.add_cylinder((x,y,z+0.68),0.16,0.26,"painted_metal",8,top_radius=0.16)
    mesh.add_cylinder((x-0.25,y,z+0.42),0.11,0.12,"painted_metal",8,top_radius=0.11)
    mesh.add_cylinder((x+0.25,y,z+0.42),0.11,0.12,"painted_metal",8,top_radius=0.11)
    collision.add_box((x,y,z+0.45),(0.55,0.48,0.9),surface=6)


def add_streetlamp(mesh: Mesh, collision: CollisionMesh, x: float, y: float, z: float,
                   direction: tuple[float,float], lamp_type: str) -> dict:
    # Pole, tapered outreach arm and a restrained rectangular LED/sodium head.
    mesh.add_cylinder((x,y,z),0.13,6.8,"painted_metal",8,top_radius=0.075)
    dx,dy=direction
    head_x,head_y=x+dx*1.05,y+dy*1.05
    mesh.add_box((x+dx*.54,y+dy*.54,z+6.65),(1.35,.11,.11),"metal")
    mesh.add_box((head_x,head_y,z+6.53),(0.72,.32,.15),"painted_metal")
    mesh.add_box((head_x,head_y,z+6.43),(0.48,.24,.055),"emissive")
    collision.add_box((x,y,z+3.25),(.28,.28,6.5),surface=6)
    palette={"sodium":(255,190,119),"neutral_led":(216,226,228),"cool_led":(182,207,233)}
    return {"x":head_x,"y":head_y,"z":z+6.55,"type":lamp_type,
            "color":palette.get(lamp_type,(235,214,171)),"intensity":0.52 if lamp_type=="sodium" else 0.38,
            "range":26.0}


def add_traffic_signal(mesh: Mesh, collision: CollisionMesh, x: float, y: float, z: float,
                       facing: tuple[float,float]) -> None:
    dx,dy=facing
    mesh.add_cylinder((x,y,z),0.10,4.6,"painted_metal",8,top_radius=0.06)
    mesh.add_box((x+dx*.22,y+dy*.22,z+4.2),(.55,.42,1.25),"metal")
    for i, material in enumerate(("sign","emissive","emissive")):
        mesh.add_ellipsoid((x+dx*.52,y+dy*.22,z+4.58-i*.34),(.13,.07,.13),material,rings=3,sides=8)
    collision.add_box((x,y,z+2.2),(.22,.22,4.4),surface=6)


def add_road_sign(mesh: Mesh, collision: CollisionMesh, x: float, y: float, z: float,
                  text_material: str="sign", width: float=1.1, height: float=1.0) -> None:
    mesh.add_cylinder((x,y,z),.055,2.45,"painted_metal",6,top_radius=.05)
    mesh.add_box((x,y,z+1.9),(width,.12,height),"metal")
    mesh.add_quad(((x-width*.47,y-.075,z+1.9-height*.42),(x+width*.47,y-.075,z+1.9-height*.42),
                   (x+width*.47,y-.075,z+1.9+height*.42),(x-width*.47,y-.075,z+1.9+height*.42)),
                  text_material)
    collision.add_box((x,y,z+1.15),(.14,.14,2.3),surface=6)


def add_bus_shelter(mesh: Mesh, collision: CollisionMesh, x: float, y: float, z: float, angle: float=0.0) -> None:
    # A single bus shelter with glass panels and a weathered steel frame.
    a=math.radians(angle)
    c,s=math.cos(a),math.sin(a)
    def tr(px,py,pz): return (x+px*c-py*s,y+px*s+py*c,z+pz)
    mesh.add_box(tr(0,0,.08),(4.2,1.75,.16),"concrete")
    mesh.add_box(tr(0,0,2.3),(4.1,.12,.14),"painted_metal")
    for px in (-1.9,1.9):
        mesh.add_box(tr(px,0,1.15),(.12,.12,2.3),"painted_metal")
    for px in (-1.25,0,1.25):
        points=(tr(px,-.03,.25),tr(px+.95,-.03,.25),tr(px+.95,-.03,2.15),tr(px,-.03,2.15))
        mesh.add_quad(points,"glass",((0,0),(1,0),(1,1),(0,1)),color=(190,211,215,235))
    collision.add_box((x,y,z+1.0),(4.2,1.75,2.0),surface=6)


def add_mailbox(mesh: Mesh, x: float, y: float, z: float) -> None:
    mesh.add_cylinder((x,y,z),.035,.65,"painted_metal",6,top_radius=.03)
    mesh.add_box((x,y,z+.92),(.42,.32,.45),"painted_metal")


def add_bench(mesh: Mesh, collision: CollisionMesh, x: float, y: float, z: float, angle: float=0.0) -> None:
    c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle))
    def tr(px,py,pz): return (x+px*c-py*s,y+px*s+py*c,z+pz)
    mesh.add_box(tr(0,0,.48),(1.8,.42,.12),"wood")
    mesh.add_box(tr(0,.15,.94),(1.8,.12,.85),"wood")
    for sx in (-.68,.68):
        mesh.add_box(tr(sx,0,.23),(.12,.42,.46),"metal")
    collision.add_box((x,y,z+.55),(1.85,.5,1.15),surface=20)
