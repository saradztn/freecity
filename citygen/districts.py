"""Seeded land-use zones and buildable parcel placement."""
from __future__ import annotations
from dataclasses import dataclass
import random
from .road_graph import RoadGraph


@dataclass
class BuildingPlacement:
    id: str
    archetype: str
    district: str
    x: float
    y: float
    width: float
    depth: float
    floors: int
    height: float
    facade: str
    seed: int
    rotation: float = 0.0
    extras: dict | None = None

    def to_dict(self) -> dict:
        return {"id": self.id, "archetype": self.archetype, "district": self.district,
                "position": [round(self.x, 3), round(self.y, 3)],
                "width": round(self.width, 2), "depth": round(self.depth, 2),
                "floors": self.floors, "height": round(self.height, 2),
                "facade": self.facade, "seed": self.seed, "rotation": self.rotation,
                "extras": self.extras or {}}


# Hand-shaped zone polygons keep the test slice purposeful; the generator can
# replace these with GIS parcels/road-block polygons for city-scale expansion.
ZONES = [
    {"name":"downtown", "bounds":(-108,-65,128,148), "use":"mixed"},
    {"name":"residential", "bounds":(-218,43,-116,145), "use":"residential"},
    {"name":"commercial", "bounds":(-108,-175,128,-75), "use":"commercial"},
    {"name":"industrial", "bounds":(133,151,225,201), "use":"industrial"},
    {"name":"park", "bounds":(140,-18,222,30), "use":"park"},
    {"name":"parking", "bounds":(77,-104,121,-54), "use":"parking"},
    {"name":"ridge_residential", "bounds":(-210,-54,-170,43), "use":"residential"},
    {"name":"west_commercial", "bounds":(-166,-35,-116,16), "use":"commercial"},
    {"name":"industrial_west", "bounds":(-205,153,-130,201), "use":"industrial"},
]


def _make_placement(pid: str, archetype: str, district: str, x: float, y: float,
                    width: float, depth: float, floors: int, height: float,
                    facade: str, seed: int, rotation: float = 0.0, extras=None) -> BuildingPlacement:
    return BuildingPlacement(pid, archetype, district, x, y, width, depth, floors, height, facade,
                             seed, rotation, extras or {})


def build_placements(seed: int, graph: RoadGraph) -> tuple[list[BuildingPlacement], list[dict]]:
    rng = random.Random(seed ^ 0x5A17)
    out: list[BuildingPlacement] = []
    facilities = [
        ("bldg_office_01", "office_tower", "downtown", -55, -8, 34, 38, 12, 62, "stone_glass"),
        ("bldg_glass_01", "glass_tower", "downtown", 66, -8, 36, 39, 16, 86, "curtainwall"),
        ("bldg_residential_01", "luxury_apartment", "downtown", -55, 94, 37, 37, 9, 43, "brick_balcony"),
        ("bldg_hotel_01", "hotel", "downtown", 67, 95, 38, 36, 11, 54, "stone_glass"),
        ("bldg_hospital_01", "hospital", "downtown", -20, 102, 29, 26, 5, 25, "institutional"),
        ("bldg_police_01", "police_station", "downtown", 102, 101, 25, 23, 3, 15, "institutional"),
        ("bldg_fire_01", "fire_station", "downtown", 40, 128, 27, 23, 2, 12, "institutional"),
        ("bldg_school_01", "school", "residential", -140, 92, 40, 36, 2, 13, "institutional"),
        ("bldg_house_01", "suburban_house", "residential", -185, 95, 13, 16, 2, 8, "siding"),
        ("bldg_house_02", "townhouse", "residential", -140, 122, 18, 16, 3, 10.5, "brick"),
        ("bldg_house_03", "suburban_house", "residential", -185, -42, 13, 16, 2, 8, "stucco"),
        ("bldg_house_04", "townhouse", "residential", -185, 20, 13, 16, 2, 8.5, "siding"),
        ("bldg_strip_01", "strip_mall", "commercial", -54, -124, 53, 31, 1, 9, "painted_concrete"),
        ("bldg_gas_01", "gas_station", "commercial", 68, -125, 38, 36, 1, 7.5, "painted_metal"),
        ("bldg_motel_01", "motel", "commercial", -55, -156, 34, 22, 2, 11, "painted_concrete"),
        ("bldg_diner_01", "diner", "commercial", -185, -14, 13, 16, 1, 7.5, "painted_metal"),
        ("bldg_restaurant_01", "restaurant", "commercial", -140, -14, 22, 20, 2, 10, "brick"),
        ("bldg_warehouse_01", "warehouse", "industrial", 177, 191, 49, 16, 1, 9, "metal"),
        ("bldg_factory_01", "factory", "industrial", -174, 178, 34, 25, 2, 15, "industrial"),
        ("bldg_smallcom_01", "small_commercial", "commercial", 91, -157, 28, 16, 2, 9, "brick"),
        ("bldg_garage_01", "parking_garage", "downtown", 35, -86, 19, 26, 5, 18, "concrete_open"),
    ]
    for row in facilities:
        pid, arch, district, x, y, w, d, floors, height, facade = row
        variation = rng.uniform(0.94, 1.06)
        rotation_choice = rng.choice((0.0, 0.0, 0.0, 90.0))
        out.append(_make_placement(pid, arch, district, x, y, w * variation, d * variation,
                                   floors, height * variation, facade,
                                   seed + len(out) * 7919,
                                   rotation=0.0 if arch == "strip_mall" else rotation_choice,
                                   extras={"windows": True, "roof_hvac": arch not in ("suburban_house", "townhouse"),
                                           "sign": arch in ("motel", "diner", "restaurant", "gas_station", "strip_mall")}))

    # A varied street edge of small commercial/residential infill. Candidate
    # parcels are deterministic and rejected if they overlap a road envelope.
    candidates = [
        (-137,11,"townhouse","residential",18,20,3,10,"brick"),
    ]
    for x,y,arch,district,w,d,floors,height,facade in candidates:
        dist, seg, _ = graph.road_distance(x,y)
        if seg and dist < max(w,d)*0.5 + seg.paved_width*0.5 + 6.0:
            continue
        scale = rng.uniform(.92, 1.08)
        out.append(_make_placement(f"bldg_infill_{len(out):02d}", arch, district, x, y,
                                   w*scale,d*scale,floors,height*scale,facade,
                                   seed + 104729 * (len(out)+1),
                                   rotation=rng.choice((0.0,0.0,90.0)),
                                   extras={"windows": True, "roof_hvac": arch not in ("suburban_house","townhouse")}))

    # Parking fields and park are first-class land-use systems rather than
    # decorative labels. Their geometry is generated in props/vegetation.
    feature_meta = [
        {"id":"park_bay", "kind":"urban_park", "bounds":[140,-18,222,30], "district":"park"},
        {"id":"parking_lot_01", "kind":"surface_parking", "bounds":[77,-104,121,-54], "district":"parking", "spaces":20,"entrance":"east_bridge_approach"},
    ]
    return out, feature_meta
