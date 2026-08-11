# MRI Sorting Tool

Desktop GUI for labeling MRI NIfTI scans and saving them into a lab BIDS-like layout.

**Saves are copy-only:** the tool never modifies the original NIfTI or JSON files. It copies each scan into the output tree and writes a new sidecar beside the copy.

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

1. **Input folder** — recursively searched for `.nii` / `.nii.gz` (the folder name becomes the top-level dataset folder in the output)
2. **Output folder** — parent directory where `<dataset_name>/...` will be created

Or pass paths explicitly:

```bash
sorting-tool --input /path/to/MyDataset --output /path/to/bids_parent
```

## Workflow

1. Open a scan (axial / sagittal / coronal views + slice / brightness sliders).
2. Confirm Protocol / Series metadata from the JSON sidecar.
3. Set **Subject ID**, **Session date** (`YYYYMMDD` or `unknown`), and single-select **Acq / VOI / Desc / Type**.
4. Click **Save Image to BIDS** — copies the scan using the labels currently selected in the UI.
5. Use Previous / Next to walk the dataset.

### Viewing controls

- **Stretch** slider at the top of the image column (default **0% = Fit**):  
  - `0` keeps aspect ratio  
  - `100` fills the viewport  
  - values in between blend Fit → Fill
- **Scroll wheel** on an image: zoom in/out.
- **Click-drag** on an image: pan.
- **Double-click** an image: reset zoom and pan.

## Output naming

Top-level folder matches the **input dataset folder name**:

```text
<output>/<input_dataset_name>/
  sub-<ID>/
    ses-<YYYYMMDD>/
      sub-<ID>_ses-<YYYYMMDD>_voi-<voi>_acq-<acq>[_desc-<desc>]_<type>.nii.gz
      sub-<ID>_ses-<YYYYMMDD>_voi-<voi>_acq-<acq>[_desc-<desc>]_<type>.json
```

Label values:

| Field | Options |
|-------|---------|
| `voi` | `cervical`, `lumbar`, `brain`, `thoracic` |
| `acq` | `axial`, `sagittal` |
| `desc` | omitted when `none`; else `fatSat_Pre_gad` or `fatSat_Post_gad` |
| type suffix | `t2w`, `t2star`, `t1` |

Example:

```text
TestData/sub-amuAL/ses-20220812/sub-amuAL_ses-20220812_voi-cervical_acq-sagittal_desc-fatSat_Post_gad_t1.nii.gz
```

If a name already exists, `_run-<N>` is inserted before the type suffix. Progress is tracked in `sorting_progress.json` under the dataset output folder.

## Tests

```bash
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m unittest discover -s tests -v
```
