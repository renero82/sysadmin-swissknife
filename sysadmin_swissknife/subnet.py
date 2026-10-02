"""IPv4/IPv6 subnet logic: visual splitter tree and "is this address inside?" checks.

Pure Python (stdlib ``ipaddress``), no GUI code, fully unit tested.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Iterator, Optional, Union

IPNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]
IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

MAX_LEAVES = 4096          # the splitter refuses divisions that would create more rows


def format_count(n: int) -> str:
    """1,234 for normal numbers, 2^64 for the huge IPv6 ones."""
    if n < 10**12:
        return f"{n:,}"
    bits = n.bit_length() - 1
    return f"2^{bits}" if n == 1 << bits else f"{n:.3e}"


# --------------------------------------------------------------------------- parsing
def parse_network(text: str) -> tuple[IPNetwork, bool]:
    """Parse an IPv4 or IPv6 address/network.

    IPv4: '10.0.0.0/24', '10.0.0.0 255.255.255.0', '10.0.0.0 24', '10.0.0.5' (/32).
    IPv6: '2001:db8::/32', '2001:db8::1' (/128), '2001:db8:: 48'.
    Returns (network, had_host_bits). Host bits are cleared: 10.0.0.7/24 -> 10.0.0.0/24.
    """
    t = " ".join(str(text).strip().split())
    if not t:
        raise ValueError("empty input")
    t = t.replace(" /", "/").replace("/ ", "/")
    if " " in t and "/" not in t:              # "10.0.0.0 255.255.255.0" or "2001:db8:: 48"
        addr, mask = t.split(" ", 1)
        t = f"{addr}/{mask}"
    try:
        return ipaddress.ip_network(t, strict=True), False
    except ValueError:
        pass
    try:
        net = ipaddress.ip_network(t, strict=False)
    except ValueError as exc:
        raise ValueError(f"not a valid IP address or network: {str(text).strip()!r}") from exc
    return net, True


# --------------------------------------------------------------------------- info
@dataclass(frozen=True)
class SubnetInfo:
    network: IPNetwork

    @property
    def is_v6(self) -> bool:
        return self.network.version == 6

    @property
    def max_prefix(self) -> int:
        return self.network.max_prefixlen

    @property
    def cidr(self) -> str:
        return str(self.network)

    @property
    def netmask(self) -> str:
        return str(self.network.netmask)

    @property
    def wildcard(self) -> str:
        return str(self.network.hostmask)

    @property
    def first(self) -> IPAddress:
        return self.network.network_address

    @property
    def last(self) -> IPAddress:
        return self.network.broadcast_address

    @property
    def address_range(self) -> str:
        if self.network.prefixlen == self.max_prefix:
            return str(self.first)
        return f"{self.first} - {self.last}"

    @property
    def usable_first(self) -> IPAddress:
        if self.is_v6 or self.network.prefixlen >= 31:
            return self.first
        return self.first + 1

    @property
    def usable_last(self) -> IPAddress:
        if self.is_v6 or self.network.prefixlen >= 31:
            return self.last
        return self.last - 1

    @property
    def usable_range(self) -> str:
        if self.network.prefixlen == self.max_prefix:
            return str(self.first)
        return f"{self.usable_first} - {self.usable_last}"

    @property
    def hosts(self) -> int:
        """Usable addresses. IPv4: RFC 3021 (/31 = 2, /32 = 1). IPv6 has no broadcast."""
        if self.is_v6:
            return self.network.num_addresses
        p = self.network.prefixlen
        if p == 32:
            return 1
        if p == 31:
            return 2
        return self.network.num_addresses - 2

    @property
    def hosts_text(self) -> str:
        return format_count(self.hosts)

    @property
    def total(self) -> int:
        return self.network.num_addresses


# --------------------------------------------------------------------------- splitter tree
@dataclass(eq=False)
class SubnetNode:
    network: IPNetwork
    parent: Optional["SubnetNode"] = None
    children: Optional[tuple["SubnetNode", ...]] = None
    depth: int = 0

    @property
    def is_leaf(self) -> bool:
        return self.children is None

    @property
    def can_divide(self) -> bool:
        return self.is_leaf and self.network.prefixlen < self.network.max_prefixlen

    @property
    def info(self) -> SubnetInfo:
        return SubnetInfo(self.network)

    def divide(self, bits: int = 1) -> None:
        """Split into 2**bits equal parts (1 bit = halves, 4 bits = 16 parts, ...)."""
        if not self.can_divide:
            raise ValueError(f"cannot divide {self.network}")
        bits = max(1, min(bits, self.network.max_prefixlen - self.network.prefixlen))
        self.children = tuple(SubnetNode(n, self, None, self.depth + 1)
                              for n in self.network.subnets(prefixlen_diff=bits))

    def join(self) -> None:
        self.children = None

    def leaves(self) -> Iterator["SubnetNode"]:
        if self.is_leaf:
            yield self
        else:
            for c in self.children:
                yield from c.leaves()

    def internal_nodes(self) -> Iterator["SubnetNode"]:
        if not self.is_leaf:
            yield self
            for c in self.children:
                yield from c.internal_nodes()


class SubnetTree:
    """The layout shown in the splitter: a root network divided into leaves."""

    def __init__(self, network: IPNetwork):
        self.root = SubnetNode(network)

    def leaves(self) -> list[SubnetNode]:
        return list(self.root.leaves())

    def max_depth(self) -> int:
        return max(leaf.depth for leaf in self.root.leaves())

    def leaf_count(self) -> int:
        return sum(1 for _ in self.root.leaves())

    def can_divide(self, node: SubnetNode, bits: int) -> tuple[bool, str]:
        """Checks a division before doing it (IPv6 can explode into millions of rows)."""
        if not node.can_divide:
            return False, f"/{node.network.prefixlen} cannot be divided"
        bits = min(bits, node.network.max_prefixlen - node.network.prefixlen)
        after = self.leaf_count() - 1 + (1 << bits)
        if after > MAX_LEAVES:
            return False, f"that would create {after:,} rows (limit {MAX_LEAVES:,})"
        return True, ""

    def join_cells(self) -> list[tuple[SubnetNode, int, int, int]]:
        """(node, column, first_row, row_count) for every divided node.

        Column 0 is the deepest level (next to the Divide buttons) and the last column is the
        root, as in the davidc.net visual subnet calculator.
        """
        leaves = self.leaves()
        index = {id(leaf): i for i, leaf in enumerate(leaves)}
        maxd = self.max_depth()
        cells = []
        for node in self.root.internal_nodes():
            node_leaves = list(node.leaves())
            cells.append((node, (maxd - 1) - node.depth, index[id(node_leaves[0])],
                          len(node_leaves)))
        return cells

    def to_state(self) -> str:
        """Text form of the layout, keeping the grouping: 10.0.0.0/24(10.0.0.0/25,10.0.0.128/25)"""
        def enc(node):
            if node.is_leaf:
                return node.network.with_prefixlen
            return f"{node.network.with_prefixlen}({','.join(enc(c) for c in node.children)})"
        return enc(self.root)

    @classmethod
    def from_state(cls, root: IPNetwork, state: str) -> "SubnetTree":
        """Rebuilds a layout saved by to_state (also accepts the 1.0 flat list of leaves)."""
        state = state.strip()
        if "(" not in state:
            return cls.from_leaves(root, [ipaddress.ip_network(s) for s in state.split(",") if s])
        tree = cls(root)
        pos = 0

        def token():
            nonlocal pos
            end = pos
            while end < len(state) and state[end] not in "(),":
                end += 1
            net = ipaddress.ip_network(state[pos:end])
            pos = end
            return net

        def peek_token():
            end = pos
            while end < len(state) and state[end] not in "(),":
                end += 1
            return ipaddress.ip_network(state[pos:end])

        def parse(node):
            nonlocal pos
            if token() != node.network:
                raise ValueError("saved layout does not match the network")
            if pos < len(state) and state[pos] == "(":
                pos += 1
                first = peek_token()
                node.divide(first.prefixlen - node.network.prefixlen)
                for i, child in enumerate(node.children):
                    parse(child)
                    expected = ")" if i == len(node.children) - 1 else ","
                    if pos >= len(state) or state[pos] != expected:
                        raise ValueError("bad saved layout")
                    pos += 1

        parse(tree.root)
        if pos != len(state):
            raise ValueError("bad saved layout")
        return tree

    @classmethod
    def from_leaves(cls, root: IPNetwork, leaves: list[IPNetwork]) -> "SubnetTree":
        tree = cls(root)
        for target in sorted(leaves, key=lambda n: (int(n.network_address), n.prefixlen)):
            if not target.subnet_of(root):
                raise ValueError(f"{target} is not inside {root}")
            node = tree.root
            while node.network != target:
                if node.is_leaf:
                    node.divide()
                node = next(c for c in node.children if target.subnet_of(c.network))
        return tree


# --------------------------------------------------------------------------- membership
@dataclass(frozen=True)
class CheckResult:
    candidate: IPNetwork
    subnet: IPNetwork
    status: str                  # inside | outside | partial
    candidate_host_bits: bool
    subnet_host_bits: bool
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def inside(self) -> bool:
        return self.status == "inside"


def check(candidate_text: str, subnet_text: str) -> CheckResult:
    """Is the address (or network) ``candidate_text`` inside ``subnet_text``? IPv4 and IPv6."""
    cand, cand_hb = parse_network(candidate_text)
    sub, sub_hb = parse_network(subnet_text)
    if cand.version != sub.version:
        raise ValueError(f"cannot compare an IPv{cand.version} address with an IPv{sub.version} subnet")
    notes = []
    single = cand.prefixlen == cand.max_prefixlen
    if cand.subnet_of(sub):
        status = "inside"
        ip = cand.network_address
        if single and sub.version == 4 and sub.prefixlen <= 30:
            if ip == sub.network_address:
                notes.append("it is the network address of the subnet: not assignable to a host")
            elif ip == sub.broadcast_address:
                notes.append("it is the broadcast address of the subnet: not assignable to a host")
            else:
                pos = int(ip) - int(sub.network_address)
                notes.append(f"usable host {pos:,} of {sub.num_addresses - 2:,}")
        elif single and sub.version == 6 and sub.prefixlen <= 126:
            if ip == sub.network_address:
                notes.append("it is the Subnet-Router anycast address (RFC 4291): "
                             "usually not assigned to a host")
            else:
                pos = int(ip) - int(sub.network_address)
                notes.append(f"address offset {pos:#x} in a subnet of {format_count(sub.num_addresses)}")
        elif not single:
            notes.append(f"the whole range {cand} is contained in {sub}")
    elif cand.overlaps(sub):
        status = "partial"
        notes.append(f"{cand} is larger than {sub} and contains it: only partially inside")
    else:
        status = "outside"
    if sub_hb:
        notes.append(f"the subnet had host bits set, it was read as {sub}")
    if cand_hb and not single:
        notes.append(f"the first value had host bits set, it was read as {cand}")
    return CheckResult(cand, sub, status, cand_hb, sub_hb, tuple(notes))


# --------------------------------------------------------------------------- address list
MAX_LIST = 65_536          # largest list the IP List tool produces (a /16, or a /112 in IPv6)


def parse_exclusions(text: str, version: int) -> list[tuple[int, int]]:
    """Addresses to leave out of a list, as sorted (first, last) integer ranges.

    Items are separated by commas, semicolons, spaces or new lines; each one can be an address
    (``192.168.1.1``), a network (``192.168.1.0/28``) or a range (``192.168.1.10-192.168.1.20``,
    or the short IPv4 form ``192.168.1.10-20``).
    """
    ranges = []
    for item in text.replace(",", " ").replace(";", " ").split():
        try:
            if "-" in item:
                a, b = item.split("-", 1)
                first = ipaddress.ip_address(a)
                if version == 4 and b.isdigit():          # 192.168.1.10-20
                    b = a.rsplit(".", 1)[0] + "." + b
                last = ipaddress.ip_address(b)
                if first.version != last.version:
                    raise ValueError
                if int(last) < int(first):
                    first, last = last, first
            else:
                net = ipaddress.ip_network(item, strict=False)
                first, last = net.network_address, net.broadcast_address
        except ValueError:
            raise ValueError(f"not a valid address, network or range to exclude: {item!r}") from None
        if first.version != version:
            raise ValueError(f"{item} is IPv{first.version}, the subnet is IPv{version}")
        ranges.append((int(first), int(last)))
    return sorted(ranges)


@dataclass(frozen=True)
class AddressList:
    network: IPNetwork
    addresses: tuple[str, ...]
    excluded: int                # how many addresses of the range were removed by the exclusions
    host_bits: bool              # the subnet was typed with host bits set
    usable_only: bool

    def as_text(self, separator: str = "\n") -> str:
        return separator.join(self.addresses)


def list_addresses(subnet_text: str, usable_only: bool = True, exclude_text: str = "",
                   limit: int = MAX_LIST) -> AddressList:
    """All the addresses of a subnet, optionally only the usable ones and minus the exclusions.

    ``usable_only`` drops the network and broadcast address of IPv4 subnets up to /30
    (/31 and /32 keep everything, RFC 3021) and the Subnet-Router anycast address of IPv6 subnets
    up to /126 (RFC 4291).
    """
    net, host_bits = parse_network(subnet_text)
    first, last = int(net.network_address), int(net.broadcast_address)
    if usable_only:
        if net.version == 4 and net.prefixlen <= 30:
            first, last = first + 1, last - 1
        elif net.version == 6 and net.prefixlen <= 126:
            first += 1
    size = last - first + 1
    if size > limit:
        smallest = net.max_prefixlen - (limit.bit_length() - 1)
        raise ValueError(f"{net} has {format_count(net.num_addresses)} addresses: the list is limited to "
                         f"{limit:,} (a /{smallest} or smaller)")
    cls = ipaddress.IPv4Address if net.version == 4 else ipaddress.IPv6Address
    out, excluded = [], 0
    ranges = parse_exclusions(exclude_text, net.version)
    r = 0
    for n in range(first, last + 1):
        while r < len(ranges) and ranges[r][1] < n:
            r += 1
        if r < len(ranges) and ranges[r][0] <= n:
            excluded += 1
            continue
        out.append(str(cls(n)))
    return AddressList(net, tuple(out), excluded, host_bits, usable_only)
