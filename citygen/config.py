"""Build configuration and stable vertical-slice identity."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CityConfig:
    name: str = "Northpoint Harbor"
    seed: int = 20261003
    # Isolated east-ocean slot, outside the Los Santos/San Andreas road fabric.
    origin_x: float = 2600.0
    origin_y: float = 0.0
    origin_z: float = 0.0
    tile_size: float = 192.0
    tiles_per_axis: int = 4
    terrain_step: float = 12.0
    asset_limit: int = 250
    triangle_budget: int = 120_000
    texture_budget_bytes: int = 32 * 1024 * 1024

    @property
    def world_min(self) -> float:
        return -(self.tile_size * self.tiles_per_axis) / 2.0

    @property
    def world_max(self) -> float:
        return (self.tile_size * self.tiles_per_axis) / 2.0

    @property
    def tile_centers(self) -> list[tuple[int, int, float, float]]:
        half = self.tiles_per_axis // 2
        result = []
        for gy in range(self.tiles_per_axis):
            for gx in range(self.tiles_per_axis):
                ix, iy = gx - half, gy - half
                cx = (gx + 0.5) * self.tile_size + self.world_min
                cy = (gy + 0.5) * self.tile_size + self.world_min
                result.append((ix, iy, cx, cy))
        return result


DEFAULT_CONFIG = CityConfig()
