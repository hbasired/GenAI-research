"""Build the HTML reading pages from the Markdown topic documents.

Each page's Markdown file is the single source of truth. The first H1, the
italic line under it and the first table become the page header; the rest of
the document becomes the body. Mermaid code fences become diagrams.

Usage:
    pip install markdown==3.7
    python research-topics/_build/build_pages.py            # full HTML documents
    python research-topics/_build/build_pages.py --fragment OUT_DIR
        # also writes skeleton-free fragments (for hosts that add their own <head>)
"""

import argparse
import html
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
MERMAID_SRC = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"
FONTS = (
    "https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700"
    "&family=Barlow:wght@400;500;600"
    "&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400"
    "&display=swap"
)

# page id -> (source md, output html, browser title, eyebrow, light accent, light soft, dark accent, dark soft)
PAGES = {
    "final": ("final_topic_when_the_data_lies.md", "final_topic_when_the_data_lies.html",
              "When the Data Lies", "Final research topic · Fidelity-gated, spoof-resilient logistics agents",
              "#1F5F99", "#DFEAF5", "#7DB3E8", "#17304A"),
    "overview": ("README.md", "00_overview.html", "Fidelity Topic Shortlist",
                 "Topic selection · Data fidelity × agentic AI in logistics",
                 "#2D5A7B", "#E0EAF1", "#8DB8D8", "#1C3242"),
    "t1": ("topic1_fidelity_gated_autonomy.md", "topic1_fidelity_gated_autonomy.html",
           "Know When Not to Act", "Research topic 1 of 3 · Decision-aware fidelity",
           "#0E6B6F", "#DCEDEC", "#5CC0C0", "#12393B"),
    "t2": ("topic2_spoof_resilient_logistics.md", "topic2_spoof_resilient_logistics.html",
           "When the Data Lies", "Research topic 2 of 3 · Adversarial fidelity",
           "#3B44A8", "#E3E5F7", "#9AA2F2", "#23264A"),
    "t3": ("topic3_verified_traceability.md", "topic3_verified_traceability.html",
           "Prove It Before It Ships", "Research topic 3 of 3 · Cross-border fidelity",
           "#2E6B3B", "#E1EEE3", "#78C089", "#1D3523"),
}
NAV = [("final", "Final topic"), ("overview", "Shortlist"), ("t1", "1 · Know When Not to Act"),
       ("t2", "2 · When the Data Lies"), ("t3", "3 · Prove It Before It Ships")]
VERDICTS = {"ACT": "ok", "SHADOW": "neutral", "ACQUIRE": "info", "VERIFY": "info",
            "REVIEW": "warn", "HOLD": "bad"}

