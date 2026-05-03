/**
 * The capabilities phi currently has registered.
 *
 * Just the names. Hand-synced from `bot/src/bot/tools/*.py`. Once the bot
 * exposes `/api/abilities`, this is replaced by a fetch — meaningful
 * descriptions, real grouping, and the operator-only flag arrive then.
 *
 * No invented categories. No source-file leakage. The names are what they
 * are.
 *
 * Skills are a different surface (load-on-demand SKILL.md packs) and live
 * elsewhere — they don't belong here.
 */

export const CAPABILITIES: string[] = [
	'changelog',
	'check_relays',
	'check_services',
	'check_urls',
	'create_feed',
	'delete_feed',
	'drop_observation',
	'follow_user',
	'get_own_posts',
	'get_trending',
	'like_post',
	'list_blog_posts',
	'list_feeds',
	'list_goals',
	'manage_labels',
	'manage_mentionable',
	'note',
	'observe',
	'post',
	'propose_goal_change',
	'publish_blog_post',
	'read_feed',
	'read_timeline',
	'recall',
	'reply_to',
	'repost_post',
	'search_network',
	'search_posts',
	'web_search'
];

/**
 * Operator-gated capabilities — only nate (the bot's owner) can invoke
 * these. This is a real distinction in the source (the `_is_owner` check),
 * not invented.
 */
export const OPERATOR_ONLY: ReadonlySet<string> = new Set([
	'manage_labels',
	'manage_mentionable'
]);
