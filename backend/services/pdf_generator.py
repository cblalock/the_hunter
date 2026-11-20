import re
from pathlib import Path
from fpdf import FPDF


def _safe(text: str) -> str:
    """Replace common Unicode chars that latin-1 fonts can't handle."""
    return (
        text.replace("—", "--")
            .replace("–", "-")
            .replace("‘", "'").replace("’", "'")
            .replace("“", '"').replace("”", '"')
            .replace("•", "*")
            .replace(" ", " ")
            .replace("é", "e").replace("è", "e")
    )


def generate_pdf(text: str, out_path: Path) -> str:
    """Render plain-text resume to a PDF file at out_path. Returns the path."""
    pdf = FPDF(unit="mm", format="Letter")
    pdf.set_margins(left=20, top=20, right=20)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    lines = _safe(text).split("\n")

    # Header: first non-empty line is the name, next few are contact
    header_done = False
    in_contact = False  # contact lines right under the name render plain
    i = 0

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        if not stripped:
            in_contact = False
            pdf.ln(2)
            i += 1
            continue

        # Detect section headers:
        # - ALL CAPS line of reasonable length with no lowercase
        # - or a line followed immediately by a line of dashes
        next_stripped = lines[i + 1].strip() if i + 1 < len(lines) else ""
        underline_follows = bool(next_stripped) and all(c in "-=" for c in next_stripped) and len(next_stripped) >= 3
        is_caps_header = (
            stripped.isupper()
            and 1 <= len(stripped.split()) <= 6
            and len(stripped) <= 50
        )

        if not header_done:
            # Name (first non-empty line)
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 7, stripped, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            header_done = True
            in_contact = True
            i += 1
            continue

        if in_contact and not is_caps_header:
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 4.5, stripped, align="L", new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue
        in_contact = False

        if is_caps_header or underline_follows:
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 5, stripped, new_x="LMARGIN", new_y="NEXT")
            # Draw a rule line
            pdf.set_line_width(0.3)
            pdf.line(pdf.get_x(), pdf.get_y(), pdf.w - 20, pdf.get_y())
            pdf.ln(1)
            pdf.set_font("Helvetica", "", 9)
            i += 1
            if underline_follows:
                i += 1  # skip the dashes line
            continue

        # Bullet points
        if stripped.startswith(("•", "-", "*")) and len(stripped) > 2:
            indent = 6
            bullet = stripped[0]
            content = stripped[1:].strip()
            pdf.set_x(pdf.l_margin + indent)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(4, 4.5, "-")
            pdf.multi_cell(0, 4.5, content, align="L", new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue

        # Entry lines: "Organization | Role | Dates" -> bold
        if " | " in stripped and len(stripped) < 160:
            pdf.ln(1)
            pdf.set_font("Helvetica", "B", 9)
            pdf.multi_cell(0, 5, stripped, align="L", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            i += 1
            continue

        # "Label: values" lines (skills) -> bold label, regular values
        label = re.match(r"^([A-Z][\w &/+-]{1,40}):\s+(.+)$", stripped)
        if label:
            pdf.set_font("Helvetica", "B", 9)
            pdf.write(4.5, label.group(1) + ": ")
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 4.5, label.group(2), align="L", new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue

        # Regular text
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 4.5, stripped, align="L", new_x="LMARGIN", new_y="NEXT")
        i += 1

    pdf.output(str(out_path))
    return str(out_path)
