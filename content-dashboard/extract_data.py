#!/usr/bin/env python3
"""
Caravan Content Dashboard - PDF Data Extractor
Reads the 6 content review PDFs and writes a single self-contained index.html.
No server needed — just double-click to open.
"""

import pdfplumber
import json
import re
import os
from datetime import date

BASE = os.path.expanduser("~/caravan/caravan-tasks/")
OUT  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

PDFS = {
    "articles_review":    BASE + "General Content Reviews and Updates - Articles.pdf",
    "infographics_review":BASE + "General Content Reviews and Updates - Infographics.pdf",
    "videos_review":      BASE + "General Content Reviews and Updates - Videos.pdf",
    "video_library":      BASE + "General Content Reviews and Updates - Video Library.pdf",
    "infographic_library":BASE + "General Content Reviews and Updates - Infographic Library.pdf",
    "article_library":    BASE + "General Content Reviews and Updates - Article Library.pdf",
}

KNOWN_AUTHORS = [
    "Diane", "Marlee", "Hope Zimmerman", "Jade Gordon", "Emily Wilson",
    "Jessica", "Madeline McGuire", "Kim", "Nicole", "Dr. Ellie",
    "Marketing & Content Coordinator", "Health Studies Contributor",
    "Madeline", "MacHope"
]

KNOWN_CREDS = [
    "Registered Nurse", "Exercise Physiologist", "Registered Dietician",
    "Behavioral Technician", "Registered Medical Assistant",
    "Marketing & Content Coordinator", "Health Studies Contributor",
]

CATEGORY_KEYWORDS = [
    ("Alcohol Use",               ["alcohol", "drinking", "mocktail", "vaping"]),
    ("Anxiety & Depression",      ["depression", "anxiety", "loneliness", "isolation", "panic", "seasonal affective", "mindfulness"]),
    ("Arthritis",                 ["arthritis", "rheumatol", "joint pain", "osteoarthritis"]),
    ("Asthma",                    ["asthma", "allerg", "inhaler", "respiratory"]),
    ("Back Pain",                 ["back pain", "back injury", "sciatica", "spine", "ergonomic"]),
    ("Brain & Neurological",      ["concussion", "brain", "neurolog", "cognitive"]),
    ("Cancer",                    ["cancer", "tumor", "oncolog", "cervical", "prostate", "mammogram"]),
    ("COPD",                      ["copd", "emphysema", "bronchitis", "lung function", "pulmonar"]),
    ("Environmental Health",      ["carbon footprint", "air quality", "conscious consumer", "energy use", "environment"]),
    ("Financial Wellness",        ["nest egg", "retirement", "debt", "financial planning", "self-advocacy"]),
    ("General Heart Health",      ["heart health", "cardio", "cardiovascular", "endorphin", "microplastics"]),
    ("Health Screenings",         ["screening", "biometric", "gynecolog", "prenatal", "check-up", "checkup"]),
    ("Heart Disease",             ["cholesterol", "blood pressure", "hypertension", "stroke", "heart attack", "artery", "hormones"]),
    ("High Cholesterol",          ["statin", "hdl", "ldl", "lipid"]),
    ("Medications",               ["medication", "glp-1", "antidepressant", "prescription", "drug"]),
    ("Nutrition",                 ["nutrition", "diet", "fodmap", "vitamin", "hydrat", "food", "processed food", "immunity-boost"]),
    ("Older Adults",              ["aging", "elder", "senior", "hearing loss", "macular", "nursing home", "cane", "walker", "foot changes"]),
    ("Physical Health & Exercise",["exercise", "strength training", "hiit", "pilates", "running", "outdoor", "joint mobility", "low-impact"]),
    ("Surgery & Recovery",        ["surgery", "recovery", "fatigue", "post-surgery", "resilience"]),
    ("Vaccinations",              ["vaccine", "vaccination", "mmr", "hepatitis", "covid", "immunization", "booster"]),
    ("Vaping & Tobacco",          ["vaping", "tobacco", "smoking", "nicotine", "quit", "dopamine", "willpower"]),
    ("Sleep",                     ["sleep", "insomnia", "circadian"]),
    ("Diabetes",                  ["diabetes", "blood sugar", "insulin", "glucose"]),
    ("Weight Management",         ["weight", "obesity", "bmi", "overweight"]),
    ("Men's Health",              ["prostate", "men's health", "testosterone"]),
    ("Women's Health",            ["women", "pregnancy", "prenatal", "perimenopause", "postmenopause"]),
    ("Workplace Wellness",        ["workplace", "work-life", "benefits", "career", "professional"]),
]

DATE_RE = re.compile(r'\b(\d{2}/\d{2}/\d{4})\b')
PRIO_RE = re.compile(r'\b(Low|Moderate|High)\b')


def infer_category(text):
    t = text.lower()
    for cat, keywords in CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in t:
                return cat
    return "General"


def clean(s):
    if not s:
        return ""
    return re.sub(r'\s+', ' ', s).strip()


def find_author(cells):
    all_text = " ".join(c for c in cells if c)
    for name in KNOWN_AUTHORS:
        if name in all_text:
            return name
    return ""


def find_creds(cells):
    all_text = " ".join(c for c in cells if c)
    for cred in KNOWN_CREDS:
        if cred in all_text:
            return cred
    return ""


def find_priority(cells):
    for c in reversed(cells):
        if not c:
            continue
        m = PRIO_RE.search(c)
        if m:
            return m.group(1)
    all_text = " ".join(c for c in cells if c)
    m = PRIO_RE.search(all_text)
    return m.group(1) if m else ""


def find_dates(cells):
    all_text = " ".join(c for c in cells if c)
    return DATE_RE.findall(all_text)