CSS = """
/* Layout: consignment-note masthead (label/value grid), then a sticky contents rail beside a ~70ch reading column */
:root {
  --paper: #F3F5F3; --surface: #FFFFFF; --ink: #18232C; --muted: #56636D;
  --rule: #D3DBD7; --tint: #E8EEEB; --code-bg: #EEF2F0;
  --accent: __A__; --accent-soft: __AS__;
  --ok: #23704A; --ok-soft: #DDEFE4; --warn: #8A5A00; --warn-soft: #F6EBD3;
  --bad: #A3342A; --bad-soft: #F6E0DD; --neutral: #4D5A63; --neutral-soft: #E4E9EC;
  --font-display: "Barlow Condensed", "Arial Narrow", "Helvetica Neue", Arial, sans-serif;
  --font-ui: "Barlow", "Helvetica Neue", Arial, sans-serif;
  --font-body: "Source Serif 4", Georgia, "Times New Roman", serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --measure: 70ch;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #0F1417; --surface: #161C20; --ink: #E2E8EA; --muted: #9AA6AE;
    --rule: #2A353B; --tint: #1B2327; --code-bg: #1A2125;
    --accent: __DA__; --accent-soft: __DAS__;
    --ok: #7FD1A2; --ok-soft: #173326; --warn: #E8B860; --warn-soft: #3A2C10;
    --bad: #F09A8F; --bad-soft: #3D1C18; --neutral: #B4C0C7; --neutral-soft: #242E34;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --paper: #0F1417; --surface: #161C20; --ink: #E2E8EA; --muted: #9AA6AE;
  --rule: #2A353B; --tint: #1B2327; --code-bg: #1A2125;
  --accent: __DA__; --accent-soft: __DAS__;
  --ok: #7FD1A2; --ok-soft: #173326; --warn: #E8B860; --warn-soft: #3A2C10;
  --bad: #F09A8F; --bad-soft: #3D1C18; --neutral: #B4C0C7; --neutral-soft: #242E34;
  color-scheme: dark;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink); font-family: var(--font-body);
  font-size: 17px; line-height: 1.62; -webkit-text-size-adjust: 100%; }
.wrap { max-width: 1180px; margin: 0 auto; padding-inline: clamp(16px, 4vw, 40px); padding-block: 0 64px; }
a { color: var(--accent); text-underline-offset: 3px; text-decoration-thickness: 1px; overflow-wrap: anywhere; }
article p, article li, article td, article blockquote { overflow-wrap: break-word; }
a:hover { text-decoration-thickness: 2px; }
a:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 2px; }

.pagenav { display: flex; flex-wrap: wrap; gap: 6px 18px; padding-block: 14px; border-bottom: 1px solid var(--rule);
  font-family: var(--font-ui); font-size: 0.86rem; }
.pagenav a { color: var(--muted); text-decoration: none; }
.pagenav a:hover { color: var(--ink); }
.pagenav a[aria-current="page"] { color: var(--ink); font-weight: 600; border-bottom: 2px solid var(--accent); }

.masthead { padding-block: 36px 28px; display: grid; gap: 18px; }
.eyebrow { font-family: var(--font-ui); font-size: 0.78rem; font-weight: 600; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--accent); margin: 0; }
.masthead h1 { font-family: var(--font-display); font-weight: 700; font-size: clamp(2.4rem, 6vw, 4.1rem);
  line-height: 0.98; letter-spacing: 0.005em; margin: 0; text-wrap: balance; text-transform: uppercase; }
.dek { font-style: italic; font-size: clamp(1.05rem, 2.2vw, 1.3rem); color: var(--muted); margin: 0; max-width: 60ch; }
.manifest { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; border: 1.5px solid var(--ink);
  background: var(--rule); margin-top: 8px; }
.manifest .cell { padding: 10px 14px 12px; background: var(--surface); min-width: 0; }
.manifest .cell.wide { grid-column: 1 / -1; }
.manifest .label { display: block; font-family: var(--font-ui); font-size: 0.7rem; font-weight: 600;
  letter-spacing: 0.11em; text-transform: uppercase; color: var(--muted); margin-bottom: 3px; }
.manifest .value { font-family: var(--font-ui); font-size: 0.98rem; line-height: 1.45; overflow-wrap: anywhere; }
.manifest .value p { margin: 0; }
.manifest .value strong { color: var(--accent); }

.layout { display: grid; grid-template-columns: 230px minmax(0, 1fr); gap: 48px; align-items: start; margin-top: 12px; }
.toc { position: sticky; top: calc(env(safe-area-inset-top, 0px) + 16px); font-family: var(--font-ui);
  font-size: 0.88rem; max-height: calc(100vh - 32px); overflow-y: auto; padding-block: 18px; }
.toc details > summary { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--muted); cursor: pointer; list-style: none; margin-bottom: 10px; }
.toc details > summary::-webkit-details-marker { display: none; }
.toc ol { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; border-left: 1px solid var(--rule); }
.toc li a { display: block; padding: 4px 0 4px 12px; color: var(--muted); text-decoration: none; line-height: 1.3;
  margin-left: -1px; border-left: 2px solid transparent; }
.toc li a:hover { color: var(--ink); border-left-color: var(--accent); }

article { min-width: 0; padding-block: 8px; }
article > * { max-width: var(--measure); }
article > .table-wrap, article > figure, article > pre { max-width: 100%; }
article h2 { font-family: var(--font-display); font-weight: 700; font-size: 1.9rem; line-height: 1.1;
  letter-spacing: 0.01em; text-transform: uppercase; margin: 2.6rem 0 0.9rem; padding-top: 0.9rem;
  border-top: 2px solid var(--ink); text-wrap: balance; scroll-margin-top: 16px; }
article h2:first-child { margin-top: 0.4rem; }
article h3 { font-family: var(--font-ui); font-weight: 600; font-size: 1.15rem; margin: 1.8rem 0 0.5rem; }
article p, article li { text-wrap: pretty; }
article p { margin: 0 0 1rem; }
article ul, article ol { padding-left: 1.3rem; margin: 0 0 1rem; }
article li { margin-bottom: 0.35rem; }
article strong { font-weight: 600; }
article hr { border: 0; border-top: 1px solid var(--rule); margin: 2rem 0; }
article em { font-style: italic; }
article blockquote { margin: 1rem 0; padding: 10px 16px; background: var(--accent-soft); border-radius: 4px; }

.table-wrap { overflow-x: auto; margin: 0.6rem 0 1.4rem; border: 1px solid var(--rule); border-radius: 4px; background: var(--surface); }
table { border-collapse: collapse; width: 100%; font-family: var(--font-ui); font-size: 0.93rem; line-height: 1.45;
  font-variant-numeric: tabular-nums; }
th, td { text-align: left; vertical-align: top; padding: 9px 12px; border-bottom: 1px solid var(--rule); }
thead th { background: var(--tint); font-size: 0.74rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--muted); white-space: nowrap; }
tbody tr:last-child td { border-bottom: 0; }
td:first-child { font-weight: 500; }
td code, li code, p code { font-family: var(--font-mono); font-size: 0.85em; background: var(--code-bg); padding: 1px 5px; border-radius: 3px; }

pre { font-family: var(--font-mono); font-size: 0.84rem; line-height: 1.5; background: var(--code-bg); color: var(--ink);
  padding: 14px 16px; border-radius: 4px; overflow-x: auto; margin: 0.6rem 0 1.4rem; }
pre code { background: none; padding: 0; }

figure.diagram { margin: 0.8rem 0 1.6rem; padding: 16px; background: var(--surface); border: 1px solid var(--rule);
  border-radius: 4px; overflow-x: auto; }
figure.diagram pre.mermaid { background: none; margin: 0; padding: 0; text-align: center; white-space: pre; }
figure.diagram figcaption { font-family: var(--font-ui); font-size: 0.8rem; color: var(--muted); margin-top: 10px; }

.chip { display: inline-block; font-family: var(--font-ui); font-weight: 600; font-size: 0.78rem; letter-spacing: 0.08em;
  padding: 1px 8px; border-radius: 999px; white-space: nowrap; }
.chip.ok { color: var(--ok); background: var(--ok-soft); }
.chip.warn { color: var(--warn); background: var(--warn-soft); }
.chip.bad { color: var(--bad); background: var(--bad-soft); }
.chip.info { color: var(--accent); background: var(--accent-soft); }
.chip.neutral { color: var(--neutral); background: var(--neutral-soft); }

.pips { display: inline-flex; gap: 3px; vertical-align: middle; margin-right: 8px; }
.pips i { width: 9px; height: 9px; border-radius: 50%; border: 1.5px solid var(--accent); display: inline-block; }
.pips i.on { background: var(--accent); }
td.score { white-space: nowrap; }

footer.colophon { margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--rule); font-family: var(--font-ui);
  font-size: 0.85rem; color: var(--muted); display: flex; flex-wrap: wrap; gap: 8px 24px; }

@media (max-width: 960px) {
  .layout { grid-template-columns: minmax(0, 1fr); gap: 8px; }
  .toc { position: static; max-height: none; padding-block: 8px; border: 1px solid var(--rule); border-radius: 4px;
    padding-inline: 14px; background: var(--surface); }
  .toc details > summary { margin-bottom: 0; }
  .toc details[open] > summary { margin-bottom: 10px; }
}
@media (max-width: 640px) {
  body { font-size: 16px; }
  .manifest { grid-template-columns: minmax(0, 1fr); }
  article h2 { font-size: 1.6rem; }
  td:first-child { min-width: 8.5rem; }
  .pips { display: none; }
}
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
"""

