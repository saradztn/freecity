"""Generated sun disc and light halo textures (alpha PNG plus compact DDS)."""
from __future__ import annotations
import math
from .textures import PixelImage, write_texture_pair


def radial_sprite(size:int,*,disc:bool=False)->PixelImage:
    image=PixelImage(size,size);c=(size-1)*.5;radius=size*.5
    for y in range(size):
        for x in range(size):
            r=math.hypot(x-c,y-c)/radius
            if disc:
                core=max(0.0,1.0-r/.48);edge=max(0.0,1.0-r)
                alpha=int(255*min(1.0,core*.78+edge*.22));intensity=.75+.25*core
            else:
                alpha=int(105*max(0.0,1-r)**2.1);intensity=max(0.0,1-r)
            image.set(x,y,(int(255*intensity),int(238*intensity),int(205*intensity),alpha))
    return image


def build_lighting_textures(texture_dir)->list[dict]:
    return [write_texture_pair(texture_dir,"sun_disc",radial_sprite(128,disc=True),write_png=True),
            write_texture_pair(texture_dir,"light_halo",radial_sprite(128),write_png=True)]
