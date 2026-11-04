#!/usr/bin/env node
/**
 * Build the browsable spec graph: docs/specs/index.html
 *
 *   node docs/specs/build.mjs
 *
 * Scans the repo for Markdown files whose frontmatter carries both `id:` and
 * `type:` -- the same rule the in-app spec graph indexes by -- renders every body
 * to HTML, and emits ONE self-contained file: no fetch, no CDN, no bundled
 * fonts. It opens over file:// with no server, and publishes unchanged to
 * GitHub Pages alongside the rest of docs/.
 *
 * Navigation is hash-routed (#/<spec-id>) so single specs are linkable, spec ids
 * mentioned in prose become clickable jumps, and reverse edges are computed so
 * every node also shows what depends on it.
 */

import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const OUT = path.join(HERE, 'index.html');
const SKIP_DIRS = new Set(['.git', 'node_modules', '.venv', 'venv', 'dist', 'build', '__pycache__', '.next', '.cache', '.superpowers']);

/* ----------------------------------------------------------- discover specs */

function* walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.') && entry.name !== '.opencode') continue;
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue;
      yield* walk(path.join(dir, entry.name));
    } else if (entry.isFile() && entry.name.endsWith('.md')) {
      yield path.join(dir, entry.name);
    }
  }
}

const stripScalar = (s) => {
  const t = s.trim();
  if (t.length > 1 && ((t.startsWith('"') && t.endsWith('"')) || (t.startsWith("'") && t.endsWith("'")))) {
    return t.slice(1, -1);
  }
  return t;
};

/** Minimal YAML-subset reader: scalars, flow lists, block lists, comments. */
function parseFrontmatter(raw) {
  const lines = raw.split(/\r?\n/);
  if (lines[0]?.trim() !== '---') return null;
  const end = lines.findIndex((l, i) => i > 0 && l.trim() === '---');
  if (end === -1) return null;

  const fm = {};
  let lastKey = null;
  for (const line of lines.slice(1, end)) {
    if (/^\s*#/.test(line) || !line.trim()) continue;
    const blockItem = line.match(/^\s+-\s+(.*)$/);
    if (blockItem && lastKey) {
      (fm[lastKey] ??= []).push(stripScalar(blockItem[1]));
      continue;
    }
    const kv = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!kv) continue;
    const [, key, rest] = kv;
    const value = rest.trim();
    if (value === '') {
      lastKey = key;
      fm[key] = [];
      continue;
    }
    lastKey = null;
    if (value.startsWith('[')) {
      const inner = value.slice(1, value.endsWith(']') ? -1 : undefined).trim();
      fm[key] = inner ? inner.split(',').map(stripScalar).filter(Boolean) : [];
      continue;
    }
    fm[key] = stripScalar(value);
  }
  return { fm, body: lines.slice(end + 1).join('\n') };
}

const asList = (v) => (v == null ? [] : Array.isArray(v) ? v : [v]);

const specs = [];
for (const file of walk(ROOT)) {
  const parsed = parseFrontmatter(readFileSync(file, 'utf8'));
  if (!parsed?.fm.id || !parsed?.fm.type) continue;
  const { fm, body } = parsed;
  specs.push({
    id: fm.id,
    type: fm.type,
    status: fm.status ?? 'unset',
    title: fm.title ?? fm.id,
    parent: fm.parent ?? null,
    dependsOn: asList(fm['depends-on']),
    references: asList(fm.references),
    implements: asList(fm.implements),
    covers: asList(fm.covers),
    tags: asList(fm.tags),
    body,
    relPath: path.relative(ROOT, file).split(path.sep).join('/'),
  });
}
specs.sort((a, b) => a.relPath.localeCompare(b.relPath));

if (!specs.length) {
  console.error('No spec files found (frontmatter needs both id: and type:).');
  process.exit(1);
}

const byId = new Map(specs.map((s) => [s.id, s]));
const IDS = new Set(byId.keys());
const TYPE_ORDER = ['goal-and-requirements', 'architecture-design', 'module-design', 'submodule-design', 'task-spec'];

