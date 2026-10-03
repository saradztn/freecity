"""Material catalog for the DX9 approximations and generated texture maps."""
from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialSpec:
    key: str
    texture: str
    base_color: tuple[int, int, int]
    roughness: float
    specular: float
    height_scale: float
    pattern: str
    shader_class: str = "surface"


MATERIALS: dict[str, MaterialSpec] = {
    "asphalt": MaterialSpec("asphalt", "fc_asphalt", (78, 82, 81), .88, .12, .20, "asphalt", "wetroad"),
    "concrete": MaterialSpec("concrete", "fc_concrete", (138, 137, 129), .86, .10, .10, "concrete"),
    "sidewalk": MaterialSpec("sidewalk", "fc_sidewalk", (152, 148, 137), .82, .12, .08, "concrete"),
    "brick": MaterialSpec("brick", "fc_brick", (128, 91, 76), .88, .08, .16, "brick"),
    "painted_concrete": MaterialSpec("painted_concrete", "fc_paintcon", (163, 157, 144), .76, .12, .06, "painted_concrete"),
    "glass": MaterialSpec("glass", "fc_glass", (77, 99, 111), .20, .72, .01, "glass", "glass"),
    "metal": MaterialSpec("metal", "fc_metal", (93, 101, 101), .38, .56, .03, "metal"),
    "painted_metal": MaterialSpec("painted_metal", "fc_pmetal", (105, 111, 108), .42, .32, .05, "painted_metal"),
    "roof": MaterialSpec("roof", "fc_roof", (82, 80, 74), .91, .07, .11, "roof"),
    "grass": MaterialSpec("grass", "fc_grass", (70, 87, 66), .94, .05, .24, "grass"),
    "soil": MaterialSpec("soil", "fc_soil", (99, 83, 67), .96, .03, .22, "soil"),
    "sand": MaterialSpec("sand", "fc_sand", (160, 147, 119), .94, .04, .15, "sand"),
    "road_marking": MaterialSpec("road_marking", "fc_roadmark", (218, 213, 191), .75, .16, .01, "road_marking"),
    "wood": MaterialSpec("wood", "fc_wood", (115, 87, 62), .83, .12, .10, "wood"),
    "stone": MaterialSpec("stone", "fc_stone", (120, 119, 111), .91, .08, .15, "stone"),
    "window_dark": MaterialSpec("window_dark", "fc_windark", (31, 48, 56), .24, .55, .01, "window_dark", "window"),
    "window_warm": MaterialSpec("window_warm", "fc_winwarm", (165, 130, 86), .26, .42, .01, "window_warm", "window"),
    "window_cool": MaterialSpec("window_cool", "fc_wincool", (94, 127, 145), .22, .52, .01, "window_cool", "window"),
    "sign": MaterialSpec("sign", "fc_sign", (197, 174, 132), .35, .30, .01, "sign", "emissive"),
    "water": MaterialSpec("water", "fc_water", (48, 79, 90), .10, .90, .02, "water", "water"),
    "leaves": MaterialSpec("leaves", "fc_leaves", (59, 81, 58), .88, .06, .16, "leaves"),
    "emissive": MaterialSpec("emissive", "fc_emissive", (202, 177, 121), .30, .18, .00, "emissive", "emissive"),
}

# GTA:SA COL surface codes used for collision/audio/tyres.
COL_SURFACE = {
    "asphalt": 5, "concrete": 5, "sidewalk": 5, "brick": 26,
    "painted_concrete": 5, "glass": 7, "metal": 6, "painted_metal": 6,
    "roof": 5, "grass": 2, "soil": 3, "sand": 18, "road_marking": 5,
    "wood": 20, "stone": 26, "water": 19,
}


def txd_texture_names() -> list[str]:
    return list(dict.fromkeys(spec.texture for spec in MATERIALS.values()))
