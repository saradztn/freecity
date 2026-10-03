# Northpoint Harbor — MTA:SA procedural vertical slice

Northpoint Harbor is a new, seedable American coastal-city slice for Multi Theft Auto: San Andreas. It is generated from Python source in this repository; it is not a Los Santos reskin, post-processing preset, or reference-project port.

The current slice contains a connected road graph, a creek bridge, a short tunnel, a freeway/ramp connection, a roundabout and curved local street, a small downtown, residential and commercial blocks, an industrial edge, a park, a marked surface parking lot, generated vegetation, static street furniture, day/weather controls, and 4×4 high/low model tiles. The resource and generator are in scope as a **vertical slice**, not a finished full-size city.

## Build and validate

From the repository root:

```sh
python tools/build_city.py                 # full deterministic rebuild, including procedural textures/audio
python tools/build_city.py --reuse-generated  # re-bake models/JSON while reusing existing DDS/TXD/audio
python tools/build_city.py --clean          # remove the previous generated manifest's outputs, then rebuild
python tools/validate_city.py               # resource, references, geometry, DFF/TXD/COL3, DDS and budgets
python -m unittest discover -s tests -v
```

The first full texture build is CPU-heavy because the maps are generated without third-party imaging dependencies; expect several minutes. `--reuse-generated` requires the existing generated texture dictionary, DDS maps, and thunder WAVs. It fails rather than silently substituting missing files. The seed and world origin can be changed with `--seed`, `--origin-x`, `--origin-y`, and `--origin-z`. The generated MTA resource is `resource/fc_city/`.

## MTA installation and controls

Copy `resource/fc_city/` into the server's `resources/` directory and start it with `start fc_city`. The local development environment used here does not include an MTA server/client, so resource startup, model loading, shader compilation, driving, and weather behavior have **not** been tested in-game.

Client commands:

- `/cityspawn` — move to the generated city spawn.
- `/citydrive` — spawn/relocate with a test vehicle.
- `/fcweather auto|clear|sunset|night|rain|storm|fog|postrain`
- `/fcquality low|medium|high`
- `/fcenv` and `/fchelp`

The first build is isolated around world X=2600, outside the Los Santos road fabric. It uses sixteen 192 m tiles across a 768 m square footprint. Tile models use local coordinates and separate high/low DFFs; the MTA engine handles the object/model LOD distances. The client loads the tile assets at resource start rather than fetching individual DFFs on demand. Quality presets adjust LOD, shader use, far clip, and the budget of nearby dynamic point lights.

## Generated deliverables

- `resource/fc_city/models/` — sixteen high and low DFF tiles and COL3 collision files.
- `resource/fc_city/textures/` — RenderWare TXD, standalone DXT1 DDS maps and PNG source/albedo images.
- `resource/fc_city/data/` — runtime tile/spawn/light data, road graph, placements, registry, budgets, and build manifest.
- `resource/fc_city/client/`, `server/`, `shaders/` — MTA lifecycle, LOD/model loading, commands, time/weather/material controls, and DX9 effects.
- `citygen/` — independent terrain, road graph, road/intersection, bridge/tunnel/highway, building, land-use, prop, vegetation, texture, RenderWare, export, and validation modules.

The current measured build has **44 road nodes / 64 connected segments**, **22 buildings**, **34 generated intersection records**, **26 tree instances**, **103 possible lamp records** (quality presets cap active dynamic lights at 6/14/24), a **20-space parking lot**, **76,100 high+low visual triangles**, **17,576 collision triangles**, and about **14.3 MB of DDS+TXD texture payload**, below the configured 120,000-triangle and 32 MiB texture limits. See `resource/fc_city/data/build_report.json` for generated counts.

## Validation boundary

The Python validator checks road/layout constraints, runtime references, resource paths, JSON, DFF chunk/mesh/material indices, TXD names/mips, COL3 offsets/face groups/bounds, DDS headers/mips, and configured budgets. It performs lexical Lua/HLSL checks in this environment. No `luac`, D3D9 HLSL compiler, or MTA runtime was available; it therefore does **not** claim those languages were compiled or the resource was tested in-game. It validates the written COL3 layout structurally, not by loading it in GTA/MTA.

See [`docs/architecture.md`](docs/architecture.md) and [`docs/limitations.md`](docs/limitations.md) before extending the slice.
