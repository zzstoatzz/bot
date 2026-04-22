// Mirror of bot/utils/time.py:relative_when — same granularity slide.
// Renders an ISO timestamp as 'Ns/m/h/d/mo/y ago'.

export function relativeWhen(iso: string | null | undefined): string {
	if (!iso) return '';
	const ts = Date.parse(iso);
	if (Number.isNaN(ts)) return '';
	const delta = (Date.now() - ts) / 1000;
	if (delta < 0) return '';
	if (delta < 60) return `${Math.floor(delta)}s ago`;
	if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
	if (delta < 86400) {
		const h = delta / 3600;
		return h < 10 ? `${h.toFixed(1)}h ago` : `${Math.floor(h)}h ago`;
	}
	const days = delta / 86400;
	if (days < 30) {
		return days < 10 ? `${days.toFixed(1)}d ago` : `${Math.floor(days)}d ago`;
	}
	if (days < 365) return `${Math.floor(days / 30)}mo ago`;
	return `${Math.floor(days / 365)}y ago`;
}
