"""Living knowledge doc (§3.11): reusable findings the agents accumulate.

A deduped, append-only store of facts worth reusing across investigations — state
plugging programs, funders/charities, carbon programs, plugging contractors,
intake routes — so the swarm doesn't re-derive them per well. Backed by
`data/processed/knowledge.json` (committed, read by the app); mirrors to Redis when
reachable (graceful). Seeded from the static registries so it's non-empty, and
appended to by the swarm as it surfaces new entities.

CLI:  python services/swarm/knowledge.py seed
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
STATIC = ROOT / "data" / "static"
KFILE = PROC / "knowledge.json"
WEB = ROOT / "apps" / "web" / "public" / "data" / "knowledge.json"


def _load() -> list[dict]:
    try:
        return json.loads(KFILE.read_text()) if KFILE.exists() else []
    except Exception:  # noqa: BLE001
        return []


def _key(topic: str, value: str) -> str:
    return hashlib.sha1(f"{topic}:{value}".encode()).hexdigest()[:12]


def _write(items: list[dict]) -> None:
    KFILE.write_text(json.dumps(items, indent=1, ensure_ascii=False))
    if WEB.parent.exists():
        WEB.write_text(json.dumps(items, indent=1, ensure_ascii=False))
    # Best-effort Redis mirror (graceful; no-op when unreachable).
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent / "web"))
        import cache  # noqa: E402
        c = cache._redis()  # noqa: SLF001
        if c:
            c.set("knowledge:all", json.dumps(items), ex=60 * 60 * 24 * 30)
    except Exception:  # noqa: BLE001
        pass


def record(topic: str, value: str, source: str, well_id: str | None = None) -> bool:
    """Append a finding if new (deduped by topic+value). Returns True if added."""
    if not value or not value.strip():
        return False
    items = _load()
    keys = {i.get("key") for i in items}
    k = _key(topic, value.strip())
    if k in keys:
        return False
    items.append({"key": k, "topic": topic, "value": value.strip(),
                  "source": source, "well_id": well_id})
    _write(items)
    return True


def _csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def seed() -> None:
    """Populate from the static registries + the known carbon facts."""
    n = 0
    for r in _csv(STATIC / "state_regulators.csv"):
        if r.get("agency"):
            n += record("state_program",
                        f"{r['state']}: {r['agency']} — {r.get('program_name','plugging program')} "
                        f"(BIL/IIJA-funded)", source="state_regulators.csv")
    for r in _csv(STATIC / "intake_adapters.csv"):
        if r.get("org") and r.get("fit"):
            n += record("funder", f"{r['org']} — {r['fit']}", source="intake_adapters.csv")
    for topic, value, src in [
        ("carbon_program",
         "ACR Orphaned Well Methodology (2023): plugging a high-emitter can mint carbon "
         "credits — Zefiro ACR959 = 92,956 t CO₂e from ONE well (sold to Mercuria, 2025).",
         "Zefiro/ACR 2025"),
        ("parcel_lookup",
         "WV/OH/KY parcels are free via ArcGIS REST point-in-polygon (no key); WV uses "
         "WV_Parcels FullOwnerName. PA needs a county service or national-API trial.",
         "STRUCTURED_PROPERTY_INFORMATION.md"),
        ("funding",
         "Federal BIL/IIJA orphan-well fund is $4.7B; Justice40 prioritizes "
         "disadvantaged (CEJST) communities for set-asides.",
         "BIL/Justice40"),
    ]:
        n += record(topic, value, source=src)
    print(f"[knowledge] seeded — {len(_load())} entries total ({n} new)")


def harvest() -> None:
    """Pull reusable findings the swarm surfaced (named operators) from dossiers."""
    n = 0
    dp = PROC / "dossiers.json"
    if dp.exists():
        for wid, d in json.loads(dp.read_text()).items():
            oh = (d.get("operator_history") or "").strip()
            if oh and not oh.lower().startswith("not found"):
                n += record("operator", f"{wid}: {oh[:180]}", source="swarm dossier", well_id=wid)
    print(f"[knowledge] harvested {n} new from dossiers — {len(_load())} total")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "seed":
        seed()
    elif cmd == "harvest":
        harvest()
    else:
        print(json.dumps(_load(), indent=2))
