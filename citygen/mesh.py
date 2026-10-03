"""Render mesh construction primitives; faces are always explicit triangles."""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Iterable
from .math3d import Vec2, Vec3, add, cross, normalize, sub

Color = tuple[int, int, int, int]


@dataclass
class Vertex:
    position: Vec3
    normal: Vec3
    uv: Vec2
    color: Color = (255, 255, 255, 255)


@dataclass
class Face:
    a: int
    b: int
    c: int
    material: str


@dataclass
class Mesh:
    vertices: list[Vertex] = field(default_factory=list)
    faces: list[Face] = field(default_factory=list)

    @property
    def triangle_count(self) -> int:
        return len(self.faces)

    @property
    def materials(self) -> list[str]:
        seen: dict[str, None] = {}
        for face in self.faces:
            seen.setdefault(face.material, None)
        return list(seen)

    def append(self, other: "Mesh", offset: Vec3 = (0.0, 0.0, 0.0)) -> None:
        base = len(self.vertices)
        for v in other.vertices:
            self.vertices.append(Vertex(add(v.position, offset), v.normal, v.uv, v.color))
        self.faces.extend(Face(f.a + base, f.b + base, f.c + base, f.material) for f in other.faces)

    def add_triangle(self, points: tuple[Vec3, Vec3, Vec3], material: str,
                     uvs: tuple[Vec2, Vec2, Vec2] = ((0, 0), (1, 0), (0, 1)),
                     color: Color = (255, 255, 255, 255), normal: Vec3 | None = None) -> None:
        n = normalize(normal or cross(sub(points[1], points[0]), sub(points[2], points[0])))
        base = len(self.vertices)
        for p, uv in zip(points, uvs):
            self.vertices.append(Vertex(p, n, uv, color))
        self.faces.append(Face(base, base + 1, base + 2, material))

    def add_quad(self, points: tuple[Vec3, Vec3, Vec3, Vec3], material: str,
                 uvs: tuple[Vec2, Vec2, Vec2, Vec2] = ((0, 0), (1, 0), (1, 1), (0, 1)),
                 color: Color = (255, 255, 255, 255), normal: Vec3 | None = None) -> None:
        n = normalize(normal or cross(sub(points[1], points[0]), sub(points[2], points[0])))
        base = len(self.vertices)
        for p, uv in zip(points, uvs):
            self.vertices.append(Vertex(p, n, uv, color))
        self.faces.append(Face(base, base + 1, base + 2, material))
        self.faces.append(Face(base, base + 2, base + 3, material))

    def add_box(self, center: Vec3, size: Vec3, material: str,
                roof_material: str | None = None, color: Color = (255, 255, 255, 255)) -> None:
        """Add a closed rectangular solid with outward-facing normals."""
        cx, cy, cz = center
        hx, hy, hz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
        x0, x1, y0, y1, z0, z1 = cx - hx, cx + hx, cy - hy, cy + hy, cz - hz, cz + hz
        # UVs repeat at approximately 1 unit per 4 world units.
        u = max(1.0, size[0] / 4.0)
        v = max(1.0, size[2] / 4.0)
        side_uv = ((0, 0), (u, 0), (u, v), (0, v))
        self.add_quad(((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)), material, side_uv)
        self.add_quad(((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)), material, side_uv)
        self.add_quad(((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)), material,
                      ((0, 0), (max(1.0, size[1] / 4.0), 0), (max(1.0, size[1] / 4.0), v), (0, v)))
        self.add_quad(((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)), material,
                      ((0, 0), (max(1.0, size[1] / 4.0), 0), (max(1.0, size[1] / 4.0), v), (0, v)))
        top = roof_material or material
        self.add_quad(((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)), top,
                      ((0, 0), (u, 0), (u, max(1.0, size[1] / 4.0)), (0, max(1.0, size[1] / 4.0))))
        self.add_quad(((x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)), material,
                      ((0, 0), (u, 0), (u, max(1.0, size[1] / 4.0)), (0, max(1.0, size[1] / 4.0))))

    def add_cylinder(self, base: Vec3, radius: float, height: float, material: str,
                     sides: int = 8, top_radius: float | None = None, cap: bool = True,
                     color: Color = (255, 255, 255, 255)) -> None:
        """Add a z-axis cylinder/frustum. Suitable for poles and tree trunks."""
        x, y, z = base
        rt = radius if top_radius is None else top_radius
        low: list[Vec3] = []
        high: list[Vec3] = []
        for i in range(sides):
            a = 2.0 * math.pi * i / sides
            low.append((x + radius * math.cos(a), y + radius * math.sin(a), z))
            high.append((x + rt * math.cos(a), y + rt * math.sin(a), z + height))
        for i in range(sides):
            j = (i + 1) % sides
            # Radial face normal is supplied per face for a clean low-poly smooth approximation.
            n = normalize((math.cos(2 * math.pi * (i + 0.5) / sides),
                           math.sin(2 * math.pi * (i + 0.5) / sides), 0.0))
            self.add_quad((low[i], low[j], high[j], high[i]), material,
                          ((i / sides, 0), ((i + 1) / sides, 0), ((i + 1) / sides, height / 4), (i / sides, height / 4)),
                          color=color, normal=n)
        if cap:
            center=(x,y,z+height)
            for i in range(sides):
                j=(i+1)%sides
                self.add_triangle((center,high[i],high[j]),material,
                                  ((.5,.5),(0,0),(1,0)),color=color,normal=(0,0,1))

    def add_ellipsoid(self, center: Vec3, radii: Vec3, material: str, rings: int = 6, sides: int = 10,
                      color: Color = (255, 255, 255, 255)) -> None:
        """UV ellipsoid assembled as triangles with analytic vertex normals."""
        cx, cy, cz = center
        rx, ry, rz = radii
        grid: list[list[tuple[Vec3, Vec3, Vec2]]] = []
        for r in range(rings + 1):
            theta = math.pi * r / rings
            row = []
            for s in range(sides + 1):
                phi = 2.0 * math.pi * s / sides
                nx, ny, nz = math.sin(theta) * math.cos(phi), math.sin(theta) * math.sin(phi), math.cos(theta)
                p = (cx + rx * nx, cy + ry * ny, cz + rz * nz)
                n = normalize((nx / max(rx, 0.001), ny / max(ry, 0.001), nz / max(rz, 0.001)))
                row.append((p, n, (s / sides, r / rings)))
            grid.append(row)
        for r in range(rings):
            for s in range(sides):
                p00, p01 = grid[r][s], grid[r][s + 1]
                p10, p11 = grid[r + 1][s], grid[r + 1][s + 1]
                if r > 0:  # avoid duplicate-vertex triangles at the north pole
                    self._add_triangle_with_normals((p00, p10, p11), material, color)
                if r < rings - 1:  # and at the south pole
                    self._add_triangle_with_normals((p00, p11, p01), material, color)

    def _add_triangle_with_normals(self, verts: tuple, material: str, color: Color) -> None:
        base = len(self.vertices)
        for p, n, uv in verts:
            self.vertices.append(Vertex(p, n, uv, color))
        self.faces.append(Face(base, base + 1, base + 2, material))

    def add_disk(self, center: Vec3, radius: float, material: str, sides: int = 16,
                 color: Color = (255, 255, 255, 255), normal: Vec3 = (0, 0, 1)) -> None:
        x, y, z = center
        for i in range(sides):
            a0, a1 = 2.0 * math.pi * i / sides, 2.0 * math.pi * (i + 1) / sides
            p0 = (x, y, z)
            p1 = (x + radius * math.cos(a0), y + radius * math.sin(a0), z)
            p2 = (x + radius * math.cos(a1), y + radius * math.sin(a1), z)
            self.add_triangle((p0, p1, p2), material, ((0.5, 0.5), (0.5 + 0.5 * math.cos(a0), 0.5 + 0.5 * math.sin(a0)),
                                                           (0.5 + 0.5 * math.cos(a1), 0.5 + 0.5 * math.sin(a1))), color, normal)
