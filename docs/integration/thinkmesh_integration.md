# ThinkMesh Integration (Adapter + Fallback)

This project now includes a thin adapter at `core/thinkmesh_engine/adapter.py` that
uses ThinkMesh when available and falls back to the local HRM engine otherwise.

## How it works

- On startup, the adapter tries to import `thinkmesh` and binds `think`,
  `ThinkConfig`, `ModelSpec`, and `StrategySpec`.
- If the import or runtime fails, calls are handled by `HRMEngine` so the app
  remains fully functional.
- The adapter exposes:
  - `initialize()` – probe availability and warm up HRM fallback
  - `think(task, ...) -> ThinkResult` – run a reasoning pass
  - `recommend_strategy(text) -> {name, confidence}` – simple heuristic today

## Optional advisory link in CoAct-1

`core/engines/coact_engine.py` optionally initializes the adapter and
consults `recommend_strategy()` for very complex tasks to select an execution
strategy. If ThinkMesh is not installed, behavior is unchanged.

## Installing ThinkMesh (optional)

- Public repo: <https://github.com/Awehbelekker/ThinkMesh>
- Typical install (example):

```bash
pip install -e ".[dev,transformers]"
```

## Example usage (programmatic)

```python
from core.thinkmesh_engine.adapter import ThinkMeshAdapter

adapter = ThinkMeshAdapter()
await adapter.initialize()
res = await adapter.think("Sketch a plan to prove sqrt(2) is irrational.")
print(res.content, res.confidence)
```

## Next steps

- Swap heuristic `recommend_strategy` with a cheap ThinkMesh pass for better
  difficulty estimation.
- Expose traces/metrics from ThinkMesh into the existing logs.
- Add configuration mapping for model/backend selection from `config.json`.
