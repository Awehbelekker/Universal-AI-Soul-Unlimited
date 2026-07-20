"""Agentic tool-directive benchmark using the project's REAL code path.

Exercises the actual Universal-AI-Soul tool protocol:
  - system prompt from wow_tools.tools_system_addon()
  - generation via OllamaIntegration.generate()
  - success scored with wow_tools.parse_tool_directive() against real TOOLS

This is NOT Ollama's native tool_calls API — it is the text-directive
convention the project itself relies on. Run one model per invocation so a
GPU-constrained model (e.g. Bonsai) only needs a brief swap window:

    python benchmarks/bench_tool_directive.py --model llama3.2:3b
    python benchmarks/bench_tool_directive.py --model hf.co/prism-ml/Bonsai-27B-gguf:Q1_0

Results are printed and appended to benchmarks/tool_directive_results.jsonl.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.engines.ollama_integration import OllamaIntegration  # noqa: E402
from core.integrations.wow_tools import (  # noqa: E402
    TOOLS,
    parse_tool_directive,
    tools_system_addon,
)

# (user prompt, expected tool name, expected arg key -> substring the arg value
#  should contain, case-insensitive). arg check is lenient: None means "any arg".
TASKS = [
    ("What's the weather in Cape Town right now?", "weather", ("place", "cape town")),
    ("What time is it in Tokyo?", "time_now", ("tz", "tokyo")),
    ("What is the current price of bitcoin?", "crypto", ("symbol", "b")),
    ("Search the web for the latest SpaceX launch date.", "web_search", ("query", "spacex")),
    ("Give me a quick Wikipedia summary of the Eiffel Tower.", "wikipedia", ("query", "eiffel")),
    ("Define the word 'ephemeral'.", "define", ("word", "ephemeral")),
    ("What is the square root of 8649?", "calc", ("expression", "8649")),
    ("Translate 'good morning' into Spanish.", "translate", ("text", "good morning")),
    ("What's the latest news about renewable energy?", "news", (None, None)),
    ("Give me the weather in Johannesburg.", "weather", ("place", "johannesburg")),
]


def _build_prompt(user_msg: str) -> str:
    """Mirror how the project frames a tool-eligible turn: system addon + user."""
    return f"{tools_system_addon()}\n\nUser: {user_msg}\nAssistant:"


def _score(user_msg, expected_tool, arg_check, text):
    """Return a per-task result dict scoring the real parse path."""
    parsed = parse_tool_directive(text)
    emitted = parsed is not None
    tool_name = parsed[0] if parsed else None
    tool_args = parsed[1] if parsed else {}
    tool_is_real = bool(tool_name and tool_name in TOOLS)
    tool_correct = tool_name == expected_tool
    arg_correct = None
    if tool_correct and arg_check[0] is not None:
        key, want = arg_check
        val = ""
        for k in (key, "q", "query"):
            if isinstance(tool_args, dict) and tool_args.get(k):
                val = str(tool_args[k])
                break
        arg_correct = want.lower() in val.lower()
    elif tool_correct:
        arg_correct = True  # tools with no meaningful arg to check
    return {
        "user": user_msg,
        "expected_tool": expected_tool,
        "emitted_directive": emitted,
        "tool_name": tool_name,
        "tool_is_real": tool_is_real,
        "tool_correct": tool_correct,
        "arg_correct": arg_correct,
    }


async def run(model: str, url: str, temperature: float, max_tokens: int,
              num_gpu: int | None = None):
    integ = OllamaIntegration(model_name=model, base_url=url, auto_optimize=True)
    ok = await integ.initialize()
    if not ok:
        print(f"ERROR: could not initialize Ollama for model {model} at {url}")
        return None
    # Force full GPU offload when requested (needed for 27B models on the swap).
    gen_extra = {"num_gpu": num_gpu} if num_gpu is not None else {}

    rows = []
    tok_s_samples = []
    print(f"\n=== Benchmark: {model} ({len(TASKS)} tasks) ===")
    for user_msg, expected_tool, arg_check in TASKS:
        prompt = _build_prompt(user_msg)
        res = await integ.generate(
            prompt, max_tokens=max_tokens, temperature=temperature,
            top_p=0.95, **gen_extra
        )
        text = res.get("response", "") if res.get("success") else ""
        row = _score(user_msg, expected_tool, arg_check, text)
        row["tok_s"] = round(res.get("tokens_per_second", 0.0), 1)
        row["raw_tail"] = text.strip()[-160:]
        tok_s_samples.append(row["tok_s"])
        rows.append(row)
        mark = "OK " if row["tool_correct"] else "XX "
        print(f"  {mark}{expected_tool:<10} got={row['tool_name']!s:<12} "
              f"arg={row['arg_correct']} {row['tok_s']} tok/s")

    n = len(rows)
    summary = {
        "model": model,
        "n": n,
        "emit_rate": round(sum(r["emitted_directive"] for r in rows) / n, 3),
        "real_tool_rate": round(sum(r["tool_is_real"] for r in rows) / n, 3),
        "correct_tool_rate": round(sum(r["tool_correct"] for r in rows) / n, 3),
        "correct_arg_rate": round(
            sum(1 for r in rows if r["arg_correct"]) / n, 3
        ),
        "avg_tok_s": round(sum(tok_s_samples) / n, 1) if n else 0.0,
    }
    print("\n--- SUMMARY ---")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    out = _ROOT / "benchmarks" / "tool_directive_results.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"summary": summary, "rows": rows,
                            "ts": time.time()}) + "\n")
    print(f"\nAppended results to {out}")

    # Unload the model we loaded so we never leave VRAM pinned (keep_alive=0).
    try:
        await integ.client.post(
            f"{url}/api/generate", json={"model": model, "keep_alive": 0}
        )
        print(f"Unloaded {model} (keep_alive=0).")
    except Exception as e:  # non-fatal
        print(f"WARN: could not unload {model}: {e}")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--url", default="http://127.0.0.1:11434")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--num-gpu", type=int, default=None,
                    help="Force Ollama num_gpu (e.g. 99 for full offload).")
    a = ap.parse_args()
    asyncio.run(run(a.model, a.url, a.temperature, a.max_tokens, a.num_gpu))


if __name__ == "__main__":
    main()
