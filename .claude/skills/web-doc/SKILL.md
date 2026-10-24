---
name: web-doc
version: 2.2.0
description: >-
  Author a web_doc — docs_agent's unified rich-document format. A web_doc is
  either a flowing, responsive HTML page (scrolls, like a normal web document)
  or a paginated, print-ready paged.js document (real A4/Letter pages, running
  headers, page numbers, a TOC with page references, chapters that may start on
  a recto page; previews as a page-by-page reader and prints/exports to PDF with
  correct page breaks: textbooks, manuals, white papers, multi-chapter reports,
  brochures). Use whenever the user wants a rich document. Decide flowing vs
  paginated by asking the user ONE single-question form up front (see below),
  not by guessing. NOT for Markdown notes or Word-style .docx (use markdown/docx).
metadata:
  category: docs
  requires:
    gks: ["gk_ai_docs_paged_html"]
---

# web-doc

`web_doc` is the unified rich-document format. It has two modes, both authored
with the **`web_doc_generate`** tool:

- **Flowing** (`paginated=false`) — a single responsive HTML document that
  scrolls, like a normal web page / report. Stored as `type=html`.
- **Paginated** (`paginated=true`) — a single self-contained HTML file that
  paginates in the browser with [paged.js](https://pagedjs.org/) and renders
  through a book-reader UI (`paged_book_viewer.js`). Previews page-by-page,
  is inspected page-by-page by the backend browser tool, and prints / exports
  to PDF with the page breaks you authored. Stored as `type=paged_html`.

## First, before writing anything: ask ONE single-question form

On the FIRST document of a session, do **not** guess the mode, and do **not**
drip questions out across turns. Make exactly **one** `ask_user_questions` call
containing a **single** question whose options already encode both the layout
mode and the paper size, then wait for the answer:

- **header**: `Format`
- **question**: "How should this document be laid out?"
- **options** (single-select, exactly these three):
  1. **Web page** — "Flowing document that scrolls like a normal web page. Best
     for reading on screen."
  2. **Printable · A4 — best for Word / PDF export** — "Paginated, print-ready:
     real A4 pages, page numbers, running headers, and a table of contents with
     page references. Exports cleanly to Word and PDF."
  3. **Printable · US Letter** — "Same as A4 but on US Letter page size."

Keep the Word / PDF export note IN the Printable · A4 label (translated into
the user's language): users who plan to export a document usually cannot tell
which layout mode exports cleanly, and that note is how they find it.

Fold paper size INTO the option labels (do not ask paper size as a second
question — that is what produced the old two-step flow). Map the answer:

- Web page → `web_doc_generate(instruction=…, paginated=false)`
- Printable · A4 → `web_doc_generate(instruction=…, paginated=true,
  paper_size="a4")`
- Printable · US Letter → `web_doc_generate(instruction=…, paginated=true,
  paper_size="letter")`

**Chapter recto-start is NOT asked** — it defaults to `false` (chapters flow
onto the next page). It is a niche book-binding option that inserts blank verso
pages, which most users do not want. Only pass `chapter_recto_start=true` if the
user explicitly asks for it (e.g. "chapters should start on a right-hand page").

If the user already made the choice clear in their request (e.g. "make me a
printable A4 manual"), skip the question and generate directly. Once a document
exists, keep its mode on edits (see below) — only re-ask if the user asks to
switch. Fixing page breaks, layout, or PDF sync is never a reason to switch a
paginated document to flowing; when the user explicitly asks for that switch,
pass `convert_to_flowing=true` together with `paginated=false`.

**Sub-task mode — never ask.** When your system prompt says you are running as
a SUB-TASK spawned by another agent, there is no human in this session: an
`ask_user_questions` call ends the run with no document delivered. Skip the
form above entirely and take the layout from the sub-task brief as your
prompt's sub-task layout rule says (Word/.docx only when the brief asks for it;
otherwise `paginated=true, paper_size="letter"` by default, `"a4"` when the
brief names A4, `paginated=false` only for an explicitly flowing web page).
State the layout you chose in your final message.

## Flowing mode (`paginated=false`)

A normal responsive HTML document. `web_doc_generate(paginated=false)` produces
it; for incremental edits use the standard `html_edit` / `html_multi_edit` /
`html_insert` tools. There is no paged.js, no book reader, and `inspect_web_doc`
does not apply. Nothing else in this skill is needed for flowing mode.

## Paginated mode (`paginated=true`)

Produce a **single self-contained HTML file** that paginates with paged.js and
renders through the book reader. The rest of this skill is the paginated
contract.

### How you work in paginated mode

1. Generate with `web_doc_generate(paginated=true, …)` (or rewrite the whole
   document with it). For incremental edits use the standard
   `html_edit` / `html_multi_edit` / `html_insert` tools — a paginated web_doc
   IS html, so the same editing toolset applies. The type stays `paged_html`
   across edits. **Never use `html_generate` on a paginated web_doc** — to
   fully rewrite, always use `web_doc_generate` with `paginated=true`. (Calling
   `html_generate` would try to downgrade it to a flowing doc; the backend now
   refuses to downgrade while the content still loads paged.js, but relying on
   that guard wastes a turn.)

   `web_doc_generate` lint-checks the generated draft against the known
   pagination bug patterns below and appends a **`LAYOUT LINT`** block to its
   result when it finds one. Treat every lint line as real: fix it with
   `html_edit` BEFORE your first `inspect_web_doc` — each of those patterns
   ships a visibly broken document.
2. After generating or a layout-affecting edit, call **`inspect_web_doc`** to
   render the document in a real headless browser and reflect on it:
   - Call it with **no arguments** for a whole-book overview: it returns the
     rendered page count, console errors (with the failing resource URLs),
     blank-page / overflow / clipped-content diagnostics, a labeled page-grid
     screenshot of ALL pages (your primary check), **and full-resolution
     screenshots of any flagged (blank/overflow) page** — so you normally do
     NOT need a separate per-page call to see what's wrong.
   - Pass **`page_number`** (1-based) only to look at a specific page the
     overview did *not* already flag/capture.
   This is a backend-browser tool — do not rely on the user's preview to
   reason about pagination; inspect it yourself.
3. Iterate: read the diagnostics, fix the CSS / structure, re-inspect.

   Inspect whenever you need to — it's cheap: all inspect calls in a session
   reuse a single shared headless browser (one connection, a throw-away page per
   call), and re-inspecting an unchanged document is served from cache (the
   result SAYS so when it is). Prefer one overview after a batch of edits over
   one after every tiny change — the overview already returns diagnostics +
   flagged-page captures — but don't avoid a check you actually want.

   **Never re-inspect an unchanged document.** The render is deterministic:
   once a result says it was served from cache (or you haven't edited since
   the last inspect), calling `inspect_web_doc` again — same page or another
   page you already saw — CANNOT return new information and just burns
   iterations. If the layout isn't what you want, the next call must be an
   edit, not another look. (Staring at page 1 / page 2 in alternation while
   deciding how to fit content on one page is the classic trip-wire for the
   repeated-call loop breaker.)

   **Trust the delta line, not screenshot-identity intuition.** Repeat
   inspections report `vs previous inspection: visually changed pages: […]`
   (or that NO page changed), computed from each page's layout + text +
   core-style signature. Screenshots are deterministic and content-addressed:
   an image identical to a previous inspection means that page's pixels are
   UNCHANGED — it is never a stale cache, so do not make dummy edits to "bust"
   one. If the delta says your edit changed nothing, the edit did not affect
   the rendered result (rare blind spot: pseudo-element-only styling — compare
   the screenshots there) — fix the edit, not the tool.

### Editing a user-selected passage

When the user selects text in the page reader and sends a request, the message
arrives prefixed with `User selected text: "…"` and a `<text_container>`
snippet of the surrounding source block. Treat that as the precise edit target:
`html_grep` for the selected text (or the container) to locate it in the source,
make the **smallest** `html_edit` / `html_multi_edit` that satisfies the
request, and leave the rest of the document untouched. The container snippet is
the cleaned source block (paged.js pagination artifacts already stripped), so
match against the source — not against rendered `.pagedjs_*` markup. If the
edit changes length/structure enough to affect layout, re-`inspect_web_doc`.

### HTML contract (non-negotiable)

```html
<!doctype html>
<html lang="…" data-theme="light">
<head>
  <meta charset="utf-8" />
  <!-- Marks the document as a paged book for the canvas + viewer. -->
  <meta name="genspark-artifact-type" content="paged_book" />
  <title>…</title>
  <!-- Render math synchronously BEFORE the polyfill loads (see traps). -->
  <!-- Polyfill MUST load before the viewer; the viewer hooks
       Paged.Handler.afterRendered to build the toolbar/sidebar. -->
  <script src="/api/docs_agent/paged_assets/paged.polyfill.js"></script>
  <link rel="stylesheet" href="/api/docs_agent/paged_assets/paged_book_viewer.css" />
  <script src="/api/docs_agent/paged_assets/paged_book_viewer.js" defer></script>
  <style> /* @page rules + body / heading / figure typography */ </style>
</head>
<body>
  <!-- Optional but recommended: a one-line text preview (≤200 chars, plain
       text) as the first body child. -->
  <template id="__bundler_thumbnail">Document title — short pitch.</template>

  <!-- Your content. First <section> is page 1; use @page :first to suppress
       the running header/footer on it. -->
</body>
</html>
```

- The three viewer assets are served by the backend at
  `/api/docs_agent/paged_assets/<file>` — reference them by that exact
  absolute path (NOT a CDN, NOT a relative path). They are the vendored
  Paged.js v0.4.3 polyfill + the reader UI (toolbar with single-page /
  thumbnail-grid modes, page sidebar, keyboard nav, print hooks).
- The `genspark-artifact-type=paged_book` meta tag is REQUIRED.
- Load paged.js exactly once. Keep everything in one file. Use absolute HTTPS
  image URLs that appeared in the conversation; never base64 / data-uri.

You already know CSS Paged Media. Pick typographic defaults without asking:
22mm margins, serif body, page number in `@bottom-center`, chapter title
in `@top-right` via `string-set` declared **on the heading element itself**
(`h1.chapter-title { string-set: chapter-title content() }` — NEVER on the
section container; see traps), `target-counter()` for the TOC.

**Paper size comes from the up-front Format question** — it changes the page
geometry and the page count and the user can't tell from the preview which you
picked, so it is captured in the single Format question above, not decided
silently here:

- **Paper size.** Apply the chosen A4 or US Letter to the `@page` size rule.
  Default to A4 only if the user truly had no preference.
- **Book-binding blank pages.** Default is `chapter_recto_start=false`: chapters
  flow onto the next page (`page-break-before: always`, no recto rule, fewer
  pages, no blanks). This is NOT asked up front. Only when the user explicitly
  requests right-hand chapter starts, pass `chapter_recto_start=true` and give
  chapter openers `page-break-before: right` — the standard print/binding
  convention. It inserts a blank left (verso) filler page whenever a chapter
  would otherwise start on a left page, so the finished document then has
  intentional blank pages.

## Diagrams: SVG vs image_generation

- **Technical / explanatory diagrams** (physics, math figures, chemistry,
  charts, flowcharts, schematics, geometry): **write SVG inline.** You are
  more reliable than image models at factual diagrams. Wrap each in
  `<figure style="break-inside: avoid; page-break-inside: avoid;">`.
- **Decorative imagery** (covers, chapter art, illustrations): use
  `image_generation`.

Heuristic: "could a careful reader spot a *factual* error in this image?"
yes → SVG; no → image_generation.

## Known traps & fixes (paginated mode)

Skim before drafting — these bite as soon as content gets non-trivial.

- **Math (KaTeX / MathJax) renders too late.** The polyfill clones `<body>`
  on `DOMContentLoaded` and chunks immediately. An async math renderer
  attached via `window.onload` / `<script defer>` fires AFTER pagination and
  the chunked DOM keeps raw `$x^2$` forever. Render synchronously in a
  `window.PagedConfig.before` hook defined **before** the polyfill `<script>`,
  and re-attach the viewer in `after`:
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
      after: () => window.__pbv_attach?.(),  // explicit viewer attach
    };
  </script>
  <script src="/api/docs_agent/paged_assets/paged.polyfill.js"></script>
  ```
  Literal `<` / `>` inside `$...$` break the HTML parser — use `\lt` / `\gt`.
  Whenever the book has formulas, footnotes, or `page-break-before: right`,
  set `PagedConfig.after = () => window.__pbv_attach()` for explicit attach.

- **Silent polyfill hang on heavy content.** 100+ formulas + complex SVGs +
  many dense pages can drive the chunker into an unrecoverable layout-retry
  loop: 0 pages, no console error. `inspect_web_doc` reports this as a
  `.pagedjs_pages` container present with 0 `.pagedjs_page`. Fixes, cheapest
  first: (1) split into multiple smaller documents; (2) ensure every `<svg>`
  uses `viewBox=` with NO fixed `width`/`height`; (3) wrap large figures in
  `<figure style="break-inside: avoid;">`.

- **Verso filler pages are NOT bugs.** `page-break-before: right` on a chapter
  `<h1>` inserts a blank left page so the chapter starts on a recto — standard
  print convention. Don't try to remove empty `.pagedjs_page` elements.

- **Blank PAGE 1 (cover lands on page 2).** Two causes, check both:
  (1) any `page-break-before` (`right`/`always`/`recto`) on the FIRST content
  element — apply it only to chapters AFTER the cover/TOC, never the cover;
  (2) a `page: <named-page>` declaration on the first element triggers an
  implicit break — drop it and style the cover with `@page :first` instead.
  (A full-bleed IMAGE cover with no text is NOT blank — the inspect tool
  accounts for that, so a blank-page-1 warning means a truly empty page.)

- **Flex/grid containers must not fragment across pages.** paged.js cannot
  split a `display: flex` / `display: grid` box cleanly: when one lands on a
  page boundary (a TOC list, a timeline, a multi-item section), the
  overflowing items are laid out at a negative offset — rendered but
  INVISIBLE, and the diagnostics stay silent (the page has text, nothing
  scrolls, so neither the blank-page nor the overflow warning fires). Classic
  symptom: "the TOC heading and the first few entries just vanished". Use
  block layout for anything that may cross a page boundary; build TOC dot
  leaders with a bottom border or an `::after` element, not flex spacers.
  Flex INSIDE a single non-fragmenting page (e.g. the cover) is fine.

- **"Fill the page to full height" cannot be done by stretching blocks.**
  Under paged.js, `break-inside: avoid` blocks (and any flex/grid box kept
  whole per the trap above) render at their NATURAL height — `flex: 1`,
  `height: 100%`, `align-items: stretch` and similar rules can NOT expand
  them to absorb the white space at the bottom of a page. No amount of
  re-trying stretch variants converges (prod case: 74 edit→inspect rounds
  on exactly this). When the user asks to fill a page / remove trailing
  white space, the ONLY levers are the content's own sizing — font-size,
  line-height, margins/padding, adding or trimming content — or a
  `min-height` on the page wrapper. Calibrate with 2–3 sizing rounds; if
  white space remains after that, present the closest version, state this
  constraint, and ask the user how to proceed instead of iterating.

- **`string-set` must bind to the heading element, NEVER a container.**
  `content()` captures the text of the element the `string-set` is declared on.
  Declaring it on the chapter container —
  `.chapter { string-set: chapter-title content() }` on a `<section>` — dumps
  that section's ENTIRE text (the whole chapter) into the running header,
  overflowing/overlaying every page. Declare it on the heading only:
  `.chapter h1.chapter-title { string-set: chapter-title content() }`. Invisible
  in static preview — it only surfaces once paged.js paginates, so catch it with
  `inspect_web_doc`.

- **Accidental blank pages mid-document.** A common annoyance: empty pages
  appear between sections. Causes, in order of likelihood: (1) a forced
  `page-break-before: always` / `page-break-after: always` on a section that
  already starts (or ends) near a page boundary — prefer `break-inside: avoid`
  on the block over a hard break, and never force a break after the last
  section; (2) a `break-inside: avoid` (or `page-break-inside: avoid`) block
  TALLER than the printable page area — it can't fit so the whole block is
  pushed to a fresh page, leaving the prior page half-empty AND overflowing the
  new one; split such blocks or drop the avoid; (3) a stray trailing element
  (empty `<div>`, `<br>`, big bottom margin) after the last content forcing one
  extra page. `inspect_web_doc` reports every blank page; a blank LEFT page
  immediately before a `page-break-before: right` chapter is an intentional
  verso filler — leave those — but a blank LAST page is essentially always
  accidental.

- **No `text-align: justify`, anywhere.** On paged.js pages it pumps huge
  gaps between words in narrow blocks (a TOC, a fiche/credits page, table
  cells) and between CJK characters (worse still with inline
  `<span class="katex">` / inline SVG in the line). Both ship as visibly
  broken typography that users report as "random spaces in the text". Use
  `text-align: left; text-wrap: pretty;`.

- **Covers must fill the paper — use the full-bleed recipe whole.** A cover
  floating inside the default page margins (a colored box with a white frame
  around it) reads as a bug to users; don't ship it as a "safe" fallback. The
  recipe has two halves that only work TOGETHER: `@page :first { margin: 0 }`
  (plus `content: none` on its `@top-*`/`@bottom-*` slots so the running
  header/footer stay off the cover) AND `min-height: 297mm` (A4; 279mm
  Letter) or `100%` on the cover element. Half-applied it breaks both ways:
  ~297mm inside default margins overflows the ~253mm printable area across
  several pages; a short cover (say 240mm) on a margin-0 first page leaves a
  band of empty paper below it — below the screenshot fold, so it ships
  unnoticed unless you check the full page 1 capture.

- **`vh` units.** Never size elements with `vh` — there is no viewport; the
  document is paginated paper. Use `mm` / `%` / page-relative units.

- **Never put a fixed size on `<body>`.** Do NOT write `body { width: 210mm;
  height: 297mm }` (or any fixed `width`/`height` on `<body>` or `<html>`). The
  page size comes from `@page` — the body must stay fluid. The reader UI uses
  `<body>` as its own shell, so a fixed body width squashes the whole viewer to
  the page's physical width: the content area stops filling the pane and the
  page spills into a horizontal scrollbar. Put poster/page sizing on a content
  wrapper inside the page (e.g. a `.poster` div with `min-height: 297mm`,
  paired with a margin-0 `@page` — see the full-bleed cover trap above) — not
  on `body`.

## First-turn discipline (paginated mode)

Don't draft the whole book in turn one. You already have the paper size from
the up-front Format question — apply it (recto-start defaults to false unless
the user asked for it). Sketch a quick outline (cover + TOC + chapter list),
then write chapter by chapter and `inspect_web_doc` as you go. Re-flowing for a
different paper size or to add/remove the recto-start blanks is a full
re-layout, so settle the paper size before generating, not after. If the user
supplied existing content, paginate it — don't rewrite it.
