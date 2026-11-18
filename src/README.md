# Frontend Source

This directory contains the React/Vite frontend application.

## Structure

- `app/`: Route composition and route guards.
- `components`: Accessible, reusable UI primitives.
- `features`: Public, authentication, shell, and product feature pages.
- `lib`: Shared utilities, API client, permissions, and fixtures.
- `services`: Typed feature contracts for every production module.
- `types`: Shared API/domain types.
- `test`: Unit and integration tests.

## Styling

Global styles are in `styles.css` and `home.css`. Component-specific styles are co-located with components.

## Development

Run `npm run dev:web` to start the frontend in development mode.

Ensure the backend is running (see backend README) and set the appropriate `VITE_` environment variables.