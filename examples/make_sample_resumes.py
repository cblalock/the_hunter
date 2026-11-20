"""Builds the fake sample candidate's base resumes (examples/resumes/*.docx).

    python examples/make_sample_resumes.py
"""
from pathlib import Path

import docx

OUT = Path(__file__).parent / "resumes"
HEADER = ["Alex Rivera", "Columbus, OH | (555) 010-0142 | alex.rivera@example.com",
          "github.com/example | linkedin.com/in/example"]

EDUCATION = ["The Ohio State University | B.S. Information Systems | 2025"]
EXPERIENCE = {
    "it": ["Campus Technology Services | IT Support Technician (student) | 2022 - 2025",
           ["Resolved 30+ tickets a week across Windows, macOS and printers",
            "Imaged and deployed 200 lab machines each semester",
            "Reset accounts and managed groups in Active Directory"]],
    "data": ["Midwest Grocers Co-op | Data Analyst Intern | Summer 2024",
             ["Built a weekly SQL + Tableau report on store shrink used by 12 managers",
              "Cleaned 3 years of sales exports in Python (pandas) for a pricing study",
              "Automated an Excel reconciliation that took a day each month"]],
    "software": ["Midwest Grocers Co-op | Software Intern | Summer 2024",
                 ["Wrote Python scripts that sync inventory between two internal systems",
                  "Added tests and CI (GitHub Actions) to a small Flask service",
                  "Built a React page for store managers to request price changes"]],
}
SKILLS = {
    "it": "Windows, macOS, Active Directory, Microsoft 365, ticketing (Jira Service Desk), networking basics, CompTIA A+",
    "data": "SQL, Python (pandas), Excel, Tableau, data cleaning, reporting",
    "software": "Python, JavaScript, React, Flask, SQL, Git, GitHub Actions",
}
PROJECTS = ["Budget tracker web app (React + Flask) with CSV import and charts",
            "Home lab: Raspberry Pi DNS filter and backups"]


def build(track: str, filename: str):
    d = docx.Document()
    for line in HEADER:
        d.add_paragraph(line)

    def heading(text):
        p = d.add_paragraph()
        p.add_run(text).bold = True

    heading("Summary")
    d.add_paragraph(f"Recent Information Systems graduate looking for an entry-level {dict(it='IT support', data='data analyst', software='software')[track]} role.")
    heading("Experience")
    entry, bullets = EXPERIENCE[track]
    d.add_paragraph(entry)
    for b in bullets:
        d.add_paragraph(b, style="List Bullet")
    heading("Projects")
    for p in PROJECTS:
        d.add_paragraph(p, style="List Bullet")
    heading("Skills")
    d.add_paragraph(SKILLS[track])
    heading("Education")
    for e in EDUCATION:
        d.add_paragraph(e)
    OUT.mkdir(parents=True, exist_ok=True)
    d.save(OUT / filename)


if __name__ == "__main__":
    build("data", "resume_data.docx")
    build("it", "resume_it.docx")
    build("software", "resume_software.docx")
    print(f"Wrote sample resumes to {OUT}")
