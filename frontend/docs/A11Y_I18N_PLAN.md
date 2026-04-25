## Accessibility and i18n Plan

### Accessibility baseline (WCAG 2.1 AA)

- Use semantic elements and ARIA labels for icon-only controls.
- Ensure keyboard navigation for dashboards/charts/forms.
- Add visible focus states and skip-to-content link.
- Validate color contrast for status badges and charts.
- Add screen-reader friendly error summaries on forms.

### i18n rollout

1. Introduce i18n framework (react-i18next) with `en` default locale.
2. Externalize UI copy from `src/pages` and shared components.
3. Add locale switcher persisted in local storage.
4. Handle date/number formatting via Intl APIs.
5. Add pseudo-locale checks in CI to catch hard-coded strings.

### Definition of done

- Lighthouse accessibility score >= 90 on key pages.
- At least `en` + one additional locale configured.
- Error and empty states localized.
