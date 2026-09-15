const REPO      = 'Caravanwellness/Dashboard';
const FILE_PATH = 'client_data.json';
const BRANCH    = 'main';
const API_BASE  = `https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`;

function ghHeaders() {
  return {
    Authorization: `token ${process.env.GITHUB_TOKEN}`,
    Accept: 'application/vnd.github.v3+json',
    'Content-Type': 'application/json',
  };
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') return res.status(200).end();

  if (req.method === 'GET') {
    const r = await fetch(API_BASE, { headers: ghHeaders() });
    if (!r.ok) return res.status(500).json({ error: 'Could not fetch client data' });
    const data = await r.json();
    return res.json(JSON.parse(Buffer.from(data.content, 'base64').toString('utf-8')));
  }

  // POST: { action: 'set', clients, meta }  — replace full object
  if (req.method === 'POST') {
    const { clients, meta } = req.body || {};

    for (let attempt = 0; attempt < 3; attempt++) {
      const r = await fetch(API_BASE, { headers: ghHeaders() });
      if (!r.ok) return res.status(500).json({ error: 'Could not read client data' });
      const fileData = await r.json();
      const sha = fileData.sha;

      const updated = { clients: clients || [], meta: meta || {} };
      const content = Buffer.from(JSON.stringify(updated, null, 2)).toString('base64');
      const commitRes = await fetch(API_BASE, {
        method: 'PUT', headers: ghHeaders(),
        body: JSON.stringify({ message: 'Update client data', content, sha, branch: BRANCH }),
      });

      if (commitRes.ok) return res.json({ ok: true });
      if (commitRes.status === 409 && attempt < 2) continue;
      return res.status(500).json({ error: 'Commit failed' });
    }
  }

  res.status(405).json({ error: 'Method not allowed' });
}
