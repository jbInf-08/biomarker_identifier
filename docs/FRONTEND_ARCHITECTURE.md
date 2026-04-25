## Frontend Architecture

This document captures the React frontend structure and the improvements
completed in Weeks 3–4.

### Technology Stack

- React 18 with `react-router-dom` for routing
- Create React App build tooling with Jest + React Testing Library
- Recharts for interactive data visualizations
- Tailwind‑style utility classes for layout and styling

### Structure

- `src/pages/`
  - `Dashboard.js` – real‑time overview of analysis runs and key metrics
  - `DataUpload.js` – drag‑and‑drop, validated upload for expression/label files
  - `Results.js` – biomarker tables, filters, and rich visualizations
  - `ClinicalAnnotation.js`, `PipelineMonitoring.js`, `Reports.js`, `Login.js`
- `src/components/`
  - `Layout/` – `Layout`, `Header`, `Sidebar`, `ProtectedRoute`, `MobileLayout`
  - `Visualizations/` – charts for biomarkers, pathways, progress tracking
  - `SystemHealthMonitor` – backend and pipeline health indicators
- `src/contexts/`
  - `AuthContext`, `PipelineContext`, `WebSocketContext`
- `src/services/api.js` – typed wrappers around backend HTTP endpoints

### UX, Performance, and Accessibility

- **UX enhancements**
  - Dashboard quick actions and run summaries
  - Rich DataUpload configuration, progress indicators, and toasts
  - Results view with search, basic filtering, and multiple chart types
- **Performance**
  - Lean component composition and memoization of derived values
  - Prepared for route‑level code‑splitting and lazy‑loaded heavy charts
- **Accessibility**
  - Semantic HTML, keyboard‑focusable controls, and ARIA‑friendly components
  - ESLint + CRA accessibility rules, with axe‑style audits planned for CI

### Testing

The frontend uses Jest and React Testing Library (via CRA) for:

- Component‑level tests of pages, layout, and visualization wiring
- Integration‑style tests of key flows (login, upload, analysis navigation)

These are executed in the `frontend-tests` CI job alongside linting, type
checks, and production builds.

