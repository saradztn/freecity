"""Static MTA resource, RenderWare, geometry, shader, and budget checks."""
from __future__ import annotations
from pathlib import Path
import json
import math
import re
import shutil
import struct
import subprocess
import wave
import xml.etree.ElementTree as ET

from .materials import MATERIALS

_CONTAINER_KINDS={0x03,0x06,0x07,0x08,0x0E,0x0F,0x10,0x14,0x15,0x16,0x1A}


def _parse_chunks(data:bytes,start:int=0,end:int|None=None)->list[dict]:
    end=len(data) if end is None else end
    chunks=[];cursor=start
    while cursor<end:
        if cursor+12>end:
            raise ValueError(f"truncated RenderWare chunk header at {cursor}")
        kind,size,version=struct.unpack_from("<III",data,cursor)
        payload_start=cursor+12;chunk_end=payload_start+size
        if chunk_end>end:
            raise ValueError(f"RenderWare chunk 0x{kind:04x} overruns its parent")
        chunks.append({"kind":kind,"version":version,"start":cursor,
                       "payloadStart":payload_start,"payloadEnd":chunk_end,
                       "payload":data[payload_start:chunk_end]})
        cursor=chunk_end
    if cursor!=end:
        raise ValueError("RenderWare child chunks do not fill the parent")
    return chunks


def _walk_chunks(chunks:list[dict]):
    for chunk in chunks:
        yield chunk
        if chunk["kind"] in _CONTAINER_KINDS and chunk["payload"]:
            yield from _walk_chunks(_parse_chunks(chunk["payload"]))


def _rw_strings(chunks:list[dict])->list[str]:
    values=[]
    for node in _walk_chunks(chunks):
        if node["kind"]==0x02:
            values.append(node["payload"].split(b"\0",1)[0].decode("ascii","replace"))
    return values


