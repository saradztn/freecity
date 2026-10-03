"""Small deterministic geometry helpers (z-up coordinates)."""
from __future__ import annotations
import math
from typing import Iterable

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]


def add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a: Vec3) -> float:
    return math.sqrt(dot(a, a))


def normalize(a: Vec3, fallback: Vec3 = (0.0, 0.0, 1.0)) -> Vec3:
    n = length(a)
    if n < 1e-9:
        return fallback
    return (a[0] / n, a[1] / n, a[2] / n)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def smoothstep(a: float, b: float, x: float) -> float:
    if a == b:
        return 0.0
    t = clamp((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def distance2(a: Vec2, b: Vec2) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def bezier2(p0: Vec2, p1: Vec2, p2: Vec2, p3: Vec2, t: float) -> Vec2:
    u = 1.0 - t
    b0, b1, b2, b3 = u * u * u, 3.0 * u * u * t, 3.0 * u * t * t, t * t * t
    return (b0 * p0[0] + b1 * p1[0] + b2 * p2[0] + b3 * p3[0],
            b0 * p0[1] + b1 * p1[1] + b2 * p2[1] + b3 * p3[1])


def polyline_length(points: Iterable[Vec3]) -> float:
    pts = list(points)
    return sum(length(sub(pts[i + 1], pts[i])) for i in range(len(pts) - 1))


def closest_point_on_segment_2d(p: Vec2, a: Vec2, b: Vec2) -> tuple[Vec2, float]:
    abx, aby = b[0] - a[0], b[1] - a[1]
    d2 = abx * abx + aby * aby
    if d2 <= 1e-12:
        return a, 0.0
    t = clamp(((p[0] - a[0]) * abx + (p[1] - a[1]) * aby) / d2, 0.0, 1.0)
    return (a[0] + abx * t, a[1] + aby * t), t


def point_segment_distance_2d(p: Vec2, a: Vec2, b: Vec2) -> tuple[float, float]:
    q, t = closest_point_on_segment_2d(p, a, b)
    return distance2(p, q), t


def bounds3(points: Iterable[Vec3]) -> tuple[Vec3, Vec3]:
    pts = list(points)
    if not pts:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    return ((min(p[0] for p in pts), min(p[1] for p in pts), min(p[2] for p in pts)),
            (max(p[0] for p in pts), max(p[1] for p in pts), max(p[2] for p in pts)))


def fmt_float(value: float) -> float:
    """Round manifest floats consistently while keeping mesh precision separate."""
    return round(float(value), 4)
