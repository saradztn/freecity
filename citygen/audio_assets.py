"""Small deterministic thunder one-shots; native GTA weather supplies rain ambience."""
from __future__ import annotations
import math
import random
import struct
import wave
from pathlib import Path


def write_thunder(path:Path,seed:int,duration:float=3.6,rate:int=22050)->None:
    rng=random.Random(seed);count=int(duration*rate);low=0.0;mid=0.0;pcm=bytearray()
    for i in range(count):
        t=i/rate;white=rng.uniform(-1.0,1.0)
        low+=.018*(white-low);mid+=.11*(white-mid)
        slow=max(0.0,math.sin((t*.37+seed*.17)*2*math.pi))**5
        crackle=rng.uniform(-1,1) if rng.random()<.0007 else 0.0
        onset=math.exp(-max(0,t-.32)*1.7) if t>.32 else .08
        distant=math.exp(-max(0,t-1.5)*1.1) if t>1.5 else .15
        sample=(low*.68+mid*.24+white*.08)*(.16+slow*.42)*onset*distant+crackle*.18
        fade=min(1.0,t/.2,max(0.0,(duration-t)/.5));sample=max(-1,min(1,sample*fade))
        pcm.extend(struct.pack("<h",int(sample*23000)))
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),"wb") as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(rate);wav.writeframes(pcm)
