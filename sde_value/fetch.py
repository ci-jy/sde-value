"""Download the public BLS and IRS SOI files and cut them down to the small
extracts kept in ``data/``.

The full files are tens of megabytes; the model only needs a few occupations,
a few industries and a dozen expense lines, so the extracts are what get
committed. Run ``python -m sde_value fetch-data`` to rebuild them.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

from .data import DATA_DIR

OES_YEAR = "2024"
SOI_YEAR = "2022"

URLS = {
    "oes_national": "https://www.bls.gov/oes/special-requests/oesm24nat.zip",
    "oes_state": "https://www.bls.gov/oes/special-requests/oesm24st.zip",
    "oes_industry": "https://www.bls.gov/oes/special-requests/oesm24in4.zip",
    "ecec_data": "https://download.bls.gov/pub/time.series/cm/cm.data.0.Current",
    "soi_minor": "https://www.irs.gov/pub/irs-soi/22co51ccr.xlsx",
}

# BLS rejects scripted requests unless they look like a browser.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.bls.gov/oes/tables.htm",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Upgrade-Insecure-Requests": "1",
}

# Occupations a buyer might hire to replace an owner-operator.
OCCUPATIONS = {
    "11-1021": "General and Operations Managers",
    "49-1011": "First-Line Supervisors of Mechanics, Installers, and Repairers",
    "37-1012": "First-Line Supervisors of Landscaping, Lawn Service, and Groundskeeping Workers",
    "37-1011": "First-Line Supervisors of Housekeeping and Janitorial Workers",
    "39-1022": "First-Line Supervisors of Personal Service Workers",
}

# OES 4-digit NAICS industries used by the sample deals (OES codes pad to 6).
INDUSTRIES = {
    "238200": "Building Equipment Contractors",
    "561700": "Services to Buildings and Dwellings",
    "812300": "Drycleaning and Laundry Services",
}

# IRS SOI Table 5.1 minor-industry columns, keyed by our own short code.
SOI_INDUSTRIES = {
    "plumbing_hvac": "Plumbing, heating, and air-conditioning contractors",
    "other_admin_support": "Other administrative and support services",
    "personal_laundry": "Personal and laundry services",
    "specialty_trade_other": "Other specialty trade contractors",
}

SOI_ITEMS = {
    "Number of returns": "returns",
    "Business receipts": "business_receipts",
    "Cost of goods sold": "cogs",
    "Compensation of officers": "officer_comp",
    "Salaries and wages": "salaries_wages",
    "Repairs and maintenance": "repairs",
    "Rents paid": "rent",
    "Taxes and licenses": "taxes_licenses",
    "Interest paid": "interest",
    "Depreciation": "depreciation",
    "Amortization": "amortization",
    "Advertising": "advertising",
    "Pension, profit-sharing, etc., plans": "pension",
    "Employee benefit programs": "employee_benefits",
    "Other deductions": "other_deductions",
    "Net income (less deficit)": "net_income",
}

# ECEC benefits load: total benefits and wages per hour worked, private industry.
ECEC_SERIES = {
    "CMU2020000000111D": ("wages", "Private industry, establishments with 1-49 workers"),
    "CMU2030000000111D": ("benefits", "Private industry, establishments with 1-49 workers"),
    "CMU2020000100000D": ("wages", "Private industry, management, professional, and related"),
    "CMU2030000100000D": ("benefits", "Private industry, management, professional, and related"),
    "CMU2020000000000D": ("wages", "Private industry, all workers"),
    "CMU2030000000000D": ("benefits", "Private industry, all workers"),
}


def download(url: str, dest: Path) -> Path:
    # BLS's CDN turns away Python's TLS client even with browser headers, so
    # use curl when it is installed and fall back to urllib otherwise.
    curl = shutil.which("curl")
    if curl:
        cmd = [curl, "-sSfL", "--compressed", "-o", str(dest)]
        for key, value in HEADERS.items():
            cmd += ["-H", f"{key}: {value}"]
        subprocess.run(cmd + [url], check=True, timeout=300)
        return dest
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as fh:
        fh.write(resp.read())
    return dest


def _read_zip_xlsx(path: Path, member_suffix: str, usecols) -> pd.DataFrame:
    with zipfile.ZipFile(path) as zf:
        name = next(n for n in zf.namelist() if n.endswith(member_suffix))
        return pd.read_excel(io.BytesIO(zf.read(name)), usecols=usecols, dtype=str)


OES_COLS = ["AREA_TITLE", "PRIM_STATE", "NAICS", "NAICS_TITLE", "OCC_CODE", "OCC_TITLE",
            "TOT_EMP", "A_MEAN", "A_PCT25", "A_MEDIAN", "A_PCT75"]


def extract_oes(nat_zip: Path, st_zip: Path, ind_zip: Path) -> pd.DataFrame:
    occ = set(OCCUPATIONS)
    nat = _read_zip_xlsx(nat_zip, "national_M2024_dl.xlsx", OES_COLS)
    nat = nat[nat.OCC_CODE.isin(occ)].assign(scope="national")
    st = _read_zip_xlsx(st_zip, "state_M2024_dl.xlsx", OES_COLS)
    st = st[st.OCC_CODE.isin(occ)].assign(scope="state")
    ind = _read_zip_xlsx(ind_zip, "nat4d_M2024_dl.xlsx", OES_COLS)
    ind = ind[ind.OCC_CODE.isin(occ) & ind.NAICS.isin(set(INDUSTRIES))].assign(scope="industry")
    out = pd.concat([nat, st, ind], ignore_index=True)
    out.columns = [c.lower() for c in out.columns]
    return out[["scope"] + [c.lower() for c in OES_COLS]]


def extract_ecec(data_path: Path) -> pd.DataFrame:
    df = pd.read_csv(data_path, sep="\t", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df = df.apply(lambda s: s.str.strip())
    df = df[df.series_id.isin(set(ECEC_SERIES))].copy()
    df["value"] = df.value.astype(float)
    df["measure"] = df.series_id.map(lambda s: ECEC_SERIES[s][0])
    df["group"] = df.series_id.map(lambda s: ECEC_SERIES[s][1])
    df = df.sort_values(["series_id", "year", "period"])
    return df[["series_id", "group", "measure", "year", "period", "value"]]


def extract_soi(xlsx: Path) -> pd.DataFrame:
    raw = pd.read_excel(xlsx, header=None)
    headers = {}
    for col in range(1, raw.shape[1]):
        label = " ".join(str(v) for v in raw.iloc[3:8, col] if pd.notna(v))
        headers[col] = " ".join(label.split())
    rows = []
    for code, title in SOI_INDUSTRIES.items():
        col = next(c for c, h in headers.items() if h.startswith(title))
        for r in range(raw.shape[0]):
            item = " ".join(str(raw.iat[r, 0]).split())
            item = item.split(" [")[0].strip()
            if item in SOI_ITEMS:
                key = SOI_ITEMS[item]
                if any(row["item"] == key and row["industry"] == code for row in rows):
                    continue  # the table repeats some labels further down; keep the first
                rows.append({"industry": code, "soi_title": title, "item": key,
                             # "d" marks cells SOI suppressed to avoid disclosure
                             "value": pd.to_numeric(raw.iat[r, col], errors="coerce")})
    return pd.DataFrame(rows)


def refresh(data_dir: Path = DATA_DIR) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        files = {k: download(u, tmp / os.path.basename(u)) for k, u in URLS.items()}
        extract_oes(files["oes_national"], files["oes_state"], files["oes_industry"]).to_csv(
            data_dir / "bls_oes_wages.csv", index=False)
        extract_ecec(files["ecec_data"]).to_csv(data_dir / "bls_ecec.csv", index=False)
        extract_soi(files["soi_minor"]).to_csv(data_dir / "irs_soi_minor_industry.csv", index=False)
