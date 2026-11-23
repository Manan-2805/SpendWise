# Frontend rules (applies inside frontend/)
- Work only inside frontend/. If the API must change, stop and ask me. That is a separate session.
- Use an existing maintained library or shadcn component before writing custom code.
  Note each exception in docs/CHANGELOG_AI.md.
- TypeScript strict, no `any`. Server data lives in TanStack Query only.
- Never store tokens in localStorage. Follow the backend's cookie and origin rules.
- Every screen: keyboard accessible, visible focus, good contrast, mobile first.
- Tests with every feature: Vitest and Testing Library, plus Playwright for key flows.
## Commands
(Fill in after the foundation session.)