/* ------------------------------------------------------------------- edges */

const relMap = (map, from, to) => {
  if (!map.has(from)) map.set(from, new Set());
  map.get(from).add(to);
};

const kidsOf = new Map();
const requiredBy = new Map();
const referencedBy = new Map();
const implementedBy = new Map();
const dangling = [];

for (const s of specs) {
  const check = (kind, target) => {
    if (!IDS.has(target)) {
      dangling.push({ from: s.id, kind, to: target });
      return false;
    }
    return true;
  };
  if (s.parent && check('parent', s.parent)) relMap(kidsOf, s.parent, s.id);
  for (const d of s.dependsOn) if (check('depends-on', d)) relMap(requiredBy, d, s.id);
  for (const r of s.references) if (check('references', r)) relMap(referencedBy, r, s.id);
  for (const m of s.implements) if (check('implements', m)) relMap(implementedBy, m, s.id);
}

const roots = specs
  .filter((s) => !s.parent || !IDS.has(s.parent))
  .sort((a, b) => TYPE_ORDER.indexOf(a.type) - TYPE_ORDER.indexOf(b.type));

const dupIds = specs.length - IDS.size;
const seen = new Set();
const cycles = specs.filter((s) => {
  let node = s.parent;
  const chain = new Set([s.id]);
  while (node && byId.has(node)) {
    if (chain.has(node)) return true;
    chain.add(node);
    node = byId.get(node).parent;
  }
  seen.add(s.id);
  return false;
});

/* -------------------------------------------------------------- markdown */

const esc = (s) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const slug = (s) =>
  s.toLowerCase().replace(/[^\w\s-]/g, '').trim().replace(/\s+/g, '-').slice(0, 60);

const isFence = (l) => /^\s{0,3}(```|~~~)/.test(l);
const isHR = (l) => /^\s{0,3}(?:[-*_]\s*){3,}$/.test(l);
const listRE = /^(\s*)(?:[-*+]|\d+[.)])\s+/;
const itemRE = /^(\s*)(?:([-*+])|(\d+)[.)])\s+(.*)$/;
const boxRE = /^\[([ xX])\]\s+(.*)$/;

/** Inline spans. A bare spec id inside backticks becomes a link to that spec. */
function renderInline(text, self) {
  const codes = [];
  let out = text.replace(/`([^`]+)`/g, (_, c) => {
    codes.push(c);
    return `\u0000${codes.length - 1}\u0000`;
  });
  out = esc(out);
  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, target) => {
    const clean = target.replace(/^\.\.?\//, '');
    const owner = specs.find((s) => s.relPath === clean || s.relPath.endsWith('/' + clean) || s.relPath === target);
    if (owner) return `<a href="#/${owner.id}">${label}</a>`;
    const local = /^\.\.?\/|\.md$/.test(target);
    return `<a href="${target}"${local ? '' : ' target="_blank" rel="noopener noreferrer"'}>${label}</a>`;
  });
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  out = out.replace(/(^|[\s(])_([^_\n]+)_/g, '$1<em>$2</em>');
  out = out.replace(/~~([^~]+)~~/g, '<del>$1</del>');
  out = out.replace(/\u0000(\d+)\u0000/g, (_, i) => {
    const code = codes[Number(i)];
    const id = code.trim();
    if (IDS.has(id) && id !== self) {
      return `<a class="specref" href="#/${id}" title="Open spec ${id}"><code>${esc(code)}</code></a>`;
    }
    return `<code>${esc(code)}</code>`;
  });
  return out;
}

function renderList(lines, start, self) {
  const first = lines[start].match(itemRE);
  const base = first[1].length;
  const ordered = Boolean(first[3]);
  const items = [];
  let i = start;

  const close = () => {
    for (const it of items) {
      if (it.cont.length) it.content += ` ${it.cont.map((c) => renderInline(c, self)).join(' ')}`;
    }
    const body = items.map((it) => `<li>${it.content}${it.children.join('')}</li>`).join('');
    return { html: `<${ordered ? 'ol' : 'ul'}>${body}</${ordered ? 'ol' : 'ul'}>`, next: i };
  };

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      let j = i;
      while (j < lines.length && !lines[j].trim()) j += 1;
      const m = j < lines.length ? lines[j].match(itemRE) : null;
      if (m && m[1].length >= base) {
        i = j;
        continue;
      }
      break;
    }

    const m = line.match(itemRE);
    if (!m) {
      if (items.length && /^\s{2,}\S/.test(line) && !isFence(line) && !isHR(line)) {
        items[items.length - 1].cont.push(line.trim());
        i += 1;
        continue;
      }
      break;
    }

    const indent = m[1].length;
    if (indent < base) break;
    if (indent > base) {
      const nested = renderList(lines, i, self);
      if (items.length) items[items.length - 1].children.push(nested.html);
      i = nested.next;
      continue;
    }

    const box = m[4].match(boxRE);
    const content = box
      ? `<span class="cb${box[1] === ' ' ? '' : ' on'}" aria-hidden="true"></span>${renderInline(box[2], self)}`
      : renderInline(m[4], self);
    items.push({ content, children: [], cont: [] });
    i += 1;
  }
  return close();
}

