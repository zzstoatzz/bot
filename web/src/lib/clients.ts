/**
 * Per-record-kind viewer registry. Inspired by pdsls's uriTemplates
 * (https://tangled.org/pds.ls/pdsls — credit there).
 *
 * For each kind there's a list of viewers (clients) that can render the
 * record. The first entry is the default; user choice is persisted to
 * localStorage and then becomes the default thereafter.
 *
 * pdsls is included in every list because it's the only viewer that
 * works for every NSID.
 */

import { PHI_DID } from './api';

export type ViewKind = 'profile' | 'post' | 'blog' | 'record';

export interface Viewer {
	id: string;
	label: string;
	domain: string; // for favicon resolution
	url: (args: { handle: string; did?: string; collection?: string; rkey?: string }) => string;
}

const PDSLS: Viewer = {
	id: 'pdsls',
	label: 'pdsls',
	domain: 'pdsls.dev',
	url: ({ handle, did, collection, rkey }) => {
		const subject = handle || did || PHI_DID;
		if (collection && rkey) return `https://pdsls.dev/at/${subject}/${collection}/${rkey}`;
		if (collection) return `https://pdsls.dev/at/${subject}/${collection}`;
		return `https://pdsls.dev/at/${subject}`;
	}
};

const BSKY_PROFILE_VIEWERS: Viewer[] = [
	{
		id: 'bsky',
		label: 'bsky',
		domain: 'bsky.app',
		url: ({ handle }) => `https://bsky.app/profile/${handle}`
	},
	{
		id: 'deer',
		label: 'deer',
		domain: 'deer.social',
		url: ({ handle }) => `https://deer.social/profile/${handle}`
	},
	{
		id: 'blacksky',
		label: 'blacksky',
		domain: 'blacksky.community',
		url: ({ handle }) => `https://blacksky.community/profile/${handle}`
	},
	{
		id: 'witchsky',
		label: 'witchsky',
		domain: 'witchsky.app',
		url: ({ handle }) => `https://witchsky.app/profile/${handle}`
	},
	PDSLS
];

const BSKY_POST_VIEWERS: Viewer[] = [
	{
		id: 'bsky',
		label: 'bsky',
		domain: 'bsky.app',
		url: ({ handle, rkey }) => `https://bsky.app/profile/${handle}/post/${rkey}`
	},
	{
		id: 'deer',
		label: 'deer',
		domain: 'deer.social',
		url: ({ handle, rkey }) => `https://deer.social/profile/${handle}/post/${rkey}`
	},
	PDSLS
];

const BLOG_VIEWERS: Viewer[] = [
	{
		id: 'greengale',
		label: 'greengale',
		domain: 'greengale.app',
		url: ({ handle, rkey }) => `https://greengale.app/${handle}/${rkey}`
	},
	PDSLS
];

const RECORD_VIEWERS: Viewer[] = [PDSLS];

export const VIEWERS_BY_KIND: Record<ViewKind, Viewer[]> = {
	profile: BSKY_PROFILE_VIEWERS,
	post: BSKY_POST_VIEWERS,
	blog: BLOG_VIEWERS,
	record: RECORD_VIEWERS
};

const STORAGE_KEY_PREFIX = 'phi.viewer.';

export function getStoredViewer(kind: ViewKind): string | null {
	if (typeof localStorage === 'undefined') return null;
	try {
		return localStorage.getItem(STORAGE_KEY_PREFIX + kind);
	} catch {
		return null;
	}
}

export function setStoredViewer(kind: ViewKind, id: string) {
	if (typeof localStorage === 'undefined') return;
	try {
		localStorage.setItem(STORAGE_KEY_PREFIX + kind, id);
	} catch {
		/* private mode etc */
	}
}

export function defaultViewer(kind: ViewKind): Viewer {
	const stored = getStoredViewer(kind);
	const viewers = VIEWERS_BY_KIND[kind];
	if (stored) {
		const found = viewers.find((v) => v.id === stored);
		if (found) return found;
	}
	return viewers[0];
}
