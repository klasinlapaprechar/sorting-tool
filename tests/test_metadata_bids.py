"""Unit tests for metadata extraction and BIDS path building."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sorting_tool.bids import build_bids_paths, build_stem, save_to_bids
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
    def test_stem_order_and_ce(self):
        stem = build_stem(
            "subjectid",
            "sessionid",
            "axial",
            "lumbarspine",
            "false",
            "t1w",
        )
        self.assertEqual(
            stem,
            "sub-subjectid_ses-sessionid_acq-axial_voi-lumbarspine_ce-false_t1w",
        )

    def test_optional_sub_ses_omitted_from_filename(self):
        stem = build_stem("", "", "sagittal", "brain", "true", "t2w")
        self.assertEqual(stem, "acq-sagittal_voi-brain_ce-true_t2w")
        self.assertNotIn("sub-", stem)
        self.assertNotIn("ses-", stem)

    def test_underscore_suffix(self):
        stem = build_stem("X1", "20220812", "axial", "cervicalspine", "false", "mtoff_MTS")
        self.assertTrue(stem.endswith("_mtoff_MTS"))
        self.assertIn("_ce-false_", stem)

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
                session_id="20220812",
                acq="sagittal",
                voi="cervicalspine",
                ce="false",
                scan_type="t2w",
            )
            self.assertTrue(dest.is_file())
            expected_name = (
                "sub-amuAL_ses-20220812_acq-sagittal_voi-cervicalspine_ce-false_t2w.nii.gz"
            )
            self.assertEqual(dest.name, expected_name)
            self.assertTrue(
                str(dest.resolve()).endswith(
                    f"TestData/sub-amuAL/ses-20220812/{expected_name}"
                )
            )
            js = dest.with_name(dest.name.replace(".nii.gz", ".json"))
            self.assertTrue(js.is_file())
            payload = json.loads(js.read_text())
            self.assertEqual(payload["SortingTool"]["type"], "t2w")
            self.assertEqual(payload["SortingTool"]["voi"], "cervicalspine")
            self.assertEqual(payload["SortingTool"]["ce"], "false")
            self.assertNotIn("desc", payload["SortingTool"])

            self.assertEqual(src.stat().st_mtime_ns, src_mtime)
            if src_json_mtime is not None:
                self.assertEqual(src_json.stat().st_mtime_ns, src_json_mtime)

            dest2 = save_to_bids(
                source_nii=src,
                output_dir=out,
                dataset_name="TestData",
                subject_id="amuAL",
                session_id="20220812",
                acq="sagittal",
                voi="cervicalspine",
                ce="false",
                scan_type="t2w",
            )
            self.assertIn("_run-1_", dest2.name)

    def test_blank_ids_use_unknown_folders(self):
        nii, _ = build_bids_paths(
            Path(tempfile.gettempdir()),
            "MyDataset",
            "",
            "",
            "axial",
            "lumbarspine",
            "false",
            "t1w",
        )
        self.assertIn("sub-unknown", str(nii))
        self.assertIn("ses-unknown", str(nii))
        self.assertEqual(nii.name, "acq-axial_voi-lumbarspine_ce-false_t1w.nii.gz")


if __name__ == "__main__":
    unittest.main()
