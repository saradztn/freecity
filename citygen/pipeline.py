"""Deterministic vertical-slice orchestration and RenderWare asset export."""
from __future__ import annotations
import json
import math
import struct
from pathlib import Path

from .audio_assets import write_thunder
from .bridges import add_bridge
from .buildings import build_building
from .collision import CollisionMesh
from .config import CityConfig, DEFAULT_CONFIG
from .districts import ZONES, build_placements
from .highways import add_highway_details
from .infrastructure import build_infrastructure
from .intersections import add_intersections
from .landuse import build_land_use
from .lighting_assets import build_lighting_textures
from .materials import MATERIALS
from .mesh import Face, Mesh, Vertex
from .registry import AssetRegistry
from .renderware import write_col3, write_dff, write_txd
from .road_graph import RoadGraph, build_vertical_slice_graph
from .roads import build_roads
from .terrain import Terrain
from .textures import build_material_textures
from .tunnels import add_tunnel
from .vegetation import build_vegetation, build_vegetation_lod
from .weather_assets import build_weather_textures

ROOT=Path(__file__).resolve().parents[1]


def _rotated_size(width:float,depth:float,rotation:float)->tuple[float,float]:
    if int(round(rotation/90.0))%2:
        return depth,width
    return width,depth


def _placement_box(placement):
    w,d=_rotated_size(placement.width,placement.depth,placement.rotation)
    return (placement.x-w*.5,placement.y-d*.5,placement.x+w*.5,placement.y+d*.5)


def _point_box_distance(x:float,y:float,box)->float:
    x0,y0,x1,y1=box
    dx=max(x0-x,0.0,x-x1);dy=max(y0-y,0.0,y-y1)
    return math.hypot(dx,dy)


def validate_layout(graph:RoadGraph,terrain:Terrain,placements,features)->dict:
    errors=[];warnings=[]
    components=graph.connected_components()
    if len(components)!=1:
        errors.append(f"road graph has {len(components)} connected components")
    for seg in graph.segments.values():
        if seg.lanes<1 or seg.speed_kph<=0:
            errors.append(f"invalid lane/speed data on {seg.id}")
        if seg.start not in graph.nodes or seg.end not in graph.nodes:
            errors.append(f"road {seg.id} references a missing node")
        if seg.approximate_length(graph)<3.0:
            errors.append(f"road {seg.id} is implausibly short")
    feature_boxes=[(tuple(f["bounds"]),f["id"]) for f in features]
    for box,fid in feature_boxes:
        for seg in graph.segments.values():
            threshold=seg.paved_width*.5+(2.2 if seg.kind not in ("highway","ramp","bridge","tunnel") else 0.0)
            if any(_point_box_distance(x,y,box)<threshold for x,y,_ in seg.sample_xy(graph,spacing=3.0)):
                errors.append(f"land-use feature {fid} intersects road envelope {seg.id}")
    building_boxes=[]
    for placement in placements:
        box=_placement_box(placement)
        building_boxes.append((box,placement))
        if not terrain.inside_land(placement.x,placement.y):
            errors.append(f"{placement.id} is outside the island land mask")
        angle=math.radians(placement.rotation);c,s=math.cos(angle),math.sin(angle)
        footprint_heights=[]
        for dx in (-placement.width*.5,placement.width*.5):
            for dy in (-placement.depth*.5,placement.depth*.5):
                px=placement.x+dx*c-dy*s;py=placement.y+dx*s+dy*c
                footprint_heights.append(terrain.height(px,py))
        if max(footprint_heights)-min(footprint_heights)>.20:
            errors.append(f"{placement.id} building pad is not level")
        for fbox,fid in feature_boxes:
            if _boxes_overlap(box,fbox):
                errors.append(f"{placement.id} overlaps land-use feature {fid}")
        # Measure the road's centerline against the actual rotated footprint;
        # grade-separated freeway segments are exempt when clear above the roof.
        near=[]
        for seg in graph.segments.values():
            if seg.kind in ("highway","ramp"):
                road_z=seg.fixed_z if seg.fixed_z is not None else 18.0
                roof=terrain.height(placement.x,placement.y)+placement.height+2.2
                base=terrain.height(placement.x,placement.y)
                if road_z>roof+1.0 or road_z<base-1.0:
                    continue
            if seg.kind in ("bridge","tunnel"):
                # Their surfaces are evaluated separately from ordinary streets.
                pass
            threshold=seg.paved_width*.5+(2.2 if seg.kind not in ("highway","ramp","bridge","tunnel") else 0.0)
            for x,y,_ in seg.sample_xy(graph,spacing=4.0):
                if _point_box_distance(x,y,box)<threshold:
                    near.append(seg.id)
                    break
        if near:
            errors.append(f"{placement.id} intersects road envelope(s): {', '.join(near[:5])}")
    for i,(abox,a) in enumerate(building_boxes):
        for bbox,b in building_boxes[i+1:]:
            if _boxes_overlap(abox,bbox):
                errors.append(f"building footprints overlap: {a.id} / {b.id}")
    return {"ok":not errors,"errors":errors,"warnings":warnings,
            "nodes":len(graph.nodes),"roads":len(graph.segments),
            "connectedComponents":len(components),"buildings":len(placements)}


