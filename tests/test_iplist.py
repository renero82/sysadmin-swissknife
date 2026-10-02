import pytest

from sysadmin_swissknife.subnet import MAX_LIST, list_addresses, parse_exclusions


def test_usable_ipv4():
    r = list_addresses("192.168.1.0/29")
    assert r.addresses == tuple(f"192.168.1.{i}" for i in range(1, 7))
    assert list_addresses("192.168.1.0/29", usable_only=False).addresses[0] == "192.168.1.0"
    assert len(list_addresses("192.168.1.0/29", usable_only=False).addresses) == 8


def test_rfc3021_and_single():
    assert list_addresses("10.0.0.0/31").addresses == ("10.0.0.0", "10.0.0.1")
    assert list_addresses("10.0.0.9").addresses == ("10.0.0.9",)


def test_dotted_mask_and_host_bits():
    r = list_addresses("192.168.1.77 255.255.255.252")
    assert r.addresses == ("192.168.1.77", "192.168.1.78") and r.host_bits


def test_exclusions():
    r = list_addresses("192.168.1.0/28", exclude_text="192.168.1.1, 192.168.1.5-7; 192.168.1.12/30 10.0.0.1")
    assert r.addresses == ("192.168.1.2", "192.168.1.3", "192.168.1.4", "192.168.1.8",
                           "192.168.1.9", "192.168.1.10", "192.168.1.11")
    assert r.excluded == 7               # .1, .5-.7, .12-.14 (the /30 also covers .15, already not usable)
    assert parse_exclusions("10.0.0.20-10.0.0.10", 4) == parse_exclusions("10.0.0.10-20", 4)
    with pytest.raises(ValueError):
        list_addresses("192.168.1.0/28", exclude_text="hello")
    with pytest.raises(ValueError):
        list_addresses("192.168.1.0/28", exclude_text="2001:db8::1")


def test_ipv6():
    r = list_addresses("2001:db8::/126")
    assert r.addresses == ("2001:db8::1", "2001:db8::2", "2001:db8::3")
    assert len(list_addresses("2001:db8::/126", usable_only=False).addresses) == 4
    assert list_addresses("2001:db8::/120", exclude_text="2001:db8::1-2001:db8::ff").addresses == ()


def test_limits_and_separators():
    assert len(list_addresses("10.0.0.0/16", usable_only=False).addresses) == MAX_LIST
    for big in ("10.0.0.0/15", "2001:db8::/64"):
        with pytest.raises(ValueError, match="limited"):
            list_addresses(big)
    assert list_addresses("10.0.0.0/30").as_text(", ") == "10.0.0.1, 10.0.0.2"
