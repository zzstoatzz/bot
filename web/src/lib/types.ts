// Shape mirrors phi's PDS record schemas + bot API responses.
// Keep in sync with bot/src/bot/core/{goals,observations}.py and the json
// returned by /api/* endpoints.

// --- PDS records ---

export interface Goal {
	rkey: string;
	title: string;
	description: string;
	progress_signal: string;
	created_at: string;
	updated_at: string;
}

export interface Observation {
	rkey: string;
	content: string;
	reasoning: string;
	created_at: string;
}

export interface BlogDoc {
	rkey: string;
	title: string;
	content: string;
	tags: string[];
	publishedAt: string;
	url: string; // greengale.app URL
}

// --- /api/activity (existing endpoint, mixed feed) ---

export type ActivityType = 'post' | 'note' | 'url';

export interface ActivityItem {
	type: ActivityType;
	text: string;
	title?: string | null;
	time: string;
	uri: string;
	url?: string | null;
}

// --- /api/memory/graph ---

export interface GraphNode {
	id: string;
	label: string;
	type: 'phi' | 'user';
	x: number | null;
	y: number | null;
}

export interface GraphEdge {
	source: string;
	target: string;
}

export interface GraphData {
	nodes: GraphNode[];
	edges: GraphEdge[];
}

// --- discovery pool (hub /api/agents/discovery-pool) ---

export interface DiscoveryPost {
	uri: string;
	text: string;
	liked_at: string;
}

export interface DiscoveryEntry {
	handle: string;
	did: string;
	likes_in_window: number;
	last_liked_at: string;
	sample_posts: DiscoveryPost[];
}

// --- /health ---

export interface HealthInfo {
	status: string;
	polling_active: boolean;
	paused: boolean;
}

// --- bsky public API minimal types (used by feed/blog) ---

export interface BskyAuthor {
	did: string;
	handle: string;
	displayName?: string;
	avatar?: string;
}

export interface BskyPostRecord {
	text: string;
	createdAt: string;
	reply?: { parent: { uri: string; cid: string }; root: { uri: string; cid: string } };
	facets?: unknown[];
	embed?: unknown;
}

export interface BskyPost {
	uri: string;
	cid: string;
	author: BskyAuthor;
	record: BskyPostRecord;
	indexedAt: string;
	likeCount?: number;
	replyCount?: number;
	repostCount?: number;
}

export interface BskyFeedItem {
	post: BskyPost;
	reply?: { parent?: { author?: BskyAuthor; record?: BskyPostRecord; uri?: string } };
}
