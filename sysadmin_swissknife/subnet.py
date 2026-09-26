"""IPv4 subnet logic: visual splitter tree and "is this address inside?" checks.

Pure Python (stdlib ``ipaddress``), no GUI code, fully unit tested.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Iterator, Optional

IPv4Network = ipaddress.IPv4Network
IPv4Address = ipaddress.IPv4Address


# --------------------------------------------------------------------------- parsing
def parse_network(text: str) -> tuple[IPv4Network, bool]:
    """Parse '10.0.0.0/24', '10.0.0.0 255.255.255.0', '10.0.0.0 24' or a bare address (/32).

    Returns (network, had_host_bits). Host bits are cleared: 10.0.0.7/24 -> 10.0.0.0/24.
    """
    t = " ".join(str(text).strip().split())
    if not t:
        raise ValueError("empty input")
    t = t.replace(" /", "/").replace("/ ", "/")
    if " " in t and "/" not in t:              # "10.0.0.0 255.255.255.0" or "10.0.0.0 24"
        addr, mask = t.split(" ", 1)
        t = f"{addr}/{mask}"
    try:
        return ipaddress.IPv4Network(t, strict=True), False
    except ValueError:
        pass
    try:
        net = ipaddress.IPv4Network(t, strict=False)
    except ValueError as exc:
        raise ValueError(f"not a valid IPv4 address or network: {str(text).strip()!r}") from exc
    return net, True


# --------------------------------------------------------------------------- info
@dataclass(frozen=True)
class SubnetInfo:
    network: IPv4Network

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
    def first(self) -> IPv4Address:
        return self.network.network_address

    @property
    def last(self) -> IPv4Address:
        return self.network.broadcast_address

    @property
    def address_range(self) -> str:
        if self.network.prefixlen == 32:
            return str(self.first)
        return f"{self.first} - {self.last}"

    @property
    def usable_first(self) -> IPv4Address:
        return self.first if self.network.prefixlen >= 31 else self.first + 1

    @property
    def usable_last(self) -> IPv4Address:
        return self.last if self.network.prefixlen >= 31 else self.last - 1

    @property
    def usable_range(self) -> str:
        if self.network.prefixlen == 32:
            return str(self.first)
        return f"{self.usable_first} - {self.usable_last}"

    @property
    def hosts(self) -> int:
        """Usable host addresses (RFC 3021: a /31 has 2, a /32 has 1)."""
        p = self.network.prefixlen
        if p == 32:
            return 1
        if p == 31:
            return 2
        return self.network.num_addresses - 2

    @property
    def total(self) -> int:
        return self.network.num_addresses


# --------------------------------------------------------------------------- splitter tree
@dataclass(eq=False)
class SubnetNode:
    network: IPv4Network
    parent: Optional["SubnetNode"] = None
    children: Optional[tuple["SubnetNode", "SubnetNode"]] = None
    depth: int = 0

    @property
    def is_leaf(self) -> bool:
        return self.children is None

    @property
    def can_divide(self) -> bool:
        return self.is_leaf and self.network.prefixlen < 32

    @property
    def info(self) -> SubnetInfo:
        return SubnetInfo(self.network)

    def divide(self) -> None:
        if not self.can_divide:
            raise ValueError(f"cannot divide {self.network}")
        a, b = self.network.subnets(prefixlen_diff=1)
        self.children = (SubnetNode(a, self, None, self.depth + 1),
                         SubnetNode(b, self, None, self.depth + 1))

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

    def __init__(self, network: IPv4Network):
        self.root = SubnetNode(network)

    def leaves(self) -> list[SubnetNode]:
        return list(self.root.leaves())

    def max_depth(self) -> int:
        return max(leaf.depth for leaf in self.root.leaves())

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
        """Compact text form of the layout: the leaves' CIDRs, comma separated."""
        return ",".join(leaf.network.with_prefixlen for leaf in self.leaves())

    @classmethod
    def from_leaves(cls, root: IPv4Network, leaves: list[IPv4Network]) -> "SubnetTree":
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
    candidate: IPv4Network
    subnet: IPv4Network
    status: str                  # inside | outside | partial
    candidate_host_bits: bool
    subnet_host_bits: bool
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def inside(self) -> bool:
        return self.status == "inside"


def check(candidate_text: str, subnet_text: str) -> CheckResult:
    """Is the address (or network) ``candidate_text`` inside ``subnet_text``?"""
    cand, cand_hb = parse_network(candidate_text)
    sub, sub_hb = parse_network(subnet_text)
    notes = []
    if cand.subnet_of(sub):
        status = "inside"
        if cand.prefixlen == 32 and sub.prefixlen <= 30:
            ip = cand.network_address
            if ip == sub.network_address:
                notes.append("it is the network address of the subnet: not assignable to a host")
            elif ip == sub.broadcast_address:
                notes.append("it is the broadcast address of the subnet: not assignable to a host")
            else:
                pos = int(ip) - int(sub.network_address)
                notes.append(f"usable host {pos:,} of {sub.num_addresses - 2:,}")
        elif cand.prefixlen < 32:
            notes.append(f"the whole range {cand} is contained in {sub}")
    elif cand.overlaps(sub):
        status = "partial"
        notes.append(f"{cand} is larger than {sub} and contains it: only partially inside")
    else:
        status = "outside"
    if sub_hb:
        notes.append(f"the subnet had host bits set, it was read as {sub}")
    if cand_hb and cand.prefixlen < 32:
        notes.append(f"the first value had host bits set, it was read as {cand}")
    return CheckResult(cand, sub, status, cand_hb, sub_hb, tuple(notes))
