// Historical memory rows used naive UTC timestamps; newer rows include an offset.
export function memoryDate(iso: string | null): string {
	if (!iso) return 'date unavailable';
	const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(iso) ? iso : `${iso}Z`;
	const date = new Date(normalized);
	if (Number.isNaN(date.getTime())) return 'date unavailable';
	return new Intl.DateTimeFormat('en-US', {
		timeZone: 'America/Chicago', month: 'short', day: 'numeric', year: 'numeric'
	}).format(date);
}

export function exchangePreview(content: string): string {
	return content.split('\n')[0].replace(/^user: /, '') || 'Open saved exchange';
}
