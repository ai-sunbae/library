#!/usr/bin/env node
// Render a paginated web_doc with paged.js in headless Chromium and report
// what the pages actually look like.
//
//   node inspect.js <doc.html> [--out DIR] [--page N] [--pdf FILE] [--timeout MS]
//
// Prints page count, console/request errors, blank/overflow/clipped/header
// diagnostics, and a delta against the previous run in the same --out dir.
// Writes overview.png (all pages in a labeled grid), page-NNN.png for every
// flagged page (and for --page N), and optionally a PDF.
//
// If the paged.js CDN is unreachable (sandboxed container), the script is
// served from a local copy fetched with `npm pack pagedjs@<version>`.

const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');

function parseArgs(argv) {
  const args = { file: null, out: null, page: null, pdf: null, timeout: 90000 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--out') args.out = argv[++i];
    else if (a === '--page') args.page = parseInt(argv[++i], 10);
    else if (a === '--pdf') args.pdf = argv[++i];
    else if (a === '--timeout') args.timeout = parseInt(argv[++i], 10);
    else if (!args.file) args.file = a;
  }
  if (!args.file) {
    console.error('usage: node inspect.js <doc.html> [--out DIR] [--page N] [--pdf FILE]');
    process.exit(2);
  }
  args.file = path.resolve(args.file);
  args.out = path.resolve(args.out || path.join(os.tmpdir(), 'web-doc-inspect', path.basename(args.file, '.html')));
  return args;
}

// Local fallback for pagedjs/katex files when the CDN is blocked.
const CACHE = path.join(os.homedir(), '.cache', 'web-doc-inspect');
function localNpmFile(pkg, version, relPath) {
  const dir = path.join(CACHE, `${pkg}-${version}`);
  const target = path.join(dir, 'package', relPath);
  if (!fs.existsSync(target)) {
    fs.mkdirSync(dir, { recursive: true });
    const tgz = execFileSync('npm', ['pack', `${pkg}@${version}`, '--silent'], { cwd: dir }).toString().trim().split('\n').pop();
    execFileSync('tar', ['xzf', tgz], { cwd: dir });
  }
  return fs.existsSync(target) ? target : null;
}

// Map a CDN URL to {pkg, version, relPath}, or null.
function npmFromUrl(url) {
  let m = url.match(/^https:\/\/(?:cdn\.jsdelivr\.net\/npm|unpkg\.com)\/(@?[^@/]+(?:\/[^@/]+)?)@([^/]+)\/(.+?)(?:\?.*)?$/);
  if (m) return { pkg: m[1], version: m[2], relPath: m[3] };
  m = url.match(/^https:\/\/cdnjs\.cloudflare\.com\/ajax\/libs\/pagedjs\/([^/]+)\/(.+?)(?:\?.*)?$/);
  if (m) return { pkg: 'pagedjs', version: m[1], relPath: path.posix.join('dist', m[2]) };
  return null;
}

function contentType(p) {
  if (p.endsWith('.js')) return 'application/javascript';
  if (p.endsWith('.css')) return 'text/css';
  if (p.endsWith('.woff2')) return 'font/woff2';
  if (p.endsWith('.woff')) return 'font/woff';
  if (p.endsWith('.ttf')) return 'font/ttf';
  return 'application/octet-stream';
}

