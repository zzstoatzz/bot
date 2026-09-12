# Connection coverage

Verified 2026-09-12 using the hosted MCP at https://semble.fastmcp.app/mcp:
`connections_list_by_user(identifier=<Phi DID>, page=1, limit=100)` returned
3 items, total_count=3, total_pages=1, has_more=false. Paging Phi's PDS
`network.cosmik.connection` records returned 16. The three visible connections
have literal URL endpoints; other stored records include UUID and AT-URI
references. This is an observed difference, not a proof of every missing
record's cause or validity. Recheck current state before citing these counts.

For graph work:

1. Page the PDS connections and the relevant Semble endpoint independently.
2. Resolve AT-URI endpoints through PDS reads and UUID endpoints through the
   discovered card lookup schema. Keep unresolved endpoints explicit.
3. Return counts with scope, observation time, completion status, and a few
   identifying examples. Distinguish stored records, resolved edges, and
   endpoint-visible results.
4. Use the PDS inventory for work requiring the whole stored graph. Do not
   recreate or delete an edge merely because an index query omitted it.

The MCP's executable metadata search and stateless execute tools are already
available. Updating those tools does not itself repair Semble's backend index.
