# METRC Room Report Generator

## What it does
Upload one or more METRC plant Excel exports and generate a grouped room report containing:

- Facility license detected from the filename
- Vegetative or Flowering phase detected from the filename
- Room/location
- Strain
- Phase/flowering date
- Continuous plant-tag ranges using the last five digits
- Plant counts and total plants
- Downloadable PDF and Excel reports

## macOS setup
1. Install Python 3.11 or newer from python.org if it is not already installed.
2. Clone or download this repository.
3. Double-click `run_mac.command`.
4. On the first launch, the script creates a local virtual environment and installs the required packages.
5. Streamlit opens the app in your browser. Upload the METRC Excel export and download the report.

If macOS blocks the script the first time, right-click `run_mac.command`, choose **Open**, then confirm **Open**.

## Windows setup
1. Install Python 3.11 or newer from python.org. During installation, select **Add Python to PATH**.
2. Extract this folder.
3. Double-click `run_app.bat`.
4. The app opens in your browser.
5. Upload the METRC Excel export and download the report.

After the first launch, the required packages remain installed, so future launches are faster.

## Manual launch
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Notes
- METRC exports should contain Tag, Strain, and Location columns.
- Phase Date is optional.
- You can upload exports from multiple facilities at once; the report keeps facilities separate.
- Discontinuous tag sequences are automatically split into separate ranges.


## Mac compatibility note
The app itself is cross-platform Python. `run_app.bat` is for Windows; `run_mac.command` is the macOS launcher.

## Tag precision fix
This fork preserves long METRC tag suffixes as Python integers when building tag ranges, avoiding floating-point precision loss on very long tag values.