// Pass a request through; if the network refuses it, serve a CDN npm file
// from the local cache instead.
async function serve(route, localFallbacks = [], failedRequests = []) {
  const url = route.request().url();
  let reason = 'blocked';
  try {
    const resp = await route.fetch({ timeout: 15000 });
    if (resp.status() < 400) return route.fulfill({ response: resp });
    reason = `HTTP ${resp.status()}`;
  } catch (err) {
    reason = err.message.split('\n')[0];
  }
  const npm = npmFromUrl(url);
  const local = npm && localNpmFile(npm.pkg, npm.version, npm.relPath);
  if (local) {
    localFallbacks.push(url);
    return route.fulfill({ body: fs.readFileSync(local), contentType: contentType(local) });
  }
  failedRequests.push(`${url} (${reason})`);
  return route.abort();
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  fs.mkdirSync(args.out, { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  const consoleErrors = [];
  const failedRequests = [];
  const localFallbacks = [];

  page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('pageerror', (err) => consoleErrors.push(String(err)));

  await page.route(/^https?:\/\//, (route) => serve(route, localFallbacks, failedRequests));

  await page.goto('file://' + args.file, { waitUntil: 'load', timeout: args.timeout });

  // Wait until paged.js has produced pages and the count stops changing.
  const deadline = Date.now() + args.timeout;
  let last = -1, stableSince = Date.now(), hasContainer = false;
  while (Date.now() < deadline) {
    const state = await page.evaluate(() => ({
      container: !!document.querySelector('.pagedjs_pages'),
      count: document.querySelectorAll('.pagedjs_page').length,
    }));
    hasContainer = state.container;
    if (state.count !== last) { last = state.count; stableSince = Date.now(); }
    if (state.count > 0 && Date.now() - stableSince > 2000) break;
    await page.waitForTimeout(250);
  }

  const report = await page.evaluate(() => {
    const pages = [...document.querySelectorAll('.pagedjs_page')];
    return pages.map((pg, i) => {
      const area = pg.querySelector('.pagedjs_page_content') || pg;
      const areaBox = area.getBoundingClientRect();
      const text = (area.innerText || '').replace(/\s+/g, ' ').trim();
      const media = area.querySelectorAll('img, svg, canvas, video, picture').length;
      const bgImage = [...area.querySelectorAll('*')].some((el) => {
        const bg = getComputedStyle(el).backgroundImage;
        return bg && bg !== 'none';
      });
      const coloredBlock = [...area.querySelectorAll('*')].some((el) => {
        const r = el.getBoundingClientRect();
        const c = getComputedStyle(el).backgroundColor;
        return r.height > areaBox.height * 0.5 && c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent';
      });
      const blank = !text && !media && !bgImage && !coloredBlock;

      const inner = area.firstElementChild || area;
      const overflow = Math.max(area.scrollHeight - area.clientHeight, inner.scrollHeight - area.clientHeight);

      // Text-bearing elements laid out outside the content box: clipped or
      // pushed to a negative offset (fragmented flex/grid).
      const clipped = [];
      for (const el of area.querySelectorAll('*')) {
        if (!el.childNodes.length || el.children.length) continue;
        const t = (el.textContent || '').trim();
        if (!t) continue;
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;
        if (r.bottom < areaBox.top - 2 || r.top > areaBox.bottom + 2 || r.right < areaBox.left - 2 || r.left > areaBox.right + 2) {
          clipped.push(t.slice(0, 60));
          if (clipped.length >= 5) break;
        }
      }

      // Running header/footer text is generated into ::before/::after.
      const margins = [...pg.querySelectorAll('.pagedjs_margin-content')].map((m) => {
        const pseudo = ['::before', '::after'].map((ps) => {
          const c = getComputedStyle(m, ps).content;
          return c && c.startsWith('"') ? c.slice(1, -1) : '';
        }).join('');
        return ((m.innerText || '') + pseudo).trim();
      }).filter(Boolean);
      const longHeader = margins.find((t) => t.length > 80) || null;

      const sig = JSON.stringify({
        text,
        boxes: [...area.querySelectorAll('*')].slice(0, 400).map((el) => {
          const r = el.getBoundingClientRect();
          const cs = getComputedStyle(el);
          return [el.tagName, Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height),
            cs.fontSize, cs.fontWeight, cs.color, cs.backgroundColor];
        }),
        margins,
      });

      return {
        n: i + 1,
        side: pg.classList.contains('pagedjs_left_page') ? 'left' : pg.classList.contains('pagedjs_right_page') ? 'right' : '',
        blank,
        overflow: overflow > 2 ? overflow : 0,
        clipped,
        longHeader,
        chars: text.length,
        sig,
      };
    });
  });

  const lines = [];
  lines.push(`file: ${args.file}`);
  lines.push(`pages: ${report.length}`);
  if (!report.length) {
    lines.push(hasContainer
      ? 'ERROR: .pagedjs_pages exists but 0 .pagedjs_page — polyfill hang (see "Silent polyfill hang" trap).'
      : 'ERROR: paged.js never ran (no .pagedjs_pages). Check the polyfill <script> URL and console errors.');
  }
  if (localFallbacks.length) lines.push(`cdn blocked here, served from local npm copy: ${localFallbacks.length} file(s)`);
  for (const e of consoleErrors) lines.push(`console error: ${e}`);
  for (const r of failedRequests) lines.push(`failed request: ${r}`);

  const flagged = new Set();
  for (const p of report) {
    const issues = [];
    if (p.blank) {
      const next = report[p.n];
      if (p.n === report.length) issues.push('BLANK LAST PAGE (almost always accidental)');
      else if (p.n === 1) issues.push('BLANK PAGE 1 (see "Blank PAGE 1" trap)');
      else if (p.side === 'left' && next) issues.push('blank left page (verso filler if the next page opens a page-break-before: right chapter)');
      else issues.push('BLANK PAGE');
    }
    if (p.overflow) issues.push(`OVERFLOW by ${p.overflow}px`);
    if (p.clipped.length) issues.push(`CLIPPED/OFF-PAGE text: ${p.clipped.map((t) => JSON.stringify(t)).join(', ')}`);
    if (p.longHeader) issues.push(`RUNNING HEADER/FOOTER is ${p.longHeader.length} chars — string-set bound to a container?`);
    if (issues.length) {
      flagged.add(p.n);
      lines.push(`page ${p.n}: ${issues.join('; ')}`);
    }
  }
  if (report.length && !flagged.size) lines.push('no blank/overflow/clipped pages detected');

  // Delta vs previous run in the same out dir.
  const sigs = report.map((p) => crypto.createHash('sha1').update(p.sig).digest('hex'));
  const sigFile = path.join(args.out, 'signatures.json');
  if (fs.existsSync(sigFile)) {
    const prev = JSON.parse(fs.readFileSync(sigFile, 'utf8'));
    const changed = [];
    for (let i = 0; i < Math.max(prev.length, sigs.length); i++) if (prev[i] !== sigs[i]) changed.push(i + 1);
    lines.push(changed.length
      ? `vs previous inspection: visually changed pages: [${changed.join(', ')}] (pages ${prev.length} -> ${sigs.length})`
      : 'vs previous inspection: NO page changed — your edit did not affect the render');
  }
  fs.writeFileSync(sigFile, JSON.stringify(sigs));

  // Screenshots: labeled grid of all pages, then full-size flagged pages.
  if (report.length) {
    for (const n of [...flagged, args.page].filter(Boolean)) {
      const el = await page.$(`.pagedjs_page:nth-of-type(${n})`) || (await page.$$('.pagedjs_page'))[n - 1];
      if (el) {
        const f = path.join(args.out, `page-${String(n).padStart(3, '0')}.png`);
        await el.screenshot({ path: f });
        lines.push(`screenshot: ${f}`);
      }
    }

    await page.addStyleTag({ content: `
      .pagedjs_pages { display: flex !important; flex-wrap: wrap !important; gap: 24px !important;
        padding: 24px !important; background: #8a8a8a !important; transform: none !important; }
      .pagedjs_page { position: relative !important; margin: 0 !important; box-shadow: 0 0 0 1px #555 !important; background: #fff; }
      .__wdi_label { position: absolute; top: 4px; left: 4px; z-index: 99999; background: #d00; color: #fff;
        font: bold 28px/1 sans-serif; padding: 4px 8px; }
      .__wdi_label.ok { background: #222; }
      body > :not(.pagedjs_pages) { display: none !important; }
    ` });
    await page.evaluate((flaggedList) => {
      document.querySelectorAll('.pagedjs_page').forEach((pg, i) => {
        const l = document.createElement('div');
        l.className = '__wdi_label' + (flaggedList.includes(i + 1) ? '' : ' ok');
        l.textContent = String(i + 1);
        pg.appendChild(l);
      });
      const cols = Math.min(6, document.querySelectorAll('.pagedjs_page').length);
      const w = document.querySelector('.pagedjs_page').getBoundingClientRect().width;
      const gridW = (cols * (w + 24) + 48) + 'px';
      document.querySelector('.pagedjs_pages').style.width = gridW;
      document.documentElement.style.width = document.body.style.width = gridW;
      document.body.style.margin = '0';
    }, [...flagged]);
    const grid = await page.$('.pagedjs_pages');
    const box = await grid.boundingBox();
    const scale = Math.min(1, 2400 / box.width);
    await page.evaluate((s) => { document.querySelector('.pagedjs_pages').style.zoom = s; }, scale);
    const overview = path.join(args.out, 'overview.png');
    await grid.screenshot({ path: overview });
    lines.push(`overview: ${overview}`);
  }

  if (args.pdf && report.length) {
    // Re-render cleanly (the overview CSS above altered the layout).
    const clean = await browser.newPage();
    await clean.route(/^https?:\/\//, (route) => serve(route));
    await clean.goto('file://' + args.file, { waitUntil: 'load', timeout: args.timeout });
    await clean.waitForFunction((n) => document.querySelectorAll('.pagedjs_page').length >= n, report.length, { timeout: args.timeout });
    await clean.waitForTimeout(1500);
    await clean.pdf({ path: path.resolve(args.pdf), preferCSSPageSize: true, printBackground: true });
    lines.push(`pdf: ${path.resolve(args.pdf)}`);
  }

  console.log(lines.join('\n'));
  await browser.close();
}

main().catch((err) => { console.error(err); process.exit(1); });
