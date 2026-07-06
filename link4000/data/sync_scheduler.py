"""Automatic synchronization scheduler for all shared Link4000 stores.

The :class:`SyncScheduler` orchestrates synchronization across every shared
store: once at startup, debounced after local changes, on a periodic timer,
and explicitly on graceful exit. It is UI-agnostic and communicates results
through optional callbacks so the GUI can refresh and surface conflicts.
"""

import threading
from typing import Callable, List, Optional

from link4000.data.link_store import LinkStore
from link4000.data.store_registry import StoreRegistry
from link4000.data.sync import ConflictRecord, SyncEngine, SyncResult
from link4000.utils.config import get_sync_config

# Default debounce interval (seconds) used when config omits the value.
_DEFAULT_DEBOUNCE_SECONDS = 5


class SyncScheduler:
    """Drives automatic synchronization for all shared stores.

    The scheduler is robust: each store's sync runs in its own try/except and
    any exception is captured into a synthetic :class:`SyncResult` so a
    disconnected share never crashes the host application.

    Args:
        registry: The :class:`StoreRegistry` whose shared stores are synced.
        on_sync_finished: Optional callback invoked after each sync pass with
            the list of :class:`SyncResult` objects (for UI refresh/status).
        on_conflicts: Optional callback invoked when conflicts were
            encountered, receiving the aggregated list of
            :class:`ConflictRecord` from all stores.
    """

    def __init__(
        self,
        registry: StoreRegistry,
        on_sync_finished: Optional[Callable[[List[SyncResult]], None]] = None,
        on_conflicts: Optional[Callable[[list], None]] = None,
    ) -> None:
        """Initialize the scheduler and its re-entrancy lock."""
        self._registry = registry
        self._on_sync_finished = on_sync_finished
        self._on_conflicts = on_conflicts
        self._lock = threading.Lock()
        self._debounce_timer: Optional[threading.Timer] = None
        self._periodic_timer: Optional[threading.Timer] = None

    # ------------------------------------------------------------------
    # Engine construction
    # ------------------------------------------------------------------
    def _build_engine(self, store: LinkStore) -> SyncEngine:
        """Build a :class:`SyncEngine` for a single shared store.

        The shared file path is taken from ``store.filepath`` (a
        ``pathlib.Path``, converted to ``str``) and the tombstone retention
        comes from the ``[sync]`` configuration.

        Args:
            store: The shared :class:`LinkStore` to build an engine for.

        Returns:
            A configured :class:`SyncEngine` instance.
        """
        config = get_sync_config()
        return SyncEngine(
            local_store=store,
            shared_file_path=str(store.filepath),
            tombstone_retention_days=int(config.get("tombstone_retention_days", 30)),
        )

    # ------------------------------------------------------------------
    # Sync passes
    # ------------------------------------------------------------------
    def startup_sync(self) -> None:
        """Run an initial synchronization pass for every shared store.

        No-op when sync is disabled in configuration. Failures for individual
        stores are captured into the result list rather than raised.
        """
        if not get_sync_config().get("enabled", False):
            return
        results = self._sync_all_stores()
        if self._on_sync_finished is not None:
            self._on_sync_finished(results)

    def notify_local_change(self) -> None:
        """Schedule a debounced synchronization after a local change.

        Repeated calls before the debounce window elapses cancel the pending
        timer and restart it, so only a single sync fires after activity
        settles. The debounce interval comes from ``[sync]
        on_change_debounce_seconds`` (default 5). No-op when sync is disabled.
        """
        if not get_sync_config().get("enabled", False):
            return
        debounce = int(
            get_sync_config().get(
                "on_change_debounce_seconds", _DEFAULT_DEBOUNCE_SECONDS
            )
        )
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(debounce, self._fire_debounced)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _fire_debounced(self) -> None:
        """Clear the pending debounce timer reference and run the sync."""
        with self._lock:
            self._debounce_timer = None
        self._run_sync()

    def _run_sync(self) -> None:
        """Run a synchronization pass for all shared stores.

        Aggregates each store's :class:`SyncResult`, invokes
        ``on_sync_finished``, and - when conflicts were encountered - invokes
        ``on_conflicts`` with the combined conflict list. Per-store errors are
        captured instead of propagating.
        """
        results = self._sync_all_stores()
        if self._on_sync_finished is not None:
            self._on_sync_finished(results)
        if self._on_conflicts is not None:
            all_conflicts: List[ConflictRecord] = []
            for result in results:
                all_conflicts.extend(result.conflicts)
            if all_conflicts:
                self._on_conflicts(all_conflicts)

    def _sync_all_stores(self) -> List[SyncResult]:
        """Synchronize every shared store, isolating per-store failures.

        Returns:
            A list with one :class:`SyncResult` per shared store (synthetic
            results for stores whose sync raised).
        """
        results: List[SyncResult] = []
        for store in self._registry.shared_stores():
            try:
                engine = self._build_engine(store)
                results.append(engine.sync_store())
            except Exception as exc:  # noqa: BLE001 - keep the app alive
                synthetic = SyncResult()
                synthetic.errors.append(f"Sync failed for {store.filepath}: {exc}")
                results.append(synthetic)
        return results

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start_periodic(self) -> None:
        """Start a self-re-arming periodic sync timer for shared stores.

        No-op when sync is disabled or ``sync_interval_minutes`` is not
        positive. The timer fires every ``sync_interval_minutes * 60`` seconds.
        """
        config = get_sync_config()
        if not config.get("enabled", False):
            return
        interval_minutes = int(config.get("sync_interval_minutes", 0))
        if interval_minutes <= 0:
            return
        self._start_periodic_timer(interval_minutes * 60)

    def _start_periodic_timer(self, interval_seconds: int) -> None:
        """(Re)arm the periodic timer for the given interval.

        Args:
            interval_seconds: Period in seconds between sync passes.
        """

        def _tick() -> None:
            self._run_sync()
            self._start_periodic_timer(interval_seconds)

        with self._lock:
            self._periodic_timer = threading.Timer(interval_seconds, _tick)
            self._periodic_timer.daemon = True
            self._periodic_timer.start()

    def stop(self) -> None:
        """Cancel the periodic and pending debounce timers.

        Does not perform a final sync; call :meth:`shutdown_sync` explicitly on
        exit if a final sync is desired.
        """
        with self._lock:
            if self._periodic_timer is not None:
                self._periodic_timer.cancel()
                self._periodic_timer = None
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None

    def sync_now(self) -> List[SyncResult]:
        """Force an immediate synchronization of all shared stores.

        Returns:
            The list of :class:`SyncResult` objects produced.
        """
        results = self._sync_all_stores()
        if self._on_sync_finished is not None:
            self._on_sync_finished(results)
        return results

    def shutdown_sync(self) -> List[SyncResult]:
        """Synchronize all shared stores on application exit.

        Cancels any pending timers first, then performs the sync. Intended to
        be called from a graceful-exit path.

        Returns:
            The list of :class:`SyncResult` objects produced.
        """
        self.stop()
        return self.sync_now()