def _boxes_overlap(a,b)->bool:
    return a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]


def grade_city_parcels(terrain:Terrain,placements,features)->None:
    """Add flat build pads before terrain/building/parking meshes are emitted."""
    for placement in placements:
        terrain.add_flat_pad(placement.x,placement.y,placement.width,placement.depth,
                             rotation=placement.rotation,elevation=terrain.raw_height(placement.x,placement.y),
                             blend_distance=4.0,name=placement.id)
    for feature in features:
        if feature["kind"]=="surface_parking":
            x0,y0,x1,y1=feature["bounds"]
            cx,cy=(x0+x1)*.5,(y0+y1)*.5
            terrain.add_flat_pad(cx,cy,x1-x0,y1-y0,
                                 elevation=terrain.raw_height(cx,cy),blend_distance=4.0,name=feature["id"])


def _tile_index(x:float,y:float,config:CityConfig)->tuple[int,int]:
    gx=int(math.floor((x-config.world_min)/config.tile_size))
    gy=int(math.floor((y-config.world_min)/config.tile_size))
    gx=max(0,min(config.tiles_per_axis-1,gx))
    gy=max(0,min(config.tiles_per_axis-1,gy))
    return gx,gy


def _split_mesh(mesh:Mesh,config:CityConfig)->dict[tuple[int,int],Mesh]:
    bins={(gx,gy):Mesh() for gy in range(config.tiles_per_axis) for gx in range(config.tiles_per_axis)}
    centers={(gx,gy):(config.world_min+(gx+.5)*config.tile_size,
                       config.world_min+(gy+.5)*config.tile_size)
             for gy in range(config.tiles_per_axis) for gx in range(config.tiles_per_axis)}
    vertex_maps={(gx,gy):{} for gy in range(config.tiles_per_axis) for gx in range(config.tiles_per_axis)}
    for face in mesh.faces:
        source_ids=(face.a,face.b,face.c)
        pts=[mesh.vertices[i].position for i in source_ids]
        cx=sum(p[0] for p in pts)/3;cy=sum(p[1] for p in pts)/3
        key=_tile_index(cx,cy,config)
        target=bins[key];mapping=vertex_maps[key]
        local_ids=[]
        tile_x,tile_y=centers[key]
        for source_id in source_ids:
            if source_id not in mapping:
                vertex=mesh.vertices[source_id]
                local_position=(vertex.position[0]-tile_x,vertex.position[1]-tile_y,vertex.position[2])
                mapping[source_id]=len(target.vertices)
                target.vertices.append(Vertex(local_position,vertex.normal,vertex.uv,vertex.color))
            local_ids.append(mapping[source_id])
        target.faces.append(Face(local_ids[0],local_ids[1],local_ids[2],face.material))
    return bins


