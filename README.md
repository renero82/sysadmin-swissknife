# Sysadmin Swissknife

Small network tools for system administrators, in a native-looking **macOS app**.

![Subnet Splitter](docs/splitter.png)

## Tools

### Subnet Splitter
A visual IPv4 subnet calculator, inspired by the davidc.net *Visual Subnet Calculator*:

- enter a network (`192.168.0.0/24` or `192.168.0.0 255.255.255.0`)
- press **Divide** on any row to split it in two, click a colored **Join** cell to merge it back
- every subnet shows netmask, address range, usable IPs and number of hosts
  (/31 and /32 handled as per RFC 3021)
- **Copy table** (ready to paste in Excel/Numbers) or **Export CSV**
- the layout is saved and restored when you reopen the app

### IP in Subnet?
![IP in Subnet](docs/check.png)

Type an address and a subnet and see immediately if it is **inside** or **outside**:

- warns when the address is the network or broadcast address
- shows the host position, netmask, wildcard, usable range and a binary view where the
  network bits are highlighted
- works with a whole network too (`10.0.0.128/25` inside `10.0.0.0/24`? yes; `10.0.0.0/23`? partially)
- one click opens the subnet in the Splitter

## Download

Get `sysadmin-swissknife-vX.Y.Z-macos-arm64.zip` from the
[latest release](https://github.com/renero82/sysadmin-swissknife/releases/latest),
unzip it and drag **Sysadmin Swissknife.app** to Applications.

The app is not signed: the first time, right-click it → **Open** → **Open**.
If macOS says the app is damaged, run once:

```bash
xattr -dr com.apple.quarantine "/Applications/Sysadmin Swissknife.app"
```

## Run from source

```bash
git clone https://github.com/renero82/sysadmin-swissknife.git
cd sysadmin-swissknife
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

## Development

```bash
pip install pytest && python -m pytest -q tests     # unit tests of the subnet logic
./scripts/build_macos.sh                             # tests + app build + selftest
```

Pushing a tag like `v1.0.0` makes GitHub Actions run the tests, build the app, run its
`--selftest` and publish the release. The tag must match the version in
`sysadmin_swissknife/__init__.py`.

## License

[MIT](LICENSE)
