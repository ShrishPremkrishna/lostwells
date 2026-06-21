"""Curated 'hero' wells for the human-impact narrative.

Currently EMPTY. The prior heroes (Admiral King OH, Vowinckel PA, AllenCo CA)
were *confirmed / already-remediated* wells, not part of the U-Net Appalachia
discovery set — so they were removed. New hero cases will be chosen from the
wells we actually discovered (see docs/IMPLEMENTATION_PLAN.md §3.14): 3 wells,
each demonstrating a different plugging pathway and each ranking high on local
negative impact. They flow through the same enrichment + scoring + swarm pipeline
plus a `hero` metadata block driving the topo-dissolve UI.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

HEROES: list[dict] = []


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    out = PROC / "heroes.base.json"
    out.write_text(json.dumps(HEROES, separators=(",", ":")))
    print(f"[heroes] wrote {len(HEROES)} hero wells -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