def _split_collision(mesh:CollisionMesh,config:CityConfig)->dict[tuple[int,int],CollisionMesh]:
    bins={(gx,gy):CollisionMesh() for gy in range(config.tiles_per_axis) for gx in range(config.tiles_per_axis)}
    centers={(gx,gy):(config.world_min+(gx+.5)*config.tile_size,
                       config.world_min+(gy+.5)*config.tile_size)
             for gy in range(config.tiles_per_axis) for gx in range(config.tiles_per_axis)}
    for face in mesh.faces:
        pts=[mesh.vertices[i] for i in (face.a,face.b,face.c)]
        key=_tile_index(sum(p[0] for p in pts)/3,sum(p[1] for p in pts)/3,config)
        cx,cy=centers[key]
        local=[(p[0]-cx,p[1]-cy,p[2]) for p in pts]
        bins[key].add_triangle(*local,surface=face.surface,light=face.light)
    return bins


def _tile_label(ix:int,iy:int)->str:
    def part(v): return f"m{abs(v)}" if v<0 else f"p{v}"
    return f"{part(ix)}_{part(iy)}"


def _relative(path:Path,resource_dir:Path)->str:
    return path.resolve().relative_to(resource_dir.resolve()).as_posix()


def _write_json(path:Path,value)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")


def _build_meshes(config:CityConfig,graph:RoadGraph,terrain:Terrain,placements,features,seed:int):
    high=Mesh();low=Mesh();collision=CollisionMesh()
    # Ground, drivable ribbons, collision, intersection fans and land-use.
    ground,ground_collision=terrain.mesh(lod=False)
    high.append(ground);collision.extend(ground_collision)
    low_ground,_=terrain.mesh(lod=True);low.append(low_ground)
    roads,road_collision=build_roads(graph,terrain,lod=False)
    high.append(roads);collision.extend(road_collision)
    low_roads,_=build_roads(graph,terrain,lod=True);low.append(low_roads)
    intersection_mesh=Mesh();intersection_collision=CollisionMesh()
    intersection_records=add_intersections(intersection_mesh,intersection_collision,graph,terrain.height)
    high.append(intersection_mesh);collision.extend(intersection_collision)
    low_intersections=Mesh();low_intersection_collision=CollisionMesh()
    add_intersections(low_intersections,low_intersection_collision,graph,terrain.height)
    low.append(low_intersections)
    land_mesh,land_collision,land_records=build_land_use(features,terrain,seed,lod=False)
    high.append(land_mesh);collision.extend(land_collision)
    low_land,_,_=build_land_use(features,terrain,seed,lod=True);low.append(low_land)

    # Buildings are merged per tile, but each placement still has an individual
    # deterministic seed, archetype, facade, and conservative collision shell.
    for placement in placements:
        mesh,building_collision=build_building(placement,terrain,lod=False)
        high.append(mesh);collision.extend(building_collision)
        low_mesh,_=build_building(placement,terrain,lod=True)
        low.append(low_mesh)

    infrastructure,infra_collision,lights=build_infrastructure(graph,terrain,seed,lod=False)
    high.append(infrastructure);collision.extend(infra_collision)
    low_infra,_,_=build_infrastructure(graph,terrain,seed,lod=True);low.append(low_infra)

    blocked=[]
    for placement in placements:
        x0,y0,x1,y1=_placement_box(placement)
        blocked.append((x0-6.0,y0-6.0,x1+6.0,y1+6.0))
    for feature in features:
        if feature["kind"]=="surface_parking":
            x0,y0,x1,y1=feature["bounds"]
            blocked.append((x0-6.0,y0-6.0,x1+6.0,y1+6.0))
    vegetation,veg_collision,tree_records=build_vegetation(seed,graph,terrain,lod=False,blocked_areas=blocked)
    high.append(vegetation);collision.extend(veg_collision)
    low.append(build_vegetation_lod(tree_records))

    highway_mesh=Mesh();highway_collision=CollisionMesh()
    highway_signs=add_highway_details(highway_mesh,graph,terrain.raw_height,highway_collision)
    high.append(highway_mesh);collision.extend(highway_collision)
    low_highway=Mesh();low_highway_collision=CollisionMesh()
    add_highway_details(low_highway,graph,terrain.raw_height,low_highway_collision)
    low.append(low_highway)

    for segment in graph.segments.values():
        if segment.kind=="bridge":
            bridge_mesh=Mesh();bridge_collision=CollisionMesh()
            add_bridge(bridge_mesh,bridge_collision,segment,graph,terrain.raw_height)
            high.append(bridge_mesh);collision.extend(bridge_collision)
            low_bridge=Mesh();low_bridge_collision=CollisionMesh()
            add_bridge(low_bridge,low_bridge_collision,segment,graph,terrain.raw_height)
            low.append(low_bridge)
        elif segment.kind=="tunnel" and segment.alignment!="ramp":
            tunnel_mesh=Mesh();tunnel_collision=CollisionMesh()
            add_tunnel(tunnel_mesh,tunnel_collision,segment,graph,terrain)
            high.append(tunnel_mesh);collision.extend(tunnel_collision)
            low_tunnel=Mesh();low_tunnel_collision=CollisionMesh()
            add_tunnel(low_tunnel,low_tunnel_collision,segment,graph,terrain)
            low.append(low_tunnel)
    return high,low,collision,{"intersections":intersection_records,"landUse":land_records,
                               "lights":lights,"trees":tree_records,"highwaySigns":highway_signs}


