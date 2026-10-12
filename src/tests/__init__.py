"""The launcher's unit tests, every one run with the Mac's clock in the same time zone."""

import os
import socket
import time

# The launcher dates its records by the Mac's local date, so the zone is an input like the clock: left to the machine,
# a test written on the Founder's Mac fails wherever the same moment falls on another date, as it does in CI's UTC.
# US Pacific time, where fakes.SUNDAY_RUN is Sunday 16:00, spelled out so that no time zone database is needed.
os.environ["TZ"] = "PST8PDT,M3.2.0,M11.1.0"
time.tzset()

from gr0wthlab import fetch  # noqa: E402

# No unit test may open the network. fetch.send is the launcher's one way onto it, so here it is replaced by a refusal:
# a test that forgets to give a client its own transport fails at once, on any machine. REAL_SEND keeps the real
# function for the one test that checks what it puts on the wire, against a connection class it replaces.
REAL_SEND = fetch.send


def no_network(host, target, headers, timeout, limit, deadline):
    raise AssertionError(f"a unit test tried to open the network: GET https://{host}{target}")


fetch.send = no_network

# Nor may anything else the launcher runs in a unit test: a connection or a name lookup beyond this machine is refused
# at the socket, whatever opened it, and listed here, so a whole run under test shows that it tried none. The boundary
# check's own listeners are local, and stay reachable.
ATTEMPTS: list[object] = []
LOCAL = ("127.0.0.1", "::1", "localhost", "", None)
connect, lookup = socket.socket.connect, socket.getaddrinfo


def refuse(host):
    ATTEMPTS.append(host)
    raise AssertionError(f"a unit test tried to open the network: a connection to {host}")


def local_connect(sock, address):
    if sock.family != socket.AF_UNIX and address[0] not in LOCAL:
        refuse(address[0])
    return connect(sock, address)


def local_lookup(host, *args, **kwargs):
    if host not in LOCAL:
        refuse(host)
    return lookup(host, *args, **kwargs)


socket.socket.connect = local_connect
socket.getaddrinfo = local_lookup
