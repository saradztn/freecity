"""Procedural albedo/PBR texture authoring and PNG/DDS/TXD source images."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import math
import random
import struct
import zlib
from .materials import MATERIALS, MaterialSpec


@dataclass
class PixelImage:
    width: int
    height: int
    pixels: bytearray | None = None

    def __post_init__(self):
        if self.pixels is None:
            self.pixels=bytearray([0,0,0,255])*(self.width*self.height)

    def set(self,x:int,y:int,color:tuple[int,int,int,int]) -> None:
        i=(y*self.width+x)*4
        self.pixels[i:i+4]=bytes(max(0,min(255,int(c))) for c in color)

    def get(self,x:int,y:int)->tuple[int,int,int,int]:
        i=(y*self.width+x)*4
        return tuple(self.pixels[i:i+4])


def _png_chunk(kind: bytes,data: bytes)->bytes:
    return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data)&0xffffffff)


def encode_png(image: PixelImage)->bytes:
    raw=bytearray()
    row_bytes=image.width*4
    for y in range(image.height):
        raw.append(0)
        start=y*row_bytes
        raw.extend(image.pixels[start:start+row_bytes])
    ihdr=struct.pack(">IIBBBBB",image.width,image.height,8,6,0,0,0)
    return b"\x89PNG\r\n\x1a\n"+_png_chunk(b"IHDR",ihdr)+_png_chunk(b"IDAT",zlib.compress(bytes(raw),7))+_png_chunk(b"IEND",b"")


def write_texture_pair(texture_dir: Path,name:str,image:PixelImage,*,compression="DXT1",write_png=True)->dict:
    from .dds import encode_dds
    texture_dir=Path(texture_dir)
    texture_dir.mkdir(parents=True,exist_ok=True)
    dds_path=texture_dir/f"{name}.dds"
    dds_path.write_bytes(encode_dds(image))
    result={"name":name,"width":image.width,"height":image.height,
            "dds":str(dds_path).replace("\\","/"),"format":compression}
    if write_png:
        png_path=texture_dir/f"{name}.png"
        png_path.write_bytes(encode_png(image))
        result["png"]=str(png_path).replace("\\","/")
    return result


def _hash_noise(x:int,y:int,seed:int)->float:
    n=(x*374761393+y*668265263+seed*1442695041)&0xffffffff
    n=(n^(n>>13))*1274126177&0xffffffff
    n^=n>>16
    return (n&0xffff)/65535.0


def _value_noise(x:float,y:float,seed:int,scale:int)->float:
    gx=x/scale;gy=y/scale
    ix=int(math.floor(gx));iy=int(math.floor(gy));fx=gx-ix;fy=gy-iy
    sx=fx*fx*(3-2*fx);sy=fy*fy*(3-2*fy)
    a=_hash_noise(ix,iy,seed);b=_hash_noise(ix+1,iy,seed)
    c=_hash_noise(ix,iy+1,seed);d=_hash_noise(ix+1,iy+1,seed)
    return (a*(1-sx)+b*sx)*(1-sy)+(c*(1-sx)+d*sx)*sy


def _segment_distance(px,py,a,b):
    dx=b[0]-a[0];dy=b[1]-a[1]
    denom=dx*dx+dy*dy
    t=0.0 if denom<1e-9 else max(0,min(1,((px-a[0])*dx+(py-a[1])*dy)/denom))
    return math.hypot(px-(a[0]+t*dx),py-(a[1]+t*dy))


def _boxes(size:int,seed:int,count:int,kind:str):
    rng=random.Random(seed)
    result=[]
    for _ in range(count):
        x=rng.randrange(size);y=rng.randrange(size)
        w=rng.randrange(max(3,size//45),max(5,size//9))
        h=rng.randrange(max(3,size//70),max(5,size//12))
        result.append((x,y,w,h,rng.uniform(.55,.86)))
    return result


def _cracks(size:int,seed:int,count:int):
    rng=random.Random(seed)
    result=[]
    for _ in range(count):
        x=rng.randrange(size);y=rng.randrange(size)
        angle=rng.uniform(0,math.pi*2);length=rng.uniform(size*.025,size*.16)
        points=[(x,y)]
        for i in range(1,5):
            t=i/4
            jitter=rng.uniform(-size*.012,size*.012)
            points.append((x+math.cos(angle)*length*t-math.sin(angle)*jitter,
                           y+math.sin(angle)*length*t+math.cos(angle)*jitter))
        result.extend((points[i],points[i+1],rng.uniform(.45,1.4)) for i in range(len(points)-1))
    return result


def _base_color(spec:MaterialSpec,x:int,y:int,size:int,seed:int,patches,cracks):
    pat=spec.pattern
    macro=_value_noise(x,y,seed,48)
    mid=_value_noise(x,y,seed+41,13)
    fine=_hash_noise(x,y,seed+11)-.5
    grain=(macro-.5)*24+(mid-.5)*12+fine*12
    r,g,b=spec.base_color
    h=128.0
    puddle=0.0
    if pat=="asphalt":
        # Crushed aggregate grain, old repair patches, faint rubber tracks,
        # oil discolouration and an irregular puddle response mask.
        patch=0.0
        for px,py,pw,ph,shade in patches:
            dx=min((x-px)%size,(px-x)%size)
            dy=min((y-py)%size,(py-y)%size)
            if dx<pw and dy<ph and _value_noise(x,y,seed+91,5)>.31:
                patch=max(patch,1.0-shade)
        crack=0.0
        for a,c,width in cracks:
            d=min(_segment_distance(x,y,a,c),
                  _segment_distance(x-size,y,a,c),_segment_distance(x+size,y,a,c))
            if d<width:
                crack=max(crack,1.0-d/max(width,.01))
        wear=(math.exp(-((y-size*.43)/(size*.025))**2)+math.exp(-((y-size*.73)/(size*.03))**2))*.11
        puddle=max(0.0,(_value_noise(x,y,seed+18,33)-.73)*3.4)
        oil=max(0.0,(_value_noise(x+73,y-42,seed+121,24)-.76)*2.1)
        grain-=patch*14+crack*52+wear*10+oil*18
        grain*=1.0-puddle*.24
        h=128+(macro-.5)*45+(mid-.5)*22-crack*70+patch*18
    elif pat=="concrete":
        seam_x=(x%(size//4+1));seam_y=(y%(size//4+1))
        seam=1.0 if seam_x<2 or seam_y<2 else 0.0
        grain-=seam*20
        h=128+(macro-.5)*26+(mid-.5)*18-seam*28
    elif pat=="brick":
        row_h=max(8,size//12);brick_w=max(12,size//5)
        row=(y//row_h);offset=(brick_w//2 if row%2 else 0)
        gx=(x+offset)%brick_w;gy=y%row_h
        mortar= gx<2 or gy<2
        brick_noise=_value_noise(x,y,seed+5,9)-.5
        grain+=brick_noise*24-(27 if mortar else 0)
        h=128+(18 if mortar else -7)+(brick_noise*30)
    elif pat=="glass":
        band=.5+.5*math.sin((x/size)*math.pi*14+macro*2)
        glare=max(0,math.sin((x+y*.13)/size*math.pi*8))*10
        grain=(macro-.5)*11+(mid-.5)*7+fine*4+band*9+glare
        r,g,b=58,77,87
        h=128+(macro-.5)*3
    elif pat=="painted_concrete":
        grain+=(_value_noise(x,y,seed+82,22)-.5)*10
        h=128+(macro-.5)*12+(mid-.5)*8
    elif pat=="metal" or pat=="painted_metal":
        brush=math.sin(y*.12+macro*3)*4
        grain+=(macro-.5)*9+brush
        h=128+(macro-.5)*8
    elif pat=="roof":
        shingle=((x+((y//12)%2)*16)%32<2 or y%12<2)
        grain-=22 if shingle else 0
        h=128+(macro-.5)*30-(28 if shingle else 0)
    elif pat=="grass" or pat=="leaves":
        grain+=(mid-.5)*18+(macro-.5)*16
        if pat=="leaves":
            grain+=(.5-_value_noise(x*1.4,y*.8,seed+63,8))*18
        h=128+(macro-.5)*70+(mid-.5)*35
    elif pat=="soil":
        grain+=(macro-.5)*20+(mid-.5)*16
        h=128+(macro-.5)*52+(mid-.5)*30
    elif pat=="sand":
        grain+=(mid-.5)*15+(fine)*7
        h=128+(macro-.5)*23+(mid-.5)*28
    elif pat=="road_marking":
        grain+=(macro-.5)*12+(fine)*10
        h=128+(macro-.5)*10
    elif pat=="wood":
        grain+=math.sin((x+y*.14)*.11+macro)*14+(macro-.5)*15
        h=128+(macro-.5)*20
    elif pat=="stone":
        grain+=(macro-.5)*24+(mid-.5)*13
        h=128+(macro-.5)*44+(mid-.5)*24
    elif pat=="window_dark":
        r,g,b=29,43,50
        grain+=(macro-.5)*16+max(0,math.sin(x/size*math.pi*8))*10
        h=128+(macro-.5)*2
    elif pat=="window_warm":
        r,g,b=161,126,80
        grain+=(macro-.5)*15+(mid-.5)*8
        h=128+(macro-.5)*2
    elif pat=="window_cool":
        r,g,b=77,112,133
        grain+=(macro-.5)*18+math.sin(x/size*math.pi*9)*8
        h=128+(macro-.5)*2
    elif pat=="sign":
        grain+=(macro-.5)*5
        h=128
    elif pat=="water":
        grain+=(mid-.5)*13+math.sin(y*.08+macro*4)*5
        h=128+(mid-.5)*3
    elif pat=="emissive":
        grain+=(macro-.5)*3
        h=128
    r=int(max(0,min(255,r+grain)));g=int(max(0,min(255,g+grain*.94)));b=int(max(0,min(255,b+grain*.88)))
    if pat=="brick":
        mortar=(x%(max(12,size//5))<2 or y%(max(8,size//12))<2)
        if mortar:
            r=max(0,r-18);g=max(0,g-17);b=max(0,b-15)
    if pat=="asphalt" and puddle>.2:
        r=int(r*(1-.24*puddle));g=int(g*(1-.24*puddle));b=int(b*(1-.24*puddle))
    return (r,g,b,255),max(0,min(255,int(h))),puddle


def _generate_material(spec:MaterialSpec,size:int,seed:int):
    albedo=PixelImage(size,size);height=PixelImage(size,size);rough=PixelImage(size,size);specular=PixelImage(size,size);mask=PixelImage(size,size)
    patches=_boxes(size,seed,18,"patch") if spec.pattern=="asphalt" else []
    cracks=_cracks(size,seed+7,7) if spec.pattern=="asphalt" else []
    rough_base=int(max(20,min(250,spec.roughness*255)))
    spec_base=int(max(4,min(235,spec.specular*255)))
    heights=bytearray(size*size)
    puddles=bytearray(size*size)
    for y in range(size):
        for x in range(size):
            color,h,puddle=_base_color(spec,x,y,size,seed,patches,cracks)
            albedo.set(x,y,color)
            heights[y*size+x]=h
            puddles[y*size+x]=int(max(0,min(255,puddle*255)))
            micro=_hash_noise(x,y,seed+333)-.5
            rv=rough_base+int(micro*22)
            sv=spec_base+int((.5-micro)*18)
            if spec.pattern=="asphalt" and puddle>.05:
                rv=int(rv*(1-puddle*.88)+22*puddle*.88)
                sv=int(sv*(1-puddle*.25)+165*puddle*.25)
            rough.set(x,y,(rv,rv,rv,255))
            specular.set(x,y,(sv,sv,sv,255))
            mask.set(x,y,(puddles[y*size+x],)*3+(255,))
            height.set(x,y,(h,h,h,255))
    normal=PixelImage(size,size)
    scale=1.7 if spec.pattern in ("asphalt","stone","brick") else .75
    for y in range(size):
        for x in range(size):
            hL=heights[y*size+max(0,x-1)];hR=heights[y*size+min(size-1,x+1)]
            hD=heights[max(0,y-1)*size+x];hU=heights[min(size-1,y+1)*size+x]
            nx=(hL-hR)/255*scale;ny=(hD-hU)/255*scale;nz=1.0
            nlen=math.sqrt(nx*nx+ny*ny+nz*nz)
            rgb=(int((nx/nlen*.5+.5)*255),int((ny/nlen*.5+.5)*255),int((nz/nlen*.5+.5)*255),255)
            normal.set(x,y,rgb)
    return {"albedo":albedo,"normal":normal,"specular":specular,"roughness":rough,"height":height,"mask":mask}


ALBEDO_SIZE={"asphalt":1024,"concrete":512,"sidewalk":512,"brick":512,"glass":512,
             "roof":512,"grass":512,"road_marking":256,"water":256}


def build_material_textures(texture_dir:Path)->tuple[list[dict],dict[str,PixelImage]]:
    texture_dir=Path(texture_dir);texture_dir.mkdir(parents=True,exist_ok=True)
    records=[];albedos={}
    for index,spec in enumerate(MATERIALS.values()):
        size=ALBEDO_SIZE.get(spec.key,256)
        maps=_generate_material(spec,size,271+index*7919)
        asset_base=spec.texture
        # The DFF/TXD albedo naming is deliberately short (<=31 chars).
        albedo_record=write_texture_pair(texture_dir,asset_base,maps["albedo"],write_png=True)
        albedo_record.update({"material":spec.key,"map":"albedo","texture_name":spec.texture})
        records.append(albedo_record)
        albedos[spec.texture]=maps["albedo"]
        map_size=min(size,512)
        for map_name,suffix in (("normal","_n"),("specular","_s"),("roughness","_r"),("height","_h"),("mask","_m")):
            image=maps[map_name]
            if map_size<size:
                # Fixed deterministic nearest sample for auxiliary maps.
                reduced=PixelImage(map_size,map_size)
                for y in range(map_size):
                    for x in range(map_size):
                        sx=int(x*size/map_size);sy=int(y*size/map_size)
                        reduced.set(x,y,image.get(sx,sy))
                image=reduced
            rec=write_texture_pair(texture_dir,asset_base+suffix,image,write_png=False)
            rec.update({"material":spec.key,"map":map_name})
            records.append(rec)
    return records,albedos
