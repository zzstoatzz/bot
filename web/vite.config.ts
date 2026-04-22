import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		// proxy bot's /api/* in dev so we can use relative URLs in fetch()
		proxy: {
			'/api': 'http://localhost:8000',
			'/health': 'http://localhost:8000'
		}
	}
});
