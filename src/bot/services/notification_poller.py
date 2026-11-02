"""Notification poller — drives the notifications batch, daily reflection, and cycle schedules."""

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import logfire

from bot.config import settings
from bot.core import operator_reports
from bot.core.alert_watch import fetch_alert_states, gate_scoped
from bot.core.atproto_client import BotClient
from bot.core.fork_appview import ForkAppView, app_for_uri, fork_views
from bot.core.override import get_override
from bot.core.provider_watch import check_provider_watch
from bot.core.relay_watch import fetch_relay_states, is_relay_key, wake_material
from bot.memory.encounters import ENCOUNTER_NAMESPACE
from bot.services.encounter_recovery import recover_encounters
from bot.services.message_handler import MessageHandler
from bot.services.notification_history import (
    IncompleteNotificationScan,
    visible_unread_notifications,
)
from bot.status import bot_status

logger = logging.getLogger("bot.poller")


def _operator_tz() -> ZoneInfo:
    """ZoneInfo for the operator's clock, falling back to UTC on bad config."""
    try:
        return ZoneInfo(settings.operator_timezone)
    except ZoneInfoNotFoundError:
        logger.warning(
            f"unknown operator_timezone {settings.operator_timezone!r}; "
            "falling back to UTC for schedule"
        )
        return ZoneInfo("UTC")


def _now_local() -> datetime:
    """Current time in the operator's timezone — schedule slots are local hours."""
    return datetime.now(_operator_tz())


MAX_CONCURRENT = 3


