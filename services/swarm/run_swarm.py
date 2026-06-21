"""Run the investigator swarm on a cohort and cache dossiers.

Cohort = the hero wells + the top-ranked candidates (default 12 total, per the
locked budget decision). Reads ANTHROPIC_API_KEY from the environment. Existing
dossiers in data/processed/dossiers.json are reused (cache/fallback) — only
uncached wells are investigated live, so re-runs are cheap and the demo always
has data even if the live swarm is skipped.

Usage:
  python run_swarm.py --total 12          # 3 heroes + 9 top candidates
  python run_swarm.py --smoke 1           # one well, for a live sanity check
  python run_swarm.py --total 12 --force  # re-investigate even if cached
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # services/
from dotenv_min import load_root_env  # noqa: E402

load_root_env()  # pick up ANTHROPIC_API_KEY from <repo-root>/.env if present
from graph import build_graph  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"


APPALACHIA = {"OH", "PA", "WV", "KY"}


def load_cohort(total: int) -> list[dict]:
    """Heroes + top Appalachia candidates. (Global rank puts CA/OK first, which is
    the validation layer — the swarm investigates the discovery set.)"""
    heroes = json.loads((PROC / "heroes.json").read_text()) if (PROC / "heroes.json").exists() else []
    hero_ids = {h.get("well_id") for h in heroes}
    candidates = json.loads((PROC / "candidates.scored.json").read_text())
    app = [c for c in candidates
           if c.get("state_abbr") in APPALACHIA and c.get("well_id") not in hero_ids]
    app.sort(key=lambda c: c.get("rank") if c.get("rank") is not None else 10**9)
    n_cand = max(0, total - len(heroes))
    return heroes + app[:n_cand]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--total", type=int, default=12)
    ap.add_argument("--smoke", type=int, default=0, help="investigate only N wells")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[swarm] ANTHROPIC_API_KEY not set — cannot run live. Cached dossiers (if any) "
              "remain the app's data source.")
        sys.exit(1)

    cohort = load_cohort(args.total)
    if args.smoke:
        cohort = cohort[: args.smoke]

    dossiers_path = PROC / "dossiers.json"
    existing = json.loads(dossiers_path.read_text()) if dossiers_path.exists() else {}

    todo = cohort if args.force else [
        w for w in cohort if existing.get(w["well_id"], {}).get("status") not in ("complete", "partial")
    ]
    print(f"[swarm] cohort={len(cohort)} | cached={len(cohort) - len(todo)} | to investigate={len(todo)}")
    if not todo:
        print("[swarm] nothing to do — all cohort wells already have dossiers.")
        return

    graph = build_graph()
    result = graph.invoke(
        {"wells": todo, "dossiers": []},
        config={"max_concurrency": args.concurrency, "configurable": {"thread_id": "lost-wells-swarm"}},
    )

    for d in result["dossiers"]:
        if d.get("well_id"):
            existing[d["well_id"]] = d
    dossiers_path.write_text(json.dumps(existing, indent=2, default=str))

    ok = sum(1 for d in result["dossiers"] if d.get("status") == "complete")
    print(f"[swarm] investigated {len(result['dossiers'])} wells "
          f"({ok} complete) -> {dossiers_path.relative_to(ROOT)}")
    for d in result["dossiers"]:
        print(f"    [{d.get('status'):>8}] {d.get('well_id')}: "
              f"{(d.get('narrative') or '')[:90]}")


if __name__ == "__main__":
    main()