def find_version(cells):
    all_text = " ".join(c for c in cells if c)
    m = re.search(r'\|\s*([1-9])\s*\|', all_text)
    return m.group(1) if m else ""


def extract_review_tracker(path, content_type, id_prefix):
    items = []
    id_counter = 1
    seen_titles = set()
    skip_headers = {"title", "video titles", "video name", ""}

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or not row[0]:
                        continue
                    title = clean(row[0])
                    if title.lower() in skip_headers or len(title) < 5:
                        continue
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)

                    cells = [clean(c) for c in row]
                    dates  = find_dates(cells)
                    prio   = find_priority(cells)
                    author = find_author(cells)
                    creds  = find_creds(cells)
                    ver    = find_version(cells)
                    cat    = infer_category(title)

                    link = ""
                    for c in cells:
                        if "http" in c or "docs.go" in c:
                            link = c
                            break

                    items.append({
                        "id":               f"{id_prefix}-{id_counter:04d}",
                        "type":             content_type,
                        "title":            title.rstrip("*"),
                        "category":         cat,
                        "link":             link,
                        "author":           author,
                        "author_creds":     creds,
                        "date_created":     dates[0] if dates else "",
                        "peer_reviewer":    "",
                        "review_priority":  prio,
                        "version":          ver or "1",
                        "date_revised":     dates[1] if len(dates) > 1 else "",
                        "nature_of_updates":"",
                        "client_licenses":  [],
                        "notes":            "",
                    })
                    id_counter += 1

    return items


def extract_video_library(path):
    items = []
    id_counter = 1
    seen = set()

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row:
                        continue
                    raw_name = clean(row[4]) if len(row) > 4 else ""
                    if not raw_name or raw_name.lower() in {"video name", "(english)", ""}:
                        continue
                    if raw_name in seen:
                        continue
                    seen.add(raw_name)

                    lang    = clean(row[0])  if len(row) > 0  else ""
                    cat     = clean(row[2])  if len(row) > 2  else ""
                    prog    = clean(row[3])  if len(row) > 3  else ""
                    length  = clean(row[5])  if len(row) > 5  else ""
                    teacher = clean(row[6])  if len(row) > 6  else ""
                    url     = clean(row[10]) if len(row) > 10 else ""
                    desc    = clean(row[11]) if len(row) > 11 else ""

                    vimeo = ""
                    for c in reversed(row):
                        if c and "vimeo" in clean(c).lower():
                            vimeo = clean(c)
                            break

                    if not cat:
                        cat = infer_category(raw_name)

                    items.append({
                        "id":            f"VLB-{id_counter:04d}",
                        "type":          "Video Library",
                        "title":         raw_name,
                        "program":       prog,
                        "category":      cat,
                        "language":      lang,
                        "length_min":    length,
                        "teacher":       teacher,
                        "url":           url,
                        "vimeo_link":    vimeo,
                        "description":   desc[:300] if desc else "",
                        "client_licenses": [],
                        "notes":         "",
                    })
                    id_counter += 1

    return items


def extract_article_library(path):
    items = []
    id_counter = 1
    seen = set()
    skip = {"title", "article title", "language", ""}

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 2:
                        continue
                    title = clean(row[1])
                    if not title or title.lower() in skip or len(title) < 5:
                        continue
                    if title in seen:
                        continue
                    seen.add(title)

                    lang     = clean(row[0]) if row[0] else "English"
                    reviewer = clean(row[3]) if len(row) > 3 and row[3] else ""
                    cat      = infer_category(title)

                    items.append({
                        "id":            f"ALB-{id_counter:04d}",
                        "type":          "Article Library",
                        "title":         title.rstrip("*"),
                        "category":      cat,
                        "language":      lang,
                        "peer_reviewer": reviewer,
                        "link":          "",
                        "client_licenses": [],
                        "notes":         "",
                    })
                    id_counter += 1

    return items


