"""Unit tests for metadata extraction and BIDS path building."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sorting_tool.bids import build_bids_paths, save_to_bids
from sorting_tool.discovery import discover_scans
from sorting_tool.metadata import extract_meta

TESTDATA = Path("/Users/kla/LAB/Summer_Data/TestData")


class TestDiscovery(unittest.TestCase):
    def test_discovers_testdata(self):
        if not TESTDATA.is_dir():
            self.skipTest("TestData not present")
        scans = discover_scans(TESTDATA)
        self.assertGreaterEqual(len(scans), 40)
        self.assertTrue(all(p.suffixes[-1] == ".gz" or p.suffix == ".nii" for p in scans))


class TestMetadata(unittest.TestCase):
    def test_subject_from_folder(self):
        if not TESTDATA.is_dir():
            self.skipTest("TestData not present")
        path = TESTDATA / "sub-amuAL" / "anat" / "sub-amuAL_T2w.nii.gz"
        if not path.is_file():
            self.skipTest("sample missing")
        meta = extract_meta(path)
        self.assertEqual(meta.subject_id, "amuAL")
        self.assertTrue(meta.protocol)
        self.assertTrue(meta.series)
        self.assertEqual(meta.guess_type, "T2w")


class TestBids(unittest.TestCase):
    def test_path_and_save(self):
        if not TESTDATA.is_dir():
            self.skipTest("TestData not present")
        src = TESTDATA / "sub-amuAL" / "anat" / "sub-amuAL_T2w.nii.gz"
        if not src.is_file():
            self.skipTest("sample missing")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            dest = save_to_bids(
                source_nii=src,
                output_dir=out,
                subject_id="amuAL",
                session_date="unknown",
                voi="cervicalspine",
                acq="Sagittal",
                ce="False",
                scan_type="T2w",
            )
            self.assertTrue(dest.is_file())
            self.assertIn("voi-cervicalspine", dest.name)
            self.assertIn("acq-sagittal", dest.name)
            self.assertTrue(dest.name.endswith("_T2w.nii.gz"))
            self.assertNotIn("ce-true", dest.name)
            js = dest.with_name(dest.name.replace(".nii.gz", ".json"))
            self.assertTrue(js.is_file())
            payload = json.loads(js.read_text())
            self.assertEqual(payload["SortingTool"]["type"], "T2w")
            self.assertEqual(payload["SortingTool"]["acq"], "sagittal")

            # collision -> run-1
            dest2 = save_to_bids(
                source_nii=src,
                output_dir=out,
                subject_id="amuAL",
                session_date="unknown",
                voi="cervicalspine",
                acq="Sagittal",
                ce="False",
                scan_type="T2w",
            )
            self.assertIn("_run-1_", dest2.name)

    def test_ce_true_entity(self):
        nii, _ = build_bids_paths(
            Path(tempfile.gettempdir()),
            "X1",
            "01012020",
            "pelvis",
            "Axial",
            "True",
            "T1w",
        )
        self.assertIn("_ce-true_", nii.name)


if __name__ == "__main__":
    unittest.main()