def validate_dff(path:Path)->dict:
    data=path.read_bytes()
    roots=_parse_chunks(data)
    if len(roots)!=1 or roots[0]["kind"]!=0x10:
        raise ValueError("DFF must contain one outer Clump chunk")
    chunks=list(_walk_chunks(roots))
    geometries=[c for c in chunks if c["kind"]==0x0F]
    if len(geometries)!=1:
        raise ValueError(f"expected one static geometry, found {len(geometries)}")
    geometry=geometries[0]
    children=_parse_chunks(geometry["payload"])
    struct_chunks=[c for c in children if c["kind"]==0x01]
    if len(struct_chunks)!=1 or len(struct_chunks[0]["payload"])<16:
        raise ValueError("geometry has no valid Struct chunk")
    geom=struct_chunks[0]["payload"]
    flags,triangle_count,vertex_count,morph_count=struct.unpack_from("<4I",geom,0)
    if morph_count!=1 or vertex_count==0 or triangle_count==0:
        raise ValueError("DFF geometry must contain one non-empty morph target")
    cursor=16
    if flags&0x08: cursor+=vertex_count*4
    uv_sets=(1 if flags&0x04 else 0)+(1 if flags&0x80 else 0)
    cursor+=vertex_count*8*uv_sets
    faces_start=cursor
    cursor+=triangle_count*8
    if cursor+24>len(geom):
        raise ValueError("DFF triangle/morph data is truncated")
    cursor+=24
    vertex_start=cursor
    cursor+=vertex_count*12
    normal_start=cursor
    if flags&0x10: cursor+=vertex_count*12
    if cursor!=len(geom):
        raise ValueError(f"DFF geometry size mismatch: parsed {cursor}, stored {len(geom)}")
    material_lists=[c for c in children if c["kind"]==0x08]
    if len(material_lists)!=1:
        raise ValueError("DFF must have exactly one MaterialList")
    ml_children=_parse_chunks(material_lists[0]["payload"])
    ml_struct=next((c for c in ml_children if c["kind"]==0x01),None)
    if ml_struct is None or len(ml_struct["payload"])<4:
        raise ValueError("MaterialList has no valid Struct")
    material_count=struct.unpack_from("<I",ml_struct["payload"],0)[0]
    if len(ml_struct["payload"])!=4+material_count*4:
        raise ValueError("MaterialList index table has an invalid length")
    materials=[c for c in ml_children if c["kind"]==0x07]
    if len(materials)!=material_count:
        raise ValueError("MaterialList count does not match its material chunks")
    texture_names=[]
    for material in materials:
        mat_children=_parse_chunks(material["payload"])
        texture=next((c for c in mat_children if c["kind"]==0x06),None)
        if texture:
            names=[s for s in _rw_strings([texture]) if s]
            if names:texture_names.append(names[0])
    faces=[]
    for index in range(triangle_count):
        b,a,material,c=struct.unpack_from("<4H",geom,faces_start+index*8)
        if max(a,b,c)>=vertex_count: raise ValueError(f"DFF face {index} has an invalid vertex index")
        if material>=material_count: raise ValueError(f"DFF face {index} has an invalid material index")
        faces.append((a,b,c,material))
    for offset in range(vertex_start,vertex_start+vertex_count*12,4):
        value=struct.unpack_from("<f",geom,offset)[0]
        if not math.isfinite(value):raise ValueError("DFF contains a non-finite position")
    if flags&0x10:
        for offset in range(normal_start,normal_start+vertex_count*12,4):
            value=struct.unpack_from("<f",geom,offset)[0]
            if not math.isfinite(value):raise ValueError("DFF contains a non-finite normal")
    binmeshes=[]
    for ext in [c for c in children if c["kind"]==0x03]:
        for plugin in _parse_chunks(ext["payload"]) if ext["payload"] else []:
            if plugin["kind"]==0x050E:
                binmeshes.append(plugin)
    if not binmeshes:
        raise ValueError("DFF geometry has no BinMesh plugin")
    for plugin in binmeshes:
        payload=plugin["payload"]
        if len(payload)<12:raise ValueError("truncated BinMesh header")
        _,mesh_count,total_indices=struct.unpack_from("<III",payload,0)
        cursor=12;seen=0
        for _ in range(mesh_count):
            if cursor+8>len(payload):raise ValueError("truncated BinMesh entry")
            count,material=struct.unpack_from("<II",payload,cursor);cursor+=8
            if material>=material_count or count%3:
                raise ValueError("BinMesh material/index count is invalid")
            if cursor+count*4>len(payload):raise ValueError("truncated BinMesh indices")
            indices=struct.unpack_from("<"+"I"*count,payload,cursor) if count else ()
            if any(i>=vertex_count for i in indices):raise ValueError("BinMesh has invalid vertex index")
            cursor+=count*4;seen+=count
        if cursor!=len(payload) or seen!=total_indices:
            raise ValueError("BinMesh index total/size mismatch")
    return {"bytes":len(data),"vertices":vertex_count,"triangles":triangle_count,
            "materials":material_count,"textureNames":sorted(set(texture_names)),"chunks":len(chunks)}


