// Build the research proposal .docx from content.js.
// Usage: node build_proposal.js <out.docx> <headings.json>
// The table of contents is inserted afterwards by build.py, which fills in page numbers.

const fs = require("fs");
const path = require("path");
const {
  AlignmentType, Bookmark, BorderStyle, Document, Footer, HeadingLevel, ImageRun, LevelFormat,
  LineRuleType, Packer, PageNumber, Paragraph, Tab, TabStopType, Table, TableCell, TableRow,
  TextRun, WidthType,
} = require("docx");
const { meta, blocks, references } = require("./content.js");

const [outPath, headingsPath] = process.argv.slice(2);
const FIG_DIR = path.join(__dirname, "figures");
const SERIF = "Times New Roman";
const SANS = "Calibri";
const ACCENT = "2F5496";
const CONTENT_WIDTH = 9360; // US Letter with 1-inch margins, in DXA

// ---------------------------------------------------------------- citations
const citeOrder = [];
function cite(text) {
  return text.replace(/\[@([^\]]+)\]/g, (_, inner) =>
    inner.split(",").map((k) => {
      const key = k.trim().replace(/^@/, "");
      if (!(key in references)) throw new Error(`Unknown reference key: ${key}`);
      if (!citeOrder.includes(key)) citeOrder.push(key);
      return `[${citeOrder.indexOf(key) + 1}]`;
    }).join(", "));
}

// ---------------------------------------------------------------- inline markup
// **bold**, *italic*, _{subscript}, ^{superscript}
function runs(text, base = {}) {
  text = cite(text);
  const out = [];
  let bold = false, italics = false, buf = "";
  const flush = (extra = {}) => {
    if (buf) out.push(new TextRun({ text: buf, bold, italics, ...base, ...extra }));
    buf = "";
  };
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === "*" && text[i + 1] === "*") { flush(); bold = !bold; i++; continue; }
    if (c === "*") { flush(); italics = !italics; continue; }
    if ((c === "_" || c === "^") && text[i + 1] === "{") {
      const end = text.indexOf("}", i + 2);
      if (end < 0) throw new Error(`Unclosed ${c}{ in: ${text}`);
      flush();
      buf = text.slice(i + 2, end);
      flush(c === "_" ? { subScript: true } : { superScript: true });
      i = end;
      continue;
    }
    buf += c;
  }
  flush();
  return out;
}

// ---------------------------------------------------------------- builders
const headings = [];
let bookmarkCount = 0;

function heading(text, level, opts = {}) {
  const id = `_Toc${String(++bookmarkCount).padStart(4, "0")}`;
  headings.push({ level, text, bookmark: id });
  return new Paragraph({
    heading: level === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
    pageBreakBefore: !!opts.pageBreakBefore,
    alignment: opts.center ? AlignmentType.CENTER : undefined,
    children: [new Bookmark({ id, children: [new TextRun(text)] })],
  });
}

const body = (text, opts = {}) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  spacing: { after: 140 },
  ...opts,
  children: runs(text),
});

function equation(text, n) {
  return new Paragraph({
    tabStops: [
      { type: TabStopType.CENTER, position: CONTENT_WIDTH / 2 },
      { type: TabStopType.RIGHT, position: CONTENT_WIDTH },
    ],
    spacing: { before: 60, after: 160 },
    keepLines: true,
    children: [
      new TextRun({ children: [new Tab()] }),
      ...runs(text, { font: "Cambria Math", size: 22 }),
      new TextRun({ children: [new Tab(), `(${n})`] }),
    ],
  });
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "8C99A6" };
const borders = { top: border, bottom: border, left: border, right: border };

function table(spec) {
  const total = spec.widths.reduce((a, b) => a + b, 0);
  if (total !== CONTENT_WIDTH) throw new Error(`Table widths sum to ${total}, expected ${CONTENT_WIDTH}`);
  // Short tables stay on one page; every table keeps its caption with its last row.
  const keepWhole = spec.rows.length <= 8;
  const cell = (text, width, header, keepNext) => new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ spacing: { after: 0 }, keepNext, children: runs(header ? `**${text}**` : text, { size: 19 }) })],
  });
  const last = spec.rows.length - 1;
  const rows = [
    new TableRow({ tableHeader: true, cantSplit: true, children: spec.header.map((h, i) => cell(h, spec.widths[i], true, true)) }),
    ...spec.rows.map((r, j) => new TableRow({ cantSplit: true,
      children: r.map((t, i) => cell(t, spec.widths[i], false, keepWhole || j === last)) })),
  ];
  const out = [new Table({ width: { size: CONTENT_WIDTH, type: WidthType.DXA }, columnWidths: spec.widths, rows })];
  if (spec.caption) {
    out.push(new Paragraph({ spacing: { before: 80, after: 220 }, children: runs(`*${spec.caption}*`, { size: 19 }) }));
  }
  return out;
}

function figure(file, widthIn, caption) {
  const data = fs.readFileSync(path.join(FIG_DIR, file));
  // PNG header holds width and height at bytes 16-23
  const w = data.readUInt32BE(16), h = data.readUInt32BE(20);
  const width = Math.round(widthIn * 96);
  const height = Math.round((width * h) / w);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      keepNext: true,
      spacing: { before: 120, after: 60, line: 240, lineRule: LineRuleType.AUTO },
      children: [new ImageRun({ type: "png", data, transformation: { width, height },
        altText: { title: caption, description: caption, name: file } })],
    }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 220 }, children: runs(`*${caption}*`, { size: 19 }) }),
  ];
}

