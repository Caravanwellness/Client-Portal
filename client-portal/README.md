# Caravan Wellness — Client Portal

Standalone version of the "Client Portal" tab, extracted from the main
`content-dashboard` app so it can live on its own domain/repo/Vercel project.

## What this is

A single-page video shop: browse/filter the catalog, add to cart, and
checkout writes a real license entry for the selected client. No admin
tools (export/import, field editing, review workflow, etc.) are included —
this is only the client-facing surface.

## How it shares data with the main dashboard

Nothing was duplicated as a live data source. All the API routes in `api/`
are unmodified copies of the ones in `content-dashboard/api/` and point at
the **same** GitHub repo (`Caravanwellness/Dashboard`) as the source of
truth:

- `api/save-edits.js` — reads `content_edits.json` (field overlays: title,
  description, thumbnail, etc.)
- `api/save-licenses.js` — reads/writes `data/client_licenses.json` (this is
  what checkout writes to)
- `api/save-content.js` — reads `extra_content.json` (content added after
  the base catalog was built)
- `api/save-clients.js` — reads `client_data.json` (client roster, for the
  "Viewing as" dropdown)

Because every API route already sends `Access-Control-Allow-Origin: *`, this
works from a completely different domain with zero backend changes.

**The one exception is `data.json`** (the base catalog, ~4MB) — it's loaded
as a static file (`/data.json`) exactly like the main dashboard does, not
fetched live from GitHub. That means it's a snapshot as of whenever it was
last copied here, and needs to be manually refreshed (copy the latest
`content-dashboard/data.json` over this one) and redeployed if the base
catalog changes. This matches the main dashboard's own behavior today — it
has the same staleness characteristic, just worth knowing going in.

## Deploy setup

1. `vercel env add GITHUB_TOKEN` — same GitHub personal access token used by
   `content-dashboard` (needs read/write on `Caravanwellness/Dashboard`).
2. No build step, no `package.json`/dependencies — same as the source
   project. Deploy as-is.

## Intentionally left out (per the current scope)

- **Real client login/authentication.** "Viewing as [client]" is a plain
  dropdown, not a session — same as it is in the main dashboard today.
  `api/save-licenses.js`'s POST endpoint has no auth check, so anyone who can
  reach this deployment can write a license. Don't treat this as
  production-ready for real external clients until that's addressed.
- Admin dashboard, all other tabs, export/import, field editing,
  authentication overlay, AI search, transcripts, changelog, bios — none of
  that code was copied.
