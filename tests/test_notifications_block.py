"""[NEW NOTIFICATIONS] frames a thread the way a person reads it: whose it
is, what it is about, and who brought phi in.

regression (2026-09-02): tagged for a marble-cake recipe four replies into
hailey's "agents on atprotocol" thread, phi answered with the recipe. the
root was the first line of a flat context and nothing marked it as the
frame."""

from bot.agent import _format_notifications_block, _thread_frame

ROOT = "at://did:plc:host/app.bsky.feed.post/3root"


def _entry(
    uri, author, text, root_author="hailey.at", root_text="share what you're building"
):
    return {
        "uri": uri,
        "reason": "mention",
        "author_handle": author,
        "post_text": text,
        "root_uri": ROOT,
        "root_author_handle": root_author,
        "root_text": root_text,
        "thread_context": f"@{root_author}: {root_text}\n@{author}: {text}",
        "indexed_at": "2026-09-02T22:41:00Z",
    }


def test_tag_in_someone_elses_thread_names_the_host():
    e = _entry(
        "at://did:plc:noah/app.bsky.feed.post/3cake",
        "noah.bsky.social",
        "@phi cake recipe?",
    )
    block = _format_notifications_block({e["uri"]: e})
    frame = block.splitlines()[2]
    assert frame.startswith("thread by @hailey.at:")
    assert "share what you're building" in frame
    assert "@noah.bsky.social brought you in" in frame
    assert "the thread is @hailey.at's, not theirs" in frame


def test_tag_in_the_hosts_own_thread_says_so():
    e = _entry(
        "at://did:plc:host/app.bsky.feed.post/3leaf",
        "hailey.at",
        "@phi what do you think?",
    )
    assert (
        _thread_frame(ROOT, [e])
        == 'thread by @hailey.at, their own: "share what you\'re building"'
    )


def test_root_level_mention_has_no_frame():
    e = _entry(ROOT, "hailey.at", "@phi hello")
    assert _thread_frame(ROOT, [e]) == ""


def test_unknown_root_has_no_frame():
    e = _entry(
        "at://did:plc:noah/app.bsky.feed.post/3x",
        "noah.bsky.social",
        "hi",
        root_author="",
    )
    assert _thread_frame(ROOT, [e]) == ""
    assert "thread by" not in _format_notifications_block({e["uri"]: e})


def test_cited_post_shows_its_size_and_thread():
    """regression (2026-10-20): asked to "analyze this thread" with nate's post
    quoted, phi answered from the quoted screenshot alone; the payoff was four
    replies down and nothing in the block said there were replies at all."""
    src = "at://did:plc:devlog/app.bsky.feed.post/3ask"
    cited = "at://did:plc:nate/app.bsky.feed.post/3bee"
    block = _format_notifications_block(
        {
            src: {
                "uri": src,
                "reason": "mention",
                "author_handle": "devlog.test",
                "post_text": "please analyze this thread",
                "root_uri": src,
                "thread_context": "",
            },
            cited: {
                "uri": cited,
                "reason": "cited",
                "cited_by": src,
                "author_handle": "nate.test",
                "post_text": "what? i have been living in ignorance",
                "reply_count": 1,
                "quote_count": 2,
                "thread_context": "@nate.test: what?\n@a2.test: and yet the bee flies anyway",
            },
        }
    )
    assert "(1 reply, 2 quotes)" in block
    assert "    @a2.test: and yet the bee flies anyway" in block