function renderBlocks(lines, self) {
  const out = [];
  const para = [];
  const flush = () => {
    if (para.length) {
      // Render the joined paragraph, then turn soft breaks back into <br>, so
      // emphasis that spans a wrapped line (**foo\nbar**) still closes.
      out.push(`<p>${renderInline(para.join('\n'), self).replace(/\n/g, '<br>')}</p>`);
      para.length = 0;
    }
  };
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      flush();
      i += 1;
      continue;
    }

    if (isFence(line)) {
      flush();
      const marker = line.trim().slice(0, 3);
      const info = line.trim().slice(3).trim();
      const buf = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith(marker)) buf.push(lines[i++]);
      i += 1;
      const long = buf.length > 24;
      out.push(
        `<figure class="codeblock${long ? ' collapsible' : ''}">` +
          `<figcaption><span>${esc(info || 'text')}</span>${long ? '<button type="button" data-fold>toggle</button>' : ''}</figcaption>` +
          `<pre><code>${esc(buf.join('\n'))}</code></pre>` +
          `</figure>`,
      );
      continue;
    }

    const h = line.match(/^\s{0,3}(#{1,6})\s+(.*)$/);
    if (h) {
      flush();
      const text = h[2].replace(/\s+#+\s*$/, '');
      const id = `${self}--${slug(text)}`;
      out.push(`<h${h[1].length} id="${id}">${renderInline(text, self)}</h${h[1].length}>`);
      i += 1;
      continue;
    }

    if (isHR(line)) {
      flush();
      out.push('<hr>');
      i += 1;
      continue;
    }

    if (/^\s{0,3}>/.test(line)) {
      flush();
      const buf = [];
      while (i < lines.length && /^\s{0,3}>/.test(lines[i])) {
        buf.push(lines[i].replace(/^\s{0,3}>\s?/, ''));
        i += 1;
      }
      out.push(`<blockquote>${renderBlocks(buf, self).join('')}</blockquote>`);
      continue;
    }

    if (line.includes('|') && i + 1 < lines.length && /^\s*\|?[\s:]*-{2,}[-\s:|]*\|?\s*$/.test(lines[i + 1])) {
      flush();
      const cut = (l) => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
      const head = cut(line);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].trim() && lines[i].includes('|')) rows.push(cut(lines[i++]));
      out.push(
        `<div class="tablewrap"><table><thead><tr>${head.map((c) => `<th>${renderInline(c, self)}</th>`).join('')}</tr></thead>` +
          `<tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${renderInline(c, self)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`,
      );
      continue;
    }

    if (listRE.test(line)) {
      flush();
      const list = renderList(lines, i, self);
      out.push(list.html);
      i = list.next;
      continue;
    }

    para.push(line);
    i += 1;
  }
  flush();
  return out;
}

/* ------------------------------------------------------------ page pieces */

