"""Minimal RenderWare 3.6 DFF/TXD + GTA:SA COL3 serializers.

The writer intentionally uses ordinary (non-native) geometry, one frame, a
material list, and BinMesh PLG triangle lists.  This keeps output inspectable
and compatible with standard PC DFF/TXD readers rather than claiming PBR
features RenderWare does not have.
"""
from __future__ import annotations
from pathlib import Path
import math
import struct
from .mesh import Mesh
from .collision import CollisionMesh
from .dds import encode_bc1, mip_chain
from .textures import PixelImage
from .math3d import bounds3
from .materials import MATERIALS

RW_VERSION=0x1803FFFF


def rw_chunk(kind:int,payload:bytes,version:int=RW_VERSION)->bytes:
    return struct.pack("<III",kind,len(payload),version)+payload


def _rw_string(value:str)->bytes:
    return rw_chunk(0x02,value.encode("ascii","replace")+b"\0")


def _texture_chunk(name:str)->bytes:
    filter_flags=6|(1<<8)|(1<<12)  # linear mip/linear, wrap U/V
    body=rw_chunk(0x01,struct.pack("<I",filter_flags))
    body+=_rw_string(name)
    body+=_rw_string("")
    body+=rw_chunk(0x03,b"")
    return rw_chunk(0x06,body)


def _material_chunk(texture_name:str)->bytes:
    # Flags, RGBA, unused, textured, ambient/specular/diffuse.
    data=struct.pack("<I4sII3f",0,b"\xff\xff\xff\xff",0,1,1.0,0.08,1.0)
    body=rw_chunk(0x01,data)+_texture_chunk(texture_name)+rw_chunk(0x03,b"")
    return rw_chunk(0x07,body)


def _material_list(materials:list[str])->bytes:
    data=struct.pack("<I",len(materials))+b"".join(struct.pack("<i",-1) for _ in materials)
    body=rw_chunk(0x01,data)
    texture_names=[MATERIALS[name].texture if name in MATERIALS else name for name in materials]
    body+=b"".join(_material_chunk(name) for name in texture_names)
    return rw_chunk(0x08,body)


def _bin_mesh(mesh:Mesh,material_indices:dict[str,int])->bytes:
    groups=[]
    for name in mesh.materials:
        indices=[]
        mid=material_indices[name]
        for face in mesh.faces:
            if material_indices[face.material]==mid:
                indices.extend((face.a,face.b,face.c))
        if indices:
            groups.append((mid,indices))
    total=sum(len(ids) for _,ids in groups)
    payload=struct.pack("<III",0,len(groups),total)
    for material_id,indices in groups:
        payload+=struct.pack("<II",len(indices),material_id)
        payload+=struct.pack("<"+"I"*len(indices),*indices)
    return rw_chunk(0x050E,payload)


