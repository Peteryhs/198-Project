# Reproducing model coefficients

From the repository root use `uv run --locked python scripts/<script>.py ...`.
`pyproject.toml` pins the three numerical packages, `uv.lock` pins transitive packages,
and Python is constrained to 3.12 (the accepted export was verified with 3.12.14).
`requirements-modelling.txt` remains the version contract; its agreement with the project/lock
is checked by `scripts/test_modelling_environment.py`. Imported modelling code fails before
fitting when installed versions differ, including a bypass via `--no-project --with ...`.

For an explicit bootstrap without a project environment:

```sh
uv venv --python 3.12 /tmp/tally-env
uv pip sync --python /tmp/tally-env/bin/python scripts/requirements-modelling.txt
/tmp/tally-env/bin/python scripts/test_modelling_environment.py
```

`uv run` defaults to a local `.venv`; set `UV_PROJECT_ENVIRONMENT` and `UV_CACHE_DIR` to writable
paths if required. Round two uses `/tmp/tally-round2-env` and `/tmp/tally-uv-cache`. A version pin
prevents silent solver upgrades; CPU/BLAS/platform numerical differences remain possible, so
export verification is still required. Keep the historical exports; do not refresh them just
to make a changed solver pass.

```sh
uv run --locked python scripts/test_realtime_pipeline.py
uv run --locked python scripts/verify_linear_export.py model/realtime-linear --arm-object
uv run --locked python scripts/test_paired_pipeline.py
uv run --locked python scripts/test_streaming_pipeline.py
uv run --locked python scripts/test_paired_runtime.py
```

Simulation and optical-reference commands require the pinned optional host extra:
`uv run --locked --extra simulation python scripts/test_limb_simulation.py` and
`uv run --locked --extra simulation python scripts/simulation_experiment.py data/phytmo/inertial/upper`.
The extra is excluded from deployment; MCU inference uses only the generated C coefficients.

Additional round-two checks:

```sh
uv run --locked --extra simulation python scripts/verify_round2.py
uv run --locked python scripts/measure_round2_target.py
```

`verify_round2.py` imports the placement experiment and therefore needs the host simulation extra.
It verifies every stored LOSO series decision, exact fresh-fit coefficient agreement and C parity
for all valid paired models/controls. The size command uses Clang/llvm-size/llvm-nm and emits an
unlinked target unity object without requiring an installed ARM linker or Arduino core.
