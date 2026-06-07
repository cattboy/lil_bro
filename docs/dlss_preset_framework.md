# DLSS Preset Framework

How lil_bro decides which DLSS preset to force via NVIDIA Profile Inspector.

## Why a framework

NPI's "Forced Preset Letter" sets ONE global preset letter for all DLSS games.
The real axis is **FP8 hardware capability + a quality/FPS lean**, not VRAM or a
flat per-generation letter. The policy is baked into the exe as Python constants
(`src/utils/dlss_presets.py`) so the "latest model" is a one-line edit; the
letter ↔ NPI-value mechanics stay in `src/utils/nvidia_npi.py`
(`DLSS_VALUE_BY_LETTER`, reverse of `DLSS_LETTER_MAP`).

## Resolution model

| GPU tier | `quality` | `fps` |
|---|---|---|
| FP8 (RTX 40/50) | **M** (gen-2, Performance-tuned) | **L** (gen-2, Ultra-Performance-tuned) |
| no-FP8 (RTX 20/30) | **K** (gen-1) | **K** |
| unsupported (GTX / Pascal / non-RTX / workstation / unknown) | none — "DLSS not supported" | none |

`quality` is the quality-leaning choice *between M and L* (NOT NVIDIA's absolute
DLAA/Quality default, which is K). lil_bro's stance: on FP8 hardware, prefer the
gen-2 transformer. Known tradeoff: in some ray-traced games K can look better than
M/L if the game's denoiser interacts poorly — override per-game if needed.

## Data flow

```
specs["NVIDIA"][0]["GPU"]   (e.g. "NVIDIA GeForce RTX 5090")
        │
        ▼
   classify(name) ─► "unsupported" / "unknown" ─► get_preset() = None
        │                                              │
   "fp8" / "no_fp8"                          ┌─────────┴──────────┐
        │                                    ▼                    ▼
        │                          analyzer: skipped msg   dashboard: card hidden
        ▼
config.nvidia.dlss.priority   (live singleton; seeded QSettings > monitor > JSON > "quality")
        │  "quality" | "fps"   (invalid -> "quality" fallback)
        ▼
   get_preset(name) ─► DlssPreset(letter, value, model_name, tier, priority)
        │                         value via DLSS_VALUE_BY_LETTER (nvidia_npi.py)
        ├─► _check_dlss .............. compare raw[dlss_preset_letter] == preset.value
        ├─► fix_nvidia_profile (full)  write dlss_preset_letter = preset.value
        ├─► fix_nvidia_dlss_preset ... write the 2 DLSS SettingIDs only
        └─► dashboard.set_nvidia_data  "Recommended: DLSS Preset {preset.letter}"
```

## Priority resolution & precedence

`config.nvidia.dlss.priority` is the single live source every consumer reads. It
is seeded once at GUI startup by `Dashboard.seed_dlss_priority(specs)`:

```
manual QSettings toggle  >  monitor-aware default  >  lil_bro_config.json  >  "quality"
```

- **Manual toggle** (`nvidia_profile_card` Quality/FPS buttons): writes
  `QSettings("lil_bro","GUI") dlss/priority`, updates the live config singleton,
  re-renders the card. Once set, it always wins.
- **Monitor-aware** (`monitor_aware_priority`, E2): from the primary display —
  `refresh ≤ 60 → quality`; `≥ 4K → quality`; else `None` (1440p/sub-4K
  high-refresh leaves the toggle/config to decide).
- **lil_bro_config.json** `nvidia.dlss.priority` ("quality"|"fps"): the on-disk
  default, written on first run by `config.save_default_config()`.

The toggle changes no system setting on its own; only **Apply** writes the
profile (gated by approval + a revertible `.nip` backup via the dashboard-fix
manifest path).

## Updating for a new DLSS model

Edit `src/utils/dlss_presets.py`: `_TIERS` (tier → priority → letter), `_GEN_TIER`
(generation → tier), `_MODEL_NAMES` (factual labels). No other code changes. If a
new letter is introduced, confirm it exists in `DLSS_LETTER_MAP` (`nvidia_npi.py`),
cross-referenced to `docs/NPI_CustomSettingNames.xml`.

## Reference data

`docs/dlss_4_5_presets_by_gpu.json` is the detailed per-GPU research reference
(VRAM footprints, sources, caveats). It is NOT loaded at runtime — the runtime
policy is the constants above.

## Deferred (V2, see TODOS)

T-028 (per-resolution `target_mode` + `forced_letter` overrides), E3 (Frame
Generation guidance), E4 (per-game NPI profiles), E5 (DLL version swapping),
E6 (FSR/XeSS for AMD/Intel).
