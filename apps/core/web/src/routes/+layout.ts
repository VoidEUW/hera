/**
 * A single-page application: no server-side rendering and no prerendering of routes that need
 * data. The API is the only source of anything, and it is on the same origin (ADR 6).
 */
export const ssr = false;
export const prerender = false;
export const trailingSlash = 'never';
