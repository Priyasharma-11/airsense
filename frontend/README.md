# AirSense web (Next.js 16)

See the [project README](../README.md). Scripts:

| Command | |
|---|---|
| `npm run dev` | dev server on :3000 (proxies `/api/v1` to `BACKEND_URL`, default `http://127.0.0.1:8000`) |
| `npm run build && npm start` | production build (standalone output) |
| `npm test` | Vitest + React Testing Library |
| `npm run typecheck` · `npx eslint src e2e` | static checks |
| `npx playwright test` | E2E against running API + web |
