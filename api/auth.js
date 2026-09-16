import crypto from 'crypto';
import { getUser } from './_lib/token.js';
import { ghReadJson, ghWriteJson } from './_lib/github.js';

// Client Portal accounts are a separate namespace from the internal
// dashboard's users.json — different people, different rules (any email can
// sign up here, not just @caravanwellness.com), so they get their own files
// rather than sharing the staff account list.
const REPO         = 'Caravanwellness/Dashboard';
const PATH         = 'client_portal_users.json';
const PENDING_PATH = 'client_portal_pending_signups.json';
const BRANCH       = 'main';
const OTP_TTL_MS   = 10 * 60 * 1000; // 10 minutes

function isAdminEmail(email) {
  return String(email || '').toLowerCase().trim().endsWith('@caravanwellness.com');
}

async function sendOtpEmail(toEmail, name, otp) {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) throw new Error('RESEND_API_KEY is not configured.');
  const from = process.env.RESEND_FROM || 'noreply@caravanwellness.com';
  const r = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from,
      to: [toEmail],
      subject: 'Your Caravan Wellness Client Portal verification code',
      html: `<p>Hi ${name},</p>
<p>Your verification code for the Caravan Wellness Client Portal is:</p>
<p style="font-size:32px;font-weight:bold;letter-spacing:8px;color:#1a1a2e">${otp}</p>
<p>This code expires in 10 minutes. If you didn't request this, you can ignore this email.</p>`,
    }),
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.message || `Resend API error ${r.status}`);
  }
}

function hashPw(password, email) {
  return crypto.createHash('sha256').update(password + ':' + email).digest('hex');
}

function makeToken(email, name) {
  const secret  = process.env.SESSION_SECRET;
  const expiry  = Date.now() + 8 * 60 * 60 * 1000;
  const payload = Buffer.from(JSON.stringify({ email, name, expiry })).toString('base64');
  const sig     = crypto.createHmac('sha256', secret).update(payload).digest('hex');
  return `${payload}.${sig}`;
}

let _usersCache = null;
let _usersCacheAt = 0;
const CACHE_TTL = 60 * 1000; // shorter than the dashboard's — client/removed status needs to be fresh

async function readUsers(token, { skipCache = false } = {}) {
  if (!skipCache && _usersCache && Date.now() - _usersCacheAt < CACHE_TTL) {
    return _usersCache;
  }
  const result = await ghReadJson(REPO, PATH, token);
  _usersCache = result;
  _usersCacheAt = Date.now();
  return result;
}

async function writeUsers(users, sha, token) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const ok = await ghWriteJson(REPO, PATH, BRANCH, users, 'Update client portal users', token, sha);
    if (ok) {
      _usersCache = { data: users, sha: typeof ok === 'string' ? ok : sha };
      _usersCacheAt = Date.now();
      return;
    }
  }
  throw new Error('Could not write users after retries');
}

