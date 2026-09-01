/// <reference types="@sveltejs/kit" />

/**
 * The whole point of this file is what it does *not* do: it never touches `/api/*`. That is
 * every request a turn makes — sending a message, streaming its events over SSE, resuming one
 * after a permission card, every tool call — and a service worker sitting between a phone and
 * any of that is a bug wearing a feature's clothes. Everything below is scoped to the built
 * shell and the static assets beside it, so installing Hera changes nothing about how a turn
 * behaves; it only makes the shell load once and start faster the next time.
 */
import { build, files, version } from '$service-worker';

declare let self: ServiceWorkerGlobalScope;

const CACHE = `hera-shell-${version}`;
const ASSETS = new Set([...build, ...files]);

self.addEventListener('install', (event) => {
	async function precache() {
		const cache = await caches.open(CACHE);
		await cache.addAll([...ASSETS]);
	}
	event.waitUntil(precache());
});

self.addEventListener('activate', (event) => {
	async function dropStale() {
		for (const key of await caches.keys()) {
			if (key !== CACHE) await caches.delete(key);
		}
	}
	event.waitUntil(dropStale());
});

self.addEventListener('fetch', (event) => {
	if (event.request.method !== 'GET') return;

	const url = new URL(event.request.url);
	if (url.origin !== self.location.origin) return;
	// Never cached, never intercepted: a stale API response is not a smaller version of the
	// same answer, it is a wrong one.
	if (url.pathname.startsWith('/api/')) return;

	async function respond(): Promise<Response> {
		const cache = await caches.open(CACHE);

		if (ASSETS.has(url.pathname)) {
			const cached = await cache.match(url.pathname);
			if (cached) return cached;
		}

		try {
			const response = await fetch(event.request);
			// Only a real, complete response is worth keeping — an opaque or error response
			// cached here would be served back as if it were the real thing.
			if (response.status === 200) cache.put(event.request, response.clone());
			return response;
		} catch (cause) {
			const cached = await cache.match(event.request);
			if (cached) return cached;
			throw cause;
		}
	}

	event.respondWith(respond());
});
