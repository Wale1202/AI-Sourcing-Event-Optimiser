# AI Sourcing Event Optimiser — Frontend

React + TypeScript + Vite + Tailwind CSS dashboard for the AI Sourcing Event
Optimiser. Talks to the FastAPI backend over `/api/v1`.

## Requirements
- Node.js 18+
- The backend running on http://127.0.0.1:8000 (see `../backend/README.md`)

## Setup

```bash
cd frontend
npm install
cp .env.example .env    # optional — only if you want to point at a non-default backend
npm run dev
```

The dev server runs at http://127.0.0.1:5173.

## Scripts
- `npm run dev` — Vite dev server with HMR
- `npm run build` — type-check + production build to `dist/`
- `npm run preview` — serve the built `dist/`
- `npm run typecheck` — `tsc -b --noEmit`

## Project layout

```
frontend/
├── index.html
├── vite.config.ts
├── tailwind.config.js
└── src/
    ├── main.tsx         React entry + router
    ├── App.tsx          route table
    ├── api/             axios client + one module per resource
    ├── types/           TypeScript shapes mirroring backend schemas
    ├── components/      shared primitives (Button, Card, Input, …)
    └── pages/           one component per route
```

## Pages

| Route | Page | Purpose |
| ----- | ---- | ------- |
| `/` | Dashboard | List sourcing events; entry point to create new ones |
| `/events/new` | Create Event | Form for event metadata + constraints |
| `/events/:id` | Event Detail | Manage suppliers and bids for an event |
| `/events/:id/optimise` | Optimisation | Run the CP-SAT solver, view allocation + explanation |
| `/briefs` | Brief Assistant | Parse a natural-language brief into draft event fields |

All pages handle loading and error states. The Brief Assistant can hand its
draft to the Create Event form via the router's location state — the buyer
always sees the prefilled fields and confirms before submission.

## Configuration

The backend URL is read from `VITE_API_URL` at build time, defaulting to
`http://127.0.0.1:8000`. To point at a different backend (e.g. a deployed
preview), set it in `.env`.
