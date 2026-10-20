import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [
		sveltekit({
			preprocess: vitePreprocess(),
			/**
			 * Built into the API's static directory, so one process serves one origin and there
			 * is no CORS to configure (ADR 6). `fallback` makes it a single-page application:
			 * /chat/<uuid> is a real URL to the browser and an unknown file to the server, and
			 * the fallback is what turns the second into the first.
			 */
			adapter: adapter({
				pages: '../src/hera_core/static',
				assets: '../src/hera_core/static',
				fallback: 'index.html',
				precompress: false,
				strict: true
			}),
			alias: { $lib: 'src/lib' }
		})
	],
	server: {
		// `npm run dev` talks to a `hera serve` on its usual port, so the interface can be
		// developed with hot reload against the real API rather than against a mock of it.
		proxy: { '/api': 'http://127.0.0.1:8756' }
	},
	test: {
		include: ['src/**/*.test.ts'],
		environment: 'node'
	}
});
