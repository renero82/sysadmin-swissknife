# Changelog

## 1.3.0
- New **IP List**: every address of a subnet (IPv4 or IPv6, up to 65,536) ready to copy or
  save, usable addresses only or all of them, one per line or comma/space/semicolon separated.
  An **Exclude** field removes the addresses already in use (single IPs, ranges like
  `192.168.1.10-20`, or networks).
- IP in Subnet?: new button to list the IPs of the subnet.

## 1.2.0
- **IPv6** in the Subnet Splitter and in IP in Subnet? (hex view, anycast note, 2^n counts).
- Subnet Splitter: **Divide into** 2, 4, 16 or 256 parts; the saved layout keeps the grouping.
- New **MOTD Builder**: ASCII-art banners, icons, frames, colors, legal warnings and live
  system information, as a static `/etc/motd` or a dynamic script for Ubuntu/Debian or RHEL.
- GitHub Actions updated to the Node 24 versions.

## 1.1.0
- Windows version: a single portable `.exe`, nothing to install.
- The release workflow builds and selftests both the macOS and the Windows app.

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
