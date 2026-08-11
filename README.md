# MRI Sorting Tool

Desktop GUI for labeling MRI NIfTI scans and saving them into a lab BIDS-like layout.

## Requirements

- Python 3.10+
- PyQt6, nibabel, numpy, scipy (installed via `requirements.txt`)

## Install (any machine)

```bash
git clone https://github.com/klasinlapaprechar/sorting-tool.git
cd sorting-tool
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## Run

With the virtualenv activated:

```bash
sorting-tool
# or
python -m sorting_tool
```

You will be prompted for:

1. **Input folder** — recursively searched for `.nii` / `.nii.gz`
2. **Output folder** — BIDS-like destinations are written here

Or pass paths explicitly:

```bash
sorting-tool --input /path/to/scans --output /path/to/bids_out
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
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m unittest discover -s tests -v
```