def _scan_existing_textures(texture_dir:Path)->list[dict]:
    records=[]
    known={}
    for spec in MATERIALS.values():
        known[spec.texture]=(spec.key,"albedo")
        for map_name,suffix in (("normal","_n"),("specular","_s"),("roughness","_r"),("height","_h"),("mask","_m")):
            known[spec.texture+suffix]=(spec.key,map_name)
    for path in sorted(texture_dir.glob("*.dds")):
        header=path.read_bytes()[:128]
        if len(header)<128 or header[:4]!=b"DDS ":
            raise ValueError(f"invalid DDS while reusing textures: {path}")
        height,width=struct.unpack_from("<II",header,12)
        record={"name":path.stem,"width":width,"height":height,
                "dds":str(path),"format":"DXT1"}
        if path.stem in known:
            record["material"],record["map"]=known[path.stem]
        png=path.with_suffix(".png")
        if png.is_file():record["png"]=str(png)
        records.append(record)
    if not records:
        raise ValueError(f"no reusable DDS textures in {texture_dir}")
    required={spec.texture for spec in MATERIALS.values()}
    required.update(spec.texture+suffix for spec in MATERIALS.values()
                    for suffix in ("_n","_s","_r","_h","_m"))
    required.update(("weather_noise","cloud_noise","sun_disc","light_halo"))
    missing=sorted(required-{record["name"] for record in records})
    if missing:
        raise ValueError("reusable texture set is incomplete: "+", ".join(missing))
    return records


def _write_meta(resource_dir:Path,file_paths:list[str],config:CityConfig)->None:
    fixed_scripts=[
        ("client/main.lua","client"),("client/streaming.lua","client"),
        ("client/environment.lua","client"),("client/ui.lua","client"),
        ("server/main.lua","server"),
    ]
    lines=["<meta>",
           f'    <info author="Freecity Procedural Pipeline" name="{config.name}" version="0.1.0" type="script" />',
           '    <min_mta_version server="1.6.0-9.22678.0" client="1.6.0-9.22678.0" />']
    for script,kind in fixed_scripts:
        lines.append(f'    <script src="{script}" type="{kind}" cache="false" />')
    for src in sorted(set(file_paths)):
        lines.append(f'    <file src="{src}" />')
    lines.append("</meta>")
    (resource_dir/"meta.xml").write_text("\n".join(lines)+"\n",encoding="utf-8")


