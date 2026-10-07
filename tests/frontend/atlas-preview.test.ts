import { expect, test } from 'bun:test';
import { parseAtlasPreview } from '../../web/src/lib/atlas-preview';

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