const chip = (id) =>
  IDS.has(id)
    ? `<a class="chip" href="#/${id}">${esc(id)}</a>`
    : `<span class="chip ghost" title="no spec declares this id">${esc(id)}</span>`;

const edge = (label, ids, empty) =>
  `<div class="edge"><span class="edge-k">${label}</span><span class="edge-v">${
    ids.length ? ids.map(chip).join('') : `<em class="none">${empty}</em>`
  }</span></div>`;

const sortIds = (ids) =>
  [...ids].sort(
    (a, b) => TYPE_ORDER.indexOf(byId.get(a)?.type) - TYPE_ORDER.indexOf(byId.get(b)?.type) || a.localeCompare(b),
  );

function treeNode(id) {
  const s = byId.get(id);
  const kids = sortIds(kidsOf.get(id) ?? []);
  return (
    `<li><a href="#/${id}" data-nav="${id}" data-search="${esc((s.title + ' ' + s.id + ' ' + s.type + ' ' + s.status).toLowerCase())}">` +
    `<span class="dot ${esc(s.type)}"></span><span class="t">${esc(s.title)}</span>` +
    `<span class="u">${esc(s.id)}${s.status === 'draft' ? ' · draft' : ''}</span></a>` +
    (kids.length ? `<ul class="kids">${kids.map(treeNode).join('')}</ul>` : '') +
    `</li>`
  );
}

const navTree = roots.map((r) => treeNode(r.id)).join('');

const typeCounts = TYPE_ORDER.map((t) => [t, specs.filter((s) => s.type === t).length]).filter((n) => n[1]);
const statusList = [...new Set(specs.map((s) => s.status))];
const draftCount = specs.filter((s) => s.status === 'draft').length;

const integrity =
  dangling.length || dupIds || cycles.length
    ? `<p>Something is wrong with the graph. Fix these before trusting cross-links:</p><ul>` +
      dangling.map((d) => `<li>${chip(d.from)} → <code>${d.kind}</code> → <span class="chip ghost">${esc(d.to)}</span> <em>target missing</em></li>`).join('') +
      (dupIds ? `<li><em>${dupIds} duplicate id(s)</em></li>` : '') +
      (cycles.length ? `<li><em>parent cycle involving: ${cycles.map((c) => esc(c.id)).join(', ')}</em></li>` : '') +
      `</ul>`
    : `<p class="ok">Validated: no dangling links, no duplicate ids, no parent cycles.</p>`;

const overview =
  `<h1>Spec graph</h1>` +
  `<p class="lede">Every documented goal, boundary, contract, and decision in this repository — read straight off the Markdown files in the tree. This page is generated, not a second copy of anything.</p>` +
  `<div class="stats">` +
  `<div><b>${specs.length}</b><span>specs</span></div>` +
  `<div><b>${roots.length}</b><span>root(s)</span></div>` +
  `<div><b>${draftCount}</b><span>awaiting review</span></div>` +
  `<div><b>${dangling.length + dupIds + cycles.length}</b><span>graph issues</span></div>` +
  `</div>` +
  `<h2>What this is</h2>` +
  `<p>Each spec is a normal <code>.md</code> file in the repo. The frontmatter <code>id</code> and <code>type</code> are what make it a node; the sidebar tree is the <code>parent</code> edge, and every spec header lists its edges in both directions.</p>` +
  `<p>Regenerate after editing any spec:</p>` +
  `<pre><code>node docs/specs/build.mjs</code></pre>` +
  `<h2>By type</h2><div class="chiplist">` +
  typeCounts.map(([t, n]) => `<a class="chip filter" href="#/${specs.find((s) => s.type === t).id}"><span class="dot ${esc(t)}"></span>${esc(t)} <em>${n}</em></a>`).join('') +
  `</div>` +
  `<h2>By status</h2><div class="chiplist">` +
  statusList.map((st) => `<span class="chip st">${esc(st)} <em>${specs.filter((s) => s.status === st).length}</em></span>`).join('') +
  `</div>` +
  `<h2>Graph integrity</h2>${integrity}` +
  `<h2>Reading the specs</h2>` +
  `<ul>` +
  `<li>Anything written in backticks that matches a spec id is a clickable jump.</li>` +
  `<li>URLs are stable: <code>#&lt;spec-id&gt;</code> opens one node, so a specific decision can be linked directly.</li>` +
  `<li><em>draft</em> means the node is adopted but the owner has not reviewed it yet — do not treat drift callouts in those as settled.</li>` +
  `<li>Long code blocks are collapsible; the ASCII diagrams are verbatim from the files.</li>` +
  `</ul>`;

