import { expect, test } from 'bun:test';
import { parseToolUsage } from '../../web/src/lib/tool-usage';

const tool = {
 name: 'read_memory', requests: 2, runs: 1, calls: 0,
 returned: 0, raised: 0, unfinished: 0, last_called: null
};
const snapshot = { since: null, window_days: 30, tools: [tool], recent: [] };

test('old snapshots still render; unused tools can link to an offered run', () => {
 expect(parseToolUsage(snapshot).tools[0]?.offeredTraceUrl).toBeNull();
 const url = 'https://logfire-us.pydantic.dev/waow/phi/?q=trace';
 const parsed = parseToolUsage({ ...snapshot, tools: [{ ...tool, last_offered_trace_url: url }] });
 expect(parsed.tools[0]?.offeredTraceUrl).toBe(url);
 expect(parsed.tools[0]?.calls).toBe(0);
});

test('offered trace links reject executable URL schemes at the boundary', () => {
 expect(() => parseToolUsage({ ...snapshot, tools: [{ ...tool, last_offered_trace_url: 'javascript:alert(1)' }] })).toThrow();
});
