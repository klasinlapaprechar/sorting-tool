# MRI Sorting Tool

Desktop GUI for labeling MRI NIfTI scans and saving them into a lab BIDS-like layout.

![MRI Sorting Tool GUI](docs/gui-screenshot-filled-panel.png)

*Beta UI: compact JSON sidecar that fills the side panel; optional Subject/Session IDs; Acq / VOI / CE / Type.*

**Saves are copy-only:** the tool never moves or modifies the original NIfTI or JSON files. It **copies** each scan into the output tree and writes a **new** sidecar beside the copy.

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

### 1. Activate the environment

Every time you open a new terminal, go into the repo and activate the virtualenv:

```bash
cd sorting-tool
source .venv/bin/activate          # Windows: .venv\Scripts\activate
```

You should see `(.venv)` at the start of your prompt.

### 2. Launch the tool

```bash
sorting-tool
```

(or `python -m sorting_tool`)

The terminal will ask:

1. `Input folder path:` — paste or type the **input folder PATH** (root folder that contains your NIfTI scans). The tool searches this folder recursively for `.nii` / `.nii.gz`.
2. `Output folder path:` — paste or type the **output folder PATH** (parent directory for sorted BIDS results). The tool creates a subfolder named after the input folder inside this path.

Then the GUI window opens.

Sorted copies are written under:

```text
/OUTPUT/FOLDER/PATH/<input_folder_name>/sub-<ID>/ses-<sessionid>/...
```

Original files under the input folder PATH are never modified or moved.

### 3. Use the GUI

1. Confirm the **file name** and scroll the **JSON sidecar** panel on the right.
2. Confirm Protocol / Series text (summarized above the labels).
3. Optionally edit **Subject ID** and **Session ID** (free-text strings; may be left blank).
4. Select **Acq**, **VOI**, **CE** (`true` / `false`), and **Type** / suffix (one choice each).
5. Use the left viewports to inspect axial / sagittal / coronal slices (slice + brightness sliders).
6. Click **Save Image to BIDS** to **copy** the current scan into the output folder PATH using those labels.
7. Click **Next Image Button** / **Previous Image Button** to move through the dataset.

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
  sub-<subjectid|/unknown>/
    ses-<sessionid|/unknown>/
      [sub-<subjectid>_][ses-<sessionid>_]acq-<acq>_voi-<voi>_ce-<true|false>[_run-N]_<suffix>.nii.gz
      [sub-<subjectid>_][ses-<sessionid>_]acq-<acq>_voi-<voi>_ce-<true|false>[_run-N]_<suffix>.json
```

- **Subject ID** and **Session ID** are optional. If blank, they are omitted from the **filename**, and folders use `sub-unknown` / `ses-unknown`.
- There is **no** `desc-` entity. Contrast is encoded as **`ce-true`** or **`ce-false`**.
- If a name already exists, `_run-<N>` is inserted before the suffix.

Example:

```text
sub-subjectid_ses-sessionid_acq-axial_voi-lumbarspine_ce-false_t1w.nii.gz
```

### Label options

| Field | Options |
|-------|---------|
| `acq` | `axial`, `sagittal`, `coronal` |
| `voi` | `brain`, `cervicalspine`, `cervicothoracicspine`, `thoracicspine`, `thoracolumbarspine`, `lumbarspine`, `fullspine`, `pelvis`, `hip`, `thigh`, `knee`, `leg`, `ankle`, `foot`, `shoulder`, `arm`, `elbow`, `forearm`, `hand`, `abdomen`, `thorax`, `liver`, `heart`, `head`, `jaw` |
| `ce` | `true`, `false` |
| suffix | `t1w`, `t2w`, `t2sfatsat`, `t1wfatsat`, `t2star`, `mtoff_MTS`, `mton_MTS`, `t1w_MTS`, `stir`, `flair`, `dwi`, `func`, `fat`, `water`, `inphase`, `outphase` |

Progress is tracked in `sorting_progress.json` under the dataset output folder.

## Tests

```bash
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m unittest discover -s tests -v
```
