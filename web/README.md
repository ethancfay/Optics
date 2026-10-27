# Optics — Dashboard (`web/`)

A static Vite + React + TypeScript single-page app. It reads only four
precomputed, same-origin JSON files from `public/data/` and makes no
other runtime network requests.

## Commands

```bash
npm install      # install pinned dependencies
npm run dev      # start the Vite dev server
npm run build    # type-check (tsc -b) then produce the production build
npm run preview  # preview the production build locally
npm run test     # run the Vitest suite once (vitest --run)
```

## Deployment (Vercel)

This app is deployed on Vercel. **The Vercel project root directory must be set
to `web`** (Project Settings → General → Root Directory → `web`). Vercel then
builds from this folder and serves the `dist/` output.

`vercel.json` rewrites every path to `/index.html` so client-side routes
(react-router v6 `BrowserRouter`) resolve correctly on direct entry and refresh.

## Layout

```
web/
  public/data/      # the four same-origin data files (served at /data/*)
  src/
    components/     # shared UI + visualizations
    data/           # JSON contract types, validators, pure logic, providers
    pages/          # routed pages
    styles/         # palette + page styles
    test/           # test setup (jsdom + Testing Library + jest-dom)
  index.html
  vite.config.ts
  vitest.config.ts  # jsdom test environment
  vercel.json       # SPA rewrite to /index.html
```

## Tooling

- Build/dev: Vite + `@vitejs/plugin-react`
- Routing: `react-router-dom` v6 (`BrowserRouter`)
- Map projection: `d3-geo` (no map tiles)
- Tests: Vitest (jsdom) + `@testing-library/react` + `@testing-library/jest-dom`
  + `fast-check`

All dependencies are pinned to exact versions (no `^`/`~` ranges).
