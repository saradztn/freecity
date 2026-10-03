"""Dependency-free DDS/DXT1 writer used for MTA/DX9 texture assets."""
from __future__ import annotations
import struct
from .textures import PixelImage


def _rgb565(rgb: tuple[int,int,int]) -> int:
    r,g,b=rgb
    return ((r*31+127)//255<<11)|((g*63+127)//255<<5)|((b*31+127)//255)


def _unpack565(value: int) -> tuple[int,int,int]:
    r=(value>>11)&31;g=(value>>5)&63;b=value&31
    return (r*255//31,g*255//63,b*255//31)


def _encode_block(pixels: list[tuple[int,int,int]]) -> bytes:
    # Bounding-box endpoints are stable, cheap, and suitable for tiled
    # grayscale/stone/asphalt content. Transparent blocks are not used by BC1.
    lo=tuple(min(p[i] for p in pixels) for i in range(3))
    hi=tuple(max(p[i] for p in pixels) for i in range(3))
    c0,c1=_rgb565(hi),_rgb565(lo)
    if c0<c1:
        c0,c1=c1,c0
    if c0==c1:
        c0=min(0xffff,c0+1)
    p0,p1=_unpack565(c0),_unpack565(c1)
    palette=(p0,p1,tuple((2*p0[i]+p1[i])//3 for i in range(3)),tuple((p0[i]+2*p1[i])//3 for i in range(3)))
    bits=0
    for idx,p in enumerate(pixels):
        best=min(range(4),key=lambda j:sum((p[k]-palette[j][k])**2 for k in range(3)))
        bits|=best<<(2*idx)
    return struct.pack("<HHI",c0,c1,bits)


def encode_bc1(image: PixelImage) -> bytes:
    out=bytearray()
    width,height=image.width,image.height
    for by in range(0,height,4):
        for bx in range(0,width,4):
            block=[]
            for y in range(4):
                py=min(height-1,by+y)
                for x in range(4):
                    px=min(width-1,bx+x)
                    r,g,b,_=image.get(px,py)
                    block.append((r,g,b))
            out.extend(_encode_block(block))
    return bytes(out)


def downsample(image: PixelImage) -> PixelImage:
    w=max(1,image.width//2);h=max(1,image.height//2)
    out=PixelImage(w,h)
    for y in range(h):
        for x in range(w):
            samples=[image.get(min(image.width-1,x*2+dx),min(image.height-1,y*2+dy)) for dy in (0,1) for dx in (0,1)]
            out.set(x,y,tuple(sum(s[i] for s in samples)//4 for i in range(4)))
    return out


def mip_chain(image: PixelImage) -> list[PixelImage]:
    result=[image]
    current=image
    while current.width>1 or current.height>1:
        current=downsample(current)
        result.append(current)
    return result


def dds_header(width: int,height: int,mip_count: int,base_size: int) -> bytes:
    flags=0x1|0x2|0x4|0x1000|0x80000
    if mip_count>1:
        flags|=0x20000
    pf=(32,0x4,0x31545844,0,0,0,0,0)
    caps=0x1000
    if mip_count>1:
        caps|=0x8|0x400000
    caps_rest=(0,0,0,0)
    fields=(124,flags,height,width,base_size,0,mip_count)+((0,)*11)+pf+(caps,)+caps_rest
    return b"DDS "+struct.pack("<31I",*fields)


def encode_dds(image: PixelImage) -> bytes:
    levels=mip_chain(image)
    blocks=[encode_bc1(level) for level in levels]
    data=b"".join(blocks)
    header=dds_header(image.width,image.height,len(levels),len(blocks[0]))
    return header+data
