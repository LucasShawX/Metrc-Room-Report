import io
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

st.set_page_config(page_title="METRC Room Report", page_icon="🌱", layout="wide")

ALIASES = {
    "tag": ["tag", "plant tag", "label"],
    "strain": ["strain", "strain name"],
    "location": ["location", "room", "plant location"],
    "sublocation": ["sublocation", "sub location"],
    "phase_date": ["phase date", "flowering date", "flower date"],
}


def normalize(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def find_column(columns, aliases, required=True):
    normalized = {normalize(c): c for c in columns}
    for alias in aliases:
        if normalize(alias) in normalized:
            return normalized[normalize(alias)]
    for c in columns:
        nc = normalize(c)
        if any(normalize(a) in nc for a in aliases):
            return c
    if required:
        raise ValueError(f"Missing required column. Expected one of: {', '.join(aliases)}")
    return None


def facility_from_filename(name):
    stem = Path(name).stem
    match = re.search(r"(GAAI-[A-Z0-9]+-[A-Z0-9]+)", stem, re.I)
    return match.group(1).upper() if match else stem


def phase_from_filename(name):
    low = name.lower()
    if "flower" in low:
        return "Flowering"
    if "vegetative" in low or "veg" in low:
        return "Vegetative"
    return "Plants"


def read_metrc(upload):
    raw = upload.getvalue()
    df = pd.read_excel(io.BytesIO(raw), engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    tag = find_column(df.columns, ALIASES["tag"])
    strain = find_column(df.columns, ALIASES["strain"])
    location = find_column(df.columns, ALIASES["location"])
    sublocation = find_column(df.columns, ALIASES["sublocation"], required=False)
    phase_date = find_column(df.columns, ALIASES["phase_date"], required=False)

    out = pd.DataFrame({
        "Tag": df[tag].astype(str).str.strip(),
        "Strain": df[strain].fillna("Unspecified").astype(str).str.strip(),
        "Room": df[location].fillna("Unassigned").astype(str).str.strip(),
    })
    if sublocation:
        sub = df[sublocation].fillna("").astype(str).str.strip()
        out["Room"] = out["Room"] + sub.where(sub.eq(""), " / " + sub)
    out["Phase Date"] = pd.to_datetime(df[phase_date], errors="coerce") if phase_date else pd.NaT
    out = out[out["Tag"].notna() & out["Tag"].ne("") & out["Tag"].ne("nan")].copy()
    # Parse tag suffixes with Python integers instead of pandas numeric conversion.
    # METRC tags can exceed fixed-width integer limits; pd.to_numeric may coerce
    # them to floating point and silently alter the last digits.
    tag_suffix = out["Tag"].str.extract(r"(\d+)$")[0]
    out["Tag Number"] = tag_suffix.map(lambda value: int(value) if pd.notna(value) else None)
    out = out[out["Tag Number"].notna()].copy()
    out["Facility"] = facility_from_filename(upload.name)
    out["Phase"] = phase_from_filename(upload.name)
    return out


def make_ranges(values):
    nums = sorted(set(int(v) for v in values))
    if not nums:
        return []
    result, start, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n != prev + 1:
            result.append((start, prev))
            start = n
        prev = n
    result.append((start, prev))
    return result


def summarize(df, digits):
    rows = []
    group_cols = ["Facility", "Phase", "Room", "Strain"]
    for keys, group in df.groupby(group_cols, dropna=False, sort=True):
        facility, phase, room, strain = keys
        dates = group["Phase Date"].dropna()
        date_text = ", ".join(sorted({d.strftime("%m/%d/%Y") for d in dates})) if len(dates) else ""
        for start, end in make_ranges(group["Tag Number"]):
            mask = group["Tag Number"].between(start, end)
            start_text = str(start)[-digits:].zfill(digits)
            end_text = str(end)[-digits:].zfill(digits)
            rows.append({
                "Facility": facility,
                "Phase": phase,
                "Room": room,
                "Strain": strain,
                "Phase Date": date_text,
                "Tag Range": start_text if start == end else f"{start_text}–{end_text}",
                "Plants": int(mask.sum()),
            })
    return pd.DataFrame(rows)


def build_excel(summary):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter", datetime_format="mm/dd/yyyy") as writer:
        summary.to_excel(writer, sheet_name="Room Report", index=False)
        workbook = writer.book
        sheet = writer.sheets["Room Report"]
        header = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#2F6B45", "border": 1, "align": "center"})
        body = workbook.add_format({"border": 1, "valign": "vcenter"})
        count = workbook.add_format({"border": 1, "align": "center", "num_format": "0"})
        for col, name in enumerate(summary.columns):
            sheet.write(0, col, name, header)
            width = min(max(len(name) + 2, int(summary[name].astype(str).map(len).max()) + 2), 32)
            sheet.set_column(col, col, width, count if name == "Plants" else body)
        sheet.freeze_panes(1, 0)
        sheet.autofilter(0, 0, len(summary), len(summary.columns) - 1)
        total_row = len(summary) + 2
        sheet.write(total_row, len(summary.columns) - 2, "Total Plants", header)
        sheet.write_formula(total_row, len(summary.columns) - 1, f"=SUM(G2:G{len(summary)+1})", count)
    return output.getvalue()


def build_pdf(summary, title):
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(letter), leftMargin=0.35*inch, rightMargin=0.35*inch, topMargin=0.4*inch, bottomMargin=0.4*inch)
    styles = getSampleStyleSheet()
    elements = [Paragraph(title, styles["Title"]), Paragraph(f"Generated {datetime.now().strftime('%m/%d/%Y')} • Total plants: {summary['Plants'].sum():,}", styles["Normal"]), Spacer(1, 0.15*inch)]
    cols = ["Facility", "Phase", "Room", "Strain", "Phase Date", "Tag Range", "Plants"]
    data = [cols] + [[str(v) for v in row] for row in summary[cols].itertuples(index=False, name=None)]
    table = Table(data, colWidths=[1.45*inch, 0.8*inch, 1.0*inch, 2.1*inch, 1.15*inch, 1.35*inch, 0.65*inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2F6B45")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#A7B0AA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F1F6F2")]),
        ("ALIGN", (0,0), (-1,0), "CENTER"),
        ("ALIGN", (-1,1), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("FONTSIZE", (0,0), (-1,-1), 8.5),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    elements.append(table)
    doc.build(elements)
    return output.getvalue()


st.title("🌱 METRC Room Report Generator")
st.write("Upload one or more METRC plant Excel exports. The app automatically groups each facility by room and strain, finds continuous tag ranges, and creates PDF and Excel reports.")

uploads = st.file_uploader("Upload METRC plant Excel files", type=["xlsx", "xls"], accept_multiple_files=True)
col1, col2 = st.columns([1, 2])
with col1:
    digits = st.number_input("Tag digits to display", min_value=3, max_value=10, value=5, step=1)
with col2:
    report_title = st.text_input("Report title", value="METRC Room / Strain / Tag Range Report")

if uploads:
    frames, errors = [], []
    for upload in uploads:
        try:
            frames.append(read_metrc(upload))
        except Exception as exc:
            errors.append(f"{upload.name}: {exc}")
    for error in errors:
        st.error(error)
    if frames:
        combined = pd.concat(frames, ignore_index=True)
        summary = summarize(combined, int(digits))
        st.success(f"Processed {len(combined):,} plant records from {len(frames)} file(s).")
        st.dataframe(summary, use_container_width=True, hide_index=True)

        facilities = "_".join(sorted(summary["Facility"].unique()))
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", facilities)[:80]
        pdf = build_pdf(summary, report_title)
        xlsx = build_excel(summary)
        left, right = st.columns(2)
        with left:
            st.download_button("Download PDF", pdf, file_name=f"{safe_name}_Room_Report.pdf", mime="application/pdf", use_container_width=True)
        with right:
            st.download_button("Download Excel", xlsx, file_name=f"{safe_name}_Room_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
else:
    st.info("Upload a METRC Vegetative or Flowering Excel export to begin.")
