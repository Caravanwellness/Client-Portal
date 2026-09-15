import { ghReadJson, ghWriteJson } from './_lib/github.js';

const REPO   = 'Caravanwellness/Dashboard';
const PATH   = 'content_edits.json';
const BRANCH = 'main';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const token = process.env.GITHUB_TOKEN;

  // GET — return all edits + SHA for client-side caching
  if (req.method === 'GET') {
    res.setHeader('Cache-Control', 'no-store');
    try {
      const { data, sha } = await ghReadJson(REPO, PATH, token);
      return res.json({ _data: data, _sha: sha });
    } catch(e) {
      return res.status(500).json({ error: e.message });
    }
  }

  // POST — single: { id, field, value }  OR  bulk: { bulk: [{id, field, value},...], message }
  if (req.method === 'POST') {
    const { id, field, value, bulk, message } = req.body || {};
    const changes = bulk && Array.isArray(bulk) ? bulk : (id && field !== undefined ? [{ id, field, value }] : null);
    if (!changes) return res.status(400).json({ error: 'id+field or bulk array required' });

    const ts = new Date().toISOString();
    const commitMsg = message || (changes.length === 1
      ? `Edit ${changes[0].id}: ${changes[0].field}`
      : `Bulk update ${changes.length} fields`);

    const delay = ms => new Promise(r => setTimeout(r, ms));

    // Always read fresh and merge just this change in — never trust a client-sent
    // full snapshot as the new file content. A browser's in-memory `edits` only
    // reflects what it loaded at page-load plus its own local changes; it never
    // resyncs with what other people save mid-session, so a "fast path" that
    // wrote that snapshot verbatim would silently revert everyone else's
    // concurrent edits whenever this client's cached SHA still happened to be
    // valid. (Confirmed happening in production — see git history.)
    for (let attempt = 0; attempt < 5; attempt++) {
      if (attempt > 0) await delay(600 + Math.random() * 400);
      try {
        const { data: edits, sha } = await ghReadJson(REPO, PATH, token);

        for (const { id: cId, field: cField, value: cVal } of changes) {
          if (!edits[cId]) edits[cId] = {};
          edits[cId][cField] = cVal;
          edits[cId]._at = ts;
        }

        const result = await ghWriteJson(REPO, PATH, BRANCH, edits, commitMsg, token, sha);
        if (result) return res.json({ ok: true, count: changes.length, _sha: typeof result === 'string' ? result : null });
        // false = SHA conflict, retry with fresh read
      } catch(e) {
        return res.status(500).json({ error: e.message });
      }
    }
    return res.status(500).json({ error: 'Too many concurrent writes — try again' });
  }

  res.status(405).json({ error: 'Method not allowed' });
}