class NotificationPoller:
    """Polls for and processes notifications from Bluesky and its forks."""

    def __init__(self, client: BotClient):
        self.client = client
        self.handler = MessageHandler(client)
        self.app_views = fork_views(client)
        self._app_poll_failing: set[str] = set()
        self._running = False
        self._task: asyncio.Task | None = None
        self._recovery_task: asyncio.Task | None = None
        self._processed_uris: set[str] = set()
        self._first_poll = True
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        self._batch_task: asyncio.Task | None = None
        self._background_tasks: set[asyncio.Task] = set()
        self._next_alert_watch_poll = 0.0
        self._next_relay_watch_poll = 0.0
        self._next_provider_watch_poll = 0.0
        self._next_review_poll = 0.0
        self._next_dm_poll = 0.0
        self._dm_task: asyncio.Task | None = None
        self._bio_task: asyncio.Task | None = None
        self._next_bio_refresh = 0.0

    async def start(self) -> asyncio.Task:
        """Start polling for notifications."""
        await self.client.authenticate()
        self._running = True
        bot_status.polling_active = True
        bot_status.record_tick()
        self._task = asyncio.create_task(self._poll_loop())
        self._recovery_task = asyncio.create_task(self._recovery_loop())
        return self._task

    async def stop(self):
        """Stop polling and wait for in-flight handlers to finish."""
        self._running = False
        bot_status.polling_active = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        recovery = getattr(self, "_recovery_task", None)
        if recovery:
            recovery.cancel()
            try:
                await recovery
            except asyncio.CancelledError:
                pass
        if self._background_tasks:
            if self._bio_task:
                self._bio_task.cancel()
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

    async def _recovery_loop(self):
        """Capture visible history independently of actions and UI read flags.

        Five measured pages covered over two months on September 5. Limit each
        traversal to twenty pages; a scan completes on exhaustion or on reaching
        what the last completed scan stored.
        Transport/storage failures retry after five minutes. Structural bounds
        remain visible as incomplete and wait until the next scheduled scan.
        Recovered events never dispatch a backlog of public actions.
        """
        memory = self.handler.agent.memory
        if memory is None:
            logger.error("encounter recovery requires memory storage")
            return
        while self._running:
            delay = 6 * 60 * 60
            try:
                receipt = await recover_encounters(
                    self.client, memory.client, ENCOUNTER_NAMESPACE, max_pages=20
                )
                logger.info(
                    "encounter recovery completed: %s pages, %s deliveries, scan %s",
                    receipt["pages_captured"],
                    receipt["deliveries_captured"],
                    receipt["id"],
                )
            except asyncio.CancelledError:
                raise
            except IncompleteNotificationScan as e:
                logger.warning(f"encounter recovery reached its traversal bound: {e}")
            except Exception:
                logger.exception("encounter recovery incomplete")
                delay = 5 * 60
            await asyncio.sleep(delay)

    async def _poll_loop(self):
        """Main polling loop."""
        await self.client.authenticate()

        bot_status.assume_schedule_ran(datetime.now(UTC))

        while self._running:
            try:
                await self._check_notifications()
            except Exception as e:
                logger.error(f"notification poll error: {e}", exc_info=settings.debug)
                bot_status.record_error()
                await asyncio.sleep(settings.notification_poll_interval)
                continue
            bot_status.record_tick()
            self._schedule_bio_refresh()

            if time.monotonic() >= self._next_dm_poll:
                self._next_dm_poll = time.monotonic() + 30
                if self._dm_task is None or self._dm_task.done():
                    self._dm_task = asyncio.create_task(self._check_operator_messages())
                    self._background_tasks.add(self._dm_task)
                    self._dm_task.add_done_callback(self._background_tasks.discard)

            try:
                if self._should_do_daily_post():
                    task = asyncio.create_task(self._maybe_daily_post())
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
            except Exception as e:
                logger.error(f"daily reflection error: {e}", exc_info=settings.debug)

            try:
                if self._should_run_cycle():
                    task = asyncio.create_task(self._maybe_run_cycle())
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
            except Exception as e:
                logger.error(f"cycle error: {e}", exc_info=settings.debug)

            try:
                if time.monotonic() >= self._next_alert_watch_poll:
                    self._next_alert_watch_poll = (
                        time.monotonic() + settings.alert_poll_interval
                    )
                    await self._check_alert_watch()
            except Exception as e:
                logger.error(f"alert watch poll error: {e}", exc_info=True)

            try:
                if settings.relay_watch_interval > 0 and (
                    time.monotonic() >= self._next_relay_watch_poll
                ):
                    self._next_relay_watch_poll = (
                        time.monotonic() + settings.relay_watch_interval
                    )
                    await self._check_relay_watch()
            except Exception as e:
                logger.error(f"relay watch poll error: {e}", exc_info=True)

            try:
                if settings.provider_watch_interval > 0 and (
                    time.monotonic() >= self._next_provider_watch_poll
                ):
                    self._next_provider_watch_poll = (
                        time.monotonic() + settings.provider_watch_interval
                    )
                    await check_provider_watch()
            except Exception as e:
                logger.error(f"provider watch error: {e}", exc_info=True)

            try:
                if time.monotonic() >= self._next_review_poll:
                    self._next_review_poll = (
                        time.monotonic() + settings.review_poll_interval
                    )
                    await self._check_review_comments()
            except Exception as e:
                logger.error(f"review poll error: {e}", exc_info=True)

            try:
                await asyncio.sleep(settings.notification_poll_interval)
            except asyncio.CancelledError:
                logger.info("notification poller shutting down")
                raise

    def _schedule_bio_refresh(self):
        if bot_status.paused or settings.voice_reset:
            return
        if time.monotonic() < self._next_bio_refresh:
            return
        if self._bio_task and not self._bio_task.done():
            return
        if (wait := bot_status.seconds_until_bio_refresh()) > 0:
            self._next_bio_refresh = time.monotonic() + wait
            return
        self._next_bio_refresh = time.monotonic() + 24 * 60 * 60
        self._bio_task = asyncio.create_task(self._refresh_bio(), name="bio-refresh")
        self._background_tasks.add(self._bio_task)
        self._bio_task.add_done_callback(self._background_tasks.discard)

    async def _refresh_bio(self):
        try:
            async with self._semaphore:
                if bot_status.paused or settings.voice_reset:
                    return
                if (await get_override())["active"]:
                    return
                now = datetime.now(UTC)
                last_review = bot_status.last_profile_review_at
                review_images = last_review is None or now - last_review >= timedelta(
                    days=7
                )
                async with asyncio.timeout(600 if review_images else 180):
                    result = await self.handler.agent.process_bio(
                        review_images=review_images
                    )
                if not result.startswith("bio rewrite failed:"):
                    bot_status.record_bio_refresh(now, review_images)
        except Exception:
            logger.exception("bio refresh failed; keeping the existing profile")

    async def _check_operator_messages(self):
        try:
            if (
                bot_status.paused
                or settings.voice_reset
                or (await get_override())["active"]
            ):
                return
            async with self._semaphore:
                history, ids = await operator_reports.incoming_messages()
                if not ids:
                    return
                material = operator_reports.conversation_material(history, ids)
                result = await self.handler.agent.process_operator_dm(material, ids[-1])
                if result.startswith("operator-dm failed:"):
                    self._next_dm_poll = time.monotonic() + 300
                    logger.error("operator DM run failed; incoming messages retained")
                    return
                operator_reports.mark_messages_handled(ids)
        except Exception as error:
            logger.error("operator DM check failed: %s", type(error).__name__)

    async def _check_review_comments(self):
        """Wake phi for review comments on her pull requests that jetstream
        did not deliver (see core/review_poll.py). One wake per comment,
        dispatched in the background so the poll loop keeps its cadence."""
        import httpx

        from bot.core import review_poll
        from bot.core.ops_log import pull_comment_material

        me = getattr(self.client.client, "me", None)
        if not me or not settings.reviewer_dids:
            return
        async with httpx.AsyncClient() as http:
            comments = await review_poll.new_review_comments(
                me.did, tuple(settings.reviewer_dids), http
            )
        for comment in comments:
            review_poll.mark_handled(comment["uri"])
            handle = comment["did"]
            try:
                profile = self.client.client.app.bsky.actor.get_profile(
                    {"actor": comment["did"]}
                )
                handle = profile.handle or handle
            except Exception as e:
                logger.debug(f"commenter handle lookup failed: {e}")
            material = pull_comment_material(comment["record"], handle)
            logger.info(f"review poll: waking for {comment['uri']}")
            task = asyncio.create_task(self.handler.pull_comment(material))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    async def _check_notifications(self):
        """Check for new notifications and dispatch the whole batch as one task.

        The unit of work is *one poll cycle*. Every unread notification at this
        moment goes into a single batch that the handler processes as one
        cognitive event. This means a chain of replies in a thread, or activity
        across multiple threads, all gets considered together by one agent run
        that decides what (if anything) to do about each item.
        """
        check_time = self.client.client.get_current_time_iso()

        with logfire.span("fetch notifications", check_time=check_time) as fetch_span:
            notifications = await visible_unread_notifications(
                self.client, capture=self.handler.capture_notifications
            )
            for view in self.app_views:
                notifications += await self._app_notifications(view)

            unread = [n for n in notifications if not n.is_read]

            fetch_span.set_attribute("total_count", len(notifications))
            fetch_span.set_attribute("unread_count", len(unread))
            if unread:
                fetch_span.set_attribute(
                    "unread_items",
                    [
                        {
                            "uri": n.uri,
                            "app": app.name
                            if (app := app_for_uri(n.uri))
                            else "bluesky",
                            "cid": getattr(n, "cid", "") or "",
                            "author_handle": n.author.handle,
                            "reason": n.reason,
                            "reason_subject": getattr(n, "reason_subject", None) or "",
                            "indexed_at": str(getattr(n, "indexed_at", "") or ""),
                            "is_read": n.is_read,
                        }
                        for n in unread
                    ],
                )

        # First poll: show initial state
        if self._first_poll:
            self._first_poll = False
            if notifications:
                logger.info(
                    f"found {len(notifications)} notifications ({len(unread)} unread)"
                )
        elif unread:
            logger.info(f"{len(unread)} new notifications")

        # Pausing actions does not stop recording received evidence.
        if bot_status.paused:
            if unread:
                logger.debug(f"paused, skipping {len(unread)} unread notifications")
            return

        # Build the batch from unread notifications phi hasn't already processed
        batch = [n for n in unread if n.uri not in self._processed_uris]
        if not batch:
            return
        self._dispatch_batch(batch, check_time)

    async def _app_notifications(self, view: ForkAppView) -> list:
        """The unread window of one fork app; empty when its AppView can't be read.

        A fork being down, or phi not being a member, must not cost her the
        Bluesky batch, so failures are logged once per outage and skipped.
        """
        name = view.app.name
        try:
            found = await visible_unread_notifications(
                view, max_pages=5, capture=self.handler.capture_notifications
            )
        except Exception as e:
            if name not in self._app_poll_failing:
                logger.warning(f"{name} notifications unavailable: {e}")
            self._app_poll_failing.add(name)
            return []
        if name in self._app_poll_failing:
            logger.info(f"{name} notifications readable again")
            self._app_poll_failing.discard(name)
        return found

    def _dispatch_batch(self, batch: list, check_time: str) -> bool:
        """Start one handler run for *batch*, unless one is already running.

        One cognitive event at a time. On 2026-08-21 three posts in one
        thread arrived ~25s apart, each became a one-item batch, and the
        three runs overlapped — three drafts of the same rewrite, seven
        replies in a minute. While a run is in flight, new notifications
        are left unclaimed (not added to _processed_uris) so the poll after
        it finishes batches them together with whatever else arrived: the
        follow-ups join one run instead of each starting their own.
        """
        if self._batch_task is not None and not self._batch_task.done():
            logger.info(
                f"batch in flight; {len(batch)} notifications wait for the next poll"
            )
            return False
        for n in batch:
            self._processed_uris.add(n.uri)
        task = asyncio.create_task(self._handle_batch_with_semaphore(batch, check_time))
        self._batch_task = task
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        logger.info(f"dispatched batch of {len(batch)} notifications")
        return True

        if len(self._processed_uris) > 1000:
            self._processed_uris = set(list(self._processed_uris)[-500:])

    async def _check_alert_watch(self):
        """Fold the current logfire alert states into phi's incident record.

        Perception only — no dispatch. The [ALERT WATCH] block in agent.py
        renders whatever this accumulates; phi decides in her ordinary runs
        whether anything deserves words.
        """
        states = await fetch_alert_states()
        if states is None:
            return
        incidents, cursor = gate_scoped(
            states,
            bot_status.alert_incidents,
            bot_status.alert_watch_cursor,
            time.time(),
            scope=lambda k: not is_relay_key(k),
        )
        opened = set(incidents) - set(bot_status.alert_incidents)
        closed = [
            k
            for k, v in incidents.items()
            if v.get("closed_ts")
            and not bot_status.alert_incidents.get(k, {}).get("closed_ts")
        ]
        if opened or closed:
            logger.info(
                f"alert watch: {len(opened)} opened {sorted(opened)}, "
                f"{len(closed)} quieted {sorted(closed)}"
            )
        bot_status.alert_incidents = incidents
        bot_status.alert_watch_cursor = cursor
        bot_status._save()

    async def _check_relay_watch(self):
        """Fold relay-eval's behind-the-network verdict into the incident
        record, and wake phi when a watched host newly goes behind.

        Unlike the logfire reconcile this path dispatches: alerts arrive by
        webhook push, but nothing pushes relay regressions — this poll *is*
        the detection. The wake carries the event's content so the run
        starts with recall keyed on the host and its numbers, the way a
        notification run starts with recall keyed on the batch.
        """
        states = await fetch_relay_states()
        if states is None:
            return
        before = bot_status.alert_incidents
        incidents, cursor = gate_scoped(
            states,
            before,
            bot_status.alert_watch_cursor,
            time.time(),
            scope=is_relay_key,
        )
        opened = [
            k
            for k, v in incidents.items()
            if is_relay_key(k)
            and not v.get("closed_ts")
            and (k not in before or before[k].get("closed_ts"))
        ]
        bot_status.alert_incidents = incidents
        bot_status.alert_watch_cursor = cursor
        bot_status._save()
        if opened:
            logger.info(f"relay watch opened {sorted(opened)}")
        if opened and not bot_status.paused:
            await self.handler.alerts(wake_material(incidents, opened))

    async def _handle_batch_with_semaphore(self, batch: list, check_time: str):
        """Handle a notification batch with concurrency limiting.

        Notifications are marked seen AFTER the handler finishes, not at
        dispatch. Marking at dispatch permanently consumed any batch the
        process died holding — on 2026-08-07 a mention landed mid-deploy,
        the poller marked it read, the machine restarted before the run
        replied, and phi never saw the thread. Died-holding batches now
        stay unread and a fresh process re-batches them (the in-memory
        _processed_uris dedup is empty after restart, and within one
        process it prevents re-dispatch between polls). A handler that
        *failed* still marks seen — retrying a poison batch every 10s
        forever is the worse failure; the error is logged and counted.
        """
        async with self._semaphore:
            try:
                await self.handler.handle_batch(batch)
            except Exception as e:
                logger.error(f"batch handler error: {e}", exc_info=settings.debug)
                bot_status.record_error()
            try:
                await self.client.mark_notifications_seen(check_time)
            except Exception as e:
                logger.warning(f"mark_notifications_seen failed: {e}")
            for view in self.app_views:
                if not any(app_for_uri(n.uri) == view.app for n in batch):
                    continue
                try:
                    await view.mark_notifications_seen(check_time)
                except Exception as e:
                    logger.warning(f"{view.app.name} updateSeen failed: {e}")

    def _should_do_daily_post(self) -> bool:
        """Check if it's time for a daily reflection (operator-local hour)."""
        now_local = _now_local()
        if now_local.hour < settings.daily_reflection_hour:
            return False
        if bot_status.paused:
            return False
        last = bot_status.last_daily_reflection_at
        return (
            last is None or last.astimezone(_operator_tz()).date() != now_local.date()
        )

    async def _maybe_daily_post(self):
        """Post a daily reflection."""
        bot_status.record_daily_reflection(datetime.now(UTC))
        logger.info("triggering daily reflection")
        try:
            await self.handler.daily_reflection()
        except Exception as e:
            logger.error(f"daily reflection error: {e}", exc_info=settings.debug)

    def _should_run_cycle(self) -> bool:
        """Check if it's time for a cognitive cycle (operator-local hour).

        One cycle subsumes what used to be three separate scheduled jobs
        (musing / relay check / prefect check). Fires at each
        ``settings.thought_post_hours`` slot, at most once per slot per day.
        """
        now_local = _now_local()
        if bot_status.paused or now_local.hour not in settings.thought_post_hours:
            return False
        last = bot_status.last_cycle_at
        if last is None:
            return True
        last_local = last.astimezone(_operator_tz())
        return (last_local.date(), last_local.hour) != (
            now_local.date(),
            now_local.hour,
        )

    async def _maybe_run_cycle(self):
        """Trigger one cognitive cycle."""
        now_local = _now_local()
        bot_status.record_cycle(now_local)
        # a slot is either a general cycle or a people pass. same rhythm,
        # different attention — see settings.people_pass_hours.
        is_people = now_local.hour in settings.people_pass_hours
        kind = "people pass" if is_people else "cycle"
        logger.info(f"triggering {kind} (local hour {now_local.hour})")
        try:
            await (self.handler.people() if is_people else self.handler.cycle())
        except Exception as e:
            logger.error(f"{kind} error: {e}", exc_info=settings.debug)
