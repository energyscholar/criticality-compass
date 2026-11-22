# Security policy

## Supported versions

The latest 0.x release of Criticality Compass, and the default branch. Older releases are not patched.

## Reporting a vulnerability

Use GitHub private vulnerability reporting (the Security tab of the repository, "Report a vulnerability"), or write to `energyscholar+criticality-compass@gmail.com`. Please do not open a public issue for a vulnerability.

This is a single-maintainer project. A reply is best effort, usually within a week; there is no bounty.

## In scope

- The `compass` command line and `bin/cc`.
- The checks that read stored results and frozen files (`bin/cc validate` and the hash checks), which must refuse a file that does not match its recorded hash.
- The loopback-TCP simulated server described in `contract/SCHEMA-1525.md`. It listens on the loopback interface only and is meant for tests.

## Known items

These are known and judged low risk. Reporting them again is not needed.

- The committed Linux build of the Rust kernel, `cc/_ext/kernel_rs.so`, carries a build path from the author's build host as a string inside the binary. It holds no credential. Build your own with `maturin` (`README.md`, "The Rust kernel") if you do not want to run a committed binary.
