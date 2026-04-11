# Research Paper Assistant — UI/UX Wireframes & Design System

**Phase 1 Output — ui-ux agent**
**Date:** 2026-04-11
**Status:** Complete — ready for Phase 2 (frontend agent)

---

## Table of Contents

1. [Design System](#design-system)
2. [Component Hierarchy](#component-hierarchy)
3. [Page Wireframes](#page-wireframes)
   - [/ — Home / Dashboard](#1----home--dashboard)
   - [/upload — Paper Upload / Ingestion](#2--upload----paper-upload--ingestion)
   - [/query — Research Query / Search](#3--query----research-query--search)
   - [/library — Paper Library](#4--library----paper-library)
   - [/results/[id] — Literature Review Detail](#5--resultsid----literature-review-detail)
4. [User Flows](#user-flows)
5. [State & Interaction Notes](#state--interaction-notes)

---

## Design System

### Color Palette (Tailwind Classes)

| Role        | Tailwind Class        | Hex       | Usage                                      |
|-------------|----------------------|-----------|---------------------------------------------|
| Primary     | `blue-600`           | #2563EB   | CTAs, active nav, links, primary buttons    |
| Primary Hover | `blue-700`         | #1D4ED8   | Hover state on primary buttons              |
| Primary Light | `blue-50`          | #EFF6FF   | Selected row highlight, active card bg      |
| Success     | `green-500`          | #22C55E   | External badge, success toasts, upload done |
| Success Light | `green-50`         | #F0FDF4   | Success alert backgrounds                   |
| Warning     | `amber-500`          | #F59E0B   | Processing state, duplicate warning         |
| Warning Light | `amber-50`         | #FFFBEB   | Warning alert backgrounds                   |
| Error       | `red-500`            | #EF4444   | Error states, delete confirmations          |
| Error Light | `red-50`             | #FEF2F2   | Error alert backgrounds                     |
| Neutral 50  | `gray-50`            | #F9FAFB   | Page background                             |
| Neutral 100 | `gray-100`           | #F3F4F6   | Card backgrounds, table alternating rows    |
| Neutral 200 | `gray-200`           | #E5E7EB   | Borders, dividers                           |
| Neutral 500 | `gray-500`           | #6B7280   | Secondary text, placeholders                |
| Neutral 700 | `gray-700`           | #374151   | Body text                                   |
| Neutral 900 | `gray-900`           | #111827   | Headings                                    |
| White       | `white`              | #FFFFFF   | Card surfaces, input backgrounds            |

**Source Badges:**
- PDF: `bg-blue-100 text-blue-700`
- DOI: `bg-purple-100 text-purple-700`
- arXiv: `bg-orange-100 text-orange-700`
- Local (citation): `bg-blue-100 text-blue-700`
- External (citation): `bg-green-100 text-green-700`

### Typography

**Font:** Inter (Google Fonts). Load via `next/font/google`.

| Token   | Element     | Tailwind Classes                          | Size / Weight         |
|---------|-------------|--------------------------------------------|-----------------------|
| h1      | Page title  | `text-3xl font-bold text-gray-900`        | 30px / 700            |
| h2      | Section heading | `text-2xl font-semibold text-gray-900` | 24px / 600            |
| h3      | Card title  | `text-lg font-semibold text-gray-900`     | 18px / 600            |
| h4      | Sub-section | `text-base font-semibold text-gray-700`   | 16px / 600            |
| body    | Default text | `text-sm text-gray-700`                  | 14px / 400            |
| body-lg | Paragraphs  | `text-base text-gray-700`                 | 16px / 400            |
| caption | Helper text | `text-xs text-gray-500`                   | 12px / 400            |
| code    | Inline code | `font-mono text-xs bg-gray-100 px-1 rounded` | 12px / mono        |
| label   | Form labels | `text-sm font-medium text-gray-700`       | 14px / 500            |

### Spacing Conventions

- **Page padding:** `px-6 py-8` (desktop), `px-4 py-6` (mobile)
- **Card padding:** `p-6`
- **Section gap:** `gap-6` between major sections
- **Form field gap:** `gap-4` between form elements
- **Button padding:** `px-4 py-2` (default), `px-6 py-3` (large)
- **Table cell padding:** `px-4 py-3`
- **Inline badge padding:** `px-2 py-0.5`

### Border Radius & Shadow

| Token        | Tailwind Class     | Usage                            |
|--------------|-------------------|-----------------------------------|
| Rounded SM   | `rounded`         | Badges, tags, small elements      |
| Rounded MD   | `rounded-md`      | Buttons, inputs                   |
| Rounded LG   | `rounded-lg`      | Cards, modals, dropzones          |
| Rounded XL   | `rounded-xl`      | Large panels                      |
| Shadow SM    | `shadow-sm`       | Cards in default state            |
| Shadow MD    | `shadow-md`       | Dropdowns, tooltips               |
| Shadow LG    | `shadow-lg`       | Modals, overlays                  |
| Border       | `border border-gray-200` | Cards, inputs, table borders |

### shadcn/ui Components Mapping

| shadcn Component | Used In                                              |
|-----------------|------------------------------------------------------|
| `Button`        | All CTAs, form submits, actions                      |
| `Card`          | Stats cards, result sections, paper previews         |
| `Badge`         | Source labels (PDF/DOI/arXiv/Local/External)         |
| `Table`         | Paper list, library, citations                       |
| `Textarea`      | Research question input, DOI/URL input               |
| `Input`         | Search/filter fields                                 |
| `Progress`      | Upload progress bars                                 |
| `Tabs`          | Results panel sections on /query                     |
| `Separator`     | Section dividers                                     |
| `Toast`         | Success/error notifications                          |
| `Dialog`        | Delete confirmation, paper detail preview            |
| `Skeleton`      | Loading placeholder states                           |
| `Alert`         | Error and warning messages                           |
| `Checkbox`      | Bulk selection in library                            |
| `Select`        | Filter dropdowns                                     |
| `Tooltip`       | Action icon hints                                    |

### Dark Mode

Dark mode is noted as a future enhancement. Phase 2 should use Tailwind's `dark:` variant on all color tokens so dark mode can be enabled later by adding `class="dark"` to the `<html>` tag. The design spec in this document is light-mode-first.

---

## Component Hierarchy

```
App (RootLayout)
├── Navbar
│   ├── Logo (text + icon)
│   ├── NavLink ("Dashboard" / "/" )
│   ├── NavLink ("Upload" / "/upload")
│   ├── NavLink ("Query" / "/query")
│   ├── NavLink ("Library" / "/library")
│   └── StatusIndicator (DB connection dot)
│
├── Page: / (Dashboard)
│   ├── PageHeader (title, subtitle)
│   ├── StatsGrid
│   │   ├── StatCard ("Total Papers")
│   │   ├── StatCard ("Queries Run")
│   │   ├── StatCard ("DB Size")
│   │   └── StatCard ("Last Activity")
│   ├── RecentActivitySection
│   │   ├── RecentQueriesList
│   │   │   └── QueryHistoryItem (question text, timestamp, result link)
│   │   └── RecentPapersList
│   │       └── PaperHistoryItem (title, authors, source badge, date added)
│   └── QuickActions
│       ├── QuickActionCard ("Upload Papers" -> /upload)
│       └── QuickActionCard ("Start Research" -> /query)
│
├── Page: /upload (Upload)
│   ├── PageHeader
│   ├── UploadSection
│   │   ├── UploadZone (drag-and-drop, click-to-browse)
│   │   │   ├── UploadIcon
│   │   │   ├── UploadPromptText
│   │   │   └── FileTypeHint ("PDF files only, max 50MB each")
│   │   └── UploadFileList
│   │       └── UploadFileItem (filename, size, ProgressBar, StatusIcon, RemoveButton)
│   ├── DOISection
│   │   ├── SectionLabel
│   │   ├── Textarea (DOI/URL input)
│   │   └── FetchButton ("Fetch & Store")
│   ├── UploadStatusBar (total count, DB size)
│   └── PaperTable (papers in DB)
│       ├── TableToolbar (search input, filter select)
│       ├── Table
│       │   └── PaperTableRow (title, authors, year, SourceBadge, date added, actions)
│       └── EmptyState (no papers yet)
│
├── Page: /query (Research Query)
│   ├── PageHeader
│   ├── SearchForm
│   │   ├── Textarea (research question)
│   │   ├── SearchButton ("Search")
│   │   └── HintText
│   ├── LoadingSteps (conditional, while loading)
│   │   ├── LoadingStep ("Searching local DB..." — step 1)
│   │   ├── LoadingStep ("Fetching external papers..." — step 2, conditional)
│   │   └── LoadingStep ("Generating literature review..." — step 3)
│   ├── ResultsPanel (conditional, when results exist)
│   │   ├── Tabs
│   │   │   ├── TabTrigger "Summary"
│   │   │   ├── TabTrigger "Agreements"
│   │   │   ├── TabTrigger "Contradictions"
│   │   │   ├── TabTrigger "Research Gaps"
│   │   │   └── TabTrigger "Citations"
│   │   ├── TabContent: Summary (prose paragraph)
│   │   ├── TabContent: Agreements (bulleted list)
│   │   ├── TabContent: Contradictions (bulleted list)
│   │   ├── TabContent: Research Gaps (bulleted list)
│   │   └── TabContent: Citations
│   │       └── CitationCard (title, authors, year, SourceBadge, DOI/link)
│   └── EmptyState (before first query)
│
├── Page: /library (Library)
│   ├── PageHeader (title, paper count)
│   ├── LibraryToolbar
│   │   ├── SearchInput (filter by title/author)
│   │   ├── SourceFilter (Select: All / PDF / DOI / arXiv)
│   │   ├── YearRangeFilter (two Inputs: from year, to year)
│   │   └── BulkDeleteButton (enabled when rows selected)
│   ├── PaperTable (full library version)
│   │   ├── TableHeader (checkbox, Title, Authors, Year, Source, Abstract, Actions)
│   │   └── PaperLibraryRow
│   │       ├── Checkbox
│   │       ├── Title (truncated, tooltip with full)
│   │       ├── Authors (truncated)
│   │       ├── Year
│   │       ├── SourceBadge
│   │       ├── AbstractPreview (first 120 chars)
│   │       └── RowActions (ViewButton, DeleteButton)
│   ├── Pagination (page X of Y, prev/next, 20 per page)
│   └── EmptyState (no papers)
│
├── Page: /results/[id] (Result Detail)
│   ├── ResultDetailHeader
│   │   ├── BackButton ("Back to Query")
│   │   ├── QueryTitle (the original question)
│   │   ├── Timestamp
│   │   └── ExportActions (CopyButton, ExportMarkdownButton, ExportPDFButton)
│   ├── ResultLayout (two-column: main + sidebar)
│   │   ├── MainContent
│   │   │   ├── ResultSection "Summary"
│   │   │   ├── ResultSection "Key Agreements"
│   │   │   ├── ResultSection "Contradictions"
│   │   │   └── ResultSection "Research Gaps"
│   │   └── CitationSidebar
│   │       ├── SidebarTitle ("Cited Papers")
│   │       └── CitationSidebarItem[] (number, title, authors, year, SourceBadge, link)
│   └── Footer (Phase 2: static only)
│
└── Shared Components
    ├── StatusBadge (props: variant: "pdf"|"doi"|"arxiv"|"local"|"external")
    ├── EmptyState (props: icon, title, description, actionLabel, onAction)
    ├── ErrorAlert (props: title, message, onRetry?)
    ├── LoadingSpinner
    ├── SkeletonCard (loading placeholder for card)
    ├── SkeletonRow (loading placeholder for table row)
    └── PageHeader (props: title, subtitle, actions?)
```

---

## Page Wireframes

### 1. / — Home / Dashboard

**Route:** `/`
**Purpose:** Give professors an at-a-glance view of their research assistant status and quick access to core actions.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ NAVBAR                                                                    │
│ [Logo: ResearchAI]   Dashboard   Upload   Query   Library   [● Connected] │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  PAGE CONTENT (max-w-7xl mx-auto px-6 py-8)                              │
│                                                                           │
│  Research Paper Assistant                                                 │
│  Your local-first academic research tool                                  │
│                                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ STAT CARD    │  │ STAT CARD    │  │ STAT CARD    │  │ STAT CARD    │ │
│  │              │  │              │  │              │  │              │ │
│  │  47          │  │  12          │  │  128 MB      │  │  2 hrs ago   │ │
│  │  Total Papers│  │  Queries Run │  │  DB Size     │  │ Last Activity│ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                                           │
│  ┌───────────────────────────────┐  ┌───────────────────────────────┐   │
│  │ RECENT QUERIES                │  │ RECENTLY ADDED PAPERS          │   │
│  │ ─────────────────────────     │  │ ──────────────────────────     │   │
│  │ > What is the state of...     │  │ [PDF] Attention is All You...  │   │
│  │   2 hrs ago  [View →]         │  │ Vaswani et al. 2017   2d ago   │   │
│  │                               │  │                                │   │
│  │ > Compare transformer arch... │  │ [arXiv] BERT: Pre-training...  │   │
│  │   Yesterday  [View →]         │  │ Devlin et al. 2018   5d ago    │   │
│  │                               │  │                                │   │
│  │ > Survey of RAG methods...    │  │ [DOI] Chain-of-Thought...      │   │
│  │   3 days ago [View →]         │  │ Wei et al. 2022   1w ago       │   │
│  │                               │  │                                │   │
│  │ > [No more recent queries]    │  │ [View all papers →]            │   │
│  └───────────────────────────────┘  └───────────────────────────────┘   │
│                                                                           │
│  ┌───────────────────────────────┐  ┌───────────────────────────────┐   │
│  │ QUICK ACTION CARD             │  │ QUICK ACTION CARD              │   │
│  │                               │  │                                │   │
│  │  [↑ Upload icon]              │  │  [🔍 Search icon]              │   │
│  │                               │  │                                │   │
│  │  Upload Papers                │  │  Start Research                │   │
│  │  Add PDFs or DOIs to your     │  │  Ask a question across your    │   │
│  │  local library                │  │  paper library                 │   │
│  │                               │  │                                │   │
│  │  [Go to Upload →]             │  │  [Go to Query →]               │   │
│  └───────────────────────────────┘  └───────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
```

**Component Notes:**
- `StatCard`: `Card` with a large number (`text-3xl font-bold text-blue-600`), label below (`text-sm text-gray-500`), optional trend icon. Width: `w-full`. Grid: `grid-cols-4 gap-6`.
- `RecentQueriesList` and `RecentPapersList`: side-by-side `grid-cols-2 gap-6`. Each is a `Card` with `p-6`. List items separated by `Separator`.
- `QueryHistoryItem`: question truncated to 60 chars, timestamp in `text-xs text-gray-500`, "View" link in `text-blue-600`.
- `QuickActionCard`: `Card` with centered icon (48px, `text-blue-600`), h3 title, description in `text-sm text-gray-500`, `Button` variant="outline" at bottom. Grid: `grid-cols-2 gap-6`.
- Empty state for stats: show `--` instead of numbers while loading; use `Skeleton` components.

---

### 2. /upload — Paper Upload / Ingestion

**Route:** `/upload`
**Purpose:** Allow professors to add papers to ChromaDB via PDF upload or DOI/URL entry.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ NAVBAR                                                                    │
│ [Logo]   Dashboard   [Upload ←active]   Query   Library   [● Connected]  │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  Upload Papers                                                            │
│  Add research papers to your local ChromaDB library                       │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │ UPLOAD ZONE (dashed border, rounded-lg, p-12, bg-gray-50)         │   │
│  │                                                                   │   │
│  │              [↑ Upload cloud icon — 48px, text-gray-400]          │   │
│  │                                                                   │   │
│  │           Drag and drop PDF files here, or click to browse        │   │
│  │                                                                   │   │
│  │                 PDF files only · Max 50MB per file                │   │
│  │                                                                   │   │
│  │                    [Browse Files  button]                         │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  FILE LIST (appears below drop zone after files are selected)             │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │ [PDF icon] attention-is-all-you-need.pdf         2.3 MB   [x]    │   │
│  │ ████████████████████░░░░  Processing... 78%                       │   │
│  │                                                                   │   │
│  │ [PDF icon] bert-paper.pdf                        1.8 MB   [✓]    │   │
│  │ ████████████████████████  Stored successfully                     │   │
│  │                                                                   │   │
│  │ [PDF icon] invalid-file.docx                     0.5 MB   [✗]    │   │
│  │ [!] Error: Only PDF files are supported                           │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ─────────────────────────────────────────────────────────────────────   │
│                                                                           │
│  OR FETCH BY DOI / URL                                                    │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │ Textarea (rows=5, placeholder="Enter one DOI or URL per line      │   │
│  │ e.g.  10.48550/arXiv.1706.03762                                   │   │
│  │        https://arxiv.org/abs/1810.04805")                         │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│  [Fetch & Store]  (Button primary, full width on mobile)                  │
│                                                                           │
│  ─────────────────────────────────────────────────────────────────────   │
│                                                                           │
│  LIBRARY STATUS BAR                                                       │
│  47 papers stored  ·  128 MB used  ·  ChromaDB: Connected ●              │
│                                                                           │
│  PAPERS IN YOUR LIBRARY                                                   │
│  ┌────────────────┬─────────────────────┬──────┬────────┬────────────┐   │
│  │ Title          │ Authors             │ Year │ Source │ Added      │   │
│  ├────────────────┼─────────────────────┼──────┼────────┼────────────┤   │
│  │ Attention Is   │ Vaswani, Shazeer... │ 2017 │ [PDF]  │ 2 days ago │   │
│  ├────────────────┼─────────────────────┼──────┼────────┼────────────┤   │
│  │ BERT: Pre-tr...│ Devlin, Chang...    │ 2018 │ [DOI]  │ 5 days ago │   │
│  ├────────────────┼─────────────────────┼──────┼────────┼────────────┤   │
│  │ Chain-of-Tho...│ Wei, Wang...        │ 2022 │ [arXiv]│ 1 week ago │   │
│  └────────────────┴─────────────────────┴──────┴────────┴────────────┘   │
│                                                                           │
│  EMPTY STATE (when no papers):                                            │
│  [Document icon]  No papers yet. Upload a PDF or enter a DOI above.      │
└──────────────────────────────────────────────────────────────────────────┘
```

**Component Notes:**
- `UploadZone`: `div` with `border-2 border-dashed border-gray-300 rounded-lg`. On drag-over: `border-blue-400 bg-blue-50`. Uses HTML5 `ondragover`/`ondrop` + hidden `<input type="file" accept=".pdf" multiple>`. Clicking the zone triggers the hidden input.
- `UploadFileItem`: flex row. Left: PDF icon + filename (`text-sm font-medium text-gray-700`) + size (`text-xs text-gray-400`). Right: remove/status icon. Below: `Progress` component (`value={0-100}`), status text. States: `idle`, `uploading`, `success`, `error`. Success: green checkmark icon. Error: red X icon + `Alert` component with error text.
- `DOISection`: label, `Textarea` (shadcn), then `Button variant="default"` labeled "Fetch & Store". Full width. Below the button show a `Spinner` inline while fetching.
- `StatusBar`: `div` with `text-sm text-gray-600`, flex, gap-4, items separated by `·`. DB connection indicator: green dot `w-2 h-2 rounded-full bg-green-500 inline-block` or red if disconnected.
- `PaperTable` on `/upload`: no checkboxes, no abstract, no bulk actions. Columns: Title (max-w truncate), Authors (max-w truncate), Year, SourceBadge, Date Added. Table has `divide-y divide-gray-200`. Rows hover: `hover:bg-gray-50`.
- Error state examples:
  - Invalid file: inline `text-xs text-red-500` under file item.
  - Duplicate: `Alert variant="warning"` with title "Duplicate paper" and paper title.
  - Fetch failed: `Alert variant="destructive"` with the DOI that failed.

---

### 3. /query — Research Query / Search

**Route:** `/query`
**Purpose:** Primary research interface. Professors enter a question; the system searches local DB, optionally fetches external papers, and returns a structured literature review.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ NAVBAR                                                                    │
│ [Logo]   Dashboard   Upload   [Query ←active]   Library   [● Connected]  │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  Research Query                                                           │
│  Ask a question across your paper library                                  │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │ SEARCH FORM CARD                                                  │   │
│  │                                                                   │   │
│  │  What would you like to research?                                 │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │ Textarea (rows=4)                                           │ │   │
│  │  │ placeholder: "e.g. What are the key differences between     │ │   │
│  │  │ transformer-based and RNN-based language models?"           │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │                                                                   │   │
│  │  [Search Papers]  Button (primary, px-6 py-2, float right)        │   │
│  │  Hint: "Your query will first search 47 local papers."            │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ─── LOADING STATE (shown while processing) ───────────────────────────  │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │ LOADING STEPS CARD                                                │   │
│  │                                                                   │   │
│  │  [✓] Searching local database...                 [green checkmark]│   │
│  │      Found 8 relevant papers                                      │   │
│  │                                                                   │   │
│  │  [○] Fetching additional papers from Semantic Scholar...  [spinner]│  │
│  │      (only shown if local results are insufficient)               │   │
│  │                                                                   │   │
│  │  [○] Generating literature review...              [spinner]       │   │
│  │                                                                   │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ─── RESULTS (shown after loading completes) ──────────────────────────  │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │ RESULTS PANEL                                                     │   │
│  │                                                                   │   │
│  │  [Summary] [Agreements] [Contradictions] [Research Gaps] [Cit...]│   │
│  │  ──────────────────────────────────────────────────────────────   │   │
│  │                                                                   │   │
│  │  TAB: Summary                                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │ Prose paragraph summarizing the state of research on the    │ │   │
│  │  │ topic across all cited papers. 2-4 sentences minimum.       │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │                                                                   │   │
│  │  TAB: Agreements                                                  │   │
│  │  • Bullet point 1 — key consensus finding [1][3]                 │   │
│  │  • Bullet point 2 — another agreed finding [2]                   │   │
│  │                                                                   │   │
│  │  TAB: Contradictions                                              │   │
│  │  • Paper A claims X while Paper B claims Y [1][4]                │   │
│  │                                                                   │   │
│  │  TAB: Research Gaps                                               │   │
│  │  • No study has examined Z in context of Y                       │   │
│  │                                                                   │   │
│  │  TAB: Citations (N)                                               │   │
│  │  ┌────────────────────────────────────────────────────────────┐  │   │
│  │  │ [1] Attention Is All You Need                   [Local]    │  │   │
│  │  │     Vaswani et al. · 2017 · DOI: 10.48550/...             │  │   │
│  │  ├────────────────────────────────────────────────────────────┤  │   │
│  │  │ [2] Language Models are Few-Shot Learners     [External]   │  │   │
│  │  │     Brown et al. · 2020 · arXiv: 2005.14165               │  │   │
│  │  └────────────────────────────────────────────────────────────┘  │   │
│  │                                                                   │   │
│  │  [View Full Review →]  links to /results/[id]                     │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ─── EMPTY STATE (before any query) ───────────────────────────────────  │
│  [Magnifier icon — 64px, text-gray-300]                                   │
│  Ask a research question above to get started.                            │
│  Your results will appear here.                                           │
│                                                                           │
│  ─── ERROR STATE ───────────────────────────────────────────────────────  │
│  [Alert variant="destructive"]                                            │
│  Search failed: Unable to connect to the research pipeline.               │
│  [Try Again] button                                                       │
└──────────────────────────────────────────────────────────────────────────┘
```

**Component Notes:**
- `SearchForm`: `Card` wrapping a `label` + `Textarea` (4 rows) + `Button`. The button text changes: default "Search Papers", loading "Searching..." (disabled, with `Spinner` inline).
- `LoadingSteps`: shown only when `isLoading === true`. Each `LoadingStep` has: icon (checkmark `text-green-500` when done, `Spinner` when active, circle outline when pending), label text, optional sub-text. The "Fetching external papers" step is conditionally rendered based on whether external search is triggered.
- `ResultsPanel`: `Card` with `Tabs` (shadcn). Tab labels include the count in parentheses where relevant (e.g. "Citations (12)"). Content uses `TabsContent` for each section.
- Inline citation refs like `[1]` are superscript spans: `<sup className="text-blue-600 font-semibold cursor-pointer hover:underline">`.
- `CitationCard` (in Citations tab): flex row. Left: index number in `w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold`. Middle: title (`text-sm font-semibold`), authors + year (`text-xs text-gray-500`), DOI/link (`text-xs text-blue-500 hover:underline`). Right: `SourceBadge`.
- `EmptyState`: centered column, icon (gray), h3 title, p description, optional action button.

---

### 4. /library — Paper Library

**Route:** `/library`
**Purpose:** Full, searchable, filterable view of all ingested papers with management capabilities.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ NAVBAR                                                                    │
│ [Logo]   Dashboard   Upload   Query   [Library ←active]   [● Connected]  │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  Paper Library                                  47 papers                 │
│  Browse and manage your ingested research papers                           │
│                                                                           │
│  TOOLBAR                                                                  │
│  ┌──────────────────────────────────────┐  ┌────────┐  ┌────┐  ┌──────┐ │
│  │ Search papers...         [search icon]│  │ Source▼│  │From│  │  To  │ │
│  └──────────────────────────────────────┘  └────────┘  └────┘  └──────┘ │
│  [Delete Selected (3)]  ← only visible when checkboxes selected           │
│                                                                           │
│  TABLE                                                                    │
│  ┌──┬──────────────────┬──────────────┬──────┬────────┬────────────────┐ │
│  │☐ │ Title            │ Authors      │ Year │ Source │ Abstract       │ │
│  ├──┼──────────────────┼──────────────┼──────┼────────┼────────────────┤ │
│  │☑ │ Attention Is All │ Vaswani +4   │ 2017 │ [PDF]  │ The dominant   │ │
│  │  │ You Need         │              │      │        │ sequence tran..│ │
│  ├──┼──────────────────┼──────────────┼──────┼────────┼────────────────┤ │
│  │☐ │ BERT: Pre-train..│ Devlin +3    │ 2018 │ [DOI]  │ We introduce a │ │
│  │  │                  │              │      │        │ new language...│ │
│  ├──┼──────────────────┼──────────────┼──────┼────────┼────────────────┤ │
│  │☐ │ Chain-of-Thought  │ Wei +5      │ 2022 │ [arXiv]│ We explore how │ │
│  │  │ Prompting        │              │      │        │ generating a...│ │
│  └──┴──────────────────┴──────────────┴──────┴────────┴────────────────┘ │
│                                   [View] [Delete] ← row action icons      │
│                                                                           │
│  PAGINATION                                                               │
│  Showing 1-20 of 47     [< Prev]  [1] [2] [3]  [Next >]                  │
│                                                                           │
│  EMPTY STATE (when no papers or no filter matches):                       │
│  [Stack-of-docs icon — 64px, text-gray-300]                               │
│  No papers found.                                                         │
│  [Upload Papers] button (primary, links to /upload)                       │
└──────────────────────────────────────────────────────────────────────────┘
```

**Component Notes:**
- `LibraryToolbar`: flex row, `gap-3`, wraps on mobile. Search `Input` is `flex-1`. Source `Select` has options: All Sources, PDF, DOI, arXiv. Year inputs: two small `Input type="number"` with `placeholder="From"` / `placeholder="To"`, `w-20` each. `BulkDeleteButton`: `Button variant="destructive"` only visible (`opacity-100`) when `selectedCount > 0`, shows count in label.
- `PaperLibraryRow`: Title is `text-sm font-medium text-gray-900 max-w-xs truncate`. Authors truncated: show first author + "+N" if more than 1. Abstract: `text-xs text-gray-500 max-w-sm truncate` (first 120 chars). Row actions appear on `group-hover` of the row (`opacity-0 group-hover:opacity-100`): eye icon (view) + trash icon (delete), both `Button variant="ghost" size="icon"`.
- Delete triggers a `Dialog` confirmation: "Delete this paper? This action cannot be undone." with Cancel / Delete (destructive) buttons.
- Bulk delete: `Dialog` confirmation listing count: "Delete 3 papers?".
- Pagination: `flex items-center gap-2`. Page number buttons: `Button variant="outline" size="sm"`, active page: `Button variant="default" size="sm"`.
- Checkboxes: shadcn `Checkbox`. Header checkbox = select all / deselect all. Row checkbox state tracked in array of selected paper IDs.
- Loading state: show 5 `SkeletonRow` components while fetching.

---

### 5. /results/[id] — Literature Review Detail

**Route:** `/results/[id]` (e.g. `/results/abc123`)
**Purpose:** Full-page view of a saved literature review with export capabilities.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ NAVBAR                                                                    │
│ [Logo]   Dashboard   Upload   Query   Library   [● Connected]             │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  DETAIL HEADER                                                            │
│  [← Back to Query]                                                        │
│                                                                           │
│  "What are the key differences between transformer and RNN architectures?"│
│  Generated on April 11, 2026 · 12 papers cited                           │
│                                                                           │
│  [Copy to Clipboard]  [Export Markdown]  [Export PDF]                     │
│                                                                           │
│  ─────────────────────────────────────────────────────────────────────   │
│                                                                           │
│  ┌────────────────────────────────────────────┬─────────────────────┐   │
│  │ MAIN CONTENT                               │ CITED PAPERS        │   │
│  │ (flex-1)                                   │ (w-72, sticky top-8)│   │
│  │                                            │                     │   │
│  │  ## Summary                                │ Cited Papers (12)   │   │
│  │  ┌──────────────────────────────────────┐  │ ─────────────────── │   │
│  │  │ Full prose summary paragraph(s).     │  │ [1] Attention Is... │   │
│  │  │ References papers inline via [1][2]  │  │     Vaswani · 2017  │   │
│  │  └──────────────────────────────────────┘  │     [Local]         │   │
│  │                                            │                     │   │
│  │  ## Key Agreements                         │ [2] Language Models │   │
│  │  • Finding one [1][3]                      │     Brown · 2020    │   │
│  │  • Finding two [2]                         │     [External]      │   │
│  │  • Finding three [1][4]                    │                     │   │
│  │                                            │ [3] BERT: Pre-tr... │   │
│  │  ## Contradictions                         │     Devlin · 2018   │   │
│  │  • Paper A claims X [1], Paper B Y [4]     │     [Local]         │   │
│  │                                            │                     │   │
│  │  ## Research Gaps                          │ ... (scrollable)    │   │
│  │  • Area not yet studied                    │                     │   │
│  │  • Longitudinal studies needed             │                     │   │
│  │                                            │                     │   │
│  └────────────────────────────────────────────┴─────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
```

**Component Notes:**
- `ResultDetailHeader`: `div` with `mb-8`. Back button: `Button variant="ghost"` with `ArrowLeft` icon, links to `/query`. Query text: `text-2xl font-bold text-gray-900`. Meta line: `text-sm text-gray-500`. Export buttons: `Button variant="outline" size="sm"` each, with `Copy`/`FileText`/`Download` icons from `lucide-react`.
- `ResultLayout`: `flex gap-8 items-start`. Main content: `flex-1 min-w-0`. Sidebar: `w-72 shrink-0 sticky top-8 self-start`.
- `ResultSection`: `div` with `mb-8`. Title: h2 styled (`text-xl font-semibold text-gray-900 mb-4`). Content inside `Card p-6`. Bullet lists: `ul` with `space-y-2`, items `text-base text-gray-700`.
- `CitationSidebar`: `Card p-4`. Title: `text-sm font-semibold text-gray-900 mb-4`. List: `space-y-3`, max-height `calc(100vh - 200px)` with `overflow-y-auto`. `CitationSidebarItem`: citation number in small badge, title in `text-xs font-medium text-gray-800 leading-tight`, author + year in `text-xs text-gray-500`, `SourceBadge` inline.
- "Copy to Clipboard" uses the `navigator.clipboard.writeText()` API, copies the full review as plain text. On success: `Toast` "Copied to clipboard!".
- "Export Markdown" triggers a client-side download of a `.md` file generated from the review content.
- "Export PDF" triggers a `window.print()` call with a print stylesheet, or a future backend endpoint.
- Inline citation refs (`[1]`, `[2]`) are clickable: clicking one scrolls to / highlights the corresponding `CitationSidebarItem`.

---

## User Flows

### Flow 1: Professor Uploads a PDF

```
1. Professor navigates to /upload
2. Drags a PDF file onto the UploadZone (or clicks "Browse Files")
3. UploadFileItem appears with filename, size, and progress bar at 0%
4. Progress bar fills as file uploads (mock: simulated progress)
5. On success: progress bar turns green, checkmark icon, "Stored successfully"
6. PaperTable below refreshes to show the new paper in the list
7. StatusBar updates paper count
8. Professor can navigate to /library to see full list
```

**State transitions:** `idle` -> `uploading` (0-99%) -> `success` | `error`

**Error path:** If file is not a PDF: immediately show `error` state with "Only PDF files are supported". If upload fails (server error): show "Upload failed. Please try again." with a retry button.

---

### Flow 2: Professor Fetches a Paper by DOI

```
1. Professor is on /upload
2. Types or pastes DOIs into the DOI/URL textarea (one per line)
3. Clicks "Fetch & Store"
4. Button becomes disabled, shows inline Spinner
5. Success: Toast notification "2 papers fetched and stored successfully"
6. PaperTable refreshes with new papers (source badge: DOI or arXiv)
7. Failed DOI: Alert component shows "Could not fetch: [DOI]. Please verify."
```

**Edge cases:**
- Duplicate DOI: Alert warning "Paper already in library: [title]". Does not add duplicate.
- Invalid format: inline validation before submission, "Invalid DOI format" message.
- Mixed results: some succeed, some fail — show success toast with count, plus error alert for failures.

---

### Flow 3: Professor Runs a Research Query

```
1. Professor navigates to /query
2. Types research question in the Textarea
3. Clicks "Search Papers"
4. SearchForm shows loading state (button disabled, "Searching...")
5. LoadingSteps panel appears below form:
   Step 1: "Searching local database..." — spinner -> checkmark with "Found N relevant papers"
   Step 2 (conditional): "Fetching external papers..." — shown only if local results < threshold
   Step 3: "Generating literature review..." — spinner -> checkmark
6. ResultsPanel fades in with Tabs
7. Summary tab is active by default
8. Professor reads summary, switches to Agreements, Contradictions, Research Gaps
9. Professor clicks Citations tab to see all cited papers with Local/External badges
10. Professor clicks "View Full Review →" to open /results/[id]
```

**Error path:** If pipeline fails at any step, LoadingSteps shows an X on the failed step, ErrorAlert appears below with "Search failed: [reason]. Try Again."

---

### Flow 4: Professor Views, Copies, and Exports a Review

```
1. Professor is on /results/[id] (arrived from /query results panel link)
2. Reads the full structured review in the main content area
3. Uses sidebar to navigate to cited papers (clicks citation number to scroll/highlight)
4. Clicks "Copy to Clipboard" -> Toast: "Copied to clipboard!"
5. Clicks "Export Markdown" -> browser downloads "review-2026-04-11.md"
6. Clicks "Export PDF" -> browser print dialog opens (print-optimized layout)
7. Clicks "← Back to Query" to return to /query with previous query still in the form
```

---

## State & Interaction Notes

### Global State (for Phase 2 mock implementation)

The frontend agent should implement a simple React context or Zustand store with:

```typescript
interface AppState {
  papers: Paper[];              // papers in local DB (mock data)
  queries: QueryResult[];       // past query results (mock data)
  dbStats: {
    paperCount: number;
    dbSizeMB: number;
    isConnected: boolean;
  };
}

interface Paper {
  id: string;
  title: string;
  authors: string[];
  year: number;
  source: 'pdf' | 'doi' | 'arxiv';
  abstract: string;
  dateAdded: string;           // ISO date string
  doi?: string;
  url?: string;
}

interface QueryResult {
  id: string;
  question: string;
  createdAt: string;
  summary: string;
  agreements: string[];
  contradictions: string[];
  researchGaps: string[];
  citations: Citation[];
}

interface Citation {
  index: number;
  title: string;
  authors: string[];
  year: number;
  source: 'local' | 'external';
  doi?: string;
  url?: string;
}
```

### Navbar Active State

The `NavLink` component checks `usePathname()` to apply active styling:
- Active: `text-blue-600 font-semibold border-b-2 border-blue-600`
- Inactive: `text-gray-600 hover:text-gray-900`

### Responsive Breakpoints

| Layout           | Mobile (<768px)        | Desktop (>=768px)          |
|------------------|------------------------|----------------------------|
| Navbar           | Hamburger menu         | Horizontal links           |
| Stats Grid       | `grid-cols-2`          | `grid-cols-4`              |
| Recent Activity  | Stacked (1 col)        | Side by side (2 col)       |
| Quick Actions    | Stacked (1 col)        | Side by side (2 col)       |
| Upload + DOI     | Stacked                | Stacked (full width)       |
| Library Table    | Horizontal scroll      | Full table                 |
| Result Layout    | Stacked (main then sidebar) | Two-column side by side |

### Loading Skeletons

Every data-fetching view must have a loading skeleton:
- `SkeletonCard`: `div` with `h-24 bg-gray-200 rounded-lg animate-pulse`
- `SkeletonRow`: `div` with `h-12 bg-gray-200 rounded animate-pulse`
- Show 3-5 skeleton rows/cards while data loads

### Toast Notifications

Use shadcn `Toaster` at the root layout level. Toast types:
- Success: `variant="default"` with green icon
- Error: `variant="destructive"`
- Warning: custom styling with amber border

---

## Acceptance Criteria for Phase 1

- [x] `docs/WIREFRAMES.md` exists with all 5 pages documented
- [x] Each page has an ASCII wireframe layout
- [x] Component hierarchy is fully documented (tree format)
- [x] Design system specifies colors, typography, spacing, border-radius, shadows
- [x] shadcn/ui component mapping is documented per feature
- [x] User flows for all 4 major flows are documented with state transitions
- [x] TypeScript interfaces for mock state are defined
- [x] Responsive breakpoints are specified
- [x] Loading, error, and empty states are defined for every page
- [x] Frontend agent can implement without asking questions

---

*End of Phase 1 — UI/UX Wireframes. Ready for Phase 2: Frontend Implementation.*
