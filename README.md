# FastF1 Race Parameter Pipeline

> 🇨🇳 阅读中文版本？请查看 [`README.zh-CN.md`](README.zh-CN.md).

## Overview

This repository automates the preparation of race parameter (`pars`) files for the **F1 Manager** ecosystem by extracting real-world telemetry from the [FastF1](https://theoehrly.github.io/Fast-F1/) API.  
The pipeline converts an initial `race_pars_*.ini` template into a fully populated `pars_*.ini` file that includes refreshed tyre strategies, fitted tyre degradation coefficients, grid positions, tyre availability, and qualifying pace references.

```
Race data (FastF1) ──▶ race_pars template ──▶ updated strategy ──▶ fitted tyres ──▶ final pars file
```

### Key Features

- Fetches race and qualifying data directly from FastF1 with local caching.
- Rebuilds per-driver stint strategy entries (`strategy_info` and `real_strategy` blocks).
- Fits tyre degradation models (linear by default) for missing compounds using SciPy curve fitting.
- Updates pit lane loss estimates and qualifying benchmark pace in the track parameters.
- Produces final `pars_*.ini` files ready for downstream simulations or Monte Carlo tooling.

## Repository Layout

- `f1_pipeline_main.py` – orchestrates the three-stage pipeline.
- `update_ini_strategy.py` – replaces strategy sections using actual stint data.
- `fit_tire_degradation.py` – derives tyre wear coefficients and pit time losses.
- `convert_pars.py` – normalises the INI structure and injects qualifying & tyre metadata.
- `data/` – sample input templates (`race_pars`) and Monte Carlo parameter packs.
- `f1_cache/` – cached FastF1 telemetry (created automatically on first run).

## Prerequisites

- Python 3.9+ (FastF1 currently targets modern CPython releases).
- A working internet connection for initial FastF1 downloads.
- Microsoft Visual C++ Build Tools (Windows) if SciPy wheels fall back to compilation.

Install Python dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate          # PowerShell on Windows
pip install -r requirements.txt
```

> Tip: Keep the virtual environment activated whenever you run the pipeline.

## FastF1 Cache

The first request for a session retrieves data from F1 servers and stores it under `f1_cache/`.  
Subsequent runs reuse the cached parquet/JSON files. You can prune unused seasons manually if disk space becomes tight, but keep at least the sessions you intend to process.

## Running the Pipeline

1. Place or update your base `race_pars_*.ini` file in the project root (or adjust the path).
2. Open `f1_pipeline_main.py` and edit the configuration block in `main()`:

```python
YEAR = 2025
RACE_NAME = "Japan"
BASE_INI_FILE = "race_pars_Suzuka.ini"
```

3. Execute the orchestrator:

```bash
python f1_pipeline_main.py
```

4. Follow the console prompts. By default, intermediate files are kept:
   - `<base>_updated.ini` – after strategy refresh
   - `<base>_final.ini` – after tyre fitting
   - `pars_<track>_<year>.ini` – final output

5. Optionally choose to delete intermediate artefacts when prompted.

### Using the Stages Individually

Each module exposes a callable entry point:

- `update_ini_strategy.update_ini_file(input_file, output_file, year, race_name)`
- `fit_tire_degradation.update_tire_parameters(input_file, output_file, year, race_name, model="lin")`
- `convert_pars.convert_race_pars_to_pars(input_file, output_file, year, race_name)`

You can import these functions into notebooks or scripts for custom workflows.

## Configuration Notes

- **Tyre mapping**: both `update_ini_strategy.py` and `fit_tire_degradation.py` contain dictionaries that translate FastF1 compound labels to the game-specific nomenclature (`A2`, `A3`, ...). Adjust them for sprint formats or special events if needed.
- **Tyre models**: switch to the quadratic model by passing `model="quad"` into `update_tire_parameters`, understanding it requires more data points per stint for stable fits.
- **Special driver codes**: Nico Hülkenberg (`HÜL`) receives bespoke handling to align with INI expectations.
- **Fuel effect assumption**: `fit_tire_degradation.py` subtracts `0.063 s/lap` by default. Tune `FUEL_EFFECT_PER_LAP` when modelling alternative fuel burn assumptions.

## Troubleshooting

- **Missing sessions**: FastF1 session names use English event titles (e.g., `"Singapore"`). Verify `RACE_NAME` matches the official calendar.
- **HTTP failures**: If API calls fail, ensure you are on FastF1 ≥ 3.2 and that SSL certificates are up to date.
- **Insufficient laps**: Some drivers/compounds may not have enough valid laps for curve fitting. The pipeline reports these cases and leaves parameters untouched.

## Contributing

Pull requests are welcome. If you add new circuits or tweak modelling assumptions, document the change in both `README` files and ensure the pipeline continues to run end-to-end.

## License

This project is distributed for personal data exploration. Please confirm that your use of FastF1 data complies with the F1 timing terms of service.


