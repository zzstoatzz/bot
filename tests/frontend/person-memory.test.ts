import { expect, test } from 'bun:test';
import {
	memoryDate,
	exchangePreview,
	memorySourceLink,
} from '../../web/src/lib/person-memory';

test('legacy UTC and offset timestamps show the same calendar date', () => {
	expect(memoryDate('2026-09-02T00:30:00')).toBe('Sep 1, 2026');
	expect(memoryDate('2026-09-02T00:30:00Z')).toBe('Sep 1, 2026');
	expect(memoryDate('2026-09-01T19:30:00-05:00')).toBe('Sep 1, 2026');
	expect(memoryDate(null)).toBe('date unavailable');
	expect(memoryDate('nonsense')).toBe('date unavailable');
});

test('preview preserves words and leaves the full stored exchange untouched', () => {
	const content = 'user: Can you read this?\nbot: Yes.';
	expect(exchangePreview(content)).toBe('Can you read this?');
	expect(exchangePreview('a note without a role')).toBe(
		'a note without a role',
	);
	expect(content).toBe('user: Can you read this?\nbot: Yes.');
});

test('memory sources include other lexicons and web evidence without executable links', () => {
	expect(memorySourceLink('at://did:plc:abc/app.bsky.feed.post/123')).toBe(
		'https://bsky.app/profile/did%3Aplc%3Aabc/post/123',
	);
	expect(memorySourceLink('at://did:plc:abc/network.cosmik.card/123')).toBe(
		'https://pdsls.dev/at://did:plc:abc/network.cosmik.card/123',
	);
	expect(memorySourceLink('https://example.com/evidence')).toBe(
		'https://example.com/evidence',
	);
	expect(memorySourceLink('javascript:alert(1)')).toBeNull();
	expect(memorySourceLink('at://incomplete')).toBeNull();
});
