import { expect, test } from 'bun:test';
import { parseCapabilities, parseSkills } from '../../web/src/lib/capabilities';

test('an unavailable or malformed inventory cannot masquerade as an empty list', () => {
	expect(parseCapabilities([])).toEqual([]);
	expect(() => parseCapabilities({ error: 'unavailable' })).toThrow();
	expect(() =>
		parseSkills([
			{ name: 'self-traces', description: 'Read history', resources: null },
		]),
	).toThrow();
});
test('authorization markers survive parsing and cannot be inferred from truthy strings', () => {
	const tool = {
		name: 'request_workflow',
		description: 'Request work',
		operator_only: true,
	};
	expect(parseCapabilities([tool])).toEqual([tool]);
	expect(() =>
		parseCapabilities([{ ...tool, operator_only: 'false' }]),
	).toThrow();
});