def build_dff(mesh:Mesh,model_name:str="freecity_model")->bytes:
    if not mesh.vertices or not mesh.faces:
        raise ValueError("cannot write an empty DFF geometry")
    if len(mesh.vertices)>65535 or len(mesh.faces)>65535:
        raise ValueError(f"DFF geometry limit exceeded: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")
    materials=mesh.materials
    mat_index={name:i for i,name in enumerate(materials)}
    flags=0x00000002|0x00000004|0x00000008|0x00000010|0x00000020|(1<<16)
    geom=bytearray(struct.pack("<IIII",flags,len(mesh.faces),len(mesh.vertices),1))
    # Geometry prelight RGBA and one UV set.
    for vertex in mesh.vertices:
        geom.extend(bytes(max(0,min(255,int(c))) for c in vertex.color))
    for vertex in mesh.vertices:
        geom.extend(struct.pack("<2f",float(vertex.uv[0]),float(vertex.uv[1])))
    for face in mesh.faces:
        if max(face.a,face.b,face.c)>=len(mesh.vertices):
            raise ValueError("face has out-of-range vertex index")
        # RenderWare RpTriangle wire order is vertex2, vertex1, material, vertex3.
        geom.extend(struct.pack("<4H",face.b,face.a,mat_index[face.material],face.c))
    lo,hi=bounds3(v.position for v in mesh.vertices)
    center=tuple((lo[i]+hi[i])*.5 for i in range(3))
    radius=max(math.dist(center,v.position) for v in mesh.vertices)
    geom.extend(struct.pack("<4fII",*center,radius,1,1))
    for vertex in mesh.vertices:
        geom.extend(struct.pack("<3f",*vertex.position))
    for vertex in mesh.vertices:
        n=vertex.normal
        nn=math.sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]) or 1
        geom.extend(struct.pack("<3f",n[0]/nn,n[1]/nn,n[2]/nn))
    geometry=rw_chunk(0x0F,rw_chunk(0x01,bytes(geom))+_material_list(materials)+
                      rw_chunk(0x03,_bin_mesh(mesh,mat_index)))
    geom_list=rw_chunk(0x1A,rw_chunk(0x01,struct.pack("<I",1))+geometry)
    frame_data=struct.pack("<12fii",1,0,0,0,1,0,0,0,1,0,0,0,-1,0)
    frames=rw_chunk(0x0E,rw_chunk(0x01,struct.pack("<I",1)+frame_data)+rw_chunk(0x03,b""))
    atomic=rw_chunk(0x14,rw_chunk(0x01,struct.pack("<4I",0,0,5,0))+rw_chunk(0x03,b""))
    clump_body=rw_chunk(0x01,struct.pack("<3I",1,0,0))+frames+geom_list+atomic+rw_chunk(0x03,b"")
    del model_name  # model identity is carried by the resource filename/COL model name
    return rw_chunk(0x10,clump_body)


def write_dff(mesh:Mesh,path:Path,model_name:str)->dict:
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=build_dff(mesh,model_name)
    path.write_bytes(data)
    lo,hi=bounds3(v.position for v in mesh.vertices)
    return {"path":str(path).replace("\\","/"),"bytes":len(data),"vertices":len(mesh.vertices),
            "triangles":len(mesh.faces),"materials":mesh.materials,
            "bounds":[list(lo),list(hi)]}


def build_txd(textures:dict[str,PixelImage])->bytes:
    if len(textures)>65535:
        raise ValueError("TXD exceeds texture count field")
    payload=rw_chunk(0x01,struct.pack("<HH",len(textures),2))
    for name,image in textures.items():
        name=name[:31]
        levels=mip_chain(image)
        filter_flags=6|(1<<8)|(1<<12)
        name_bytes=name.encode("ascii","replace")[:31].ljust(32,b"\0")
        mask=b"".ljust(32,b"\0")
        # Platform 9 (PC D3D9), RGB565/DXT1 raster, explicit mip chain.
        native=struct.pack("<II32s32sI4sHHBBBB",9,filter_flags,name_bytes,mask,
                           0x0200|0x8000,b"DXT1",image.width,image.height,16,len(levels),4,8)
        for level in levels:
            encoded=encode_bc1(level)
            native+=struct.pack("<I",len(encoded))+encoded
        payload+=rw_chunk(0x15,rw_chunk(0x01,native)+rw_chunk(0x03,b""))
    payload+=rw_chunk(0x03,b"")
    return rw_chunk(0x16,payload)


def write_txd(textures:dict[str,PixelImage],path:Path)->dict:
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=build_txd(textures);path.write_bytes(data)
    return {"path":str(path).replace("\\","/"),"bytes":len(data),"textures":len(textures),
            "names":list(textures)}


