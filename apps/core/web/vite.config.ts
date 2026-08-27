import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
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
