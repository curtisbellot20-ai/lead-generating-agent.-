import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from lead_gen import config

HEADERS = [
    "Business Name",
    "Owner Name",
    "Phone",
    "Address",
    "Website",
    "Category",
    "Rating",
    "Reviews",
    "Years in Biz",
    "Industry Tag",
    "Source",
    "Outreach Note",
]

COL_WIDTHS = [35, 20, 18, 45, 35, 20, 10, 10, 12, 18, 16, 65]


def _border():
    s = Side(style="thin", color="DDDDDD")
    return Border(left=s, right=s, top=s, bottom=s)


def export_to_excel(leads: list[dict], query: str, location: str) -> str:
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = query.lower().replace(" ", "_")
    filename = f"{config.OUTPUT_DIR}/leads_{slug}_{timestamp}.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"

    dark_blue = "0F3460"
    mid_blue  = "1A1A2E"
    alt_gray  = "F8F9FA"
    border    = _border()

    # ── Title row ──────────────────────────────────────────────────
    last_col = get_column_letter(len(HEADERS))
    ws.merge_cells(f"A1:{last_col}1")
    tc = ws["A1"]
    tc.value     = f"Lead Generation Report — {query.title()} in {location}"
    tc.font      = Font(bold=True, color="FFFFFF", size=13)
    tc.fill      = PatternFill(start_color=dark_blue, end_color=dark_blue, fill_type="solid")
    tc.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 35

    # ── Meta row ───────────────────────────────────────────────────
    ws.merge_cells(f"A2:{last_col}2")
    mc = ws["A2"]
    mc.value = (
        f"Generated: {datetime.now().strftime('%B %d, %Y %I:%M %p')}  "
        f"|  Total Leads: {len(leads)}"
    )
    mc.font      = Font(italic=True, color="666666", size=10)
    mc.alignment = Alignment(horizontal="center")
    ws.row_dimensions[2].height = 20

    # ── Header row ─────────────────────────────────────────────────
    hdr_fill  = PatternFill(start_color=mid_blue, end_color=mid_blue, fill_type="solid")
    hdr_font  = Font(bold=True, color="FFFFFF", size=11)
    hdr_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for col, (hdr, width) in enumerate(zip(HEADERS, COL_WIDTHS), 1):
        cell = ws.cell(row=3, column=col, value=hdr)
        cell.font      = hdr_font
        cell.fill      = hdr_fill
        cell.alignment = hdr_align
        cell.border    = border
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.row_dimensions[3].height = 30

    # ── Data rows ──────────────────────────────────────────────────
    data_align = Alignment(vertical="center", wrap_text=True)
    for row_idx, lead in enumerate(leads, 4):
        row_fill = (
            PatternFill(start_color=alt_gray, end_color=alt_gray, fill_type="solid")
            if row_idx % 2 == 0 else None
        )
        values = [
            lead.get("name", ""),
            lead.get("owner_name", "Owner"),
            lead.get("phone", ""),
            lead.get("address", ""),
            lead.get("website", ""),
            lead.get("category", ""),
            lead.get("rating", ""),
            lead.get("reviews", ""),
            lead.get("years_in_business", ""),
            lead.get("industry_tag", ""),
            lead.get("source", ""),
            lead.get("outreach_note", ""),
        ]
        for col, value in enumerate(values, 1):
            cell            = ws.cell(row=row_idx, column=col, value=value)
            cell.alignment  = data_align
            cell.border     = border
            if row_fill:
                cell.fill = row_fill
        ws.row_dimensions[row_idx].height = 45

    ws.freeze_panes = "A4"

    # ── Summary sheet ──────────────────────────────────────────────
    ws2 = wb.create_sheet("Summary")
    ws2["A1"].value = f"Summary — {query.title()} in {location}"
    ws2["A1"].font  = Font(bold=True, size=14)
    ws2["A2"].value = f"{len(leads)} total leads"
    ws2["A2"].font  = Font(italic=True, color="666666")

    sources: dict[str, int] = {}
    industries: dict[str, int] = {}
    for lead in leads:
        src = lead.get("source", "Unknown")
        sources[src] = sources.get(src, 0) + 1
        ind = lead.get("industry_tag") or "Unknown"
        industries[ind] = industries.get(ind, 0) + 1

    row = 4
    ws2.cell(row=row, column=1, value="Leads by Source").font = Font(bold=True)
    row += 1
    for src, cnt in sorted(sources.items(), key=lambda x: -x[1]):
        ws2.cell(row=row, column=1, value=src)
        ws2.cell(row=row, column=2, value=cnt)
        row += 1

    row += 1
    ws2.cell(row=row, column=1, value="Leads by Industry").font = Font(bold=True)
    row += 1
    for ind, cnt in sorted(industries.items(), key=lambda x: -x[1]):
        ws2.cell(row=row, column=1, value=ind)
        ws2.cell(row=row, column=2, value=cnt)
        row += 1

    ws2.column_dimensions["A"].width = 30
    ws2.column_dimensions["B"].width = 15

    wb.save(filename)
    print(f"  [Exporter] Saved: {filename}")
    return filename
