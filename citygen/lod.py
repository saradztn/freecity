"""Low-detail geometry policy for static city tiles."""
from __future__ import annotations
from .mesh import Mesh


# These are deliberately conservative runtime ranges. MTA applies the user's
# global draw-distance multiplier and caps far objects at the engine limit.
LOD_HIGH_DISTANCE = 125.0
LOD_FAR_DISTANCE = 310.0


def simplify_mesh(source: Mesh, *, stride: int = 3) -> Mesh:
    """Fallback triangle reducer used for tiny utility meshes.

    City tiles normally supply authored low-detail geometry during generation
    (flat building masses, downsampled terrain, no small props). This reducer is
    only a safety net for isolated simple meshes and is not a decimator that
    preserves arbitrary topology.
    """
    if stride <= 1 or len(source.faces) < 12:
        return source
    out = Mesh()
    for index, face in enumerate(source.faces):
        if index % stride == 0:
            tri = (source.vertices[face.a], source.vertices[face.b], source.vertices[face.c])
            out.add_triangle(tuple(v.position for v in tri), face.material,
                             tuple(v.uv for v in tri), tri[0].color,
                             normal=tri[0].normal)
    return out
