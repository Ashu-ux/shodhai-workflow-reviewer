"""
Converts ENGINEERING_NOTE.md to a publication-ready HTML file and renders it to PDF via Chrome.
"""

import os
import subprocess
import html
import re

def markdown_to_html(md_text: str) -> str:
    # Convert basic markdown formatting to clean HTML
    lines = md_text.split("\n")
    html_lines = []
    in_table = False
    in_code = False
    table_rows = []

    for line in lines:
        if line.startswith("```"):
            if in_code:
                html_lines.append("</pre>")
                in_code = False
            else:
                html_lines.append("<pre><code>")
                in_code = True
            continue

        if in_code:
            html_lines.append(html.escape(line))
            continue

        if line.startswith("|") and line.endswith("|"):
            if not in_table:
                in_table = True
                table_rows = []
            if "---" in line:
                continue  # separator
            cells = [c.strip() for c in line.strip("|").split("|")]
            table_rows.append(cells)
            continue
        else:
            if in_table:
                # render table
                html_lines.append("<table class='doc-table'>")
                # header
                if table_rows:
                    html_lines.append("<thead><tr>")
                    for h in table_rows[0]:
                        html_lines.append(f"<th>{h}</th>")
                    html_lines.append("</tr></thead><tbody>")
                    for row in table_rows[1:]:
                        html_lines.append("<tr>")
                        for cell in row:
                            html_lines.append(f"<td>{cell}</td>")
                        html_lines.append("</tr>")
                    html_lines.append("</tbody>")
                html_lines.append("</table>")
                in_table = False
                table_rows = []

        if line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("---"):
            html_lines.append("<hr/>")
        elif line.startswith("- "):
            html_lines.append(f"<li>{line[2:]}</li>")
        elif line.strip() == "":
            html_lines.append("<p></p>")
        else:
            # Inline bold and math
            l = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", line)
            l = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", l)
            l = re.sub(r"`([^`]+)`", r"<code>\1</code>", l)
            html_lines.append(f"<p>{l}</p>")

    if in_table:
        html_lines.append("<table class='doc-table'><tbody>")
        for row in table_rows:
            html_lines.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
        html_lines.append("</tbody></table>")

    body_content = "\n".join(html_lines)

    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>ShodhAI Engineering Note</title>
<style>
    @page {{
        size: letter;
        margin: 18mm 16mm 18mm 16mm;
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 10.5pt;
        line-height: 1.45;
        color: #1f2328;
        max-width: 820px;
        margin: 0 auto;
        padding: 20px;
    }}
    h1 {{
        font-size: 20pt;
        border-bottom: 2px solid #0969da;
        padding-bottom: 6px;
        margin-top: 0;
        color: #1f2328;
    }}
    h2 {{
        font-size: 13.5pt;
        border-bottom: 1px solid #d0d7de;
        padding-bottom: 4px;
        margin-top: 18px;
        margin-bottom: 8px;
        color: #0969da;
        page-break-after: avoid;
    }}
    h3 {{
        font-size: 11pt;
        margin-top: 12px;
        margin-bottom: 4px;
        color: #24292f;
        page-break-after: avoid;
    }}
    p {{
        margin: 5px 0;
    }}
    li {{
        margin-left: 20px;
        margin-bottom: 3px;
    }}
    code {{
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        font-size: 9pt;
        background-color: #f6f8fa;
        padding: 2px 4px;
        border-radius: 4px;
        border: 1px solid #e1e4e8;
    }}
    pre {{
        background-color: #f6f8fa;
        border: 1px solid #d0d7de;
        border-radius: 6px;
        padding: 10px;
        font-size: 8.5pt;
        overflow-x: auto;
        margin: 8px 0;
    }}
    table.doc-table {{
        width: 100%;
        border-collapse: collapse;
        margin: 10px 0;
        font-size: 9pt;
    }}
    table.doc-table th, table.doc-table td {{
        border: 1px solid #d0d7de;
        padding: 5px 8px;
        text-align: left;
    }}
    table.doc-table th {{
        background-color: #f6f8fa;
        font-weight: 600;
    }}
    table.doc-table tr:nth-child(even) {{
        background-color: #fcfdfe;
    }}
    hr {{
        border: 0;
        border-top: 1px solid #d0d7de;
        margin: 14px 0;
    }}
    strong {{
        color: #000;
    }}
</style>
</head>
<body>
{body_content}
</body>
</html>
"""
    return full_html


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    md_path = os.path.join(base_dir, "ENGINEERING_NOTE.md")
    html_path = os.path.join(base_dir, "ENGINEERING_NOTE.html")
    pdf_path = os.path.join(base_dir, "ENGINEERING_NOTE.pdf")

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    html_out = markdown_to_html(md_text)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"Generated HTML at: {html_path}")

    # Use Chrome to render PDF
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if os.path.exists(chrome_path):
        cmd = [
            chrome_path,
            "--headless=new",
            "--disable-gpu",
            f"--print-to-pdf={pdf_path}",
            html_path
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            print(f"Generated PDF at: {pdf_path}")
        except Exception as e:
            print(f"Chrome PDF generation error: {e}")
    else:
        print("Chrome not found for PDF conversion.")
