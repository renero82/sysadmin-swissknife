import ipaddress
import subprocess
import shutil

import pytest

from sysadmin_swissknife.subnet import SubnetInfo, SubnetTree, check, parse_network

N = ipaddress.IPv4Network


def test_parse_forms():
    assert parse_network("192.168.1.0/24") == (N("192.168.1.0/24"), False)
    assert parse_network("192.168.1.0 255.255.255.0") == (N("192.168.1.0/24"), False)
    assert parse_network("192.168.1.0 24") == (N("192.168.1.0/24"), False)
    assert parse_network("192.168.1.0 /24") == (N("192.168.1.0/24"), False)
    assert parse_network(" 10.1.2.3 ") == (N("10.1.2.3/32"), False)
    assert parse_network("10.1.2.3/24") == (N("10.1.2.0/24"), True)
    for bad in ("300.1.1.1/24", "", "10.0.0.0/33", "hello"):
        with pytest.raises(ValueError):
            parse_network(bad)


def test_info_regular_and_edges():
    i = SubnetInfo(N("192.168.0.0/24"))
    assert i.netmask == "255.255.255.0" and i.wildcard == "0.0.0.255"
    assert i.address_range == "192.168.0.0 - 192.168.0.255"
    assert i.usable_range == "192.168.0.1 - 192.168.0.254"
    assert i.hosts == 254
    assert SubnetInfo(N("10.0.0.0/31")).hosts == 2
    assert SubnetInfo(N("10.0.0.0/31")).usable_range == "10.0.0.0 - 10.0.0.1"
    assert SubnetInfo(N("10.0.0.9/32")).hosts == 1
    assert SubnetInfo(N("10.0.0.9/32")).usable_range == "10.0.0.9"
    assert SubnetInfo(N("0.0.0.0/0")).hosts == 2**32 - 2


def test_divide_join_and_layout():
    t = SubnetTree(N("192.168.0.0/24"))
    t.root.divide()
    t.root.children[0].divide()
    assert [str(l.network) for l in t.leaves()] == [
        "192.168.0.0/26", "192.168.0.64/26", "192.168.0.128/25"]
    cells = {(str(n.network), col, first, span) for n, col, first, span in t.join_cells()}
    assert cells == {("192.168.0.0/24", 1, 0, 3), ("192.168.0.0/25", 0, 0, 2)}
    t.root.children[0].join()
    assert [str(l.network) for l in t.leaves()] == ["192.168.0.0/25", "192.168.0.128/25"]


def test_state_roundtrip():
    t = SubnetTree(N("10.0.0.0/16"))
    t.root.divide(); t.root.children[1].divide(); t.root.children[1].children[0].divide()
    state = t.to_state()
    assert SubnetTree.from_state(N("10.0.0.0/16"), state).to_state() == state
    # the 1.0 format (flat list of leaves) is still accepted
    flat = ",".join(str(l.network) for l in t.leaves())
    assert [l.network for l in SubnetTree.from_state(N("10.0.0.0/16"), flat).leaves()] == \
           [l.network for l in t.leaves()]


def test_cannot_divide_32():
    t = SubnetTree(N("10.0.0.1/32"))
    assert not t.root.can_divide
    with pytest.raises(ValueError):
        t.root.divide()


@pytest.mark.parametrize("ip,subnet,status", [
    ("192.168.1.10/32", "192.168.1.0/24", "inside"),
    ("192.168.1.10", "192.168.1.0 255.255.255.0", "inside"),
    ("192.168.2.10/32", "192.168.1.0/24", "outside"),
    ("10.0.0.0/23", "10.0.0.0/24", "partial"),
    ("10.0.0.128/25", "10.0.0.0/24", "inside"),
    ("10.0.0.1", "10.0.0.0/31", "inside"),
    ("8.8.8.8", "0.0.0.0/0", "inside"),
])
def test_check(ip, subnet, status):
    assert check(ip, subnet).status == status


def test_check_notes():
    assert "network address" in check("192.168.1.0", "192.168.1.0/24").notes[0]
    assert "broadcast address" in check("192.168.1.255", "192.168.1.0/24").notes[0]
    assert check("192.168.1.10", "192.168.1.0/24").notes[0] == "usable host 10 of 254"
    r = check("192.168.1.10", "192.168.1.77/24")
    assert r.inside and any("host bits" in n for n in r.notes)


# ------------------------------------------------------------------ IPv6
N6 = ipaddress.IPv6Network


def test_parse_v6():
    assert parse_network("2001:db8::/32") == (N6("2001:db8::/32"), False)
    assert parse_network("2001:db8::1") == (N6("2001:db8::1/128"), False)
    assert parse_network("2001:db8:: 48") == (N6("2001:db8::/48"), False)
    assert parse_network("2001:db8::1/64") == (N6("2001:db8::/64"), True)


def test_info_v6():
    i = SubnetInfo(N6("2001:db8::/64"))
    assert i.hosts == 2**64 and i.hosts_text == "2^64"
    assert i.usable_range == "2001:db8:: - 2001:db8::ffff:ffff:ffff:ffff"
    assert SubnetInfo(N6("2001:db8::1/128")).usable_range == "2001:db8::1"
    assert SubnetInfo(N6("2001:db8::/127")).hosts == 2


def test_divide_nibbles_and_limit():
    t = SubnetTree(N6("2001:db8::/48"))
    t.root.divide(4)
    assert len(t.leaves()) == 16 and str(t.leaves()[1].network) == "2001:db8:0:1000::/52"
    ok, msg = t.can_divide(t.leaves()[0], 16)
    assert not ok and "limit" in msg
    state = t.to_state()
    assert SubnetTree.from_state(N6("2001:db8::/48"), state).to_state() == state
    cells = t.join_cells()
    assert len(cells) == 1 and cells[0][3] == 16


def test_check_v6():
    assert check("2001:db8::10", "2001:db8::/64").status == "inside"
    assert check("2001:db9::10", "2001:db8::/32").status == "outside"
    assert "anycast" in check("2001:db8::", "2001:db8::/64").notes[0]
    with pytest.raises(ValueError):
        check("10.0.0.1", "2001:db8::/32")
