"""Purpose-built city park and a small, connected surface parking facility."""
from __future__ import annotations
import math
import random
from .mesh import Mesh
from .collision import CollisionMesh
from .math3d import bezier2


def _surface_z(terrain,x,y,offset=.06):
    return terrain.height(x,y)+offset


def _path(mesh:Mesh,collision:CollisionMesh,terrain,points,width:float,material:str="concrete"):
    for i in range(len(points)-1):
        x0,y0=points[i];x1,y1=points[i+1]
        dx,dy=x1-x0,y1-y0
        length=math.hypot(dx,dy) or 1.0
        nx,ny=-dy/length,dx/length
        a=(x0+nx*width*.5,y0+ny*width*.5,_surface_z(terrain,x0+nx*width*.5,y0+ny*width*.5))
        b=(x0-nx*width*.5,y0-ny*width*.5,_surface_z(terrain,x0-nx*width*.5,y0-ny*width*.5))
        c=(x1-nx*width*.5,y1-ny*width*.5,_surface_z(terrain,x1-nx*width*.5,y1-ny*width*.5))
        d=(x1+nx*width*.5,y1+ny*width*.5,_surface_z(terrain,x1+nx*width*.5,y1+ny*width*.5))
        mesh.add_quad((a,b,c,d),material)
        collision.add_quad(a,b,c,d,surface=5)


