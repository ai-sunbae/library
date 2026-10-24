---
name: web-doc
description: >-
  Author a rich HTML document: either a flowing, responsive web page (scrolls
  like a normal web document) or a paginated, print-ready paged.js document
  (real A4/Letter pages, running headers, page numbers, a TOC with page
  references; prints / exports to PDF with correct page breaks: manuals,
  textbooks, white papers, multi-chapter reports, brochures). Use whenever the
  user wants a rich document, a printable document, or an HTML document to
  export as PDF. Decide flowing vs paginated by asking ONE AskUserQuestion up
  front, not by guessing. NOT for Markdown notes or Word .docx files.
---

# web-doc

A web_doc is one self-contained `.html` file in one of two modes:

- **Flowing** — a normal responsive HTML page that scrolls.
- **Paginated** — an HTML file that paginates in the browser with
  [paged.js](https://pagedjs.org/) (v0.4.3) into real paper pages and prints /
  exports to PDF with the page breaks you authored.

You write the file with **Write**, change it with **Edit**, and check paginated
output with the bundled **`inspect.js`** (headless Chromium + Playwright, see
below). Never judge pagination by reading the source: render it.

## First, before writing anything: ask ONE question

On the FIRST document of a session, do **not** guess the mode and do **not**
drip questions out across turns. Make exactly **one** `AskUserQuestion` call
with a **single** question whose options encode both mode and paper size:

- **header**: `Format`
- **question**: "How should this document be laid out?"
- **options** (single-select, exactly these three):
  1. **Web page** — "Flowing document that scrolls like a normal web page. Best
     for reading on screen."
  2. **Printable · A4 — best for PDF export** — "Paginated, print-ready: real
     A4 pages, page numbers, running headers, and a table of contents with
     page references. Exports cleanly to PDF."
  3. **Printable · US Letter** — "Same as A4 but on US Letter page size."

Write the labels in the user's language and keep the PDF-export note in the A4
label: users who plan to export usually can't tell which mode exports cleanly.
Don't ask paper size as a second question.

Skip the question when the request already settles it ("make me a printable A4
manual"), or when you are running as a sub-agent with no human to answer
(default to Printable · A4 then, Letter only if the brief names it, flowing only
for an explicit web page) and state the layout you chose.

Once a document exists, keep its mode on edits. Fixing page breaks or PDF
output is never a reason to switch a paginated document to flowing; switch only
when the user asks.

**Chapter recto-start is not asked.** Chapters flow onto the next page by
default (`page-break-before: always`). Only when the user explicitly asks for
chapters to start on a right-hand page, use `page-break-before: right`, which
inserts intentional blank left pages.

## Where the file goes

Write where the user says. Otherwise follow the repository's own convention
(in this repo: a new folder `<slug>/index.html`, styled and registered like the
existing pages), and outside a repo use the scratchpad directory. To show the
user the result, send the HTML (and PDF, if made) with `SendUserFile`, or
publish it as an Artifact when they want a shareable page.

## Flowing mode

A normal responsive HTML document: semantic headings, a readable measure
(~70ch), mobile-friendly at 360px width, light/dark aware if the surrounding
site is. No paged.js, no `inspect.js`. Nothing else in this skill is needed for
flowing mode; check it in a browser screenshot if layout matters.

## Paginated mode

### Workflow

1. **Outline first.** Don't draft the whole book in turn one: cover + TOC +
   chapter list, then write chapter by chapter, inspecting as you go. If the
   user supplied content, paginate it, don't rewrite it.
2. **Write** the file with the contract below.
3. **Inspect** it:
   ```bash
   node .claude/skills/web-doc/inspect.js path/to/doc.html --out <scratchpad>/inspect/<name>
   ```
   It prints the page count, console errors and failed requests, and per-page
   diagnostics (blank pages, overflow, clipped / off-page text, an over-long
   running header), and writes `overview.png` (all pages in a labeled grid,
   flagged pages labeled red) plus a full-size `page-NNN.png` for every flagged
   page. **Read `overview.png` every time** — it is your primary check; the
   diagnostics miss purely visual problems. Add `--page N` for a full-size
   capture of a page that wasn't flagged, and `--pdf out.pdf` to export.
4. **Iterate:** fix the CSS / structure with Edit, re-inspect.

Rules for inspecting:

- Prefer one inspection after a batch of edits over one per tiny change.
- **Never re-inspect an unchanged file.** The render is deterministic; looking
  again can't tell you anything new. If the layout is wrong, the next step is
  an edit.
- **Trust the delta line.** Re-running with the same `--out` prints
  `vs previous inspection: visually changed pages: […]` or that NO page
  changed (computed from each page's text, layout boxes and core styles). If
  your edit changed nothing, the edit didn't reach the render (rare blind
  spot: pseudo-element-only styling — compare screenshots then). Fix the
  edit; never make dummy edits to "refresh" anything.
- If paged.js can't be fetched (sandboxed container), `inspect.js` serves the
  CDN file from a local `npm pack` copy and says so. That's expected, not a bug
  in the document. Other failed requests (fonts, images) are real.

### Editing a passage the user quoted

When the user quotes text from the document and asks for a change, Grep for
that text in the source, make the **smallest** Edit that satisfies the request,
leave the rest untouched, and re-inspect if length or structure changed.

### HTML contract

```html
<!doctype html>
<html lang="…">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>…</title>
  <!-- Math, if any, must be set up BEFORE this line (see traps). -->
  <script src="https://cdn.jsdelivr.net/npm/pagedjs@0.4.3/dist/paged.polyfill.js"></script>
  <style>
    @page {
      size: A4;               /* or: letter */
      margin: 22mm;
      @top-right     { content: string(chapter-title); }
      @bottom-center { content: counter(page); }
    }
    @page :first {
      margin: 0;
      @top-right     { content: none; }
      @bottom-center { content: none; }
    }
    body { font-family: Georgia, "Noto Serif KR", serif; line-height: 1.6;
           text-align: left; text-wrap: pretty; }
    h1.chapter-title { string-set: chapter-title content();
                       page-break-before: always; }
    .toc a::after { content: " · " target-counter(attr(href), page); }

    /* On-screen preview: gray desk, white sheets. Print is unaffected. */
    @media screen {
      body { background: #e8e8e8; margin: 0; }
      .pagedjs_pages { padding: 16px 0; }
      .pagedjs_page { background: #fff; margin: 0 auto 16px;
                      box-shadow: 0 1px 6px rgba(0,0,0,.25); }
    }
  </style>
</head>
<body>
  <!-- First element is page 1 (the cover). -->
</body>
</html>
```

- Load paged.js **exactly once**, from the pinned CDN URL above. Keep
  everything in one file; images as absolute HTTPS URLs or files beside the
  HTML, never base64 data URIs.
- Typographic defaults you pick without asking: 22mm margins, serif body,
  page number in `@bottom-center`, chapter title in `@top-right` via
  `string-set` **on the heading element**, `target-counter()` for the TOC.
- For Korean / CJK text include a CJK font in the stack (e.g. Noto Serif KR /
  Noto Sans KR from Google Fonts).
- Users print with **Ctrl/Cmd+P → Save as PDF** (margins "None"/"Default",
  background graphics on), or you export with `inspect.js --pdf`.

## Diagrams: SVG vs generated images

- **Technical / explanatory diagrams** (charts, flowcharts, schematics, math,
  geometry, chemistry): **write inline SVG** with a `viewBox` and no fixed
  `width`/`height`, wrapped in
  `<figure style="break-inside: avoid; page-break-inside: avoid;">`.
- **Decorative imagery** (covers, chapter art): use an image the user gave you
  or a generated one if an image tool is available; otherwise design it with
  CSS/SVG shapes.

Heuristic: could a careful reader spot a *factual* error in this image?
yes → SVG.

## Known traps & fixes (paginated mode)

Skim before drafting — these bite as soon as content gets non-trivial.

- **Math (KaTeX) renders too late.** The polyfill clones `<body>` on
  `DOMContentLoaded` and paginates immediately; an async renderer on
  `window.onload` / `defer` runs after pagination and leaves raw `$x^2$`.
  Render synchronously in `window.PagedConfig.before`, defined **before** the
  polyfill:
  ```html
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
  <script>
    window.PagedConfig = {
      before: () => renderMathInElement(document.body, {
        delimiters: [
          { left: '$$', right: '$$', display: true },
          { left: '\\[', right: '\\]', display: true },
          { left: '$',  right: '$',  display: false },
          { left: '\\(', right: '\\)', display: false }
        ],
        throwOnError: false,
        strict: 'ignore'
      }),
    };
  </script>
  <script src="https://cdn.jsdelivr.net/npm/pagedjs@0.4.3/dist/paged.polyfill.js"></script>
  ```
  Literal `<` / `>` inside `$...$` break the HTML parser — use `\lt` / `\gt`.

- **Silent polyfill hang on heavy content.** 100+ formulas + complex SVGs +
  many dense pages can send the chunker into a retry loop: 0 pages, no console
  error. `inspect.js` reports it as `.pagedjs_pages exists but 0
  .pagedjs_page`. Fixes, cheapest first: (1) split into smaller documents;
  (2) every `<svg>` uses `viewBox` with NO fixed `width`/`height`; (3) wrap
  large figures in `<figure style="break-inside: avoid;">`.

- **Verso filler pages are NOT bugs.** With `page-break-before: right`, a
  blank left page before a chapter is intentional. `inspect.js` labels these
  "blank left page (verso filler …)". Leave them.

- **Blank PAGE 1 (cover lands on page 2).** Two causes: (1) a
  `page-break-before` on the FIRST element — apply breaks only to chapters
  after the cover/TOC; (2) a `page: <name>` declaration on the first element
  forces an implicit break — drop it and style the cover with `@page :first`.

- **Flex/grid containers must not fragment across pages.** paged.js can't
  split a `display: flex` / `grid` box: items past the page boundary are laid
  out at a negative offset — invisible. `inspect.js` flags them as
  CLIPPED/OFF-PAGE text, but check the overview too (classic symptom: "the TOC
  heading and first entries vanished"). Use block layout for anything that may
  cross a page; build TOC dot leaders with a bottom border or `::after`. Flex
  inside a single non-fragmenting page (the cover) is fine.

- **"Fill the page to full height" can't be done by stretching.** Under
  paged.js, `break-inside: avoid` blocks and whole flex/grid boxes render at
  their NATURAL height; `flex: 1`, `height: 100%`, `align-items: stretch` won't
  absorb trailing white space, and re-trying variants never converges. The only
  levers are content sizing (font-size, line-height, margins/padding, adding or
  trimming content) or a `min-height` on a page wrapper. Calibrate in 2–3
  rounds; if white space remains, show the closest version, explain the
  constraint, and ask the user how to proceed.

- **`string-set` must bind to the heading, NEVER a container.** `content()`
  captures the text of the element it's declared on. On a chapter `<section>`
  it dumps the whole chapter into the running header on every page. Declare it
  on the heading only: `h1.chapter-title { string-set: chapter-title content() }`.
  Invisible in the source; `inspect.js` flags it as an over-long RUNNING
  HEADER.

- **Accidental blank pages mid-document.** Causes, most likely first: (1) a
  forced `page-break-before/after: always` on a section that already starts
  (or ends) at a page boundary — prefer `break-inside: avoid`, and never force
  a break after the last section; (2) a `break-inside: avoid` block taller than
  the printable area — it gets pushed to a fresh page and overflows it; split
  it or drop the avoid; (3) a stray trailing element (empty `<div>`, `<br>`,
  big bottom margin) after the last content. A blank LAST page is essentially
  always accidental.

- **No `text-align: justify`, anywhere.** On paged.js pages it opens huge gaps
  between words in narrow blocks (TOC, credits, table cells) and between CJK
  characters. Use `text-align: left; text-wrap: pretty;`.

- **Covers must fill the paper — apply the full-bleed recipe whole.** Both
  halves together: `@page :first { margin: 0 }` (with `content: none` on its
  margin boxes) AND `min-height: 297mm` (A4; `279mm` Letter) on the cover
  element, with `box-sizing: border-box`. Half-applied it breaks: ~297mm inside
  default margins overflows onto extra pages; a short cover on a margin-0 page
  leaves a band of empty paper below it. Check the full page-1 capture.

- **No `vh` units.** There's no viewport; use `mm` / `%`.

- **Never put a fixed size on `<body>` or `<html>`.** `body { width: 210mm;
  height: 297mm }` fights paged.js's page boxes and breaks the screen preview
  with a horizontal scrollbar. Page size comes from `@page`; put poster sizing
  on a wrapper inside the page (e.g. `.poster { min-height: 297mm }` with a
  margin-0 `@page`).

- **Settle paper size before generating.** Switching A4 ↔ Letter, or adding /
  removing recto starts, re-flows every page.