const articles = specs
  .map((s) => {
    const kids = sortIds(kidsOf.get(s.id) ?? []);
    const back = (map) => sortIds(map.get(s.id) ?? []);
    return `<article class="spec" data-id="${esc(s.id)}" data-type="${esc(s.type)}" data-status="${esc(s.status)}" hidden>
<header class="spechead">
<div class="badges"><span class="badge type-${esc(s.type)}">${esc(s.type)}</span><span class="badge st">${esc(s.status)}</span></div>
<h1>${esc(s.title)}</h1>
<div class="idline"><code>${esc(s.id)}</code><span class="src">${esc(s.relPath)}</span></div>
</header>
<section class="edges">
${s.parent ? edge('parent', [s.parent], '') : ''}
${edge('children', kids, 'leaf node')}
${edge('depends-on', s.dependsOn, 'none declared')}
${edge('required by', back(requiredBy), 'nothing in the graph')}
${s.references.length || back(referencedBy).length ? edge('references', s.references, 'none declared') : ''}
${back(referencedBy).length ? edge('referenced by', back(referencedBy), '') : ''}
${s.implements.length ? edge('implements', s.implements, 'none declared') : ''}
${back(implementedBy).length ? edge('implemented by', back(implementedBy), '') : ''}
${s.tags.length ? `<div class="edge"><span class="edge-k">tags</span><span class="edge-v">${s.tags.map((t) => `<span class="tag">${esc(t)}</span>`).join('')}</span></div>` : ''}
</section>
<section class="body">${renderBlocks(s.body.split(/\r?\n/), s.id).join('\n')}</section>
</article>`;
  })
  .join('\n');

let revision = 'unknown revision';
try {
  revision = execSync('git rev-parse --short HEAD', { cwd: ROOT, encoding: 'utf8' }).trim();
} catch {}

const footer = `Built by <code>docs/specs/build.mjs</code> from ${specs.length} spec files at <code>${esc(revision)}</code>. Generated view: edit the Markdown, not this page.`;

/* ---------------------------------------------------------------- shell */