def build_city(config:CityConfig=DEFAULT_CONFIG,resource_dir:Path|None=None,*,clean:bool=False,reuse_generated:bool=False)->dict:
    """Generate all assets; optional reuse skips expensive texture/audio baking.

    ``reuse_generated`` is intended for interrupted/repeated builds and verifies
    existing DDS/TXD files rather than silently accepting missing inputs.
    """
    if clean and reuse_generated:
        raise ValueError("clean and reuse_generated cannot be combined")
    resource_dir=Path(resource_dir or ROOT/"resource"/"fc_city").resolve()
    resource_dir.mkdir(parents=True,exist_ok=True)
    model_dir=resource_dir/"models";texture_dir=resource_dir/"textures";data_dir=resource_dir/"data"
    model_dir.mkdir(parents=True,exist_ok=True);texture_dir.mkdir(parents=True,exist_ok=True);data_dir.mkdir(parents=True,exist_ok=True)
    previous_manifest=data_dir/"build_manifest.json"
    if clean and previous_manifest.exists():
        try:
            previous=json.loads(previous_manifest.read_text(encoding="utf-8"))
            for rel in previous.get("generatedFiles",[]):
                target=(resource_dir/rel).resolve()
                if resource_dir.resolve() in target.parents and target.is_file():
                    target.unlink()
        except (OSError,json.JSONDecodeError,TypeError):
            pass

    graph=build_vertical_slice_graph()
    terrain=Terrain(config.seed,graph,step=config.terrain_step,extent=config.world_max)
    placements,features=build_placements(config.seed,graph)
    grade_city_parcels(terrain,placements,features)
    layout=validate_layout(graph,terrain,placements,features)
    if not layout["ok"]:
        raise ValueError("layout validation failed: "+"; ".join(layout["errors"]))

    high,low,collision,records=_build_meshes(config,graph,terrain,placements,features,config.seed)
    total_visual_triangles=high.triangle_count+low.triangle_count
    if total_visual_triangles>config.triangle_budget:
        raise ValueError(f"visual triangle budget exceeded: {total_visual_triangles} > {config.triangle_budget}")

    high_tiles=_split_mesh(high,config);low_tiles=_split_mesh(low,config);col_tiles=_split_collision(collision,config)
    tile_runtime=[];asset_records=[];generated_files=[]
    registry=AssetRegistry(resource_dir)
    for ix,iy,cx,cy in config.tile_centers:
        gx,gy=ix+config.tiles_per_axis//2,iy+config.tiles_per_axis//2
        key=(gx,gy);label=_tile_label(ix,iy)
        hi_mesh=high_tiles[key];lo_mesh=low_tiles[key];col_mesh=col_tiles[key]
        stem=f"fc_tile_{label}"
        hi_path=model_dir/f"{stem}_hi.dff";lo_path=model_dir/f"{stem}_lo.dff"
        hi_info=write_dff(hi_mesh,hi_path,f"{stem}_hi")
        lo_info=write_dff(lo_mesh,lo_path,f"{stem}_lo")
        hi_info["path"]=_relative(hi_path,resource_dir)
        lo_info["path"]=_relative(lo_path,resource_dir)
        generated_files.extend((_relative(hi_path,resource_dir),_relative(lo_path,resource_dir)))
        col_path=None;col_info=None
        if col_mesh.faces:
            col_path=model_dir/f"{stem}.col"
            col_info=write_col3(f"{stem[:22]}",col_mesh,col_path)
            col_info["path"]=_relative(col_path,resource_dir)
            generated_files.append(_relative(col_path,resource_dir))
        tile={"id":f"tile_{label}","tileX":ix,"tileY":iy,
              "localX":round(cx,3),"localY":round(cy,3),
              "worldX":round(config.origin_x+cx,3),"worldY":round(config.origin_y+cy,3),
              "worldZ":config.origin_z,
              "highDff":_relative(hi_path,resource_dir),"lowDff":_relative(lo_path,resource_dir),
              "col":_relative(col_path,resource_dir) if col_path else None,
              "highTriangles":hi_info["triangles"],"lowTriangles":lo_info["triangles"],
              "collisionTriangles":col_info["triangles"] if col_info else 0}
        tile_runtime.append(tile)
        asset_records.append({"name":tile["id"],"high":hi_info,"low":lo_info,"collision":col_info,
                             "localCenter":[cx,cy,config.origin_z],"materials":hi_info["materials"]})
        registry.add_asset({"name":tile["id"],"high":hi_info,"low":lo_info,"collision":col_info})

    txd_path=texture_dir/"fc_materials.txd"
    if reuse_generated:
        if not txd_path.is_file():
            raise ValueError(f"missing reusable TXD: {txd_path}")
        texture_records=_scan_existing_textures(texture_dir)
        txd_info={"path":str(txd_path),"bytes":txd_path.stat().st_size,
                  "textures":len(MATERIALS),"names":[spec.texture for spec in MATERIALS.values()]}
    else:
        texture_records,albedos=build_material_textures(texture_dir)
        texture_records.extend(build_weather_textures(texture_dir))
        texture_records.extend(build_lighting_textures(texture_dir))
        txd_info=write_txd(albedos,txd_path)
    txd_info["path"]=_relative(txd_path,resource_dir)
    generated_files.append(_relative(txd_path,resource_dir))
    for record in texture_records:
        for field in ("dds","png"):
            path=record.get(field)
            if path:
                resolved=Path(path).resolve()
                if resolved.is_file():
                    rel=_relative(resolved,resource_dir)
                    record[field]=rel
                    generated_files.append(rel)
        registry.add_texture(record)
    # Thunder is a deterministic one-shot; native GTA weather supplies rain.
    thunder_files=[]
    for index in (1,2):
        path=resource_dir/"audio"/f"thunder_{index:02d}.wav"
        if not reuse_generated:
            write_thunder(path,config.seed+index*917,duration=3.6+index*.25)
        if not path.is_file():
            raise ValueError(f"missing reusable thunder asset: {path}")
        rel=_relative(path,resource_dir)
        thunder_files.append(rel);generated_files.append(rel)

    # Convert local lamp coordinates to the island's MTA world slot.
    runtime_lights=[]
    for index,light in enumerate(records["lights"]):
        runtime_lights.append({"id":f"street_{index:03d}",
                               "worldX":round(config.origin_x+light["x"],3),
                               "worldY":round(config.origin_y+light["y"],3),
                               "worldZ":round(config.origin_z+light["z"],3),
                               "color":list(light["color"]),"intensity":light["intensity"],
                               "range":light["range"],"type":light["type"]})
    spawn_x,spawn_y=0.0,-150.0
    spawn={"x":round(config.origin_x+spawn_x,3),"y":round(config.origin_y+spawn_y,3),
           "z":round(config.origin_z+terrain.height(spawn_x,spawn_y)+1.05,3),
           "rotation":90.0}
    runtime={"schema":1,"name":config.name,"seed":config.seed,
             "originX":config.origin_x,"originY":config.origin_y,"originZ":config.origin_z,
             "worldMin":config.world_min,"worldMax":config.world_max,
             "tileSize":config.tile_size,"tilesPerAxis":config.tiles_per_axis,
             "lodHighDistance":165,"lodFarDistance":500,
             "spawn":spawn,"tiles":tile_runtime,"lights":runtime_lights,
             "thunderFiles":thunder_files,
             "capabilities":{"nativeWeather":True,"screenSpaceReflections":False,
                              "depthAwareShadows":False,"rainPuddles":"material mask + gradual wetness shader",
                              "water":"animated local normals/specular; no screen-space reflection"}}
    _write_json(data_dir/"city_runtime.json",runtime)
    roads=graph.to_dict()
    roads["origin"]={"x":config.origin_x,"y":config.origin_y,"z":config.origin_z}
    _write_json(data_dir/"roads.json",roads)
    building_data={"schema":1,"placements":[],"archetypes":[]}
    for placement in placements:
        item=placement.to_dict()
        item["baseZ"]=round(terrain.height(placement.x,placement.y),3)
        item["worldPosition"]=[round(config.origin_x+placement.x,3),
                               round(config.origin_y+placement.y,3),
                               round(config.origin_z+terrain.height(placement.x,placement.y),3)]
        building_data["placements"].append(item)
    from .buildings import ARCHETYPES
    building_data["archetypes"]=sorted(ARCHETYPES)
    _write_json(data_dir/"buildings.json",building_data)
    _write_json(data_dir/"districts.json",{"zones":ZONES,"features":features,"records":records["landUse"]})

    texture_bytes=sum(p.stat().st_size for p in texture_dir.glob("*.dds"))
    # Every generated DDS is shipped as a standalone map; the TXD is an extra
    # base-color dictionary for the DFF materials.
    runtime_texture_bytes=texture_bytes+txd_path.stat().st_size
    stats={"nodes":len(graph.nodes),"roads":len(graph.segments),
           "buildings":len(placements),"intersections":len(records["intersections"]),
           "trees":len(records["trees"]),"streetLights":len(runtime_lights),
           "tiles":len(tile_runtime),"highTriangles":high.triangle_count,
           "lowTriangles":low.triangle_count,"combinedVisualTriangles":total_visual_triangles,
           "collisionTriangles":len(collision.faces),
           "textureSourceDDSBytes":texture_bytes,"runtimeTextureBytes":runtime_texture_bytes,
           "textureDictionaryBytes":txd_path.stat().st_size,
           "layoutValidation":layout,"budgets":{"assets":config.asset_limit,
           "triangles":config.triangle_budget,"textures":config.texture_budget_bytes}}
    if len(tile_runtime)*3>config.asset_limit:
        raise ValueError(f"tile object/model count exceeds asset budget: {len(tile_runtime)*3} > {config.asset_limit}")
    if runtime_texture_bytes>config.texture_budget_bytes:
        raise ValueError(f"runtime texture budget exceeded: {runtime_texture_bytes} > {config.texture_budget_bytes}")
    _write_json(data_dir/"build_report.json",stats)
    _write_json(data_dir/"assets.json",{"schema":1,"tiles":asset_records,
                                         "textures":texture_records,"txd":txd_info})
    registry.write_json(data_dir/"asset_registry.json",{"assets":registry.assets,
                                                           "textures":registry.texture_records,
                                                           "stats":stats})
    generated_files.extend(["data/city_runtime.json","data/roads.json","data/buildings.json",
                            "data/districts.json","data/build_report.json","data/assets.json",
                            "data/asset_registry.json"])
    file_paths=[]
    # Include every DFF/COL, TXD, and generated DDS in the MTA download list.
    file_paths.extend(path for path in generated_files if path.lower().endswith((".dff",".col",".dds",".txd",".wav",".json")))
    file_paths.extend(["shaders/wet_road.fx","shaders/water.fx","shaders/window_light.fx","shaders/glass_tint.fx"])
    _write_meta(resource_dir,file_paths,config)
    generated_files.append("meta.xml")
    manifest={"schema":1,"city":config.name,"seed":config.seed,
              "generatedFiles":sorted(set(generated_files)),"stats":stats,
              "models":asset_records,"textureDictionary":txd_info,
              "limitations":["MTA's DX9 shader path uses local normal/specular response, not depth-aware SSR.",
                             "Dynamic shadows/global illumination are not supplied by this resource.",
                             "Rain puddles are gradual material masks, not geometry or screen-space puddles."]}
    _write_json(previous_manifest,manifest)
    # Add the self-describing manifest to the resource so server owners can
    # inspect budgets without opening Python sources.
    with (resource_dir/"meta.xml").open("r+",encoding="utf-8") as stream:
        text=stream.read().replace("</meta>","    <file src=\"data/build_manifest.json\" />\n</meta>")
        stream.seek(0);stream.write(text);stream.truncate()
    return {"resource":str(resource_dir),"manifest":str(previous_manifest),"stats":stats}
