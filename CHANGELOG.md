# Changelog

## 1.0.0
First release.
- **Subnet Splitter**: visual IPv4 subnet calculator in the style of the davidc.net
  visual subnet calculator. Divide and join subnets with a click, see netmask, address range,
  usable IPs and host count for every piece; copy the table or export it as CSV.
  The layout is remembered between sessions.
- **IP in Subnet?**: tells you if an address (or a whole network) is inside a subnet,
  with network/broadcast warnings, host position, subnet details and a binary view
  of the network bits. Accepts CIDR (`10.0.0.0/24`) and dotted masks (`10.0.0.0 255.255.255.0`).
- macOS app (Apple Silicon) built and tested automatically by GitHub Actions.
