# M77 device diagnostics

The device-hosted Chinese dashboard and native collector have been deployed on
the M75 development system. The live HTTPS/API checks and reproducible OpenWrt
package build pass. Browser visual acceptance and full-image boot/upgrade
validation are still pending; this is
not yet a completed installation or DSL connection milestone.

The frontend covers startup progress, six DSL stages, physical port state,
hardware evidence, filtered logs, bounded previous-boot history and a redacted
JSON support export. It uses no CDN or external service. It displays missing
drivers, absent evidence and stale data as unavailable or blocked.

## Components and evidence contract

* `diagnostics.c`: native rpcd exec plugin and procd collector. Install the
  executable as `/usr/libexec/rpcd/ponwrt.diagnostics`; `list` and `call METHOD`
  implement the rpcd exec-plugin protocol. Its `daemon` mode writes root-only
  snapshots and bounded history. It invokes fixed programs with fixed
  arguments and exposes no command, path, flash or reboot interface.
* `setup.c`: first-use HTTPS CGI, installed as `/www/cgi-bin/ponwrt-setup` and
  `/usr/sbin/ponwrt-setup`. `--init` creates a 256-bit root-only initialization
  token without printing it. A successful setup stores a salted SHA512-crypt
  hash in the dedicated rpcd `admin` login and removes the token. It does not
  change the root password or SSH identity. The owner must obtain the token
  over an already trusted local administration path.
* `overlay/`: procd startup and the diagnostic account's narrow rpcd ACL.
  Standard rpcd sessions authenticate reads, support export and the fixed DSL
  retry request. The account cannot invoke system reboot, file reads or UCI.
* `www/`: HTML/CSS/JavaScript. Session IDs stay in memory. Data rendering uses
  text nodes. A lost connection preserves the last display with an explicit
  stale/error warning and never becomes a success indication.

The controller input is `/tmp/ponwrt/dsl-state.json`, schema 1. It must carry
the current `boot_id`, positive integer `generation`, and current monotonic
`updated_uptime_s`. More than 30 seconds old, future-dated, wrong-boot or
malformed evidence becomes `DSL_STATE_STALE`. Only a public field projection
is returned, rather than forwarding arbitrary controller JSON.

Stage IDs are `inputs`, `owner`, `endpoint`, `line`, `ppp`, `internet`. Internet
success additionally requires current-generation proof, real line showtime,
completed PPP and internet stages, boolean authentication and boolean IPv4 or
IPv6 readiness. Merely setting the top-level state to `online` cannot satisfy
these gates. The current DSL runtime has not established those proofs.

Retry uses a named root-owned mode-0600 Unix socket and requires a root-sent
`ACK <generation>` from the DSL supervisor after its running-state publication.
A successful send alone is not confirmation. Malformed/NACK replies, unexpected
descriptors and missing acknowledgements fail confirmation. A timeout is an
uncertain result; the client does not resend automatically. Sixteen isolated
client/cache contract checks pass, including the actual supervisor and
ASan/UBSan runs. Integer event timestamps and `error/stopped` states are retained.
RPC status also rechecks the underlying DSL proof so a fresh collector cache
cannot extend expired session evidence.

The collector saves stage-code changes and periodic snapshots at most every
120 seconds, retains eight previous boots, and distinguishes same-boot service
restarts from a new boot. All logs are bounded. Credential-related lines and
address patterns are suppressed before collection/export. This is conservative
redaction, not a guarantee that every possible vendor log format is anonymous;
review exported logs before sharing them.

## Validation performed

The C programs cross-compile against the exact AArch64 musl image libraries with
`-Wall -Wextra -Werror`. `test-evidence.c` exercises the production projection,
generation/line/stage gates, hostile value types and credential redaction under
ASan/UBSan. The executable does not access hardware or change configuration.

Twenty-three live checks pass on the device: pinned TLS, HTTP redirect, setup
discovery without token disclosure, unauthenticated access rejection, origin
check, invalid token/password/JSON rejection, successful single-use setup,
token removal, bad-password rejection, successful login, authenticated status,
history and support export without setup credentials, fixed-source log
selection, absent reboot/file/UCI permissions, explicit rejection when the DSL
retry service is absent, expired-cache rejection in reads and support exports,
and server-side logout.

The temporary test administrator was removed, the original rpcd configuration
was restored byte-for-byte, and a fresh first-use token was issued. No owner
password was chosen. Private credentials and raw live reports stay outside the
repository.

`prepare.py BUILD_TREE` stages `package.Makefile`, sources, web assets and
startup/ACL/default scripts as `package/ponwrt/diagnostics`. It selects the package
without changing physical networking roles. The package builds with fresh
metadata and includes its TLS generator dependency. Its defaults migrate only
this profile's unchanged HTTP listener; custom listener settings are preserved.

Remaining acceptance: browser layout/navigation/accessibility; reboot and
upgrade preservation; recovery management reachability on the physical LAN;
full image integration; real DSL controller and line/session evidence.
The current live test's link-local listener/firewall rule is a temporary
development fixture and must not be mistaken for the final network migration.
A kernel hang or power loss can also stop this web service; history helps
after recovery, and is not an independent serial console or persistent crash
recorder.