// ---------------------------------------------------------------- title page
const titlePage = [
  new Paragraph({ spacing: { before: 1200, after: 120 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: meta.title, bold: true, size: 48, font: SERIF })] }),
  new Paragraph({ spacing: { after: 160 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: meta.subtitle, bold: true, size: 30, font: SERIF })] }),
  new Paragraph({ spacing: { after: 120 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: meta.kind, bold: true, size: 26, font: SERIF })] }),
  new Paragraph({ spacing: { after: 480 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: meta.scopeLine, italics: true, size: 20, font: SERIF })] }),
  ...meta.lines.map((line) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
    indent: { left: 720, right: 720 }, children: [new TextRun({ text: line, size: 22 })] })),
  new Paragraph({ spacing: { before: 600 }, children: [] }),
  heading("Honesty note", 2, { center: true }),
  new Paragraph({ alignment: AlignmentType.CENTER, indent: { left: 720, right: 720 }, spacing: { after: 120 },
    children: [new TextRun({ text: meta.honesty, size: 20 })] }),
];

// ---------------------------------------------------------------- body
const children = [...titlePage];
for (const b of blocks) {
  if (b.h1) children.push(heading(b.h1, 1, b));
  else if (b.h2) children.push(heading(b.h2, 2, b));
  else if (b.p) children.push(body(b.p));
  else if (b.eq) children.push(equation(b.eq, b.n));
  else if (b.table) children.push(...table(b.table));
  else if (b.figure) children.push(...figure(b.figure, b.widthIn, b.caption));
  else if (b.bullets) {
    for (const item of b.bullets) {
      children.push(new Paragraph({ numbering: { reference: "bullets", level: 0 }, alignment: AlignmentType.JUSTIFIED,
        spacing: { after: 100 }, children: runs(item) }));
    }
  } else if (b.toc) {
    children.push(new Paragraph({ style: "ContentsTitle", pageBreakBefore: true, children: [new TextRun("Contents")] }));
    children.push(new Paragraph({ children: [new TextRun("%%TOC%%")] }));
  } else if (b.references) {
    children.push(heading("References", 1));
    citeOrder.forEach((key, i) => {
      children.push(new Paragraph({
        spacing: { after: 80 },
        indent: { left: 520, hanging: 520 },
        tabStops: [{ type: TabStopType.LEFT, position: 520 }],
        children: [new TextRun({ text: `[${i + 1}]`, size: 19 }), new TextRun({ children: [new Tab()], size: 19 }),
          ...runs(references[key].replace(/\*/g, ""), { size: 19 })],
      }));
    });
  } else {
    throw new Error(`Unknown block: ${JSON.stringify(b).slice(0, 80)}`);
  }
}

const unused = Object.keys(references).filter((k) => !citeOrder.includes(k));
if (unused.length) console.warn(`Note: references never cited (left out): ${unused.join(", ")}`);

// ---------------------------------------------------------------- document
const doc = new Document({
  creator: "B Hemanth",
  title: `${meta.title}: ${meta.subtitle}`,
  subject: "Research proposal",
  description: meta.scopeLine,
  keywords: "agentic AI, data fidelity, AIS, GNSS spoofing, maritime logistics, conformal risk control",
  styles: {
    // Built-in heading styles are changed in place (not redefined) so Word and LibreOffice agree.
    default: {
      document: { run: { font: SERIF, size: 22 }, paragraph: { spacing: { line: 276, lineRule: LineRuleType.AUTO } } },
      heading1: { run: { font: SANS, size: 28, bold: true, color: ACCENT },
        paragraph: { spacing: { before: 300, after: 120 }, keepNext: true, keepLines: true, outlineLevel: 0 } },
      heading2: { run: { font: SANS, size: 24, bold: false, color: ACCENT },
        paragraph: { spacing: { before: 200, after: 100 }, keepNext: true, keepLines: true, outlineLevel: 1 } },
    },
    paragraphStyles: [
      { id: "ContentsTitle", name: "Contents Title", basedOn: "Normal", next: "Normal",
        run: { font: SANS, size: 28, bold: true, color: ACCENT }, paragraph: { spacing: { after: 160 } } },
      { id: "TOC1", name: "toc 1", basedOn: "Normal", next: "Normal",
        run: { size: 21 }, paragraph: { spacing: { before: 60, after: 40 } } },
      { id: "TOC2", name: "toc 2", basedOn: "Normal", next: "Normal",
        run: { size: 21 }, paragraph: { spacing: { after: 40 }, indent: { left: 360 } } },
    ],
  },
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 540, hanging: 300 } } } }],
    }],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          tabStops: [
            { type: TabStopType.CENTER, position: CONTENT_WIDTH / 2 },
            { type: TabStopType.RIGHT, position: CONTENT_WIDTH },
          ],
          children: [
            new TextRun({ children: [new Tab(), meta.footer], size: 18, color: "55626C" }),
            new TextRun({ children: [new Tab(), PageNumber.CURRENT], size: 18, color: "55626C" }),
          ],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outPath, buf);
  fs.writeFileSync(headingsPath, JSON.stringify(headings, null, 2));
  console.log(`wrote ${outPath} (${headings.length} headings, ${citeOrder.length} references)`);
});
