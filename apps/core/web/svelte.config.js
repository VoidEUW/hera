import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/**
 * Built into the API's static directory, so one process serves one origin and there is no CORS
 * to configure (ADR 6). `fallback` makes it a single-page application: /chat/<uuid> is a real
 * URL to the browser and an unknown file to the server, and the fallback is what turns the
 * second into the first.
 *
 * @type {import('@sveltejs/kit').Config}
 */
export default {
	preprocess: vitePreprocess(),
	kit: {
		adapter: adapter({
			pages: '../src/hera_core/static',
			assets: '../src/hera_core/static',
			fallback: 'index.html',
			precompress: false,
			strict: true
		}),
		alias: { $lib: 'src/lib' }
	}
};