const css = `
:root{--bg:#fbfbfa;--panel:#fff;--ink:#1b1c20;--muted:#676b76;--line:#e4e5e9;--accent:#3b5bdb;--code:#f4f5f7;--sbw:330px;
--goal:#7048e8;--arch:#1971c2;--mod:#2b8a3e;--sub:#0c8599;--task:#e8590c}
@media (prefers-color-scheme:dark){:root{--bg:#131418;--panel:#1a1c21;--ink:#e6e7ea;--muted:#969dac;--line:#2b2e35;--accent:#7d8ffb;--code:#1e2128;
--goal:#b197fc;--arch:#74c0fc;--mod:#8ce99a;--sub:#66d9e8;--task:#ffa94d}}
html[data-theme=light]{--bg:#fbfbfa;--panel:#fff;--ink:#1b1c20;--muted:#676b76;--line:#e4e5e9;--accent:#3b5bdb;--code:#f4f5f7}
html[data-theme=dark]{--bg:#131418;--panel:#1a1c21;--ink:#e6e7ea;--muted:#969dac;--line:#2b2e35;--accent:#7d8ffb;--code:#1e2128}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
code,pre,.u,.src,.idline code{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.layout{display:grid;grid-template-columns:var(--sbw) minmax(0,1fr);min-height:100vh}
aside{position:sticky;top:0;height:100vh;overflow:auto;border-right:1px solid var(--line);background:var(--panel);padding:18px 14px 44px}
.brand{display:flex;align-items:baseline;gap:8px;font-weight:650;font-size:16.5px;letter-spacing:-.01em;margin:0 0 3px}
.brand a{color:var(--ink)}
.sub{color:var(--muted);font-size:12.5px;margin:0 0 14px}
#q{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit;font-size:14px}
#q::placeholder{color:var(--muted)}
nav ul{list-style:none;margin:12px 0 0;padding:0}
nav ul.kids{margin-left:10px;padding-left:8px;border-left:1px solid var(--line)}
nav li>a{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px;padding:5px 7px;border-radius:7px;font-size:13.5px;line-height:1.3;color:var(--ink)}
nav li>a:hover{background:var(--code);text-decoration:none}
nav li>a .t{flex:1 1 auto;min-width:0}
nav li>a .u{flex:1 1 100%;font-size:10.5px;color:var(--muted)}
nav li>a[aria-current=page]{background:color-mix(in srgb,var(--accent) 13%,transparent);box-shadow:inset 2px 0 0 var(--accent)}
nav li>a[aria-current=page] .t{font-weight:600}
nav li.hide{display:none}
.dot{width:7px;height:7px;border-radius:50%;background:var(--muted);flex:none;align-self:center}
.dot.goal-and-requirements{background:var(--goal)}.dot.architecture-design{background:var(--arch)}.dot.module-design{background:var(--mod)}
.dot.submodule-design{background:var(--sub)}.dot.task-spec{background:var(--task)}
.tools{display:flex;gap:8px;align-items:center;margin-top:16px;padding-top:12px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
.tools button{font:inherit;font-size:12px;padding:4px 8px;border:1px solid var(--line);background:var(--bg);color:var(--muted);border-radius:6px;cursor:pointer}
main{padding:34px clamp(20px,4vw,64px) 110px;max-width:930px;min-width:0}
article[hidden]{display:none}
.lede{font-size:18px;line-height:1.55;color:var(--muted);max-width:70ch}
h1{font-size:29px;letter-spacing:-.021em;margin:.15em 0 .3em;line-height:1.22}
h2{font-size:20.5px;letter-spacing:-.012em;margin:1.9em 0 .5em;padding-bottom:.3em;border-bottom:1px solid var(--line)}
h3{font-size:17px;margin:1.55em 0 .4em}
h4,h5,h6{font-size:15px;margin:1.3em 0 .3em;color:var(--muted)}
p{margin:.7em 0;max-width:74ch}
ul,ol{max-width:74ch;padding-left:1.4em}
li{margin:.3em 0}
hr{border:0;border-top:1px solid var(--line);margin:2em 0}
blockquote{margin:1.1em 0;padding:.7em 1.1em;border-left:3px solid var(--accent);background:color-mix(in srgb,var(--accent) 6%,var(--panel));border-radius:0 8px 8px 0}
blockquote p{margin:.35em 0}
code{background:var(--code);border:1px solid var(--line);border-radius:4px;padding:.08em .32em;font-size:.85em}
a.specref code{border-color:color-mix(in srgb,var(--accent) 40%,var(--line));color:var(--accent)}
pre{background:var(--code);border:1px solid var(--line);border-radius:10px;padding:14px 16px;overflow:auto;font-size:12.5px;line-height:1.5}
pre code{background:none;border:0;padding:0;font-size:inherit;white-space:pre}
figure.codeblock{margin:1.2em 0}
figure.codeblock figcaption{display:flex;justify-content:space-between;align-items:center;font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:5px}
figure.codeblock button{font:inherit;font-size:11px;text-transform:none;letter-spacing:0;border:1px solid var(--line);background:var(--panel);color:var(--muted);border-radius:5px;padding:2px 8px;cursor:pointer}
figure.collapsible.folded pre{max-height:200px;overflow:hidden;-webkit-mask-image:linear-gradient(to bottom,#000 50%,transparent);mask-image:linear-gradient(to bottom,#000 50%,transparent)}
.tablewrap{overflow-x:auto;margin:1.2em 0}
table{border-collapse:collapse;font-size:14px;width:100%}
th,td{border-bottom:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);border-bottom-width:2px}
.cb{display:inline-block;width:13px;height:13px;border:1.5px solid var(--muted);border-radius:3px;margin-right:7px;vertical-align:-2px}
.cb.on{background:var(--accent);border-color:var(--accent)}
.spechead{margin-bottom:18px}
.badges{display:flex;gap:7px;margin-bottom:9px}
.badge{font-size:11px;text-transform:uppercase;letter-spacing:.06em;padding:3px 8px;border-radius:20px;border:1px solid var(--line);color:var(--muted)}
.badge.type-goal-and-requirements{color:var(--goal);border-color:color-mix(in srgb,var(--goal) 45%,var(--line))}
.badge.type-architecture-design{color:var(--arch);border-color:color-mix(in srgb,var(--arch) 45%,var(--line))}
.badge.type-module-design{color:var(--mod);border-color:color-mix(in srgb,var(--mod) 45%,var(--line))}
.badge.type-submodule-design{color:var(--sub);border-color:color-mix(in srgb,var(--sub) 45%,var(--line))}
.badge.type-task-spec{color:var(--task);border-color:color-mix(in srgb,var(--task) 45%,var(--line))}
.badge.st[data-s=draft],.badge.st{color:var(--task)}
.idline{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;font-size:12.5px;color:var(--muted)}
.src{border-left:1px solid var(--line);padding-left:10px}
.edges{display:grid;gap:7px;padding:13px 15px;border:1px solid var(--line);border-radius:10px;background:var(--panel);margin:0 0 26px;font-size:13px}
.edge{display:grid;grid-template-columns:104px minmax(0,1fr);gap:10px;align-items:baseline}
.edge-k{color:var(--muted);font-size:11.5px;text-transform:uppercase;letter-spacing:.05em}
.edge-v{display:flex;flex-wrap:wrap;gap:6px}
.chip{border:1px solid var(--line);border-radius:6px;padding:2px 8px;font-size:12px;background:var(--bg);color:var(--ink)}
a.chip:hover{border-color:var(--accent);text-decoration:none}
.chip.ghost{color:var(--task);border-style:dashed}
.tag{border-radius:5px;background:var(--code);padding:2px 7px;font-size:11.5px;color:var(--muted)}
em.none{color:var(--muted);font-style:italic;font-size:12px}
.chiplist{display:flex;flex-wrap:wrap;gap:7px}
p.ok{color:var(--mod)}
.stats{display:flex;flex-wrap:wrap;gap:22px;margin:22px 0 6px;padding:15px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.stats div{display:flex;flex-direction:column}
.stats b{font-size:23px;font-weight:650;letter-spacing:-.02em}
.stats span{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
footer{margin-top:60px;padding-top:14px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
#burger{display:none;position:fixed;top:10px;left:10px;z-index:11;font:inherit;font-size:13px;padding:6px 11px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--ink);cursor:pointer}
#backdrop{display:none}
main{overflow-wrap:anywhere}
@media (max-width:860px){
.layout{grid-template-columns:1fr}
#backdrop{display:block;position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:9;opacity:0;pointer-events:none;transition:opacity .18s}
aside{position:fixed;left:0;top:0;bottom:0;width:min(84vw,330px);z-index:10;transform:translateX(-100%);transition:transform .2s}
body.open aside{transform:none}
body.open #backdrop{opacity:1;pointer-events:auto}
main{padding-top:64px}
#burger{display:inline-flex}
}
@media print{aside,#burger{display:none}.layout{grid-template-columns:1fr}article[hidden]{display:none}}
`;

