# Notebooks

Interactive walkthroughs of the `agent_management` library. Two notebooks, two angles:

- **`agent_management_quickstart.ipynb`** — *operate* the framework: a tour of the lifecycle and the
  `agent-mgmt-*` commands. Safe (dry-run by default).
- **`build_from_scratch.ipynb`** — *author* the artifacts: build a semantic view, agent, and evals from
  nothing, then promote them into the repo. Live (creates and drops sandbox objects).

## Environment setup (run this first)

The notebooks run in this project's `uv` environment. Install the notebook tooling (Jupyter kernel +
the package) once:

```bash
uv sync --extra notebook --extra crypto --extra dev
```

This installs `ipykernel` + `jupyterlab` alongside `agent-management` into `.venv`. Then point your
notebook front-end at that environment:

- **VS Code / Cursor**: open a notebook and pick the kernel named `.venv (Python 3.11.x)`.
- **JupyterLab**: `uv run jupyter lab`.
- **Named kernel (optional)**: register an explicit kernel that other Jupyter installs can see:

  ```bash
  uv run python -m ipykernel install --user --name agent-mgmt --display-name "Agent Mgmt (.venv)"
  ```

If you see `ModuleNotFoundError: No module named 'agent_management'`, the notebook is pointed at the
wrong kernel — reselect the project `.venv` kernel above.

## `agent_management_quickstart.ipynb`

An end-to-end showcase of the library as a complete product. It walks the full lifecycle:

```
config  ->  validate  ->  semantic views  ->  agents  ->  evals  ->  testing
```

Each step maps to a product CLI (`agent-mgmt-*`) and to the GitHub Actions workflow that runs it, so the
notebook doubles as living documentation of the CI/CD flow.

### Key properties

- **Environment-parameterized** — set `ENV = "dev"` or `ENV = "prod"` in the Parameters cell.
- **Safe by default** — `LIVE = False` keeps everything dry-run / read-only. A top-to-bottom run never
  mutates Snowflake. Set `LIVE = True` to deploy and evaluate against the selected environment.

### Running it

1. Install the package (the notebook's first code cell has `%pip install -e ..`, commented):

   ```bash
   pip install -e .
   ```

2. For **live** runs, make Snowflake credentials available to the connector before launching Jupyter,
   e.g. a named connection:

   ```bash
   export SNOWFLAKE_CONNECTION_NAME=myconnection
   ```

   or explicit key-pair auth (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY_PATH`).

3. Open the notebook and run the cells top to bottom.

## `build_from_scratch.ipynb`

A hands-on guide to **authoring** the framework's artifacts from scratch. It builds a small,
self-contained example end to end using real data already in your database:

```
demo table  ->  semantic view  ->  agent  ->  smoke test  ->  golden dataset + eval  ->  promote to repo
```

It teaches the underlying primitives (`SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`, the `deploy_agent()`
versioning path, dynamic ground-truth evals) and ends by showing exactly where each authored file
belongs in the repo and which CLI/workflow consumes it.

### Key properties

- **Environment-parameterized** — `ENV = "dev"` (recommended) or `"prod"`.
- **Live by design** — it creates real Snowflake objects in an isolated `SANDBOX` schema and drops them
  in a teardown cell. Set `RUN_LIVE = False` for a no-op read-through.
- **Non-polluting** — authored artifacts go to temp files during the demo; the final section shows how
  to copy them into `semantic-views/`, `agents/`, and `agent-evaluation/`.

### Running it

1. Install the package: `pip install -e .` (the first code cell has `%pip install -e ..`, commented).
2. Provide Snowflake credentials (e.g. `export SNOWFLAKE_CONNECTION_NAME=myconnection`).
3. Ensure the target database has the ski-resort `MARTS` tables (the demo reads `MARTS.FACT_INCIDENTS`
   and `MARTS.DIM_DATE`).
4. Run top to bottom; run the teardown cell when done.