def build_land_use(features:list[dict],terrain,seed:int,*,lod:bool=False)->tuple[Mesh,CollisionMesh,list[dict]]:
    mesh,collision=Mesh(),CollisionMesh()
    records=[]
    if lod:
        for feature in features:
            x0,y0,x1,y1=map(float,feature["bounds"])
            if feature["kind"]=="surface_parking":
                z=_surface_z(terrain,(x0+x1)*.5,(y0+y1)*.5,.07)
                corners=((x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z))
                mesh.add_quad(corners,"asphalt",((0,0),((x1-x0)/8,0),((x1-x0)/8,(y1-y0)/8),(0,(y1-y0)/8)))
            elif feature["kind"]=="urban_park":
                main=[]
                for i in range(7):
                    t=i/6
                    main.append((x0+3+(x1-x0-6)*t,y0+(y1-y0)*(.43+.11*math.sin(t*math.pi*2))))
                _path(mesh,CollisionMesh(),terrain,main,3.0,"sidewalk")
                north=[]
                for i in range(5):
                    t=i/4
                    north.append((x0+16+7*math.sin(t*math.pi),y0+5+(y1-y0-10)*t))
                _path(mesh,CollisionMesh(),terrain,north,2.25,"sidewalk")
        return mesh,collision,records
    rng=random.Random(seed ^ 0xC17A)
    for feature in features:
        x0,y0,x1,y1=map(float,feature["bounds"])
        if feature["kind"]=="urban_park":
            # A connected, lightly curving path system. The terrain underneath
            # remains natural ground; only the paved footprint is collision.
            main=[]
            for i in range(19):
                t=i/18
                px=x0+3+(x1-x0-6)*t
                py=y0+(y1-y0)*(.43+.11*math.sin(t*math.pi*2))
                main.append((px,py))
            _path(mesh,collision,terrain,main,3.0,"sidewalk")
            north=[]
            for i in range(13):
                t=i/12
                north.append((x0+16+7*math.sin(t*math.pi),y0+5+(y1-y0-10)*t))
            _path(mesh,collision,terrain,north,2.25,"sidewalk")
            # Low circular fountain, planted beds and a subtle paved apron.
            fx,fy=x0+(x1-x0)*.57,y0+(y1-y0)*.51
            fz=terrain.height(fx,fy)+.10
            mesh.add_disk((fx,fy,fz),2.6,"stone",20,color=(190,194,185,255))
            mesh.add_disk((fx,fy,fz+.10),1.55,"water",20,color=(190,211,213,255))
            for i in range(20):
                a0=2*math.pi*i/20;a1=2*math.pi*(i+1)/20
                p0=(fx,fy,fz);p1=(fx+2.6*math.cos(a0),fy+2.6*math.sin(a0),fz)
                p2=(fx+2.6*math.cos(a1),fy+2.6*math.sin(a1),fz)
                collision.add_triangle(p0,p1,p2,surface=5)
            # Four beds vary in size and tone but remain low enough for sightlines.
            for bx,by in ((x0+11,y0+8),(x1-11,y0+9),(x0+12,y1-8),(x1-12,y1-8)):
                radius=rng.uniform(1.1,1.8)
                z=terrain.height(bx,by)+.28
                mesh.add_ellipsoid((bx,by,z),(radius,radius*.78,.46),"leaves",rings=3,sides=7,
                                   color=(218,229,207,255))
            records.append({"id":feature["id"],"kind":"urban_park","path_widths":[3.0,2.25],
                            "fountain":[round(fx,2),round(fy,2)],"bounds":feature["bounds"]})
        elif feature["kind"]=="surface_parking":
            # Drivable asphalt court with raised perimeter curbs.
            z=_surface_z(terrain,(x0+x1)*.5,(y0+y1)*.5,.07)
            corners=((x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z))
            mesh.add_quad(corners,"asphalt",((0,0),((x1-x0)/8,0),((x1-x0)/8,(y1-y0)/8),(0,(y1-y0)/8)))
            collision.add_quad(*corners,surface=5)
            entrance_gap=(y0+7.0,y0+22.0)
            curb_segments=[((x0,y0),(x1,y0)),((x1,y1),(x0,y1)),((x0,y1),(x0,y0)),
                           ((x1,y0),(x1,entrance_gap[0])),((x1,entrance_gap[1]),(x1,y1))]
            for a,b in curb_segments:
                if math.dist(a,b)<.05:continue
                za,zb=_surface_z(terrain,*a,.04),_surface_z(terrain,*b,.04)
                p0=(a[0],a[1],za);p1=(b[0],b[1],zb)
                p2=(b[0],b[1],zb+.15);p3=(a[0],a[1],za+.15)
                mesh.add_quad((p0,p1,p2,p3),"concrete")
                collision.add_quad(p0,p1,p2,p3,surface=5)
            spaces=int(feature.get("spaces",38))
            per_row=max(1,spaces//2)
            pitch=(x1-x0-12.0)/per_row
            left=x0+6.0;row_y=(y0+23.0,y0+36.0)
            line_width=.11;stall_depth=5.4
            for row_index,cy in enumerate(row_y):
                for stall in range(per_row):
                    sx=left+stall*pitch;ex=sx+pitch
                    if stall:
                        xline=sx
                        p0=(xline,cy-stall_depth*.5,z+.035);p1=(xline,cy+stall_depth*.5,z+.035)
                        mesh.add_quad((p0,(xline+line_width,p0[1],p0[2]),(xline+line_width,p1[1],p1[2]),p1),
                                      "road_marking",color=(205,208,198,242))
                    # End stripe and a slightly wider accessible end stall.
                    end_y=cy+stall_depth*.5
                    p0=(sx,end_y,z+.035);p1=(ex,end_y,z+.035)
                    mesh.add_quad((p0,p1,(ex,end_y+line_width,z+.035),(sx,end_y+line_width,z+.035)),
                                  "road_marking",color=(205,208,198,242))
                    if stall==0 and row_index==0:
                        color=(105,137,151,255)
                        mesh.add_quad(((sx+line_width,cy-stall_depth*.5,z+.04),(sx+pitch*.42,cy-stall_depth*.5,z+.04),
                                       (sx+pitch*.42,cy+stall_depth*.5,z+.04),(sx+line_width,cy+stall_depth*.5,z+.04)),
                                      "painted_metal",color=color)
            # A short, six-metre driveway links the east lot gate to the bridge
            # approach at (130,-105); it also breaks the east curb at the gate.
            inner=(x1-2.0,y0+16.0);outer=(x1+9.0,y0-1.0)
            dx,dy=outer[0]-inner[0],outer[1]-inner[1]
            length=math.hypot(dx,dy) or 1.0
            nx,ny=-dy/length,dx/length
            half_drive=3.0
            left0=(inner[0]+nx*half_drive,inner[1]+ny*half_drive)
            right0=(inner[0]-nx*half_drive,inner[1]-ny*half_drive)
            left1=(outer[0]+nx*half_drive,outer[1]+ny*half_drive)
            right1=(outer[0]-nx*half_drive,outer[1]-ny*half_drive)
            entry=tuple((px,py,_surface_z(terrain,px,py,.035))
                        for px,py in (left0,right0,right1,left1))
            mesh.add_quad(entry,"asphalt");collision.add_quad(*entry,surface=5)
            # Two low pole lights, with restrained painted hardware and physical bases.
            for lx in (x0+8.0,x1-8.0):
                ly=y0+9.0;lz=terrain.height(lx,ly)
                mesh.add_cylinder((lx,ly,lz),.10,6.1,"painted_metal",8,top_radius=.07)
                mesh.add_box((lx,ly,lz+6.0),(.72,.28,.12),"emissive")
                collision.add_box((lx,ly,lz+2.9),(.22,.22,5.8),surface=6)
            records.append({"id":feature["id"],"kind":"surface_parking","spaces":spaces,
                            "bounds":feature["bounds"],"row_centers":list(row_y)})
    return mesh,collision,records