// Every account row: { name, passwordHash, client: string|null, removed: bool, createdAt }
// client === null means "signed up, verified, but no client assigned yet" — the
// frontend shows a pending-approval screen until an admin assigns one.
// @caravanwellness.com accounts don't need a client assignment; isAdminEmail()
// on their own address is what grants them the admin view, not a stored flag.

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') return res.status(200).end();

  if (!process.env.SESSION_SECRET)
    return res.status(500).json({ error: 'SERVER MISCONFIGURATION: SESSION_SECRET is not set.' });
  if (!process.env.GITHUB_TOKEN)
    return res.status(500).json({ error: 'SERVER MISCONFIGURATION: GITHUB_TOKEN is not set.' });

  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const ghToken = process.env.GITHUB_TOKEN;
  const { action, email, password, name, targetEmail, client } = req.body || {};

  try {
    // Re-validate a held token against the current user record — catches a
    // just-assigned client or a just-removed account without waiting for the
    // 8-hour token to expire. Called on every app load.
    if (action === 'session') {
      const caller = getUser(req);
      if (!caller) return res.status(401).json({ error: 'Not signed in.' });
      const admin = isAdminEmail(caller.email);
      if (admin) return res.json({ ok: true, email: caller.email, name: caller.name, client: null, isAdmin: true, removed: false });
      const { data: users } = await readUsers(ghToken);
      const rec = users[caller.email];
      if (!rec || rec.removed) return res.status(401).json({ error: 'This account no longer has access.' });
      return res.json({ ok: true, email: caller.email, name: rec.name, client: rec.client || null, isAdmin: false, removed: false });
    }

    // List all client accounts — admin only.
    if (action === 'list') {
      const caller = getUser(req);
      if (!caller || !isAdminEmail(caller.email)) return res.status(401).json({ error: 'Unauthorized' });
      const { data: users } = await readUsers(ghToken, { skipCache: true });
      return res.json({
        users: Object.entries(users).map(([e, u]) => ({
          email: e, name: u.name, client: u.client || null, removed: !!u.removed, createdAt: u.createdAt,
        })),
      });
    }

    // Assign (or change) which client an account represents — admin only.
    if (action === 'assignClient') {
      const caller = getUser(req);
      if (!caller || !isAdminEmail(caller.email)) return res.status(401).json({ error: 'Unauthorized' });
      if (!targetEmail) return res.status(400).json({ error: 'targetEmail required.' });
      const target = targetEmail.toLowerCase().trim();
      const { data: users, sha } = await readUsers(ghToken, { skipCache: true });
      if (!users[target]) return res.status(404).json({ error: 'No account found with that email.' });
      users[target].client = client || null;
      await writeUsers(users, sha, ghToken);
      return res.json({ ok: true });
    }

    // Revoke an account's access — admin only. Soft delete: the row stays
    // (so the email can't just be re-signed-up to dodge this) but `removed`
    // blocks login and every other endpoint's session check.
    if (action === 'remove') {
      const caller = getUser(req);
      if (!caller || !isAdminEmail(caller.email)) return res.status(401).json({ error: 'Unauthorized' });
      if (!targetEmail) return res.status(400).json({ error: 'targetEmail required.' });
      const target = targetEmail.toLowerCase().trim();
      const { data: users, sha } = await readUsers(ghToken, { skipCache: true });
      if (!users[target]) return res.status(404).json({ error: 'No account found with that email.' });
      users[target].removed = true;
      await writeUsers(users, sha, ghToken);
      return res.json({ ok: true });
    }

    // Restore a previously-removed account — admin only.
    if (action === 'restore') {
      const caller = getUser(req);
      if (!caller || !isAdminEmail(caller.email)) return res.status(401).json({ error: 'Unauthorized' });
      if (!targetEmail) return res.status(400).json({ error: 'targetEmail required.' });
      const target = targetEmail.toLowerCase().trim();
      const { data: users, sha } = await readUsers(ghToken, { skipCache: true });
      if (!users[target]) return res.status(404).json({ error: 'No account found with that email.' });
      users[target].removed = false;
      await writeUsers(users, sha, ghToken);
      return res.json({ ok: true });
    }

    if (!email) return res.status(400).json({ error: 'Email is required.' });
    if ((action === 'signup' || action === 'login') && !password)
      return res.status(400).json({ error: 'Email and password are required.' });
    const emailLow = email.toLowerCase().trim();

    // Sign up — any email address, no domain restriction. Send OTP, don't
    // create the account until it's verified.
    if (action === 'signup') {
      if (!name || name.trim().length < 2)
        return res.status(400).json({ error: 'Please enter your full name.' });
      if (password.length < 8)
        return res.status(400).json({ error: 'Password must be at least 8 characters.' });

      const { data: users } = await readUsers(ghToken);
      if (users[emailLow])
        return res.status(409).json({ error: 'An account with this email already exists. Please log in.' });

      const otp = String(Math.floor(100000 + Math.random() * 900000));
      const trimmedName = name.trim();
      let pending = {};
      try { const r = await ghReadJson(REPO, PENDING_PATH, ghToken); pending = r.data || {}; } catch(e) {}
      pending[emailLow] = {
        name: trimmedName,
        passwordHash: hashPw(password, emailLow),
        otp,
        expiresAt: new Date(Date.now() + OTP_TTL_MS).toISOString(),
      };
      try { await ghWriteJson(REPO, PENDING_PATH, BRANCH, pending, `Pending client portal signup: ${emailLow}`, ghToken, null); } catch(e) {}

      await sendOtpEmail(emailLow, trimmedName, otp);
      return res.json({ ok: true, pendingVerification: true, email: emailLow });
    }

    // Verify OTP and create the account. New non-admin accounts start with
    // client: null — pending an admin's assignment before they see the shop.
    if (action === 'verify') {
      const { code } = req.body || {};
      if (!emailLow || !code) return res.status(400).json({ error: 'Email and code are required.' });

      let pending = {};
      try { const r = await ghReadJson(REPO, PENDING_PATH, ghToken); pending = r.data || {}; } catch(e) {}
      const entry = pending[emailLow];
      if (!entry) return res.status(400).json({ error: 'No pending signup found. Please start over.' });
      if (new Date(entry.expiresAt) < new Date()) {
        delete pending[emailLow];
        try { await ghWriteJson(REPO, PENDING_PATH, BRANCH, pending, `Expire client portal signup: ${emailLow}`, ghToken, null); } catch(e) {}
        return res.status(400).json({ error: 'Verification code has expired. Please sign up again.' });
      }
      if (entry.otp !== String(code).trim())
        return res.status(400).json({ error: 'Incorrect code. Please try again.' });

      const { data: users, sha } = await readUsers(ghToken, { skipCache: true });
      users[emailLow] = {
        name: entry.name,
        passwordHash: entry.passwordHash,
        client: null,
        removed: false,
        createdAt: new Date().toISOString(),
      };
      await writeUsers(users, sha, ghToken);

      delete pending[emailLow];
      try { await ghWriteJson(REPO, PENDING_PATH, BRANCH, pending, `Complete client portal signup: ${emailLow}`, ghToken, null); } catch(e) {}

      return res.json({ ok: true, token: makeToken(emailLow, entry.name), name: entry.name, email: emailLow });
    }

    // Login
    if (action === 'login') {
      const { data: users } = await readUsers(ghToken, { skipCache: true });
      const user = users[emailLow];
      if (!user) return res.status(401).json({ error: 'No account found with this email.' });
      if (user.removed) return res.status(401).json({ error: 'This account no longer has access.' });
      if (user.passwordHash !== hashPw(password, emailLow))
        return res.status(401).json({ error: 'Incorrect password.' });
      return res.json({ ok: true, token: makeToken(emailLow, user.name), name: user.name, email: emailLow });
    }

    return res.status(400).json({ error: 'Unknown action.' });

  } catch(e) {
    return res.status(500).json({ error: e.message });
  }
}
