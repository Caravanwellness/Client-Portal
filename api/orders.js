import { getUser } from './_lib/token.js';
import { ghReadJson, ghWriteJson } from './_lib/github.js';

// client_licenses.json (written by save-licenses.js) only holds current
// state — which clients are licensed to which videos right now. It was
// never meant to answer "who bought what, and when" — this file is that
// purchase history, one entry per checkout.
const REPO   = 'Caravanwellness/Dashboard';
const PATH   = 'client_portal_orders.json';
const BRANCH = 'main';
const USERS_PATH = 'client_portal_users.json';

const YEAR_MS = 365 * 24 * 60 * 60 * 1000;

function isAdminEmail(email) {
  return String(email || '').toLowerCase().trim().endsWith('@caravanwellness.com');
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const token = process.env.GITHUB_TOKEN;
  const caller = getUser(req);
  if (!caller) return res.status(401).json({ error: 'Not signed in.' });
  const admin = isAdminEmail(caller.email);

  // Non-admins can only ever see/act on their own assigned client — resolved
  // fresh from users.json, never trusted from the request, so one client
  // can't view or write another's records by passing a different name.
  let callerClient = null;
  if (!admin) {
    const { data: users } = await ghReadJson(REPO, USERS_PATH, token);
    const rec = users[caller.email];
    if (!rec || rec.removed) return res.status(401).json({ error: 'This account no longer has access.' });
    if (!rec.client) return res.status(403).json({ error: 'No client assigned to this account yet.' });
    callerClient = rec.client;
  }

  try {
    if (req.method === 'GET') {
      const { data } = await ghReadJson(REPO, PATH, token);
      const orders = Array.isArray(data) ? data : [];
      const wantClient = admin ? (req.query?.client || null) : callerClient;
      const filtered = wantClient ? orders.filter(o => o.client === wantClient) : orders;
      // newest first
      filtered.sort((a, b) => new Date(b.purchasedAt) - new Date(a.purchasedAt));
      return res.json({ orders: filtered });
    }

    if (req.method === 'POST') {
      const { client, items } = req.body || {};
      if (!client || !Array.isArray(items) || !items.length)
        return res.status(400).json({ error: 'client and items[] are required.' });
      if (!admin && client !== callerClient)
        return res.status(403).json({ error: 'Cannot record a purchase for a different client.' });

      const total = items.reduce((sum, it) => sum + (Number(it.price) || 0), 0);
      const now = new Date();
      const order = {
        id: `ord_${now.getTime()}_${Math.random().toString(36).slice(2, 8)}`,
        client,
        buyerEmail: caller.email,
        buyerName: caller.name,
        items, // [{id, title, price}]
        total,
        purchasedAt: now.toISOString(),
        // Placeholder only — this app doesn't track real contract/license
        // terms yet. Shown in the UI clearly labeled as an estimate.
        estimatedExpiresAt: new Date(now.getTime() + YEAR_MS).toISOString(),
      };

      for (let attempt = 0; attempt < 5; attempt++) {
        if (attempt > 0) await new Promise(r => setTimeout(r, 600 + Math.random() * 400));
        const { data, sha } = await ghReadJson(REPO, PATH, token);
        const orders = Array.isArray(data) ? data : [];
        orders.push(order);
        const result = await ghWriteJson(REPO, PATH, BRANCH, orders,
          `Order: ${items.length} video(s) to ${client}`, token, sha);
        if (result) return res.json({ ok: true, order });
      }
      return res.status(500).json({ error: 'Too many concurrent writes — try again' });
    }

    res.status(405).json({ error: 'Method not allowed' });
  } catch(e) {
    return res.status(500).json({ error: e.message });
  }
}