const js = `
(function () {
  var articles = Array.prototype.slice.call(document.querySelectorAll('article.spec'));
  var byId = {};
  articles.forEach(function (a) { byId[a.getAttribute('data-id')] = a; });
  var navs = {};
  Array.prototype.slice.call(document.querySelectorAll('[data-nav]')).forEach(function (a) {
    navs[a.getAttribute('data-nav')] = a;
  });

  function currentId() {
    var h = decodeURIComponent(location.hash.replace(/^#\\/?/, ''));
    return byId[h] ? h : null;
  }

  function show(id) {
    articles.forEach(function (a) { a.hidden = a.getAttribute('data-id') !== id; });
    Object.keys(navs).forEach(function (k) {
      if (k === id) navs[k].setAttribute('aria-current', 'page');
      else navs[k].removeAttribute('aria-current');
    });
    var ov = document.getElementById('overview');
    ov.hidden = id !== null;
    document.title = (id ? byId[id].querySelector('h1').textContent + ' \\u2014 ' : '') + 'Local Data Stack spec graph';
    document.body.classList.remove('open');
    window.scrollTo(0, 0);
  }

  addEventListener('hashchange', function () { show(currentId()); });
  show(currentId());

  var q = document.getElementById('q');
  if (q) {
    q.addEventListener('input', function () {
      var term = q.value.trim().toLowerCase();
      Object.keys(navs).forEach(function (id) {
        var link = navs[id];
        var hit = !term || link.getAttribute('data-search').indexOf(term) !== -1;
        link.parentNode.classList.toggle('hide', !hit);
        if (hit) {
          var p = link.parentNode.parentNode.closest ? link.parentNode.parentNode.closest('li') : null;
          while (p) { p.classList.remove('hide'); p = p.parentNode.closest ? p.parentNode.closest('li') : null; }
        }
      });
    });
  }

  Array.prototype.slice.call(document.querySelectorAll('[data-fold]')).forEach(function (btn) {
    btn.addEventListener('click', function () { btn.closest('.codeblock').classList.toggle('folded'); });
  });
  Array.prototype.slice.call(document.querySelectorAll('figure.collapsible')).forEach(function (f) {
    f.classList.add('folded');
  });

  var root = document.documentElement;
  var stored = null;
  try { stored = localStorage.getItem('spec-theme'); } catch (e) {}
  if (stored === 'light' || stored === 'dark') root.setAttribute('data-theme', stored);
  var tbtn = document.getElementById('theme');
  if (tbtn) {
    tbtn.addEventListener('click', function () {
      var now = getComputedStyle(root).getPropertyValue('--bg').trim() === '#fbfbfa' ? 'light' : 'dark';
      var next = now === 'light' ? 'dark' : 'light';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('spec-theme', next); } catch (e) {}
    });
  }
  var burger = document.getElementById('burger');
  if (burger) burger.addEventListener('click', function () { document.body.classList.toggle('open'); });
})();
`;

