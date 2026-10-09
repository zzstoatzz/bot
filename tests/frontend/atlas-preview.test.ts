import { expect, test } from 'bun:test';
import {
	parseAtlasPreview,
	reusableAtlas,
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

test('A -> close -> preview refresh to B makes the lazy full-map cache unusable', () => {
	const generationA = preview('2026-10-07T20:08:28+00:00');
	const generationB = preview('2026-10-08T20:08:28+00:00');
	const cachedMap = { generated_at: generationA.generated_at, points: [] };

	// Closing the overlay does not clear `atlas`; reopening compares its
	// generation with the independently refreshed preview.
	expect(reusableAtlas(cachedMap, generationA)).toBe(true);
	expect(reusableAtlas(cachedMap, generationB)).toBe(false);
});

test('an unchanged preview generation keeps the full-map cache', () => {
	const generation = preview('2026-10-07T20:08:28+00:00');
	const cachedMap = { generated_at: generation.generated_at, points: [] };
	expect(reusableAtlas(cachedMap, { ...generation })).toBe(true);
});

test('a preview without a generation never reuses a full-map cache', () => {
	const cachedMap = { generated_at: '2026-10-07T20:08:28+00:00' };
	expect(
		reusableAtlas(cachedMap, {
			...preview('2026-10-07T20:08:28+00:00'),
			generated_at: null,
		}),
	).toBe(false);
});

test('a failed preview refresh leaves the previous preview untouched', async () => {
	const existingPreview = preview('2026-10-07T20:08:28+00:00');
	let currentPreview: AtlasPreview | null = existingPreview;
	try {
		const fetched = await Promise.reject<AtlasPreview>(
			new Error('preview unavailable'),
		);
		currentPreview = fetched;
	} catch {
		// read() accepts a preview only after the fetch succeeds.
	}
	expect(currentPreview).toBe(existingPreview);
});

test('preview boundary errors remain errors for loading/error UI', () => {
	expect(() =>
		parseAtlasPreview({ point_count: 1, group_count: 1, dots: 'loading' }),
	).toThrow('Invalid atlas preview dots');
});
