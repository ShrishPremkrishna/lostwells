from __future__ import annotations

import csv
import importlib.util
import json
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_merge_module():
    spec = importlib.util.spec_from_file_location(
        "merge_detections", ROOT / "scripts" / "merge_detections.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ManifestTests(unittest.TestCase):
    def test_core_manifest_population(self):
        path = ROOT / "manifests" / "core_appalachia_latest.csv"
        with path.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 2705)
        self.assertEqual(Counter(r["primary_state"] for r in rows), {
            "Pennsylvania": 809, "West Virginia": 435,
            "Ohio": 760, "Kentucky": 701,
        })
        self.assertEqual(len({r["scan_id"] for r in rows}), len(rows))
        self.assertTrue(all(r["geotiff_url"].startswith("https://") for r in rows))


class NotebookTests(unittest.TestCase):
    def test_all_notebook_code_cells_compile(self):
        for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
            notebook = json.loads(path.read_text())
            for index, cell in enumerate(notebook["cells"]):
                if cell["cell_type"] == "code":
                    compile("".join(cell["source"]), f"{path}:cell-{index}", "exec")


class MergeTests(unittest.TestCase):
    def test_nearby_points_merge_and_distant_point_does_not(self):
        module = load_merge_module()

        def feature(lon, lat, quad):
            return {"type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {"quad": quad, "state": "Pennsylvania",
                                   "quad_year": "1980", "dist_to_documented_m": 150}}

        merged = module.merge([
            feature(-79.0, 41.0, "A"),
            feature(-79.0005, 41.0, "B"),  # roughly 42 m at this latitude
            feature(-80.0, 41.0, "C"),
        ], 60)
        self.assertEqual(len(merged), 2)
        duplicate = max(merged, key=lambda f: f["properties"]["detection_count"])
        self.assertEqual(duplicate["properties"]["detection_count"], 2)
        self.assertEqual(duplicate["properties"]["quads"], ["A", "B"])
        self.assertEqual(len(duplicate["properties"]["source_records"]), 2)
        self.assertEqual(duplicate["properties"]["source_coordinates"],
                         [[-79.0, 41.0], [-79.0005, 41.0]])
        self.assertEqual(duplicate["properties"]["documented_distances_m"], [150, 150])


if __name__ == "__main__":
    unittest.main()
