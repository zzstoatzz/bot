// Disable SSR — adapter-static would otherwise try to prerender every
// route, including those that fetch from runtime APIs. Pure SPA.
export const ssr = false;
export const prerender = false;
