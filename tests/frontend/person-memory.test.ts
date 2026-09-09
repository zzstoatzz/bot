import { expect, test } from 'bun:test';
import { memoryDate, exchangePreview } from '../../web/src/lib/person-memory';

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
	expect(exchangePreview('a note without a role')).toBe('a note without a role');
	expect(content).toBe('user: Can you read this?\nbot: Yes.');
});
