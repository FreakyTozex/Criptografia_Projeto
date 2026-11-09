from pathlib import Path
import re
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.oxml.ns import qn

root = Path(__file__).resolve().parents[1]
source = (root / "docs" / "relatorio-tecnico.md").read_text(encoding="utf-8")
doc = Document()
sec = doc.sections[0]
sec.top_margin = Inches(.72)
sec.bottom_margin = Inches(.72)
sec.left_margin = Inches(.78)
sec.right_margin = Inches(.78)
styles = doc.styles
styles["Normal"].font.name = "Aptos"
styles["Normal"].font.size = Pt(10)
styles["Normal"].paragraph_format.space_after = Pt(5)
for name, size, color in [("Title", 25, "12304A"), ("Heading 1", 17, "12304A"), ("Heading 2", 13, "176B87")]:
    st = styles[name]
    st.font.name = "Aptos Display"
    st.font.size = Pt(size)
    st.font.bold = True
    st.font.color.rgb = RGBColor.from_string(color)
    if name == "Title" and st._element.pPr is not None:
        border = st._element.pPr.find(qn("w:pBdr"))
        if border is not None:
            st._element.pPr.remove(border)

lines = source.splitlines()
i = 0
in_code = False
code_lines = []
first_heading = True
while i < len(lines):
    line = lines[i]
    if line.startswith("```"):
        if in_code:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(.18)
            p.paragraph_format.space_after = Pt(7)
            run = p.add_run("\n".join(code_lines))
            run.font.name = "Consolas"
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor.from_string("34495E")
            code_lines = []
            in_code = False
        else:
            in_code = True
        i += 1
        continue
    if in_code:
        code_lines.append(line)
        i += 1
        continue
    if line.startswith("| "):
        rows = []
        while i < len(lines) and lines[i].startswith("| "):
            cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                rows.append(cells)
            i += 1
        if rows:
            table = doc.add_table(rows=1, cols=len(rows[0]))
            table.style = "Light Shading Accent 1"
            for j, cell in enumerate(rows[0]):
                table.rows[0].cells[j].text = cell
            for row in rows[1:]:
                cells = table.add_row().cells
                for j, cell in enumerate(row[:len(cells)]):
                    cells[j].text = cell
            for row_num, row in enumerate(table.rows):
                for cell in row.cells:
                    for p in cell.paragraphs:
                        p.paragraph_format.space_after = Pt(2)
                        for r in p.runs:
                            r.font.size = Pt(8)
                            if row_num == 0:
                                r.bold = True
        continue
    if line.startswith("# "):
        title = line[2:].strip()
        if first_heading:
            p = doc.add_paragraph(style="Title")
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.add_run(title)
            first_heading = False
        else:
            doc.add_heading(title, level=1)
    elif line.startswith("## "):
        doc.add_heading(line[3:].strip(), level=1)
    elif line.startswith("### "):
        doc.add_heading(line[4:].strip(), level=2)
    elif line.startswith("- "):
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(line[2:].replace("**", ""))
    elif re.match(r"^\d+\. ", line):
        p = doc.add_paragraph(style="List Number")
        p.add_run(re.sub(r"^\d+\. ", "", line).replace("**", ""))
    elif line.strip() and not line.startswith("---"):
        p = doc.add_paragraph()
        p.add_run(line.replace("**", "").replace("`", ""))
    i += 1

out = root / "Relatorio_Tecnico_PoC.docx"
doc.save(out)
print(out)
