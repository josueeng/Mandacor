from __future__ import annotations

import threading
import time

from mandacor.infrastructure.instruments.byk.discovery import DiscoveryChannel
from mandacor.infrastructure.instruments.byk.heartbeat import BykHeartbeat


class _HeartbeatSocket:
    def __init__(self):
        self.sent = 0
        self.closed = False

    def sendto(self, data, address):
        self.sent += 1

    def recvfrom(self, size):
        raise BlockingIOError

    def close(self):
        self.closed = True


def test_heartbeat_start_is_unique_and_stop_is_idempotent():
    udp_socket = _HeartbeatSocket()
    channel = DiscoveryChannel(udp_socket, None, "192.0.2.255", b"query", 6002)
    heartbeat = BykHeartbeat([channel], interval=0.01)
    heartbeat.start()
    first_thread = heartbeat._thread
    heartbeat.start()
    assert heartbeat._thread is first_thread
    time.sleep(0.025)
    heartbeat.stop()
    heartbeat.stop()
    assert not heartbeat.is_running
    assert udp_socket.sent >= 1
    assert udp_socket.closed
    assert not any(
        thread.name == "mandacor-byk-heartbeat" and thread.is_alive()
        for thread in threading.enumerate()
    )

