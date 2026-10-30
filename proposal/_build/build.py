"""Build the research proposal .docx with a filled-in table of contents.

Usage (from the repository root):
    python proposal/_build/build.py

Needs: Node.js with the `docx` package, matplotlib (for the figures),
LibreOffice (`soffice`) and Poppler (`pdftotext`). Steps:
1. draw the figures;
2. build the document from content.js;
3. insert a Word table-of-contents field whose entries and page numbers are
   pre-filled, so it is correct when opened (Word can refresh it with
   right-click > Update Field after edits);
4. render to PDF, read the page of every heading, write the numbers in,
   and render again to check they did not move.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "When_the_Data_Lies_Research_Proposal_B_Hemanth.docx"
RIGHT_TAB = 9350


def run(cmd: list[str], **kw) -> None:
    subprocess.run(cmd, check=True, **kw)


def toc_xml(headings: list[dict], pages: dict[str, int] | None) -> str:
    paras = []
    for i, h in enumerate(headings):
        page = str(pages.get(h["bookmark"], "")) if pages else ""
        rpr = "<w:rPr><w:noProof/><w:webHidden/></w:rPr>"
        start = ""
        if i == 0:
            start = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                     '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-2" \\h \\z \\u </w:instrText></w:r>'
                     '<w:r><w:fldChar w:fldCharType="separate"/></w:r>')
        end = '<w:r><w:fldChar w:fldCharType="end"/></w:r>' if i == len(headings) - 1 else ""
        bm = h["bookmark"]
        paras.append(
            f'<w:p><w:pPr><w:pStyle w:val="TOC{h["level"]}"/>'
            f'<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="{RIGHT_TAB}"/></w:tabs></w:pPr>'
            f"{start}"
            f'<w:hyperlink w:anchor="{bm}" w:history="1">'
            f'<w:r><w:rPr><w:noProof/></w:rPr><w:t xml:space="preserve">{html.escape(h["text"], quote=False)}</w:t></w:r>'
            f"<w:r>{rpr}<w:tab/></w:r>"
            f'<w:r>{rpr}<w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r>{rpr}<w:instrText xml:space="preserve"> PAGEREF {bm} \\h </w:instrText></w:r>'
            f'<w:r>{rpr}<w:fldChar w:fldCharType="separate"/></w:r>'
            f"<w:r>{rpr}<w:t>{page}</w:t></w:r>"
            f'<w:r>{rpr}<w:fldChar w:fldCharType="end"/></w:r>'
            f"</w:hyperlink>{end}</w:p>"
        )
    return ('<w:sdt><w:sdtPr><w:docPartObj><w:docPartGallery w:val="Table of Contents"/>'
            "<w:docPartUnique/></w:docPartObj></w:sdtPr><w:sdtContent>"
            + "".join(paras) + "</w:sdtContent></w:sdt>")


def renumber_bookmarks(xml: str) -> str:
    """Give every bookmark a unique id (docx-js writes the same id for all of them).

    Heading bookmarks never overlap, so the k-th bookmarkEnd closes the k-th bookmarkStart.
    """
    counters = {"start": 0, "end": 0}

    def number(kind: str):
        def sub(match: re.Match) -> str:
            counters[kind] += 1
            return re.sub(r'w:id="\d+"', f'w:id="{counters[kind]}"', match.group(0))
        return sub

    xml = re.sub(r"<w:bookmarkStart\b[^>]*>", number("start"), xml)
    xml = re.sub(r"<w:bookmarkEnd\b[^>]*>", number("end"), xml)
    if counters["start"] != counters["end"]:
        sys.exit(f"Unbalanced bookmarks: {counters}")
    return xml


def insert_toc(src: Path, dst: Path, headings: list[dict], pages: dict[str, int] | None) -> None:
    with zipfile.ZipFile(src) as zin:
        xml = zin.read("word/document.xml").decode("utf-8")
        idx = xml.index("%%TOC%%")
        start = max(m.start() for m in re.finditer(r"<w:p(?=[ >])", xml[:idx]))
        end = xml.index("</w:p>", idx) + len("</w:p>")
        xml = xml[:start] + toc_xml(headings, pages) + xml[end:]
        xml = renumber_bookmarks(xml)
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = xml.encode("utf-8") if item.filename == "word/document.xml" else zin.read(item.filename)
                zout.writestr(item, data)


def to_pdf(docx: Path, outdir: Path) -> Path:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        sys.exit("LibreOffice (soffice) is needed to compute page numbers")
    run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(docx)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return outdir / (docx.stem + ".pdf")


def page_texts(pdf: Path) -> list[str]:
    count = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(pdf)], capture_output=True,
                                                                text=True, check=True).stdout).group(1))
    return [subprocess.run(["pdftotext", "-layout", "-f", str(i), "-l", str(i), str(pdf), "-"],
                           capture_output=True, text=True, check=True).stdout for i in range(1, count + 1)]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def heading_pages(pdf: Path, headings: list[dict]) -> dict[str, int]:
    pages = page_texts(pdf)
    toc_pages = {i for i, t in enumerate(pages, 1) if any(norm(line) == "Contents" for line in t.splitlines())}
    found: dict[str, int] = {}
    for h in headings:
        target = norm(h["text"])
        for number, text in enumerate(pages, 1):
            if number in toc_pages:
                continue
            if any(norm(line) == target for line in text.splitlines()):
                found[h["bookmark"]] = number
                break
        else:
            sys.exit(f"Heading not found in the rendered PDF: {h['text']!r}")
    return found


def main() -> None:
    run([sys.executable, str(HERE / "figures.py")])
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        raw = tmp / "raw.docx"
        headings_json = tmp / "headings.json"
        run(["node", str(HERE / "build_proposal.js"), str(raw), str(headings_json)])
        headings = json.loads(headings_json.read_text())

        first = tmp / "pass1.docx"
        insert_toc(raw, first, headings, pages={h["bookmark"]: 99 for h in headings})
        pages = heading_pages(to_pdf(first, tmp), headings)

        final = tmp / OUT.name
        insert_toc(raw, final, headings, pages)
        check = heading_pages(to_pdf(final, tmp), headings)
        if check != pages:
            moved = [h["text"] for h in headings if check[h["bookmark"]] != pages[h["bookmark"]]]
            sys.exit(f"Page numbers moved between passes: {moved}")
        shutil.copy(final, OUT)
        shutil.copy(tmp / (OUT.stem + ".pdf"), HERE / "preview.pdf")
    print(f"wrote {OUT}")
    for h in headings:
        print(f"  {'  ' if h['level'] == 2 else ''}{h['text']} .... {pages[h['bookmark']]}")


if __name__ == "__main__":
    main()
