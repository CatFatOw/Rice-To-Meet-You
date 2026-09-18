/**
 * Single source of truth for the backend origin.
 *
 * Set VITE_API_BASE_URL at build time (Vercel project settings, or the CI build step)
 * to point a deployment at a different backend. Vite inlines this at build time, so it
 * is baked into the published bundle and is not a secret.
 *
 * The fallback targets a local backend so `npm run dev` works with no configuration.
 */
const FALLBACK_BASE_URL = 'http://127.0.0.1:8000';

// Trailing slashes are stripped because every call site builds URLs as
// `${API_BASE_URL}/path`, and a trailing slash would produce a double slash.
export const API_BASE_URL: string = (
	import.meta.env.VITE_API_BASE_URL ?? FALLBACK_BASE_URL
).replace(/\/+$/, '');
