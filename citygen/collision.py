"""COL3 collision mesh authoring and mesh-to-collision utilities."""
from __future__ import annotations
from dataclasses import dataclass, field
from .math3d import Vec3, add, bounds3
from .materials import COL_SURFACE


@dataclass
class CollisionFace:
    a: int
    b: int
    c: int
    surface: int = 5
    light: int = 255


@dataclass
class CollisionMesh:
    vertices: list[Vec3] = field(default_factory=list)
    faces: list[CollisionFace] = field(default_factory=list)
    _lookup: dict[tuple[int, int, int], int] = field(default_factory=dict, repr=False)

    def _vertex(self, p: Vec3) -> int:
        key = (round(p[0] * 128), round(p[1] * 128), round(p[2] * 128))
        if key in self._lookup:
            return self._lookup[key]
        idx = len(self.vertices)
        self.vertices.append((key[0] / 128.0, key[1] / 128.0, key[2] / 128.0))
        self._lookup[key] = idx
        return idx

    def add_triangle(self, p0: Vec3, p1: Vec3, p2: Vec3, surface: int = 5, light: int = 255) -> None:
        # Reject degenerate physics faces up front.
        ax, ay, az = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
        bx, by, bz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
        nx, ny, nz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
        if nx * nx + ny * ny + nz * nz < 1e-8:
            return
        self.faces.append(CollisionFace(self._vertex(p0), self._vertex(p1), self._vertex(p2), surface, light))

    def add_quad(self, p0: Vec3, p1: Vec3, p2: Vec3, p3: Vec3, surface: int = 5, light: int = 255) -> None:
        self.add_triangle(p0, p1, p2, surface, light)
        self.add_triangle(p0, p2, p3, surface, light)

    def add_box(self, center: Vec3, size: Vec3, surface: int = 5, light: int = 255) -> None:
        cx, cy, cz = center
        hx, hy, hz = size[0] * .5, size[1] * .5, size[2] * .5
        x0, x1, y0, y1, z0, z1 = cx - hx, cx + hx, cy - hy, cy + hy, cz - hz, cz + hz
        self.add_quad((x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1),surface,light)
        self.add_quad((x1,y1,z0),(x0,y1,z0),(x0,y1,z1),(x1,y1,z1),surface,light)
        self.add_quad((x1,y0,z0),(x1,y1,z0),(x1,y1,z1),(x1,y0,z1),surface,light)
        self.add_quad((x0,y1,z0),(x0,y0,z0),(x0,y0,z1),(x0,y1,z1),surface,light)
        self.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1),surface,light)
        self.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y0,z0),(x0,y0,z0),surface,light)

    def extend(self, other: "CollisionMesh", offset: Vec3 = (0.0, 0.0, 0.0)) -> None:
        for face in other.faces:
            p0, p1, p2 = (add(other.vertices[i], offset) for i in (face.a, face.b, face.c))
            self.add_triangle(p0, p1, p2, face.surface, face.light)

    def shifted(self, offset: Vec3) -> "CollisionMesh":
        result = CollisionMesh()
        result.extend(self, offset)
        return result

    @property
    def bounds(self) -> tuple[Vec3, Vec3]:
        return bounds3(self.vertices)

    def translated(self, offset: Vec3) -> "CollisionMesh":
        result = CollisionMesh()
        result.extend(self, (-offset[0], -offset[1], -offset[2]))
        return result


def material_surface(material: str) -> int:
    return COL_SURFACE.get(material, 5)


def add_mesh_collision(target: CollisionMesh, points: tuple[Vec3, ...], material: str) -> None:
    surface = material_surface(material)
    if len(points) == 3:
        target.add_triangle(points[0], points[1], points[2], surface)
    elif len(points) == 4:
        target.add_quad(*points, surface=surface)
