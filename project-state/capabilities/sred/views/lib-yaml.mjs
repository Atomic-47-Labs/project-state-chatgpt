// ---------------------------------------------------------------------------
// Minimal YAML reader — scoped to the shapes the project-state substrate writes.
// Zero dependencies by design: the generator must run anywhere `node` runs,
// with no install step, on a machine that may hold SR&ED records.
//
// Supported: block maps, block sequences (indented or indentless, scalars,
// inline-first-key maps and nested `- -` items), block scalars (| |- |+ > >-),
// plain and quoted scalars wrapped over several lines, flow sequences/maps,
// `~`/`null`, booleans, numbers, `#` comments (line and trailing), a leading `---`.
// Not supported (and not used by the substrate): anchors, aliases, tags,
// multi-document streams, complex keys. These THROW, as does any line the reader
// cannot place: a truncated record reads as a complete one, so it must never be
// returned quietly (FB-036).
// ---------------------------------------------------------------------------

function stripComment(s) {
  let q = null;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (q) {
      if (c === q) q = null;
      continue;
    }
    if (c === '"' || c === "'") { q = c; continue; }
    if (c === '#' && (i === 0 || /\s/.test(s[i - 1]))) return s.slice(0, i);
  }
  return s;
}

function splitFlow(body) {
  const out = [];
  let depth = 0, q = null, cur = '';
  for (const c of body) {
    if (q) {
      cur += c;
      if (c === q) q = null;
      continue;
    }
    // a quote opens a quoted scalar only where a scalar starts — not `person's`
    if ((c === '"' || c === "'") && /(^|[:[{])\s*$/.test(cur)) { q = c; cur += c; continue; }
    if (c === '[' || c === '{') { depth++; cur += c; continue; }
    if (c === ']' || c === '}') { depth--; cur += c; continue; }
    if (c === ',' && depth === 0) { out.push(cur); cur = ''; continue; }
    cur += c;
  }
  if (cur.trim() !== '') out.push(cur);
  return out.map((x) => x.trim());
}

// Has a flow collection that opens at s[0] closed again? (quotes respected)
function closed(s) {
  let depth = 0, q = null;
  for (const c of s) {
    if (q) { if (c === q) q = null; continue; }
    if (c === '"' || c === "'") q = c;
    else if (c === '[' || c === '{') depth++;
    else if (c === ']' || c === '}') { if (--depth === 0) return true; }
  }
  return false;
}

function unquote(s) {
  if (s.length >= 2 && s[0] === '"' && s[s.length - 1] === '"') {
    const esc = { n: '\n', t: '\t', r: '\r', 0: '\0', ' ': ' ', '/': '/', '"': '"', '\\': '\\' };
    return s.slice(1, -1).replace(/\\(u[0-9a-fA-F]{4}|[\s\S])/g, (all, e) =>
      e.length === 5 ? String.fromCharCode(parseInt(e.slice(1), 16)) : e in esc ? esc[e] : all);
  }
  if (s.length >= 2 && s[0] === "'" && s[s.length - 1] === "'") {
    return s.slice(1, -1).replace(/''/g, "'");
  }
  return s;
}

function parseScalar(raw) {
  const s = raw.trim();
  if (s === '' || s === '~' || s === 'null' || s === 'Null' || s === 'NULL') return null;
  if (s === 'true' || s === 'True' || s === 'yes') return true;
  if (s === 'false' || s === 'False' || s === 'no') return false;
  if (s[0] === '[' && s[s.length - 1] === ']') {
    return splitFlow(s.slice(1, -1)).map(parseScalar);
  }
  if (s[0] === '{' && s[s.length - 1] === '}') {
    const obj = {};
    for (const part of splitFlow(s.slice(1, -1))) {
      const m = part.match(/^([^:]+):\s*([\s\S]*)$/);
      if (m) obj[unquote(m[1].trim())] = parseScalar(m[2]);
    }
    return obj;
  }
  if ((s[0] === '"' && s[s.length - 1] === '"') || (s[0] === "'" && s[s.length - 1] === "'")) {
    return unquote(s);
  }
  if (/^-?\d+$/.test(s)) return parseInt(s, 10);
  if (/^-?\d*\.\d+$/.test(s)) return parseFloat(s);
  return s;
}

export function parseYaml(text) {
  const L = String(text).replace(/^\uFEFF/, '').split(/\r?\n/);
  let i = 0;

  const skippable = (idx) => idx < L.length && (/^\s*$/.test(L[idx]) || /^\s*#/.test(L[idx]));
  const indentOf = (idx) => L[idx].match(/^(\s*)/)[1].length;
  const skip = () => { while (i < L.length && skippable(i)) i++; };
  const isItem = (body) => /^-(\s|$)/.test(body);
  const fail = (idx, msg) => {
    throw new Error(`YAML line ${idx + 1}: ${msg}` + (idx < L.length ? ` — ${JSON.stringify(L[idx].trim().slice(0, 60))}` : ''));
  };

  function blockScalar(header, parentIndent) {
    const chomp = /-/.test(header) ? 'strip' : /\+/.test(header) ? 'keep' : 'clip';
    const fold = header[0] === '>';
    const buf = [];
    let base = null;
    while (i < L.length) {
      if (/^\s*$/.test(L[i])) { buf.push(''); i++; continue; }
      const ind = indentOf(i);
      if (ind <= parentIndent) break;
      if (base === null) base = ind;
      buf.push(L[i].slice(Math.min(base, ind)));
      i++;
    }
    while (buf.length && buf[buf.length - 1] === '') buf.pop();
    let out;
    if (fold) {
      // Folding: a break between two ordinary lines is a space; blank lines are
      // newlines; breaks around a more-indented line are kept as written.
      out = '';
      let prev = null, blanks = 0;
      for (const line of buf) {
        if (line === '') { blanks++; continue; }
        const more = /^\s/.test(line);
        if (prev === null) out += '\n'.repeat(blanks);
        else if (prev === 'plain' && !more) out += blanks ? '\n'.repeat(blanks) : ' ';
        else out += '\n'.repeat(blanks + 1);
        out += more ? line : line.trim();
        prev = more ? 'more' : 'plain';
        blanks = 0;
      }
    } else {
      out = buf.join('\n');
    }
    if (chomp === 'strip') out = out.replace(/\n+$/, '');
    else if (chomp === 'clip') out = out.replace(/\n+$/, '') + '\n';
    return out;
  }

  // An inline value, plus any lines indented deeper than its owner: a plain or
  // quoted scalar (or a flow collection) the writer wrapped. Lines fold with a
  // space; a blank line between them is a newline. Leaves i on the next line.
  function inlineValue(first, ownerIndent) {
    const at = i;
    const parts = [first.trim()];
    const q = /^["']/.test(parts[0]) ? parts[0][0] : null;
    // still inside the opening quote? (`''` and `\x` are escapes, not closers)
    const open = () => {
      const t = parts.join(' ').slice(1);
      return q === "'" ? !t.replace(/''/g, '').includes("'") : !/(^|[^\\])(\\\\)*"/.test(t);
    };
    i++;
    for (let j = i; j < L.length; j++) {
      if (/^\s*$/.test(L[j])) continue;
      if (indentOf(j) <= ownerIndent) break;
      if (/^\s*#/.test(L[j]) && !(q && open())) break;
      if (q && !open()) fail(j, 'indented under a quoted value that has already closed');
      if (/^[[{]/.test(parts[0]) && closed(parts.join(' '))) fail(j, 'indented under a flow collection that has already closed');
      const line = L[j].trim();
      if (!/^["'[{]/.test(parts[0]) && /^(?:[^\s"'#:][^:]*?)\s*:(\s|$)/.test(line)) {
        fail(j, 'looks like a key, but is indented under a scalar value');
      }
      for (let k = i; k < j; k++) parts.push('');
      parts.push(line);
      i = j + 1;
    }
    // In a double-quoted scalar a line ending in an odd number of `\` is an
    // escaped line break: the next line joins with no space.
    const dq = parts[0][0] === '"';
    const joined = parts.reduce((acc, p) => {
      if (p === '') return acc + '\n';
      if (acc === '' || acc.endsWith('\n')) return acc + p;
      if (dq && /(^|[^\\])(\\\\)*\\$/.test(acc)) return acc.slice(0, -1) + p;
      return acc + ' ' + p;
    }, '');
    const v = stripComment(joined).trim();
    if (/^[&*!][^\s]/.test(v)) fail(at, 'anchors, aliases and tags are not supported');
    return parseScalar(v);
  }

  function parseNode(minIndent) {
    skip();
    if (i >= L.length) return null;
    const ind = indentOf(i);
    if (ind < minIndent) return null;
    const body = L[i].slice(ind);
    if (isItem(body)) return parseSeq(ind);
    // a scalar on the line below its key: quoted, flow, or plain with no `key:`
    const quotedKey = /^("[^"]*"|'[^']*')\s*:(\s|$)/.test(body);
    if (!quotedKey && (/^["'[{]/.test(body) || !/^[^#]*?:(\s|$)/.test(stripComment(body)))) return inlineValue(body, ind - 1);
    return parseMap(ind);
  }

  function parseMap(myIndent) {
    const obj = {};
    for (;;) {
      skip();
      if (i >= L.length) break;
      const ind = indentOf(i);
      if (ind < myIndent) break;
      if (ind > myIndent) fail(i, `indented ${ind} where ${myIndent} was expected`);
      const body = L[i].slice(ind);
      // A sequence at a map's own indent is only legal straight after `key:`,
      // where it is consumed below; anywhere else it ends this map for the caller.
      if (isItem(body)) break;
      if (/^(---|\.\.\.)(\s|$)/.test(body)) fail(i, 'multi-document streams are not supported');
      if (/^\?(\s|$)/.test(body)) fail(i, 'complex keys are not supported');
      const m = body.match(/^((?:"[^"]*"|'[^']*'|[^:])+?)\s*:(?:\s+([\s\S]*))?$/);
      if (!m) fail(i, 'expected "key: value"');
      const key = unquote(m[1].trim());
      const raw = m[2] || '';
      const bs = raw.match(/^([|>][-+]?\d*)\s*(#.*)?$/);
      if (bs) {
        i++;
        obj[key] = blockScalar(bs[1], ind);
        continue;
      }
      if (stripComment(raw).trim() === '') {
        i++;
        skip();
        // `key:` then `- item` at the key's own indent — an indentless sequence,
        // which PyYAML's safe_dump writes by default.
        if (i < L.length && indentOf(i) === ind && isItem(L[i].slice(ind))) obj[key] = parseSeq(ind);
        else obj[key] = parseNode(ind + 1);
        continue;
      }
      obj[key] = inlineValue(raw, ind);
    }
    return obj;
  }

  function parseSeq(myIndent) {
    const arr = [];
    for (;;) {
      skip();
      if (i >= L.length) break;
      const ind = indentOf(i);
      if (ind < myIndent) break;
      if (ind > myIndent) fail(i, `indented ${ind} where ${myIndent} was expected`);
      const body = L[i].slice(ind);
      if (!isItem(body)) break;
      const rest = body.slice(1).replace(/^\s+/, '');
      const restCol = ind + (body.length - rest.length);
      if (stripComment(rest).trim() === '') {
        i++;
        arr.push(parseNode(myIndent + 1));
        continue;
      }
      const bs = rest.match(/^([|>][-+]?\d*)\s*(#.*)?$/);
      if (bs) {
        i++;
        arr.push(blockScalar(bs[1], myIndent));
        continue;
      }
      if (isItem(rest)) {
        L[i] = ' '.repeat(restCol) + rest;   // rewrite "- - x" as "  - x"
        arr.push(parseSeq(restCol));
        continue;
      }
      const looksLikeMap = !/^[[{"']/.test(rest) &&
        /^((?:[^:])+?)\s*:(\s|$)/.test(stripComment(rest));
      if (looksLikeMap) {
        L[i] = ' '.repeat(restCol) + rest;   // rewrite "- k: v" as "  k: v"
        arr.push(parseMap(restCol));
        continue;
      }
      arr.push(inlineValue(rest, myIndent));
    }
    return arr;
  }

  skip();
  if (i < L.length && /^---\s*$/.test(L[i])) i++;
  const doc = parseNode(0);
  skip();
  if (i < L.length) fail(i, 'unexpected content after the document');
  return doc === null ? {} : doc;
}
