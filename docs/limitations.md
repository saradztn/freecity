# MTA / Direct3D 9 behavior and current limitations

This is source/build documentation, not a claim of successful in-game integration. No MTA server or client was available during this work.

## Honest approximations

- `wet_road.fx` blends asphalt tint with a wetness scalar and a generated puddle/mask texture, then adds a small, material-local normal/specular highlight. It does **not** sample the scene depth buffer and is not screen-space reflection (SSR). Puddles are shading masks, not water geometry.
- `water.fx` animates local normal/noise response and sky tint on the generated water material. It does **not** reflect the rendered city, vehicles, or sky via SSR or a cube-map capture.
- `window_light.fx` varies generated glazing by the time-of-day controller. It is an emissive material approximation; it does not illuminate rooms or cast light into the world.
- Street lights are nearby, budgeted MTA point-light elements. They do not provide shadow maps or global illumination. Each quality level limits active local lights.
- Sun/sky/fog/rain use MTA's world/weather controls. Their visual result can depend on server sync, graphics settings and the MTA/GTA build. The resource does not draw a static sun disc or replace the screen with a pre-rendered sky.
- Thunder audio is generated locally and cued sparsely during native GTA storm weather. Visible lightning is left to the GTA weather system; this resource does not draw screen-space bolts or claim volumetric lightning control.
- Native MTA/GTA engine shadowing and vehicle lighting remain responsible for features this resource cannot supply.

## Validation boundary

The build validator structurally checks generated DFF/TXD/COL3/DDS files and validates the resource XML and references. COL3 offsets, face groups, fixed-point vertices, and triangle indices are checked, but the file has not been loaded by GTA/MTA. DFF/TXD chunks and material links are parsed by the project's own checker, not by RenderWare Studio or MTA.

The current environment lacks `luac`/MTA's Lua runtime and an HLSL compiler for the D3D9 `ps_2_0` profile. Lua blocks/brackets and shader entrypoint/brackets are checked lexically only. Use MTA's `debugscript 3`, shader diagnostics, and a test server/client before treating the resource as runtime-validated.

## Known scope gaps

The build covers one compact 4×4-tile slice. It does not yet create a complete city, traffic simulation, pedestrian/navigation network, underground interiors, procedural signs for every road, streamed asset-on-demand downloader, wetness accumulation by individual surface, or runtime collision/vehicle-performance profiling. Geometry, shader quality and actual road drivelines remain to be reviewed in MTA. Extending the generator should preserve these caveats until such tests are performed.
