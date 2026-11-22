"""Throughput probe (task T034). MANUAL: it calls the paid model API. Never runs in CI.

Sends prompts of the planned sizes with a synthetic page image, at the planned model and
effort per step, and prints output tokens per second and latency percentiles. Paste the
table into docs/experiments.md, then set the provisional budgets from it.

Usage:
  ANTHROPIC_API_KEY=... uv --project backend run python \
      scripts/measure_throughput.py --yes-spend [--n 5]
"""

from __future__ import annotations

import argparse
import base64
import statistics
import sys
from pathlib import Path

from licence_kyb.config import models_config
from licence_kyb.llm.client import (
    AnthropicTransport,
    DailyBudget,
    LLMClient,
    ModelRequest,
)
from licence_kyb.testdata.degrade import rasterise
from licence_kyb.testdata.render import render_licence
from licence_kyb.testdata.spec import make_spec

ROOT = Path(__file__).resolve().parents[1]


def page_image_b64() -> str:
    import io  # noqa: PLC0415 - local to the probe

    spec = make_spec("probe", "DET", "A", set(), seed=1)
    img = rasterise(render_licence(spec), dpi=150)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes-spend", action="store_true", help="confirm paid API use")
    parser.add_argument("--n", type=int, default=5)
    args = parser.parse_args()
    if not args.yes_spend:
        print("Refusing to call the paid API without --yes-spend.", file=sys.stderr)
        return 2

    models = models_config()
    image = page_image_b64()
    client = LLMClient(AnthropicTransport(), DailyBudget(limit_tokens=2_000_000))
    content = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": image},
        },
        {
            "type": "text",
            "text": "Transcribe every field on this licence as plain text lines.",
        },
    ]
    print("| Step | Model | Effort | n | Output tok/s (median) | Latency p50 s | Latency p95 s |")
    print("|---|---|---|---|---|---|---|")
    for step in ("route", "extract_primary", "extract_secondary"):
        cfg = getattr(models, step)
        speeds, latencies = [], []
        for i in range(args.n):
            req = ModelRequest(
                step=f"probe-{step}-{i}",
                model=cfg.model,
                effort=cfg.effort,
                max_tokens=cfg.max_tokens,
                system=f"Throughput probe {i}.",
                messages=[{"role": "user", "content": content}],
                cache_system=False,
            )
            resp = client.call(req)
            seconds = max(resp.latency_ms / 1000, 0.001)
            latencies.append(seconds)
            speeds.append(resp.usage.output_tokens / seconds)
        p95 = sorted(latencies)[max(int(len(latencies) * 0.95) - 1, 0)]
        print(
            f"| {step} | {cfg.model} | {cfg.effort} | {args.n} | {statistics.median(speeds):.0f} "
            f"| {statistics.median(latencies):.1f} | {p95:.1f} |"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
