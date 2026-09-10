import type { Capability, Skill } from './types';

function entries(value: unknown): Record<string, unknown>[] {
	if (!Array.isArray(value)) throw new Error('Invalid capability inventory');
	return value.map((item) => {
		if (!item || typeof item !== 'object' || Array.isArray(item))
			throw new Error('Invalid capability entry');
		return Object.fromEntries(Object.entries(item));
	});
}
function text(value: unknown): string {
	if (typeof value !== 'string') throw new Error('Invalid capability text');
	return value;
}
export function parseCapabilities(value: unknown): Capability[] {
	return entries(value).map((entry) => {
		if (typeof entry.operator_only !== 'boolean')
			throw new Error('Invalid authorization marker');
		return {
			name: text(entry.name),
			description: text(entry.description),
			operator_only: entry.operator_only,
		};
	});
}
export function parseSkills(value: unknown): Skill[] {
	return entries(value).map((entry) => {
		if (!Array.isArray(entry.resources))
			throw new Error('Invalid skill resources');
		return {
			name: text(entry.name),
			description: text(entry.description),
			resources: entry.resources.map(text),
		};
	});
}
