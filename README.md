# MRI Sorting Tool

Desktop GUI for labeling MRI NIfTI scans and saving them into a lab BIDS-like layout.

## Install

```bash
cd "/Users/kla/LAB/Sorting tool"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Run

```bash
sorting-tool
# or
python -m sorting_tool
```

You will be prompted for:

1. **Input folder** — recursively searched for `.nii` / `.nii.gz`
2. **Output folder** — BIDS-like destinations are written here

Flags (skip prompts):

```bash
sorting-tool \
  --input "/Users/kla/LAB/Summer_Data/TestData" \
  --output "/Users/kla/LAB/Sorting tool/out_testdata"
```

## Workflow

1. Open a scan (axial / sagittal / coronal views + slice / brightness sliders).
2. Confirm Protocol / Series metadata from the JSON sidecar.
3. Set **Subject ID**, **Session date** (`MMDDYYYY` or `unknown`), and single-select **Acq / VOI / CE / Type**.
4. Click **Save Image to BIDS** — filenames use the labels currently selected in the UI.
5. Use Previous / Next to walk the dataset.

### Viewing controls

- **Stretch** (default): fill the viewport (helps with thin / anisotropic slices).
- **Fit**: keep correct aspect ratio after applying voxel spacing from the NIfTI header.
- **Scroll wheel** on an image: zoom in/out.
- **Click-drag** on an image: pan.
- **Double-click** an image: reset zoom and pan.

## Output naming

```text
<sub>/ses-<MMDDYYYY>/
  sub-<ID>_ses-<MMDDYYYY>_voi-<voi>_acq-<acq>[_ce-true]_<type>.nii.gz
  sub-<ID>_ses-<MMDDYYYY>_voi-<voi>_acq-<acq>[_ce-true]_<type>.json
```

Progress is tracked in `sorting_progress.json` under the output folder.

## Tests

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

## Requirements

- Python 3.10+
- PyQt6, nibabel, numpy, scipy