def validate_col3(path:Path)->dict:
    data=path.read_bytes()
    if len(data)<120 or data[:4]!=b"COL3":raise ValueError("not a COL3 file or truncated header")
    declared_size=struct.unpack_from("<I",data,4)[0]
    if declared_size!=len(data)-8:raise ValueError("COL3 size field does not match file size")
    bounds=struct.unpack_from("<10f",data,32)
    if not all(math.isfinite(x) for x in bounds):raise ValueError("COL3 has non-finite bounds")
    lo=bounds[0:3];hi=bounds[3:6];center=bounds[6:9];radius=bounds[9]
    if any(lo[i]>hi[i] for i in range(3)) or radius<0:raise ValueError("COL3 has invalid bounding volume")
    num_spheres,num_boxes,num_faces,num_lines,padding,flags=struct.unpack_from("<HHHBBI",data,72)
    offsets=struct.unpack_from("<9I",data,84)
    if num_spheres or num_boxes or num_lines:
        raise ValueError("unexpected primitive collision count")
    if not flags&2:raise ValueError("COL3 collision mesh is not marked non-empty")
    if num_faces==0:raise ValueError("COL3 has no faces")
    vertex_start=offsets[3]+4;face_start=offsets[4]+4
    if vertex_start!=120 or not (vertex_start<=face_start<=len(data)):
        raise ValueError("COL3 mesh offsets are invalid")
    if offsets[0] or offsets[1] or offsets[2] or offsets[5] or offsets[6] or offsets[7] or offsets[8]:
        raise ValueError("unexpected COL3 primitive/shadow offsets")
    has_groups=bool(flags&8)
    groups=[]
    if has_groups:
        if face_start<4:raise ValueError("COL3 face-group count is missing")
        group_count=struct.unpack_from("<I",data,face_start-4)[0]
        groups_start=face_start-4-group_count*28
        if groups_start<vertex_start:raise ValueError("COL3 face groups overlap the vertex array")
        for group_index in range(group_count):
            values=struct.unpack_from("<6fHH",data,groups_start+group_index*28)
            first,last=values[6:8]
            if first>last or last>=num_faces:raise ValueError("COL3 face-group range is invalid")
            groups.append((first,last))
        if groups and (groups[0][0]!=0 or groups[-1][1]!=num_faces-1 or
                       any(groups[i][1]+1!=groups[i+1][0] for i in range(len(groups)-1))):
            raise ValueError("COL3 face groups do not cover faces contiguously")
    else:
        groups_start=face_start
    vertex_bytes=groups_start-vertex_start
    vertex_count=vertex_bytes//6
    expected_vertex_bytes=vertex_count*6+(2 if (vertex_count*6)%4 else 0)
    if vertex_count==0 or expected_vertex_bytes!=vertex_bytes:
        raise ValueError("COL3 fixed-point vertex section has invalid length")
    face_bytes=num_faces*8
    if face_start+face_bytes!=len(data):raise ValueError("COL3 face array has invalid length")
    vertices=[]
    for index in range(vertex_count):
        point=tuple(v/128.0 for v in struct.unpack_from("<3h",data,vertex_start+index*6))
        if any(point[i]<lo[i]-.02 or point[i]>hi[i]+.02 for i in range(3)):
            raise ValueError("COL3 vertex is outside stored bounds")
        vertices.append(point)
    max_index=-1
    for face_index in range(num_faces):
        a,b,c,surface,light=struct.unpack_from("<3HBB",data,face_start+face_index*8)
        if max(a,b,c)>=vertex_count:raise ValueError(f"COL3 face {face_index} references a missing vertex")
        max_index=max(max_index,a,b,c)
    needed_radius=max((math.dist(center,v) for v in vertices),default=0.0)
    if radius+0.03<needed_radius:raise ValueError("COL3 bounding sphere does not contain its vertices")
    return {"bytes":len(data),"vertices":vertex_count,"triangles":num_faces,
            "faceGroups":len(groups),"maxVertexIndex":max_index,"flags":flags}


