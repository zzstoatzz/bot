import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
	// PHI_API points the dev proxy at another phi, e.g. https://phi.zzstoatzz.io
	const api = loadEnv(mode, '.', 'PHI_').PHI_API ?? 'http://localhost:8000';
	return {
		plugins: [sveltekit()],
		server: {
			// proxy bot's /api/* in dev so we can use relative URLs in fetch()
			proxy: {
				'/api': { target: api, changeOrigin: true },
				'/health': { target: api, changeOrigin: true }
			}
		}
	};
});