MERMAID_INIT = """
(function () {
  function tok(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function render() {
    if (!window.mermaid) return;
    var tv = {
      background: tok('--surface'), primaryColor: tok('--accent-soft'), primaryBorderColor: tok('--accent'),
      primaryTextColor: tok('--ink'), nodeTextColor: tok('--ink'), textColor: tok('--ink'),
      lineColor: tok('--muted'), secondaryColor: tok('--tint'), tertiaryColor: tok('--surface'),
      clusterBkg: tok('--tint'), clusterBorder: tok('--rule'), titleColor: tok('--ink'),
      edgeLabelBackground: tok('--surface'), fontFamily: 'Barlow, Helvetica Neue, Arial, sans-serif', fontSize: '15px'
    };
    try {
      window.mermaid.initialize({ startOnLoad: false, theme: 'base', themeVariables: tv,
        flowchart: { curve: 'basis', useMaxWidth: true } });
      var p = window.mermaid.run({ querySelector: 'pre.mermaid' });
      if (p && p.catch) p.catch(function () {});
    } catch (e) {}
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', render); else render();
})();
"""


def split_header(md_text):
    """Return (title, dek, fields, body_md). fields is a list of (label, value_md)."""
    lines = md_text.splitlines()
    i = 0
    title = dek = ""
    while i < len(lines) and not lines[i].startswith("# "):
        i += 1
    title = lines[i][2:].strip()
    i += 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].startswith("*") and lines[i].endswith("*"):
        dek = lines[i].strip("*").strip()
        i += 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    fields = []
    if i < len(lines) and lines[i].startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            rows.append(lines[i])
            i += 1
        for row in rows[2:]:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if len(cells) >= 2:
                fields.append((cells[0], "|".join(cells[1:]).strip()))
    while i < len(lines) and (not lines[i].strip() or lines[i].strip() == "---"):
        i += 1
    return title, dek, fields, "\n".join(lines[i:])


