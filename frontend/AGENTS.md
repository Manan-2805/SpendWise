# Frontend rules (applies inside frontend/)
- Work only inside frontend/. If the API must change, stop and ask me. That is a separate session.
- Use an existing maintained library or shadcn component before writing custom code.
  Note each exception in docs/CHANGELOG_AI.md.
- TypeScript strict, no `any`. Server data lives in TanStack Query only.
- Never store tokens in localStorage. Follow the backend's cookie and origin rules.
- Every screen: keyboard accessible, visible focus, good contrast, mobile first.
- Tests with every feature: Vitest and Testing Library, plus Playwright for key flows.
## Commands
- From the repository root run `make frontend-install` once, then `make frontend-dev`.
- Run `make frontend-check` for lint, Vitest, strict types, build, contrast, and bundle budgets.
- Run `npm --prefix frontend exec -- playwright install chromium` once, then `make frontend-e2e`.
- Regenerate API types with `make openapi` and `npm --prefix frontend run api:generate`.
