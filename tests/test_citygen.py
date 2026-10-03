from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest

from citygen.collision import CollisionMesh
from citygen.config import DEFAULT_CONFIG
from citygen.districts import build_placements
from citygen.mesh import Mesh
from citygen.pipeline import _split_mesh, grade_city_parcels, validate_layout
from citygen.renderware import build_col3, build_dff, build_txd
from citygen.road_graph import build_vertical_slice_graph
from citygen.terrain import Terrain
from citygen.textures import PixelImage
from citygen.validator import validate_col3, validate_dff, validate_resource, validate_txd

ROOT=Path(__file__).resolve().parents[1]


class CityLayoutTests(unittest.TestCase):
    def setUp(self):
        self.graph=build_vertical_slice_graph()
        self.terrain=Terrain(DEFAULT_CONFIG.seed,self.graph,step=DEFAULT_CONFIG.terrain_step,
                            extent=DEFAULT_CONFIG.world_max)
        self.placements,self.features=build_placements(DEFAULT_CONFIG.seed,self.graph)
        grade_city_parcels(self.terrain,self.placements,self.features)

    def test_graph_is_connected_and_seeded(self):
        self.assertEqual([len(c) for c in self.graph.connected_components()],[44])
        self.assertEqual(self.graph.to_dict(),build_vertical_slice_graph().to_dict())
        self.assertEqual(len(self.graph.segments),64)
        self.assertTrue(all(seg.lanes>0 and seg.speed_kph>0 for seg in self.graph.segments.values()))

    def test_placement_and_road_clearance(self):
        layout=validate_layout(self.graph,self.terrain,self.placements,self.features)
        self.assertTrue(layout["ok"],layout["errors"])
        self.assertEqual(len(self.placements),22)
        ids=[p.id for p in self.placements]
        self.assertEqual(len(ids),len(set(ids)))

    def test_mesh_tiles_preserve_faces_and_local_extent(self):
        mesh=Mesh()
        mesh.add_quad(((90,-8,0),(102,-8,0),(102,8,0),(90,8,0)),"asphalt")
        tiles=_split_mesh(mesh,DEFAULT_CONFIG)
        self.assertEqual(sum(part.triangle_count for part in tiles.values()),2)
        for key,part in tiles.items():
            if not part.faces:continue
            self.assertTrue(all(abs(v.position[0])<=DEFAULT_CONFIG.tile_size/2+1 for v in part.vertices))
            # A face centered exactly on a tile boundary stays intact; its
            # vertices may overhang by the half-width of this test primitive.
            self.assertTrue(all(abs(v.position[1])<=DEFAULT_CONFIG.tile_size/2+8.01 for v in part.vertices))


class RenderWareTests(unittest.TestCase):
    def test_dff_materials_point_at_generated_txd_names(self):
        mesh=Mesh()
        mesh.add_quad(((-2,-2,0),(2,-2,0),(2,2,0),(-2,2,0)),"asphalt")
        mesh.add_box((0,0,2),(1,1,2),"concrete")
        dff=build_dff(mesh,"test")
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"test.dff";path.write_bytes(dff)
            info=validate_dff(path)
        self.assertEqual(info["triangles"],mesh.triangle_count)
        self.assertEqual(set(info["textureNames"]),{"fc_asphalt","fc_concrete"})

    def test_col3_offsets_and_face_groups(self):
        collision=CollisionMesh()
        collision.add_quad((-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0),surface=5)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"test.col";path.write_bytes(build_col3("test",collision))
            info=validate_col3(path)
        self.assertEqual(info["triangles"],2)
        self.assertEqual(info["faceGroups"],1)

    def test_txd_mip_chain_and_names(self):
        image=PixelImage(8,8)
        for y in range(8):
            for x in range(8):image.set(x,y,(80+x*8,90+y*8,100,255))
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"test.txd";path.write_bytes(build_txd({"fc_test":image}))
            info=validate_txd(path)
        self.assertEqual(info["textures"],1)
        self.assertEqual(info["names"],["fc_test"])


class GeneratedResourceTests(unittest.TestCase):
    @unittest.skipUnless((ROOT/"resource"/"fc_city"/"data"/"city_runtime.json").is_file(),
                         "generated resource not present; run tools/build_city.py")
    def test_full_resource_manifest_and_binary_assets(self):
        result=validate_resource(ROOT/"resource"/"fc_city")
        self.assertTrue(result["ok"],json.dumps(result["errors"],indent=2))
        self.assertGreater(result["details"]["renderware"]["highLowTriangles"],0)
        self.assertEqual(result["details"]["runtime"]["tiles"],16)

    def test_streaming_retains_engine_resources_until_unload(self):
        lua=(ROOT/"resource"/"fc_city"/"client"/"streaming.lua").read_text()
        self.assertIn("FC.loadedModels[#FC.loadedModels + 1] = dff",lua)
        self.assertIn("FC.loadedCOLs[#FC.loadedCOLs + 1] = col",lua)
        self.assertIn("if isElement(dff) then destroyElement(dff) end",lua)
        self.assertIn("if isElement(col) then destroyElement(col) end",lua)
        self.assertLess(lua.index("engineReplaceCOL(col, highID)"),lua.index("engineLoadTXD("))


if __name__=="__main__":
    unittest.main()