def inline_md(text):
    out = markdown.markdown(text, extensions=["sane_lists"])
    return re.sub(r"^<p>(.*)</p>$", r"\1", out.strip(), flags=re.S)


def link_fix(fragment):
    fragment = re.sub(r'href="README\.md(#[^"]*)?"', lambda m: f'href="00_overview.html{m.group(1) or ""}"', fragment)
    return re.sub(r'href="((?:topic[0-9]|final_topic)[^"/]*?)\.md(#[^"]*)?"',
                  lambda m: f'href="{m.group(1)}.html{m.group(2) or ""}"', fragment)


def postprocess(body, page_id):
    body = re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>',
                  lambda m: f'<figure class="diagram"><pre class="mermaid">{m.group(1)}</pre></figure>',
                  body, flags=re.S)
    body = re.sub(r"<table>", '<div class="table-wrap"><table>', body)
    body = re.sub(r"</table>", "</table></div>", body)
    for word, kind in VERDICTS.items():
        body = body.replace(f"<strong>{word}</strong>", f'<span class="chip {kind}">{word}</span>')
    if page_id == "overview":
        def pip(m):
            n = int(m.group(1))
            dots = "".join('<i class="on"></i>' if k < n else "<i></i>" for k in range(5))
            return f'<td class="score"><span class="pips" aria-hidden="true">{dots}</span>{n}</td>'
        body = re.sub(r"<td>([1-5])</td>", pip, body)
    return link_fix(body)


LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+\.)\s")


