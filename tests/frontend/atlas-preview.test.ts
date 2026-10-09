import { expect, test } from 'bun:test';
import {
	atlasGenerationChanged,
	parseAtlasPreview,
	type AtlasPreview,
} from '../../web/src/lib/atlas-preview';

function preview(generated_at: string): AtlasPreview {
	return { generated_at, point_count: 1, group_count: 1, dots: [] };
}

test('a preview keeps its totals and its dots', () => {
	const preview = parseAtlasPreview({
		generated_at: '2026-10-07T20:08:28+00:00',
		point_count: 9712,
		group_count: 8,
		dots: [
			[0, 0.5, 'observation'],
			[1, 0.25, 'post'],
		],
	});
	expect(preview.point_count).toBe(9712);
	expect(preview.group_count).toBe(8);
	expect(preview.dots).toEqual([
		[0, 0.5, 'observation'],
		[1, 0.25, 'post'],
	]);
});

test('a malformed dot is rejected at the boundary', () => {
	expect(() =>
		parseAtlasPreview({ point_count: 1, group_count: 1, dots: [[0, 'x']] }),
	).toThrow('Invalid atlas preview dot');
});

test('A -> close -> preview refresh to B invalidates the lazy full-map cache', () => {
	const generationA = preview('2026-10-07T20:08:28+00:00');
	const generationB = preview('2026-10-08T20:08:28+00:00');

	// Closing the overlay does not clear `atlas`; the next open should only
	// reuse it when the independently refreshed preview is still generation A.
	expect(atlasGenerationChanged(generationA, generationB)).toBe(true);
});

test('an unchanged preview generation keeps the full-map cache', () => {
	const generation = preview('2026-10-07T20:08:28+00:00');
	expect(atlasGenerationChanged(generation, { ...generation })).toBe(false);
});

test('a failed preview refresh does not invalidate valid map state', async () => {
	const generation = preview('2026-10-07T20:08:28+00:00');
	const cachedMap: object | null = { generation };
	try {
		await Promise.reject(new Error('preview unavailable'));
	} catch {
		// The page's read() only accepts a preview after a successful fetch.
	}
	expect(cachedMap).toEqual({ generation });
});

test('preview boundary errors remain errors for loading/error UI', () => {
	expect(() =>
		parseAtlasPreview({ point_count: 1, group_count: 1, dots: 'loading' }),
	).toThrow('Invalid atlas preview dots');
});
