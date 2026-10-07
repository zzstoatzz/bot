export interface AtlasPreview {
	generated_at: string | null;
	point_count: number;
	group_count: number;
	/** x and y in the unit square, then the record kind */
	dots: readonly (readonly [number, number, string])[];
}

function count(value: unknown): number {
	if (typeof value !== 'number' || !Number.isFinite(value) || value < 0)
		throw new Error('Invalid atlas preview count');
	return value;
}

export function parseAtlasPreview(value: unknown): AtlasPreview {
	if (!value || typeof value !== 'object')
		throw new Error('Invalid atlas preview');
	const { generated_at, point_count, group_count, dots } = Object.fromEntries(
		Object.entries(value),
	);
	if (!Array.isArray(dots)) throw new Error('Invalid atlas preview dots');
	return {
		generated_at: typeof generated_at === 'string' ? generated_at : null,
		point_count: count(point_count),
		group_count: count(group_count),
		dots: dots.map((dot: unknown) => {
			if (!Array.isArray(dot)) throw new Error('Invalid atlas preview dot');
			const [x, y, kind] = dot;
			if (
				typeof x !== 'number' ||
				typeof y !== 'number' ||
				typeof kind !== 'string'
			)
				throw new Error('Invalid atlas preview dot');
			return [x, y, kind] as const;
		}),
	};
}