def loosen_lists(text):
    """Python-Markdown needs a blank line between a paragraph and a list that follows it."""
    out, fence = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        prev = out[-1] if out else ""
        if (not fence and LIST_ITEM.match(line) and prev.strip()
                and not LIST_ITEM.match(prev) and not prev.startswith(("|", ">", "#", "    "))
                and not prev.startswith(" ")):
            out.append("")
        out.append(line)
    return "\n".join(out)


def build(page_id):
    src, out, page_title, eyebrow, acc, acc_soft, dacc, dacc_soft = PAGES[page_id]
    text = (ROOT / src).read_text(encoding="utf-8")
    title, dek, fields, body_md = split_header(text)
    body_md = loosen_lists(body_md)
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists", "attr_list"],
                           extension_configs={"toc": {"toc_depth": "2"}})
    body = postprocess(md.convert(body_md), page_id)
    toc_items = "".join(f'<li><a href="#{t["id"]}">{html.escape(t["name"])}</a></li>' for t in md.toc_tokens)

    # A long value spans both columns. A short value left without a partner
    # (next field is wide, or it is the last one) also spans, so the grid has no holes.
    wide = [len(value) > 90 for _, value in fields]
    pending = None
    for k, is_wide in enumerate(wide):
        if is_wide:
            if pending is not None:
                wide[pending] = True
            pending = None
        else:
            pending = k if pending is None else None
    if pending is not None:
        wide[pending] = True
    cells = []
    for (label, value), is_wide in zip(fields, wide):
        cells.append(f'<div class="cell{" wide" if is_wide else ""}"><span class="label">{html.escape(label)}</span>'
                     f'<div class="value">{link_fix(inline_md(value))}</div></div>')
    current = ' aria-current="page"'
    nav = "".join(
        f'<a href="{PAGES[pid][1]}"{current if pid == page_id else ""}>{label}</a>'
        for pid, label in NAV if (ROOT / PAGES[pid][0]).exists())
    css = (CSS.replace("__A__", acc).replace("__AS__", acc_soft)
              .replace("__DA__", dacc).replace("__DAS__", dacc_soft))
    content = f"""<div class="wrap">
<nav class="pagenav" aria-label="Topic pages">{nav}</nav>
<header class="masthead">
<p class="eyebrow">{html.escape(eyebrow)}</p>
<h1>{html.escape(title.split("·")[-1].strip())}</h1>
{f'<p class="dek">{html.escape(dek)}</p>' if dek else ''}
<div class="manifest">{''.join(cells)}</div>
</header>
<div class="layout">
<aside class="toc"><details open><summary>Contents</summary><ol>{toc_items}</ol></details></aside>
<article>
{body}
</article>
</div>
<footer class="colophon"><span>Prepared 7 October 2026 · built from <code>{html.escape(src)}</code></span>
<span>Open-source research plan · re-check every source before citing</span></footer>
</div>"""
    head = (f'<title>{html.escape(page_title)}</title>\n'
            f'<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            f'<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            f'<link rel="stylesheet" href="{FONTS}">\n<style>{css}</style>')
    has_mermaid = 'class="mermaid"' in body
    scripts = (f'<script src="{MERMAID_SRC}"></script>\n<script>{MERMAID_INIT}</script>') if has_mermaid else ""
    full = (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'{head}\n</head>\n<body>\n{content}\n{scripts}\n</body>\n</html>\n')
    fragment = f"{head}\n{content}\n{scripts}\n"
    return out, full, fragment


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fragment", help="also write skeleton-free fragments to this directory")
    args = ap.parse_args()
    for page_id in PAGES:
        if not (ROOT / PAGES[page_id][0]).exists():
            print("skipped", PAGES[page_id][0], "(not written yet)")
            continue
        out, full, fragment = build(page_id)
        (ROOT / out).write_text(full, encoding="utf-8")
        print("wrote", ROOT / out)
        if args.fragment:
            d = Path(args.fragment)
            d.mkdir(parents=True, exist_ok=True)
            (d / out).write_text(fragment, encoding="utf-8")


if __name__ == "__main__":
    main()
