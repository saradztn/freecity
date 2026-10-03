"""Texture noise assets used by the DX9 weather/material approximations."""
from __future__ import annotations
import math
from .textures import PixelImage, write_texture_pair


def make_noise_image(size: int=128, seed: int=41) -> PixelImage:
    image=PixelImage(size,size)
    state=seed & 0xffffffff
    coarse=[]
    for y in range(32):
        row=[]
        for x in range(32):
            state=(1664525*state+1013904223)&0xffffffff
            row.append((state>>24)&255)
        coarse.append(row)
    for y in range(size):
        for x in range(size):
            gx=x*31/(size-1);gy=y*31/(size-1)
            ix,iy=int(gx),int(gy);fx,fy=gx-ix,gy-iy
            x2=min(31,ix+1);y2=min(31,iy+1)
            sx=fx*fx*(3-2*fx);sy=fy*fy*(3-2*fy)
            v0=coarse[iy][ix]*(1-sx)+coarse[iy][x2]*sx
            v1=coarse[y2][ix]*(1-sx)+coarse[y2][x2]*sx
            v=int(v0*(1-sy)+v1*sy)
            image.set(x,y,(v,v,v,255))
    return image


def make_cloud_image(size: int=256, seed: int=80) -> PixelImage:
    image=make_noise_image(size,seed)
    # Raise the contrast into soft cloud masses but keep broad gradients.
    for y in range(size):
        for x in range(size):
            r,g,b,a=image.get(x,y)
            v=max(0,min(255,int((r-118)*1.45+126)))
            image.set(x,y,(v,v,v,255))
    return image


def build_weather_textures(texture_dir) -> list[dict]:
    records=[]
    for name,image in (("weather_noise",make_noise_image()),("cloud_noise",make_cloud_image())):
        records.append(write_texture_pair(texture_dir,name,image,compression="DXT1",write_png=True))
    return records
