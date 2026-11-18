# End-to-End Tests

This directory contains Playwright end-to-end tests for the ChapelFlow application.

## Test Files

- `critical-flows.spec.ts`: Tests for critical user journeys (authentication, attendance, etc.)
- `django-integration.spec.ts`: Tests that integrate with the Django backend.
- `intro.spec.ts`: Introduction to Playwright testing.

## Running Tests

To run the E2E tests:

```bash
npm run test:e2e
```

Ensure both the frontend and backend are running, or use the `--project` flag to test against a deployed backend.

## Configuration

See `playwright.config.ts` and `playwright.django.config.ts` for configuration details.