def validate_txd(path:Path)->dict:
    data=path.read_bytes();roots=_parse_chunks(data)
    if len(roots)!=1 or roots[0]["kind"]!=0x16:raise ValueError("TXD must contain one TextureDictionary chunk")
    children=_parse_chunks(roots[0]["payload"])
    struct_chunk=next((c for c in children if c["kind"]==0x01),None)
    if struct_chunk is None or len(struct_chunk["payload"])!=4:raise ValueError("TXD dictionary struct is invalid")
    count,device=struct.unpack("<HH",struct_chunk["payload"])
    natives=[c for c in children if c["kind"]==0x15]
    if len(natives)!=count:raise ValueError("TXD texture count does not match native textures")
    names=[]
    for native_chunk in natives:
        sub=_parse_chunks(native_chunk["payload"])
        header_chunk=next((c for c in sub if c["kind"]==0x01),None)
        if not header_chunk:raise ValueError("TXD native texture is missing its Struct")
        payload=header_chunk["payload"]
        fmt="<II32s32sI4sHHBBBB";header_size=struct.calcsize(fmt)
        if len(payload)<header_size:raise ValueError("truncated TXD native header")
        platform,filter_flags,name_raw,mask,raster,fourcc,width,height,depth,levels,raster_type,flags=struct.unpack_from(fmt,payload)
        name=name_raw.split(b"\0",1)[0].decode("ascii","replace")
        if not name or not width or not height or fourcc!=b"DXT1" or levels<1:
            raise ValueError("TXD texture header contains unsupported values")
        if platform!=9:raise ValueError(f"TXD texture {name} is not a PC D3D9 raster")
        cursor=header_size;w,h=width,height
        for _ in range(levels):
            if cursor+4>len(payload):raise ValueError("truncated TXD mip size")
            size=struct.unpack_from("<I",payload,cursor)[0];cursor+=4
            expected=max(1,(w+3)//4)*max(1,(h+3)//4)*8
            if size!=expected or cursor+size>len(payload):raise ValueError(f"TXD mip size mismatch for {name}")
            cursor+=size;w=max(1,w//2);h=max(1,h//2)
        if cursor!=len(payload):raise ValueError(f"unexpected trailing bytes in TXD texture {name}")
        names.append(name)
    if len(names)!=len(set(names)):raise ValueError("TXD contains duplicate texture names")
    return {"bytes":len(data),"textures":len(names),"names":names}


def validate_dds(path:Path)->dict:
    data=path.read_bytes()
    if len(data)<128 or data[:4]!=b"DDS ":raise ValueError("truncated/invalid DDS header")
    header_size,flags,height,width,linear_size,depth,mips=struct.unpack_from("<7I",data,4)
    fourcc=data[84:88]
    if header_size!=124 or not width or not height or fourcc!=b"DXT1":raise ValueError("DDS header is not a valid DXT1 texture")
    mips=max(1,mips);cursor=128;w,h=width,height
    for _ in range(mips):
        expected=max(1,(w+3)//4)*max(1,(h+3)//4)*8
        if cursor+expected>len(data):raise ValueError("DDS mip chain is truncated")
        cursor+=expected;w=max(1,w//2);h=max(1,h//2)
    if cursor!=len(data):raise ValueError("DDS has unaccounted trailing data")
    return {"bytes":len(data),"width":width,"height":height,"mips":mips,"format":"DXT1"}


def _mask_source(text:str,language:str)->str:
    """Blank comments/quoted strings while preserving offsets and newlines."""
    out=list(text);i=0;n=len(text)
    def blank(a,b):
        for k in range(a,b):
            if out[k]!="\n":out[k]=" "
    while i<n:
        if language=="lua" and text.startswith("--[[",i):
            end=text.find("]]",i+4);end=n if end<0 else end+2;blank(i,end);i=end;continue
        if language!="lua" and text.startswith("/*",i):
            end=text.find("*/",i+2);end=n if end<0 else end+2;blank(i,end);i=end;continue
        if language=="lua" and text.startswith("--",i):
            end=text.find("\n",i+2);end=n if end<0 else end;blank(i,end);i=end;continue
        if language!="lua" and text.startswith("//",i):
            end=text.find("\n",i+2);end=n if end<0 else end;blank(i,end);i=end;continue
        # Skip both ordinary strings and Lua's simple [[...]] long strings.
        if text[i] in "\"'" or (language=="lua" and text.startswith("[[",i)):
            if text.startswith("[[",i):
                end=text.find("]]",i+2);end=n if end<0 else end+2;blank(i,end);i=end;continue
            quote=text[i];start=i;i+=1
            while i<n:
                if text[i]=="\\":i+=2;continue
                if text[i]==quote:i+=1;break
                i+=1
            blank(start,min(i,n));continue
        i+=1
    return "".join(out)


def validate_lua(path:Path)->dict:
    source=path.read_text(encoding="utf-8");clean=_mask_source(source,"lua")
    pairs={")":"(","]":"[","}":"{"};stack=[]
    for index,ch in enumerate(clean):
        if ch in "([{":stack.append((ch,index))
        elif ch in ")]}":
            if not stack or stack[-1][0]!=pairs[ch]:raise ValueError(f"unbalanced {ch} at offset {index}")
            stack.pop()
    if stack:raise ValueError(f"unclosed {stack[-1][0]} at offset {stack[-1][1]}")
    tokens=re.findall(r"[A-Za-z_][A-Za-z0-9_]*",clean)
    blocks=[]
    for token in tokens:
        if token in ("function","if","do","repeat"):
            blocks.append(token)
        elif token=="end":
            if not blocks or blocks[-1]=="repeat":raise ValueError("unmatched Lua 'end'")
            blocks.pop()
        elif token=="until":
            if not blocks or blocks[-1]!="repeat":raise ValueError("unmatched Lua 'until'")
            blocks.pop()
    if blocks:raise ValueError(f"unclosed Lua block: {blocks[-1]}")
    compiler=next((shutil.which(name) for name in ("luac","luac5.1","luac5.4") if shutil.which(name)),None)
    if compiler:
        result=subprocess.run([compiler,"-p",str(path)],capture_output=True,text=True)
        if result.returncode:raise ValueError(f"{compiler}: {result.stderr.strip()}")
    return {"bytes":len(source.encode()),"blocksBalanced":True,"compiler":compiler or "not installed; static token check"}


def validate_shader(path:Path)->dict:
    source=path.read_text(encoding="utf-8");clean=_mask_source(source,"hlsl")
    pairs={")":"(","]":"[","}":"{"};stack=[]
    for index,ch in enumerate(clean):
        if ch in "([{":stack.append((ch,index))
        elif ch in ")]}":
            if not stack or stack[-1][0]!=pairs[ch]:raise ValueError(f"unbalanced {ch} at offset {index}")
            stack.pop()
    if stack:raise ValueError(f"unclosed {stack[-1][0]} at offset {stack[-1][1]}")
    if not re.search(r"\btechnique\s+\w+\s*\{",clean):raise ValueError("missing HLSL technique")
    if not re.search(r"compile\s+ps_2_0\s+\w+\s*\(",clean):raise ValueError("missing MTA/DX9 ps_2_0 entrypoint")
    return {"bytes":len(source.encode()),"balanced":True,"compiler":"not installed; lexical check only"}


def validate_resource(resource_dir:Path,triangle_budget:int=120000,texture_budget_bytes:int=32*1024*1024,asset_budget:int=250)->dict:
    resource_dir=Path(resource_dir).resolve();errors=[];warnings=[];details={}
    meta_path=resource_dir/"meta.xml"
    if not meta_path.is_file():return {"ok":False,"errors":["meta.xml missing"],"warnings":[],"details":{}}
    try:
        root=ET.parse(meta_path).getroot()
        if root.tag!="meta":errors.append("meta.xml root must be <meta>")
        files=[node.attrib.get("src","") for node in root.findall("file")]
        scripts=[node.attrib.get("src","") for node in root.findall("script")]
        if len(files)!=len(set(files)):errors.append("meta.xml has duplicate <file> entries")
        for src in files+scripts:
            if not src or not (resource_dir/src).is_file():errors.append(f"resource file is missing: {src}")
        details["meta"]={"files":len(files),"scripts":len(scripts)}
    except (ET.ParseError,OSError) as exc:
        errors.append(f"meta.xml parse failed: {exc}");files=[];scripts=[]
    for rel in scripts:
        path=resource_dir/rel
        if path.suffix.lower()==".lua":
            try:details[rel]=validate_lua(path)
            except Exception as exc:errors.append(f"Lua validation failed for {rel}: {exc}")
    shader_paths=sorted((resource_dir/"shaders").glob("*.fx"))
    for path in shader_paths:
        try:details[path.relative_to(resource_dir).as_posix()]=validate_shader(path)
        except Exception as exc:errors.append(f"shader validation failed for {path.name}: {exc}")
    # Check literal paths and uniform names shared between Lua and HLSL.
    lua_sources="\n".join((resource_dir/p).read_text(encoding="utf-8") for p in scripts if p.endswith(".lua") and (resource_dir/p).is_file())
    for ref in re.findall(r"[\"']((?:textures|shaders|data)/[^\"']+)[\"']",lua_sources):
        if not (resource_dir/ref).is_file():errors.append(f"Lua references missing resource: {ref}")
    shader_sources="\n".join(p.read_text(encoding="utf-8") for p in shader_paths)
    declared=set(re.findall(r"\b(?:float\d?|texture)\s+(g[A-Za-z0-9_]+)\b",shader_sources))
    assigned=set(re.findall(r"dxSetShaderValue\s*\([^,]+,\s*[\"'](g[A-Za-z0-9_]+)[\"']",lua_sources))
    unknown=sorted(assigned-declared)
    if unknown:errors.append("Lua sets undeclared shader uniform(s): "+", ".join(unknown))
    if not shutil.which("luac") and not shutil.which("luac5.1"):
        warnings.append("No Lua compiler found; Lua checks are lexical/block-balance checks, not a full MTA parser.")
    if not any(shutil.which(n) for n in ("fxc","dxc","glslangValidator")):
        warnings.append("No HLSL compiler found; shader checks cover DX9 entrypoint and lexical balance only.")
    # Parse JSON payloads, runtime links, manifests, and budgets.
    def read_json(rel):
        path=resource_dir/rel
        try:return json.loads(path.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError) as exc:
            errors.append(f"invalid/missing JSON {rel}: {exc}");return None
    runtime=read_json("data/city_runtime.json")
    report=read_json("data/build_report.json")
    assets=read_json("data/assets.json")
    manifest=read_json("data/build_manifest.json")
    if runtime:
        tiles=runtime.get("tiles",[])
        if len(tiles)!=16:errors.append(f"expected 16 streamed tiles, found {len(tiles)}")
        for tile in tiles:
            for key in ("highDff","lowDff","col"):
                rel=tile.get(key)
                if rel and not (resource_dir/rel).is_file():errors.append(f"runtime tile {tile.get('id')} missing {key}: {rel}")
        tile_ids=[tile.get("id") for tile in tiles]
        if len(tile_ids)!=len(set(tile_ids)):errors.append("runtime contains duplicate tile IDs")
        light_ids=[light.get("id") for light in runtime.get("lights",[])]
        if len(light_ids)!=len(set(light_ids)):errors.append("runtime contains duplicate light IDs")
        if not isinstance(runtime.get("spawn"),dict):errors.append("runtime spawn record is missing")
        meta_file_set=set(files)
        for rel in runtime.get("thunderFiles",[]):
            if rel not in meta_file_set:errors.append(f"runtime thunder file is absent from meta.xml: {rel}")
            try:
                with wave.open(str(resource_dir/rel),"rb") as audio:
                    if audio.getnframes()<1 or audio.getframerate()<8000:errors.append(f"invalid thunder WAV: {rel}")
            except (OSError,wave.Error) as exc:errors.append(f"invalid thunder WAV {rel}: {exc}")
        details["runtime"]={"tiles":len(tiles),"lights":len(runtime.get("lights",[])),"spawn":runtime.get("spawn")}
    roads=read_json("data/roads.json")
    if roads:
        nodes=roads.get("nodes",[]);segments=roads.get("segments",[])
        node_ids={node.get("id") for node in nodes};edge_ids={edge.get("id") for edge in segments}
        if len(node_ids)!=len(nodes):errors.append("roads.json has duplicate node IDs")
        if len(edge_ids)!=len(segments):errors.append("roads.json has duplicate segment IDs")
        adjacency={node_id:set() for node_id in node_ids}
        for edge in segments:
            start,end=edge.get("from"),edge.get("to")
            if start not in node_ids or end not in node_ids:errors.append(f"road {edge.get('id')} has a missing endpoint");continue
            adjacency[start].add(end);adjacency[end].add(start)
            if edge.get("direction") not in ("both","forward","reverse") or edge.get("lanes",0)<1 or edge.get("speed_kph",0)<=0:
                errors.append(f"road {edge.get('id')} has invalid traffic attributes")
        if node_ids:
            visited=set();todo=[next(iter(node_ids))]
            while todo:
                node=todo.pop()
                if node in visited:continue
                visited.add(node);todo.extend(adjacency[node]-visited)
            if len(visited)!=len(node_ids):errors.append("roads.json is disconnected")
        details["roadGraph"]={"nodes":len(nodes),"segments":len(segments),"connected":len(node_ids)>0 and len(visited)==len(node_ids)}
    buildings=read_json("data/buildings.json")
    if buildings:
        placements=buildings.get("placements",[])
        placement_ids=[item.get("id") for item in placements]
        if len(placement_ids)!=len(set(placement_ids)):errors.append("buildings.json has duplicate placement IDs")
        if report and len(placements)!=int(report.get("buildings",-1)):errors.append("building placement count differs from build report")
        details["buildings"]={"placements":len(placements),"archetypes":len(buildings.get("archetypes",[]))}
    districts=read_json("data/districts.json")
    if districts:
        kinds={feature.get("kind") for feature in districts.get("features",[])}
        if not {"urban_park","surface_parking"}.issubset(kinds):errors.append("district features omit the park or parking lot")
        details["districts"]={"zones":len(districts.get("zones",[])),"features":len(districts.get("features",[]))}
    if report:
        combined=int(report.get("combinedVisualTriangles",0))
        if combined>triangle_budget:errors.append(f"triangle budget exceeded: {combined}>{triangle_budget}")
        if int(report.get("runtimeTextureBytes",0))>texture_budget_bytes:errors.append("runtime texture budget exceeded")
        if int(report.get("tiles",0))*3>asset_budget:errors.append("streamed model/collision asset budget exceeded")
        if not report.get("layoutValidation",{}).get("ok"):errors.append("build report contains a failed layout validation")
        details["budgets"]={"triangles":combined,"triangleLimit":triangle_budget,
                             "runtimeTextureBytes":report.get("runtimeTextureBytes"),"textureLimit":texture_budget_bytes,
                             "tiles":report.get("tiles"),"assetLimit":asset_budget}
    if manifest:
        for rel in manifest.get("generatedFiles",[]):
            if not (resource_dir/rel).is_file():errors.append(f"manifest lists missing generated file: {rel}")
    if assets:
        txd_rel=assets.get("txd",{}).get("path","textures/fc_materials.txd")
        try:
            txd=validate_txd(resource_dir/txd_rel)
            details["txd"]={k:v for k,v in txd.items() if k!="names"}
            txd_names=set(txd["names"])
            referenced=set()
            tile_info=assets.get("tiles",[])
            dff_total=0;col_total=0
            for item in tile_info:
                for tier in ("high","low"):
                    record=item.get(tier) or {}
                    rel=record.get("path")
                    if not rel:errors.append(f"asset registry has no {tier} DFF path");continue
                    info=validate_dff(resource_dir/rel)
                    dff_total+=info["triangles"];referenced.update(info["textureNames"])
                col=item.get("collision") or {}
                if col.get("path"):
                    info=validate_col3(resource_dir/col["path"]);col_total+=info["triangles"]
            missing=sorted(referenced-txd_names)
            if missing:errors.append("DFF texture names absent from TXD: "+", ".join(missing))
            if report and dff_total!=int(report.get("combinedVisualTriangles",-1)):
                errors.append(f"DFF triangle count {dff_total} does not match report")
            if report and col_total!=int(report.get("collisionTriangles",-1)):
                errors.append(f"COL3 triangle count {col_total} does not match report")
            details["renderware"]={"highLowTriangles":dff_total,"collisionTriangles":col_total,
                                   "textureReferences":len(referenced),"txdTextures":len(txd_names)}
        except Exception as exc:errors.append(f"RenderWare validation failed: {exc}")
    dds_paths=sorted((resource_dir/"textures").glob("*.dds"))
    try:
        dds_info=[validate_dds(path) for path in dds_paths]
        dds_bytes=sum(x["bytes"] for x in dds_info)
        details["dds"]={"count":len(dds_info),"bytes":dds_bytes}
        if report and dds_bytes+int((assets or {}).get("txd",{}).get("bytes",0))!=int(report.get("runtimeTextureBytes",-1)):
            errors.append("DDS/TXD byte total does not match build report")
    except Exception as exc:errors.append(f"DDS validation failed: {exc}")
    return {"ok":not errors,"errors":errors,"warnings":warnings,"details":details}
