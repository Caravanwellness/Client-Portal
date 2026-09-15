import { ghReadJson, ghWriteJson } from './_lib/github.js';

const REPO   = 'Caravanwellness/Dashboard';
const PATH   = 'data/client_licenses.json';
const BRANCH = 'main';

const delay = ms => new Promise(r => setTimeout(r, ms));

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const token = process.env.GITHUB_TOKEN;

  if (req.method === 'GET') {
    res.setHeader('Cache-Control', 'no-store');
    try {
      const { data, sha } = await ghReadJson(REPO, PATH, token);
      return res.json({ _data: data || {}, _sha: sha });
    } catch(e) {
      return res.json({ _data: {}, _sha: null });
    }
  }

  // POST: { add?: {[itemId]: [client,...]}, remove?: {[itemId]: [client,...]},
  //         rename?: {from, to}, message? }
  // Every op is applied as a delta against a freshly-read copy of the file, inside
  // the retry loop — never as a client-computed full replacement. That's what
  // makes this safe under concurrent writes: two people tagging different clients
  // on the same item in the same moment both land, instead of the second write
  // silently overwriting the first with a stale snapshot.
  if (req.method === 'POST') {
    const { add, remove, rename, message } = req.body || {};
    if (!add && !remove && !rename)
      return res.status(400).json({ error: 'add, remove, or rename required' });

    for (let attempt = 0; attempt < 5; attempt++) {
      if (attempt > 0) await delay(600 + Math.random() * 400);
      try {
        const { data, sha } = await ghReadJson(REPO, PATH, token);
        const licenses = data || {};

        if (rename && rename.from && rename.to) {
          for (const id of Object.keys(licenses)) {
            const cur = licenses[id];
            if (Array.isArray(cur) && cur.includes(rename.from)) {
              licenses[id] = [...new Set(cur.map(c => c === rename.from ? rename.to : c))];
            }
          }
        }

        for (const [id, clients] of Object.entries(add || {})) {
          licenses[id] = [...new Set([...(licenses[id] || []), ...clients])];
        }

        for (const [id, clients] of Object.entries(remove || {})) {
          const remaining = (licenses[id] || []).filter(c => !clients.includes(c));
          if (remaining.length) licenses[id] = remaining;
          else delete licenses[id];
        }

        const count = new Set([...Object.keys(add || {}), ...Object.keys(remove || {})]).size;
        const result = await ghWriteJson(REPO, PATH, BRANCH, licenses,
          message || `Update licenses: ${count} items`, token, sha);
        if (result) return res.json({ ok: true, count, _sha: typeof result === 'string' ? result : null });
        // SHA conflict — retry
      } catch(e) {
        return res.status(500).json({ error: e.message });
      }
    }
    return res.status(500).json({ error: 'Too many concurrent writes — try again' });
  }

  res.status(405).json({ error: 'Method not allowed' });
}