const page = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="generator" content="docs/specs/build.mjs">
<title>Local Data Stack — spec graph</title>
<style>${css}</style>
<noscript><style>article[hidden]{display:block}figure.collapsible.folded pre{max-height:none;-webkit-mask-image:none;mask-image:none}</style></noscript>
</head>
<body>
<button id="burger" type="button">specs</button>
<div id="backdrop"></div>
<div class="layout">
<aside>
<div class="brand"><a href="#/">Local Data Stack</a></div>
<p class="sub">${specs.length} specs · goal → architecture → modules</p>
<input id="q" type="search" placeholder="Filter specs…" aria-label="Filter specs">
<nav>${navTree}</nav>
<div class="tools"><button id="theme" type="button">theme</button><span>hash-linked nodes</span></div>
</aside>
<main>
<article id="overview" data-id="__overview__">${overview}</article>
${articles}
<footer>${footer}</footer>
</main>
</div>
<script>${js}</script>
</body>
</html>
`;

/* trailing whitespace is stripped so pre-commit's fixer never rewrites the
 * committed artifact differently from what a rebuild produces. */
writeFileSync(OUT, page.replace(/[ \t]+$/gm, ''));
console.log(`wrote ${path.relative(ROOT, OUT)} — ${specs.length} specs, ${(page.length / 1024).toFixed(0)} KiB`);
if (dangling.length) console.log(`WARNING ${dangling.length} dangling link(s)`);
