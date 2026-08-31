from __future__ import annotations

import logging
import threading
from typing import Iterable

from mandacor.infrastructure.instruments.byk.discovery import DiscoveryChannel


logger = logging.getLogger(__name__)


class BykHeartbeat:
    def __init__(self, channels: Iterable[DiscoveryChannel], *, interval: float) -> None:
        self._channels = list(channels)
        self._interval = interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        if not self._channels:
            raise ValueError("heartbeat requires at least one discovery channel")
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker,
            name="mandacor-byk-heartbeat",
            daemon=True,
        )
        self._thread.start()

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            for channel in self._channels:
                try:
                    channel.socket.sendto(
                        channel.query, (channel.destination, channel.udp_port)
                    )
                    while True:
                        try:
                            channel.socket.recvfrom(4096)
                        except (BlockingIOError, TimeoutError):
                            break
                except OSError as error:
                    if not self._stop_event.is_set():
                        logger.warning("BYK heartbeat channel failed: %s", error)
            self._stop_event.wait(self._interval)

    def stop(self) -> None:
        self._stop_event.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=max(1.0, self._interval * 2))
        channels, self._channels = self._channels, []
        for channel in channels:
            try:
                channel.close()
            except OSError:
                pass
