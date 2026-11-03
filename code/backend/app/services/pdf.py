"""The approval form for one approved swap, as a one-page PDF (fpdf2)."""
from __future__ import annotations

from fpdf import FPDF

from app.models import SwapCycle
from app.services.mail import ist

INK, MUTED, LINE = (24, 24, 27), (100, 100, 110), (210, 210, 215)


def approval_form(cycle: SwapCycle) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_title(f"CampusSwap approval form, swap {cycle.id}")
    pdf.set_author("CampusSwap")
    pdf.set_margins(18, 18, 18)
    pdf.add_page()
    hostel = cycle.members[0].gives_seat.room.hostel

    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(*INK)
    pdf.cell(0, 8, "Room Swap Approval Form", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, f"Thapar Institute of Engineering and Technology  |  {hostel.name}  |  CampusSwap",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    facts = [
        ("Swap number", f"#{cycle.id} (matching round #{cycle.match_run_id})"),
        ("Type", f"{len(cycle.members)}-way swap chain (each member takes the next member's bed)"),
        ("Found on", ist(cycle.created_at)),
        ("Approved on", ist(cycle.closed_at)),
        ("Approved by", cycle.approved_by.name if cycle.approved_by else "-"),
    ]
    for label, value in facts:
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(*INK)
        pdf.cell(38, 6, label)
        pdf.set_font("helvetica", "", 10)
        pdf.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    widths = (8, 40, 22, 24, 30, 30, 20)
    headers = ("#", "Student", "Roll no.", "Request", "Gives up", "Moves to", "Choice")
    pdf.set_draw_color(*LINE)
    pdf.set_fill_color(244, 244, 246)
    pdf.set_font("helvetica", "B", 9)
    for w, h in zip(widths, headers):
        pdf.cell(w, 7, h, border="B", fill=True)
    pdf.ln()
    pdf.set_font("helvetica", "", 9)
    for m in cycle.members:
        student = m.request.student
        row = (str(m.position + 1), student.name, student.roll_no or "-", m.request.tracking_id,
               m.gives_seat.room.label, m.receives_seat.room.label, f"#{m.received_rank}")
        for w, value in zip(widths, row):
            pdf.cell(w, 7, value, border="B")
        pdf.ln()
    pdf.ln(3)
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 4.5, "Every member confirmed this swap on CampusSwap before the warden approved it. "
                   "Confirmation times: " + "; ".join(
                       f"{m.request.student.name} {ist(m.responded_at)}" for m in cycle.members if m.responded_at)
                   + ".", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    pdf.set_text_color(*INK)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, "Signatures", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("helvetica", "", 9)
    signers = [m.request.student.name for m in cycle.members] + [f"Warden, {hostel.name} ({hostel.warden_name})"]
    col = (pdf.w - 36) / 2
    for i, name in enumerate(signers):
        x = 18 + (i % 2) * col
        if i % 2 == 0 and i:
            pdf.ln(16)
        y = pdf.get_y() + 8
        pdf.set_draw_color(*MUTED)
        pdf.line(x, y, x + col - 10, y)
        pdf.set_xy(x, y + 1)
        pdf.cell(col - 10, 5, f"Signature: {name}")
        pdf.set_xy(18, y - 8)
    return bytes(pdf.output())
