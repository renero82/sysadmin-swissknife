# Code signing policy

**Status: planned.** Sysadmin Swissknife releases are currently **not signed**. The maintainer intends to apply for free
code signing for the Windows builds through the [SignPath Foundation](https://signpath.org). Until the application
is approved, Windows will show a SmartScreen warning and macOS a Gatekeeper warning on first launch
(see the *Download* section of the [README](https://github.com/renero82/sysadmin-swissknife#readme)). This page will be updated once signing is active.

## How signing will work

Once approved, the free code signing certificate is issued to the SignPath Foundation, which acts as publisher.
Signing will be provided by [SignPath.io](https://signpath.io), with the certificate by
[SignPath Foundation](https://signpath.org).

- Only binaries built by the project's automated [GitHub Actions workflow](https://github.com/renero82/sysadmin-swissknife/blob/HEAD/.github/workflows/build.yml)
  from the source code in this repository will be submitted for signing. SignPath verifies that origin.
- Signed artifacts: The Windows portable executable. Nothing else is signed.
- Every signing request is approved manually by the project maintainer before it is released.
- Only official release builds (tagged `v*`) are signed. Local or experimental builds are never signed.

## Team roles

| Role | Member |
|------|--------|
| Committers and reviewers | [Gabriele Batignani](https://github.com/renero82) |
| Approvers | [Gabriele Batignani](https://github.com/renero82) |

## Privacy policy

This program will not transfer any information to other networked systems unless specifically requested by the
user or the person installing or operating it. Sysadmin Swissknife runs entirely on your computer and does not collect, store
or send personal data. The only network activity is opening a link in your web browser when you click it
(for example the project page or the donation link).

## Verifying a download

Download only from the [Releases page](https://github.com/renero82/sysadmin-swissknife/releases/latest) of this repository.
