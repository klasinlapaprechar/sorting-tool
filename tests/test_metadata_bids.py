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
        self.assertEqual(meta.guess_type, "t2w")


class TestBids(unittest.TestCase):
    def test_path_and_save_copy_only(self):
        if not TESTDATA.is_dir():
            self.skipTest("TestData not present")
        src = TESTDATA / "sub-amuAL" / "anat" / "sub-amuAL_T2w.nii.gz"
        src_json = src.with_name("sub-amuAL_T2w.json")
        if not src.is_file():
            self.skipTest("sample missing")
        src_mtime = src.stat().st_mtime_ns
        src_json_mtime = src_json.stat().st_mtime_ns if src_json.is_file() else None

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            dest = save_to_bids(
                source_nii=src,
                output_dir=out,
                dataset_name="TestData",
                subject_id="amuAL",
                session_date="20220812",
                voi="cervical",
                acq="sagittal",
                desc="none",
                scan_type="t2w",
            )
            self.assertTrue(dest.is_file())
            self.assertEqual(
                dest,
                out
                / "TestData"
                / "sub-amuAL"
                / "ses-20220812"
                / "sub-amuAL_ses-20220812_voi-cervical_acq-sagittal_t2w.nii.gz",
            )
            js = dest.with_name(dest.name.replace(".nii.gz", ".json"))
            self.assertTrue(js.is_file())
            payload = json.loads(js.read_text())
            self.assertEqual(payload["SortingTool"]["type"], "t2w")
            self.assertEqual(payload["SortingTool"]["voi"], "cervical")

            # originals untouched
            self.assertEqual(src.stat().st_mtime_ns, src_mtime)
            if src_json_mtime is not None:
                self.assertEqual(src_json.stat().st_mtime_ns, src_json_mtime)

            dest2 = save_to_bids(
                source_nii=src,
                output_dir=out,
                dataset_name="TestData",
                subject_id="amuAL",
                session_date="20220812",
                voi="cervical",
                acq="sagittal",
                desc="none",
                scan_type="t2w",
            )
            self.assertIn("_run-1_", dest2.name)

    def test_desc_entity(self):
        nii, _ = build_bids_paths(
            Path(tempfile.gettempdir()),
            "MyDataset",
            "X1",
            "20220812",
            "brain",
            "axial",
            "fatSat_Post_gad",
            "t1",
        )
        self.assertIn("_desc-fatSat_Post_gad_", nii.name)
        self.assertTrue(nii.name.endswith("_t1.nii.gz"))
        self.assertIn("MyDataset", str(nii))


if __name__ == "__main__":
    unittest.main()
