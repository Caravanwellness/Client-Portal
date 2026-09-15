import { ghReadJson, ghWriteJson } from './_lib/github.js';
import { getUser } from './_lib/token.js'; // optional — used for commit attribution only

const REPO   = 'Caravanwellness/Dashboard';
const PATH   = 'extra_content.json';
const BRANCH = 'main';

const delay = ms => new Promise(r => setTimeout(r, ms));

function readArray(data) {
  if (Array.isArray(data)) return data;
  return [];
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const token = process.env.GITHUB_TOKEN;

  if (req.method === 'GET') {
    try {
      const { data } = await ghReadJson(REPO, PATH, token);
      return res.json(readArray(data));
    } catch(e) {
      return res.json([]);
    }
  }

  if (req.method === 'POST') {
    const user = getUser(req);
    const userName = user?.name || 'Dashboard';

    const { items: newItems } = req.body || {};
    if (!Array.isArray(newItems) || !newItems.length)
      return res.status(400).json({ error: 'items array required' });

    for (let attempt = 0; attempt < 5; attempt++) {
      if (attempt > 0) await delay(600 + Math.random() * 400);
      try {
        const { data, sha } = await ghReadJson(REPO, PATH, token);
        const existing = readArray(data);

        // Build lookup by title for duplicate detection
        const byTitle = {};
        existing.forEach(i => { byTitle[(i.title||'').toLowerCase().trim()] = i; });

        // Find next ID number
        let nextId = existing.reduce((max, i) => {
          const n = parseInt((i.id || '').replace('EXT-', ''));
          return isNaN(n) ? max : Math.max(max, n);
        }, 0) + 1;

        // Read fresh each attempt (this whole block is inside the retry loop),
        // so a concurrent import's IDs are already accounted for.
        const usedIds = new Set(existing.map(i => i.id).filter(Boolean));

        let added = 0, merged = 0;
        for (const item of newItems) {
          const key = (item.title||'').toLowerCase().trim();
          const dup = byTitle[key];
          if (dup) {
            // Merge client licenses into existing item
            if (item.client_licenses?.length) {
              dup.client_licenses = [...new Set([...(dup.client_licenses||[]), ...item.client_licenses])];
            }
            merged++;
          } else {
            // Prefer the imported row's own ID when it has one and it isn't
            // already taken here — falls back to an auto EXT- id otherwise,
            // same as for rows that never had an ID to begin with.
            const { id: rowId, ...rest } = item;
            const id = rowId && !usedIds.has(rowId) ? rowId : `EXT-${String(nextId++).padStart(4, '0')}`;
            usedIds.add(id);
            const entry = { ...rest, id, _addedAt: new Date().toISOString(), _addedBy: userName };
            existing.push(entry);
            byTitle[key] = entry;
            added++;
          }
        }

        const result = await ghWriteJson(REPO, PATH, BRANCH, existing,
          `Add content: ${added} new, ${merged} merged — by ${userName}`, token, sha);
        if (result) return res.json({ ok: true, added, merged, total: existing.length });
        // SHA conflict — retry
      } catch(e) {
        return res.status(500).json({ error: e.message });
      }
    }
    return res.status(500).json({ error: 'Too many concurrent writes — try again' });
  }

  res.status(405).json({ error: 'Method not allowed' });
}