def extract_infographic_library(path):
    items = []
    id_counter = 1
    seen = set()
    skip = {"pagerhealth final list", "title", "infographic title", ""}

    def add(title, counter):
        title = clean(title).rstrip("*")
        if not title or title.lower() in skip or len(title) < 5:
            return None, counter
        if title in seen:
            return None, counter
        seen.add(title)
        return {
            "id":            f"ILB-{counter:04d}",
            "type":          "Infographic Library",
            "title":         title,
            "category":      infer_category(title),
            "language":      "English",
            "link":          "",
            "client_licenses": [],
            "notes":         "",
        }, counter + 1

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row:
                        continue
                    for col_idx in [0, 4]:
                        if len(row) > col_idx and row[col_idx]:
                            item, id_counter = add(row[col_idx], id_counter)
                            if item:
                                items.append(item)

    return items


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Caravan Wellness — Content Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; background: #f0f2f5; color: #1a1a2e; }
  header { background: #1a1a2e; color: white; padding: 16px 24px; display: flex; align-items: center; gap: 16px; }
  header h1 { font-size: 20px; font-weight: 600; }
  header .meta { font-size: 12px; color: #aaa; margin-left: auto; }
  .tabs { background: white; border-bottom: 2px solid #e0e0e0; display: flex; padding: 0 24px; }
  .tab { padding: 12px 20px; cursor: pointer; font-weight: 500; color: #666; border-bottom: 3px solid transparent; margin-bottom: -2px; transition: all .2s; }
  .tab.active { color: #1a1a2e; border-bottom-color: #e63946; }
  .tab:hover:not(.active) { color: #333; background: #f9f9f9; }
  .main { display: flex; height: calc(100vh - 100px); overflow: hidden; }
  .sidebar { width: 280px; background: white; border-right: 1px solid #e0e0e0; padding: 16px; overflow-y: auto; flex-shrink: 0; }
  .sidebar h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .5px; color: #999; margin-bottom: 8px; }
  .filter-group { margin-bottom: 16px; }
  select, input[type=text] { width: 100%; padding: 8px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; outline: none; }
  select:focus, input:focus { border-color: #1a1a2e; }
  .count-badge { background: #e63946; color: white; border-radius: 10px; padding: 2px 8px; font-size: 11px; font-weight: 600; }
  .content { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  .toolbar { padding: 12px 16px; background: white; border-bottom: 1px solid #e0e0e0; display: flex; align-items: center; gap: 10px; }
  .btn { padding: 7px 14px; border: 1px solid #ddd; border-radius: 6px; cursor: pointer; font-size: 13px; background: white; color: #333; transition: all .15s; }
  .btn:hover { background: #f5f5f5; border-color: #bbb; }
  .btn.primary { background: #1a1a2e; color: white; border-color: #1a1a2e; }
  .btn.primary:hover { background: #2d2d4e; }
  .table-wrap { flex: 1; overflow-y: auto; }
  table { width: 100%; border-collapse: collapse; }
  th { position: sticky; top: 0; background: #f8f9fa; text-align: left; padding: 10px 12px; font-size: 12px; text-transform: uppercase; letter-spacing: .4px; color: #666; border-bottom: 2px solid #e0e0e0; z-index: 10; cursor: pointer; user-select: none; white-space: nowrap; }
  th:hover { background: #eee; }
  td { padding: 9px 12px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; transition: background .1s; }
  tr.row-colored td { /* color applied via inline style on td */ }
  tr:hover td { filter: brightness(0.96); }
  tr.selected td { outline: 2px solid #1a6eb5; outline-offset: -1px; }
  .id-cell { font-family: monospace; font-size: 12px; color: #888; white-space: nowrap; }
  .title-cell { max-width: 320px; }
  .title-cell .title-text { font-weight: 500; line-height: 1.4; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; white-space: nowrap; }
  .badge-High { background: #fde8e8; color: #c0392b; }
  .badge-Moderate { background: #fef3e2; color: #d68910; }
  .badge-Low { background: #e8f8f0; color: #27ae60; }
  .badge-type { background: #e8ecf8; color: #2c3e8c; }
  /* Edited indicator */
  .edited-dot { display: inline-block; width: 7px; height: 7px; background: #e63946; border-radius: 50%; margin-left: 7px; vertical-align: middle; flex-shrink: 0; }
  .edited-stamp { font-size: 11px; color: #e63946; margin-bottom: 14px; font-style: italic; }
  /* Detail panel */
  .detail-panel { width: 400px; background: white; border-left: 1px solid #e0e0e0; overflow-y: auto; flex-shrink: 0; display: none; }
  .detail-panel.open { display: block; }
  .detail-header { padding: 16px 16px 12px; border-bottom: 1px solid #eee; position: relative; }
  .detail-close { position: absolute; top: 12px; right: 12px; border: none; background: none; font-size: 20px; cursor: pointer; color: #999; line-height: 1; }
  .detail-close:hover { color: #333; }
  .title-box { border-radius: 8px; padding: 12px 14px; margin-bottom: 8px; }
  .title-box h2 { font-size: 15px; line-height: 1.45; word-break: break-word; }
  .detail-id { font-family: monospace; color: #888; font-size: 12px; }
  .detail-body { padding: 14px 16px; }
  .detail-field { margin-bottom: 14px; }
  .detail-field label { font-size: 11px; text-transform: uppercase; letter-spacing: .4px; color: #999; display: block; margin-bottom: 5px; }
  .detail-field .val { font-size: 13px; line-height: 1.5; }
  .detail-field a { color: #1a6eb5; text-decoration: none; word-break: break-all; }
  .detail-field a:hover { text-decoration: underline; }
  .field-edit { width: 100%; padding: 6px 9px; border: 1px solid #ddd; border-radius: 5px; font-size: 13px; font-family: inherit; outline: none; background: white; color: #1a1a2e; }
  .field-edit:focus { border-color: #1a1a2e; }
  select.field-edit { height: 32px; }
  .editable { width: 100%; padding: 7px 9px; border: 1px solid #ddd; border-radius: 5px; font-size: 13px; font-family: inherit; resize: vertical; outline: none; }
  .editable:focus { border-color: #1a1a2e; }
  /* Tag / license input */
  .tag-input { display: flex; flex-wrap: wrap; gap: 6px; border: 1px solid #ddd; border-radius: 5px; padding: 6px; min-height: 38px; cursor: text; }
  .tag-input:focus-within { border-color: #1a1a2e; }
  .tag { background: #1a1a2e; color: white; border-radius: 12px; padding: 2px 10px; font-size: 12px; display: flex; align-items: center; gap: 4px; }
  .tag-remove { cursor: pointer; opacity: .6; font-size: 14px; line-height: 1; }
  .tag-remove:hover { opacity: 1; }
  .tag-input input { border: none; outline: none; font-size: 13px; flex: 1; min-width: 80px; background: transparent; }
  /* Color swatches */
  .swatch-row { display: flex; gap: 7px; align-items: center; flex-wrap: wrap; margin-top: 2px; }
  .swatch { width: 24px; height: 24px; border-radius: 5px; cursor: pointer; border: 2px solid transparent; transition: transform .12s, border-color .12s; flex-shrink: 0; }
  .swatch:hover { transform: scale(1.15); }
  .swatch.active { border-color: #1a1a2e; }
  .swatch-clear { background: white; border: 2px dashed #bbb; font-size: 13px; display: flex; align-items: center; justify-content: center; color: #aaa; }
  .swatch-clear:hover { border-color: #888; }
  .color-pair { display: flex; gap: 10px; }
  .color-pair > div { flex: 1; }
  .color-pair label { font-size: 11px; text-transform: uppercase; letter-spacing: .4px; color: #999; display: block; margin-bottom: 5px; }
  /* Empty state */
  .empty-state { text-align: center; padding: 60px 20px; color: #bbb; }
  .sort-asc::after { content: ' ↑'; }
  .sort-desc::after { content: ' ↓'; }
  /* License tab */
  #licenseTab .license-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 16px; }
  .client-card { background: white; border-radius: 8px; border: 1px solid #e0e0e0; padding: 14px; }
  .client-card h3 { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
  .client-item { font-size: 12px; padding: 3px 0; border-bottom: 1px solid #f0f0f0; color: #444; }
  /* Section divider in detail */
  .detail-section-label { font-size: 10px; text-transform: uppercase; letter-spacing: .6px; color: #bbb; font-weight: 600; border-top: 1px solid #eee; padding-top: 12px; margin: 16px 0 10px; }
</style>
</head>
<body>

<header>
  <div>
    <h1>Caravan Wellness — Content Dashboard</h1>
  </div>
  <div class="meta">Last extracted: __EXTRACTED__ &nbsp;|&nbsp; <span id="totalCount"></span> items</div>
</header>

<div class="tabs">
  <div class="tab active" data-tab="reviewTab">Review Tracker</div>
  <div class="tab" data-tab="libraryTab">Content Library</div>
  <div class="tab" data-tab="licenseTab">Client Licensing</div>
</div>

<div class="main">
  <div class="sidebar" id="filterSidebar">
    <div class="filter-group">
      <h3>Search</h3>
      <input type="text" id="searchInput" placeholder="Search titles…">
    </div>
    <div class="filter-group">
      <h3>Type</h3>
      <select id="typeFilter"><option value="">All Types</option></select>
    </div>
    <div class="filter-group">
      <h3>Category</h3>
      <select id="catFilter"><option value="">All Categories</option></select>
    </div>
    <div class="filter-group" id="prioFilterGroup">
      <h3>Review Priority</h3>
      <select id="prioFilter">
        <option value="">All Priorities</option>
        <option>High</option>
        <option>Moderate</option>
        <option>Low</option>
      </select>
    </div>
    <div class="filter-group" id="authorFilterGroup">
      <h3>Author</h3>
      <select id="authorFilter"><option value="">All Authors</option></select>
    </div>
    <div class="filter-group" id="langFilterGroup" style="display:none">
      <h3>Language</h3>
      <select id="langFilter"><option value="">All Languages</option></select>
    </div>
    <div style="margin-top:8px; font-size:13px; color:#666;">
      Showing <span id="shownCount" style="font-weight:600">0</span> items
    </div>
  </div>

  <div class="content">
    <div class="toolbar">
      <button class="btn primary" onclick="exportCSV()">Export CSV</button>
      <span style="flex:1"></span>
    </div>
    <div class="table-wrap" id="tableWrap">
      <table id="dataTable">
        <thead id="tableHead"></thead>
        <tbody id="tableBody"></tbody>
      </table>
      <div class="empty-state" id="emptyState" style="display:none">
        <div>No items match your filters.</div>
      </div>
    </div>
  </div>

  <div class="detail-panel" id="detailPanel"></div>
</div>

<div id="licenseTab" style="display:none; height:calc(100vh - 100px); overflow-y:auto; background:#f0f2f5;">
  <div class="license-grid" id="licenseGrid"></div>
</div>

<script>
const DATA = __DATA_PLACEHOLDER__;

const EDITS_KEY = 'cw_edits_v3';
let userEdits = {};
try { userEdits = JSON.parse(localStorage.getItem(EDITS_KEY) || '{}'); } catch(e) {}

function saveEdits() { localStorage.setItem(EDITS_KEY, JSON.stringify(userEdits)); }

function getEdit(id, field, def) {
  return (userEdits[id] && userEdits[id][field] !== undefined) ? userEdits[id][field] : def;
}

function setEdit(id, field, val) {
  if (!userEdits[id]) userEdits[id] = {};
  userEdits[id][field] = val;
  userEdits[id]['_edited_at'] = new Date().toISOString();
  saveEdits();
}

function liveVal(item, field) {
  return getEdit(item.id, field, item[field] || '');
}

const ALL_ITEMS = [
  ...DATA.articles,
  ...DATA.infographics,
  ...DATA.videos,
  ...DATA.video_library,
  ...DATA.infographic_library,
  ...DATA.article_library,
];

document.getElementById('totalCount').textContent = ALL_ITEMS.length.toLocaleString();

let activeTab = 'reviewTab';
let currentItems = [];
let sortCol = null;
let sortDir = 1;
let selectedId = null;

const REVIEW_TYPES  = new Set(['Article','Infographic','Video']);
const LIBRARY_TYPES = new Set(['Video Library','Infographic Library','Article Library']);
const ALL_TYPES = [...REVIEW_TYPES, ...LIBRARY_TYPES];

const PRIORITIES = ['High','Moderate','Low'];
const CATEGORIES = [...new Set(ALL_ITEMS.map(i => i.category))].sort();

// Row/box color palette
const ROW_BG_COLORS = [
  { hex: '#fde8e8', label: 'Red tint' },
  { hex: '#fef3e2', label: 'Orange tint' },
  { hex: '#fffde7', label: 'Yellow tint' },
  { hex: '#e8f8f0', label: 'Green tint' },
  { hex: '#e8f4f8', label: 'Blue tint' },
  { hex: '#f0e8f8', label: 'Purple tint' },
  { hex: '#f5f5f5', label: 'Grey tint' },
  { hex: '#1a1a2e', label: 'Dark' },
];
const TEXT_COLORS = [
  { hex: '#1a1a2e', label: 'Default dark' },
  { hex: '#c0392b', label: 'Red' },
  { hex: '#d68910', label: 'Orange' },
  { hex: '#27ae60', label: 'Green' },
  { hex: '#1a6eb5', label: 'Blue' },
  { hex: '#7d3c98', label: 'Purple' },
  { hex: '#888888', label: 'Grey' },
  { hex: '#ffffff', label: 'White' },
];

function itemsForTab(tab) {
  if (tab === 'reviewTab')  return ALL_ITEMS.filter(i => REVIEW_TYPES.has(i.type));
  if (tab === 'libraryTab') return ALL_ITEMS.filter(i => LIBRARY_TYPES.has(i.type));
  return ALL_ITEMS;
}

document.querySelectorAll('.tab').forEach(t => {
  t.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    activeTab = t.dataset.tab;
    const isLicense = activeTab === 'licenseTab';
    document.querySelector('.main').style.display = isLicense ? 'none' : 'flex';
    document.getElementById('licenseTab').style.display = isLicense ? 'block' : 'none';
    if (isLicense) { renderLicenseTab(); } else { populateFilters(); applyFilters(); }
  });
});

function getFilteredItems() {
  const search = document.getElementById('searchInput').value.toLowerCase();
  const type   = document.getElementById('typeFilter').value;
  const cat    = document.getElementById('catFilter').value;
  const prio   = document.getElementById('prioFilter').value;
  const author = document.getElementById('authorFilter').value;
  const lang   = document.getElementById('langFilter').value;

  return itemsForTab(activeTab).filter(item => {
    const title = liveVal(item, 'title').toLowerCase();
    if (search && !title.includes(search)) return false;
    if (type   && liveVal(item, 'type') !== type) return false;
    if (cat    && liveVal(item, 'category') !== cat) return false;
    if (prio   && liveVal(item, 'review_priority') !== prio) return false;
    if (author && liveVal(item, 'author') !== author) return false;
    if (lang   && liveVal(item, 'language') !== lang) return false;
    return true;
  });
}

function populateFilters() {
  const base = itemsForTab(activeTab);
  const types = [...new Set(base.map(i => liveVal(i,'type')))].sort();
  document.getElementById('typeFilter').innerHTML = '<option value="">All Types</option>' + types.map(t => `<option>${t}</option>`).join('');
  const cats = [...new Set(base.map(i => liveVal(i,'category')))].sort();
  document.getElementById('catFilter').innerHTML = '<option value="">All Categories</option>' + cats.map(c => `<option>${c}</option>`).join('');
  const authors = [...new Set(base.map(i => liveVal(i,'author')).filter(Boolean))].sort();
  document.getElementById('authorFilter').innerHTML = '<option value="">All Authors</option>' + authors.map(a => `<option>${a}</option>`).join('');
  const langs = [...new Set(base.map(i => liveVal(i,'language')).filter(Boolean))].sort();
  document.getElementById('langFilter').innerHTML = '<option value="">All Languages</option>' + langs.map(l => `<option>${l}</option>`).join('');
  const isReview = activeTab === 'reviewTab';
  document.getElementById('prioFilterGroup').style.display   = isReview ? '' : 'none';
  document.getElementById('authorFilterGroup').style.display = isReview ? '' : 'none';
  document.getElementById('langFilterGroup').style.display   = activeTab === 'libraryTab' ? '' : 'none';
}

['searchInput','typeFilter','catFilter','prioFilter','authorFilter','langFilter'].forEach(id => {
  const el = document.getElementById(id);
  el.addEventListener('input', applyFilters);
  el.addEventListener('change', applyFilters);
});

function applyFilters() {
  currentItems = getFilteredItems();
  if (sortCol !== null) sortItems();
  renderTable();
  document.getElementById('shownCount').textContent = currentItems.length.toLocaleString();
}

function sortItems() {
  currentItems.sort((a, b) => {
    const av = liveVal(a, sortCol);
    const bv = liveVal(b, sortCol);
    return av.localeCompare(bv) * sortDir;
  });
}

function getColumns() {
  if (activeTab === 'reviewTab') {
    return [
      { key: 'id',              label: 'ID' },
      { key: 'type',            label: 'Type' },
      { key: 'title',           label: 'Title' },
      { key: 'category',        label: 'Category' },
      { key: 'review_priority', label: 'Priority' },
      { key: 'author',          label: 'Author' },
      { key: 'version',         label: 'Ver.' },
      { key: 'date_created',    label: 'Created' },
      { key: 'date_revised',    label: 'Revised' },
    ];
  }
  return [
    { key: 'id',       label: 'ID' },
    { key: 'type',     label: 'Type' },
    { key: 'title',    label: 'Title' },
    { key: 'category', label: 'Category' },
    { key: 'language', label: 'Language' },
    { key: 'teacher',  label: 'Teacher / Reviewer' },
  ];
}

function renderTable() {
  const cols = getColumns();
  const head = document.getElementById('tableHead');
  head.innerHTML = '<tr>' + cols.map(c => {
    let cls = '';
    if (sortCol === c.key) cls = sortDir === 1 ? 'sort-asc' : 'sort-desc';
    return `<th class="${cls}" data-key="${c.key}">${c.label}</th>`;
  }).join('') + '</tr>';

  head.querySelectorAll('th').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      if (sortCol === key) sortDir *= -1; else { sortCol = key; sortDir = 1; }
      sortItems(); renderTable();
    });
  });

  const body  = document.getElementById('tableBody');
  const empty = document.getElementById('emptyState');
  if (!currentItems.length) { body.innerHTML = ''; empty.style.display = ''; return; }
  empty.style.display = 'none';

  body.innerHTML = currentItems.map(item => {
    const sel      = item.id === selectedId ? 'selected' : '';
    const licenses = getEdit(item.id, 'licenses', item.client_licenses || []);
    const rowBg    = getEdit(item.id, 'row_bg', '');
    const rowText  = getEdit(item.id, 'row_text', '');
    const wasEdited = !!(userEdits[item.id] && userEdits[item.id]._edited_at);
    const tdStyle  = rowBg ? `style="background:${rowBg};${rowText ? 'color:'+rowText : ''}"` : (rowText ? `style="color:${rowText}"` : '');

    const cells = cols.map(c => {
      const tdS = c.key === 'id' ? '' : tdStyle;
      if (c.key === 'id') return `<td class="id-cell">${item.id}</td>`;
      if (c.key === 'title') {
        const title = liveVal(item, 'title');
        const lic  = licenses.length ? `<span style="margin-left:6px;font-size:10px;opacity:.6">[${licenses.join(', ')}]</span>` : '';
        const dot  = wasEdited ? '<span class="edited-dot" title="Recently edited"></span>' : '';
        return `<td class="title-cell" ${tdS}><div class="title-text" style="display:flex;align-items:center;gap:0">${esc(title)}${lic}${dot}</div></td>`;
      }
      if (c.key === 'type') {
        const t = liveVal(item, 'type');
        return `<td ${tdS}><span class="badge badge-type">${esc(t)}</span></td>`;
      }
      if (c.key === 'review_priority') {
        const p = liveVal(item, 'review_priority');
        return `<td ${tdS}>${p ? `<span class="badge badge-${p}">${p}</span>` : ''}</td>`;
      }
      let val = '';
      if (c.key === 'teacher') val = liveVal(item, 'teacher') || liveVal(item, 'peer_reviewer') || '';
      else val = liveVal(item, c.key);
      return `<td ${tdS}>${esc(val)}</td>`;
    }).join('');

    const rowCls = [sel, rowBg ? 'row-colored' : ''].filter(Boolean).join(' ');
    return `<tr class="${rowCls}" data-id="${item.id}">${cells}</tr>`;
  }).join('');

  body.querySelectorAll('tr').forEach(row => {
    row.addEventListener('click', () => {
      const item = ALL_ITEMS.find(i => i.id === row.dataset.id);
      if (item) showDetail(item);
    });
  });
}

function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function swatchesHtml(colors, editedKey, currentVal) {
  const clearSwatch = `<div class="swatch swatch-clear ${!currentVal?'active':''}" data-color="" data-key="${editedKey}" title="Clear">✕</div>`;
  const swatches = colors.map(c =>
    `<div class="swatch ${currentVal===c.hex?'active':''}" data-color="${c.hex}" data-key="${editedKey}" style="background:${c.hex}" title="${c.label}"></div>`
  ).join('');
  return `<div class="swatch-row">${clearSwatch}${swatches}</div>`;
}

function showDetail(item) {
  selectedId = item.id;
  document.querySelectorAll('#tableBody tr').forEach(r => r.classList.remove('selected'));
  const selRow = document.querySelector(`#tableBody tr[data-id="${item.id}"]`);
  if (selRow) selRow.classList.add('selected');

  const panel = document.getElementById('detailPanel');
  panel.classList.add('open');

  const licenses  = getEdit(item.id, 'licenses', item.client_licenses || []);
  const notes     = getEdit(item.id, 'notes', item.notes || '');
  const rowBg     = getEdit(item.id, 'row_bg', '');
  const rowText   = getEdit(item.id, 'row_text', '');
  const editedAt  = userEdits[item.id] && userEdits[item.id]._edited_at;
  const editedStr = editedAt ? (() => {
    const d = new Date(editedAt);
    return d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}) + ' at ' + d.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'});
  })() : '';

  // Live values (edits override PDF data)
  const fTitle  = liveVal(item, 'title');
  const fType   = liveVal(item, 'type');
  const fCat    = liveVal(item, 'category');
  const fPrio   = liveVal(item, 'review_priority');
  const fAuthor = liveVal(item, 'author');
  const fCreds  = liveVal(item, 'author_creds');
  const fReviewer = liveVal(item, 'peer_reviewer');
  const fVer    = liveVal(item, 'version');
  const fCreated = liveVal(item, 'date_created');
  const fRevised = liveVal(item, 'date_revised');
  const fLang   = liveVal(item, 'language');
  const fTeacher = liveVal(item, 'teacher');
  const fLink   = liveVal(item, 'link');
  const fVimeo  = liveVal(item, 'vimeo_link');
  const fDesc   = liveVal(item, 'description');

  const titleBoxStyle = `background:${rowBg||'#f0f2f5'};color:${rowText||'#1a1a2e'}`;

  const typeOpts = ALL_TYPES.map(t => `<option${fType===t?' selected':''}>${t}</option>`).join('');
  const catOpts  = CATEGORIES.map(c => `<option${fCat===c?' selected':''}>${c}</option>`).join('');
  const prioOpts = ['', ...PRIORITIES].map(p => `<option value="${p}"${fPrio===p?' selected':''}>${p||'—'}</option>`).join('');

  const tagsHtml = `
    <div class="tag-input" id="tagContainer">
      ${licenses.map(l => `<span class="tag">${esc(l)}<span class="tag-remove" data-tag="${esc(l)}">×</span></span>`).join('')}
      <input type="text" placeholder="Add client…" id="tagInputField">
    </div>`;

  panel.innerHTML = `
    <div class="detail-header">
      <button class="detail-close" onclick="closeDetail()">×</button>
      <div class="title-box" style="${titleBoxStyle}">
        <h2>${esc(fTitle)}</h2>
      </div>
      <div class="detail-id">${item.id}${editedStr ? ` &nbsp;·&nbsp; <span class="edited-stamp">Edited ${editedStr}</span>` : ''}</div>
    </div>
    <div class="detail-body">

      <div class="detail-section-label">Appearance</div>
      <div class="color-pair">
        <div>
          <label>Row &amp; Box Background</label>
          ${swatchesHtml(ROW_BG_COLORS, 'row_bg', rowBg)}
        </div>
        <div>
          <label>Text Color</label>
          ${swatchesHtml(TEXT_COLORS, 'row_text', rowText)}
        </div>
      </div>

      <div class="detail-section-label">Content Details</div>

      <div class="detail-field">
        <label>Title</label>
        <input class="field-edit" type="text" data-field="title" value="${esc(fTitle)}">
      </div>

      <div class="detail-field">
        <label>Type</label>
        <select class="field-edit" data-field="type">${typeOpts}</select>
      </div>

      <div class="detail-field">
        <label>Category</label>
        <select class="field-edit" data-field="category">${catOpts}</select>
      </div>

      ${REVIEW_TYPES.has(fType) ? `
      <div class="detail-field">
        <label>Review Priority</label>
        <select class="field-edit" data-field="review_priority">${prioOpts}</select>
      </div>` : ''}

      <div class="detail-field">
        <label>Author / Teacher</label>
        <input class="field-edit" type="text" data-field="author" value="${esc(fAuthor)}">
      </div>

      <div class="detail-field">
        <label>Author Credentials</label>
        <input class="field-edit" type="text" data-field="author_creds" value="${esc(fCreds)}">
      </div>

      <div class="detail-field">
        <label>Peer Reviewer</label>
        <input class="field-edit" type="text" data-field="peer_reviewer" value="${esc(fReviewer)}">
      </div>

      ${fLang !== undefined ? `
      <div class="detail-field">
        <label>Language</label>
        <input class="field-edit" type="text" data-field="language" value="${esc(fLang)}">
      </div>` : ''}

      <div class="detail-field">
        <label>Version</label>
        <input class="field-edit" type="text" data-field="version" value="${esc(fVer)}" style="width:80px">
      </div>

      <div class="detail-field">
        <label>Date Created</label>
        <input class="field-edit" type="text" data-field="date_created" value="${esc(fCreated)}" placeholder="MM/DD/YYYY">
      </div>

      <div class="detail-field">
        <label>Date Revised</label>
        <input class="field-edit" type="text" data-field="date_revised" value="${esc(fRevised)}" placeholder="MM/DD/YYYY">
      </div>

      <div class="detail-field">
        <label>Link</label>
        <input class="field-edit" type="text" data-field="link" value="${esc(fLink)}" placeholder="https://…">
      </div>

      ${fVimeo ? `
      <div class="detail-field">
        <label>Vimeo Link</label>
        <input class="field-edit" type="text" data-field="vimeo_link" value="${esc(fVimeo)}" placeholder="https://vimeo.com/…">
      </div>` : ''}

      ${fDesc ? `
      <div class="detail-field">
        <label>Description</label>
        <textarea class="field-edit editable" data-field="description" rows="3">${esc(fDesc)}</textarea>
      </div>` : ''}

      <div class="detail-section-label">Licensing &amp; Notes</div>

      <div class="detail-field">
        <label>Client Licenses</label>
        ${tagsHtml}
      </div>

      <div class="detail-field">
        <label>Internal Notes</label>
        <textarea class="editable" rows="4" id="notesField">${esc(notes)}</textarea>
      </div>

    </div>
  `;

  // Swatch clicks
  panel.querySelectorAll('.swatch').forEach(sw => {
    sw.addEventListener('click', () => {
      const field = sw.dataset.key;
      const color = sw.dataset.color;
      setEdit(item.id, field, color);
      // Update row immediately
      applyRowStyle(item.id);
      showDetail(item);
    });
  });

  // Field edits (debounced)
  panel.querySelectorAll('.field-edit').forEach(el => {
    let timer;
    const onChange = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const field = el.dataset.field;
        const val   = el.value;
        setEdit(item.id, field, val);
        // Refresh the row in the table
        refreshRow(item.id);
        // Update title box live
        if (field === 'title') {
          const tb = panel.querySelector('.title-box h2');
          if (tb) tb.textContent = val;
        }
      }, 300);
    };
    el.addEventListener('input', onChange);
    el.addEventListener('change', onChange);
  });

  // Tag input
  const tagInput = document.getElementById('tagInputField');
  tagInput.addEventListener('keydown', e => {
    if ((e.key === 'Enter' || e.key === ',') && tagInput.value.trim()) {
      e.preventDefault();
      const tag = tagInput.value.trim().replace(/,/g,'');
      if (tag && !licenses.includes(tag)) {
        licenses.push(tag);
        setEdit(item.id, 'licenses', licenses);
        showDetail(item);
      }
    }
  });

  panel.querySelectorAll('.tag-remove').forEach(btn => {
    btn.addEventListener('click', () => {
      const tag = btn.dataset.tag;
      const idx = licenses.indexOf(tag);
      if (idx > -1) { licenses.splice(idx,1); setEdit(item.id,'licenses',licenses); showDetail(item); }
    });
  });

  document.getElementById('notesField').addEventListener('input', e => {
    setEdit(item.id, 'notes', e.target.value);
  });
}

function applyRowStyle(id) {
  const rowBg   = getEdit(id, 'row_bg', '');
  const rowText = getEdit(id, 'row_text', '');
  const row = document.querySelector(`#tableBody tr[data-id="${id}"]`);
  if (!row) return;
  row.querySelectorAll('td:not(.id-cell)').forEach(td => {
    td.style.background = rowBg;
    td.style.color = rowText;
  });
  if (rowBg) row.classList.add('row-colored'); else row.classList.remove('row-colored');
}

function refreshRow(id) {
  // Re-render just this row in place (lightweight)
  const row = document.querySelector(`#tableBody tr[data-id="${id}"]`);
  if (row) {
    const item = ALL_ITEMS.find(i => i.id === id);
    if (!item) return;
    const cols = getColumns();
    const rowBg   = getEdit(id, 'row_bg', '');
    const rowText = getEdit(id, 'row_text', '');
    const licenses = getEdit(id, 'licenses', item.client_licenses || []);
    const wasEdited = !!(userEdits[id] && userEdits[id]._edited_at);
    const tdStyle = rowBg ? `style="background:${rowBg};${rowText?'color:'+rowText:''}"` : (rowText?`style="color:${rowText}"`:'');

    row.innerHTML = cols.map(c => {
      const tdS = c.key === 'id' ? '' : tdStyle;
      if (c.key === 'id') return `<td class="id-cell">${id}</td>`;
      if (c.key === 'title') {
        const title = liveVal(item,'title');
        const lic  = licenses.length ? `<span style="margin-left:6px;font-size:10px;opacity:.6">[${licenses.join(', ')}]</span>` : '';
        const dot  = wasEdited ? '<span class="edited-dot" title="Recently edited"></span>' : '';
        return `<td class="title-cell" ${tdS}><div class="title-text" style="display:flex;align-items:center;gap:0">${esc(title)}${lic}${dot}</div></td>`;
      }
      if (c.key === 'type') return `<td ${tdS}><span class="badge badge-type">${esc(liveVal(item,'type'))}</span></td>`;
      if (c.key === 'review_priority') {
        const p = liveVal(item,'review_priority');
        return `<td ${tdS}>${p?`<span class="badge badge-${p}">${p}</span>`:''}</td>`;
      }
      let val = c.key === 'teacher' ? (liveVal(item,'teacher') || liveVal(item,'peer_reviewer') || '') : liveVal(item,c.key);
      return `<td ${tdS}>${esc(val)}</td>`;
    }).join('');

    row.addEventListener('click', () => {
      const i = ALL_ITEMS.find(x => x.id === id);
      if (i) showDetail(i);
    });
  }
}

function closeDetail() {
  selectedId = null;
  document.getElementById('detailPanel').classList.remove('open');
  document.querySelectorAll('#tableBody tr').forEach(r => r.classList.remove('selected'));
}

function renderLicenseTab() {
  const clientMap = {};
  ALL_ITEMS.forEach(item => {
    const licenses = getEdit(item.id, 'licenses', item.client_licenses || []);
    licenses.forEach(client => {
      if (!clientMap[client]) clientMap[client] = [];
      clientMap[client].push(item);
    });
  });
  const grid = document.getElementById('licenseGrid');
  if (!Object.keys(clientMap).length) {
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:60px;color:#bbb">No client licenses assigned yet. Open an item and add a client name.</div>';
    return;
  }
  grid.innerHTML = Object.entries(clientMap).sort(([a],[b])=>a.localeCompare(b)).map(([client,items])=>`
    <div class="client-card">
      <h3>${esc(client)} <span class="count-badge">${items.length}</span></h3>
      ${items.slice(0,20).map(i=>`<div class="client-item">${esc(i.id)} — ${esc(liveVal(i,'title').slice(0,60))}</div>`).join('')}
      ${items.length>20?`<div class="client-item" style="color:#aaa">…and ${items.length-20} more</div>`:''}
    </div>`).join('');
}

function exportCSV() {
  const cols = getColumns();
  const rows = [['ID','Type','Title','Category','Priority','Author','Version','Created','Revised','Language','Teacher/Reviewer','Client Licenses','Notes'].join(',')];
  currentItems.forEach(item => {
    const licenses = getEdit(item.id, 'licenses', item.client_licenses || []);
    const notes    = getEdit(item.id, 'notes', item.notes || '');
    const vals = [
      item.id,
      liveVal(item,'type'),
      liveVal(item,'title'),
      liveVal(item,'category'),
      liveVal(item,'review_priority'),
      liveVal(item,'author'),
      liveVal(item,'version'),
      liveVal(item,'date_created'),
      liveVal(item,'date_revised'),
      liveVal(item,'language'),
      liveVal(item,'teacher') || liveVal(item,'peer_reviewer'),
      licenses.join('; '),
      notes,
    ].map(v => '"' + String(v||'').replace(/"/g,'""') + '"');
    rows.push(vals.join(','));
  });
  const blob = new Blob([rows.join('\n')], {type:'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'caravan-content-export.csv';
  a.click();
}

populateFilters();
applyFilters();
</script>
</body>
</html>"""


def main():
    print("Extracting content from PDFs...")
    all_data = {}

    print("  → Articles review tracker")
    all_data["articles"] = extract_review_tracker(PDFS["articles_review"], "Article", "ART")

    print("  → Infographics review tracker")
    all_data["infographics"] = extract_review_tracker(PDFS["infographics_review"], "Infographic", "INF")

    print("  → Videos review tracker")
    all_data["videos"] = extract_review_tracker(PDFS["videos_review"], "Video", "VID")

    print("  → Video Library catalog")
    all_data["video_library"] = extract_video_library(PDFS["video_library"])

    print("  → Infographic Library catalog")
    all_data["infographic_library"] = extract_infographic_library(PDFS["infographic_library"])

    print("  → Article Library catalog")
    all_data["article_library"] = extract_article_library(PDFS["article_library"])

    for key, items in all_data.items():
        print(f"    {key}: {len(items)} items")

    total = sum(len(v) for v in all_data.values())
    print(f"    TOTAL: {total} items")

    data_json = json.dumps(all_data, separators=(',', ':'))
    extracted_date = date.today().strftime("%B %d, %Y")

    html = HTML_TEMPLATE.replace("__DATA_PLACEHOLDER__", data_json)
    html = html.replace("__EXTRACTED__", extracted_date)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nDone. Open this file in your browser:\n  {OUT}")


if __name__ == "__main__":
    main()
