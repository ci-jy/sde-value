"""Render workbook tabs to PNG for the README (headless LibreOffice + pdftoppm).

    python3 scripts/screenshots.py out/hvac_service.xlsx docs/
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from openpyxl import load_workbook

from sde_value.check import soffice_binary

PAGES = {"Add-back Register": "addback-register.png", "Normalised Earnings": "normalised-earnings.png",
         "Multiple Valuation": "multiple-valuation.png", "DCF": "dcf.png",
         "Financing": "financing.png", "Sensitivity": "sensitivity.png"}


def main(src: str, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wb = load_workbook(src)
        for ws in wb.worksheets:
            ws.page_setup.orientation = "landscape"
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.page_setup.fitToWidth = ws.page_setup.fitToHeight = 1
        wb.save(tmp / "print.xlsx")
        subprocess.run([soffice_binary(), "--headless", f"-env:UserInstallation={(tmp / 'p').as_uri()}",
                        "--convert-to", "pdf", "--outdir", str(tmp), str(tmp / "print.xlsx")],
                       check=True, capture_output=True)
        for page, name in PAGES.items():
            n = wb.sheetnames.index(page) + 1
            stem = tmp / f"page{n}"
            subprocess.run(["pdftoppm", "-r", "200", "-png", "-singlefile", "-f", str(n), "-l", str(n),
                            str(tmp / "print.pdf"), str(stem)], check=True)
            subprocess.run(["convert", f"{stem}.png", "-trim", "-bordercolor", "white",
                            "-border", "20", str(out / name)], check=True)
            print(out / name)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