def _face_groups(collision:CollisionMesh,max_faces:int=48):
    faces=collision.faces
    # Spatial sort produces tighter groups than a pure file-order chunk and
    # keeps COL3 group ranges contiguous.
    def key(face):
        pts=[collision.vertices[i] for i in (face.a,face.b,face.c)]
        return (round(sum(p[0] for p in pts)/3/32),round(sum(p[1] for p in pts)/3/32),round(sum(p[2] for p in pts)/3/32))
    ordered=sorted(faces,key=lambda f:(key(f),f.surface))
    groups=[]
    start=0
    while start<len(ordered):
        end=min(len(ordered),start+max_faces)
        # Keep a spatial bucket together as far as practical, without leaving
        # an oversized group when the bucket is large.
        bucket=key(ordered[start])
        k=start+1
        while k<end and key(ordered[k])==bucket:
            k+=1
        if k-start>=12:
            end=k
        group_faces=ordered[start:end]
        points=[collision.vertices[i] for face in group_faces for i in (face.a,face.b,face.c)]
        lo,hi=bounds3(points)
        groups.append((start,end-1,lo,hi,group_faces))
        start=end
    return ordered,groups


def build_col3(name:str,collision:CollisionMesh,model_id:int=0)->bytes:
    if not collision.faces:
        raise ValueError("COL3 needs collision faces")
    if len(collision.vertices)>32767 or len(collision.faces)>32767:
        raise ValueError(f"COL3 limit exceeded: {len(collision.vertices)} vertices, {len(collision.faces)} faces")
    if len(collision.faces)>65535:
        raise ValueError("COL3 face count field overflow")
    lo,hi=bounds3(collision.vertices)
    center=tuple((lo[i]+hi[i])*.5 for i in range(3))
    radius=max(math.dist(center,v) for v in collision.vertices)
    ordered,groups=_face_groups(collision)
    # COL3 vertex coordinates are signed fixed-point 1/128 units.
    vertex_data=bytearray()
    for x,y,z in collision.vertices:
        vals=(round(x*128),round(y*128),round(z*128))
        if any(v<-32768 or v>32767 for v in vals):
            raise ValueError(f"COL3 vertex outside +/-256 units: {(x,y,z)}")
        vertex_data.extend(struct.pack("<3h",*vals))
    # Work out absolute offsets. Header is 120 bytes; offsets are relative to
    # the byte immediately after FourCC, as in RenderWare COL2/COL3.
    cursor=120
    offset_vertices=cursor
    cursor+=len(vertex_data)
    if len(vertex_data)%4:
        cursor+=2
    group_data=bytearray()
    for start,end,gb0,gb1,group_faces in groups:
        group_data.extend(struct.pack("<6fHH",*gb0,*gb1,start,end))
    group_data.extend(struct.pack("<I",len(groups)))
    cursor+=len(group_data)
    offset_faces=cursor
    face_data=bytearray()
    for face in ordered:
        face_data.extend(struct.pack("<3HBB",face.a,face.b,face.c,face.surface,face.light))
    cursor+=len(face_data)
    flags=2|(8 if groups else 0)
    # No spheres, boxes, lines, or shadow mesh; the optimized triangulated mesh
    # is the physical shape for this static tile.
    counts_offsets=struct.pack("<HHHBBI6I3I",0,0,len(ordered),0,0,flags,
                               0,0,0,offset_vertices-4,offset_faces-4,0,
                               0,0,0)
    header=(b"COL3"+struct.pack("<I",cursor-8)+name.encode("ascii","replace")[:22].ljust(22,b"\0")+
            struct.pack("<H",model_id)+struct.pack("<10f",*lo,*hi,*center,radius)+counts_offsets)
    if len(header)!=120:
        raise AssertionError(f"bad COL3 header length {len(header)}")
    out=bytearray(header+vertex_data)
    if len(vertex_data)%4:
        out.extend(b"\0\0")
    out.extend(group_data);out.extend(face_data)
    if len(out)!=cursor:
        raise AssertionError(f"COL3 size mismatch {len(out)} != {cursor}")
    return bytes(out)


def write_col3(name:str,collision:CollisionMesh,path:Path)->dict:
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=build_col3(name,collision);path.write_bytes(data)
    lo,hi=bounds3(collision.vertices)
    return {"path":str(path).replace("\\","/"),"bytes":len(data),"vertices":len(collision.vertices),
            "triangles":len(collision.faces),"bounds":[list(lo),list(hi)]}
