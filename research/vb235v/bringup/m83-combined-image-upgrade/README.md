# M83 combined image and guarded management integration

This candidate integrates M81 CPU admission, M79 v2 wireless recovery, M77
authenticated diagnostics and the disabled native DSL development runtime over
the protected M75 NAND/PHY profile. WLAN NPU remains off. Physical DSL and PPP
have not been accepted. Building an artifact does not establish installation or
hardware acceptance.

## Management migration

`99zz-ponwrt-management-m83` runs after M77 diagnostics and M73 persistent
defaults. Their existing lexical order removed fresh-install HTTPS after M77
added it. The final stage restores the intended TLS listeners and migrates only
the exact known isolated LAN from `lan-test` to `br-lan` containing `lan-test`
and `eth2`. It never includes `eth1`. Custom settings and staged UCI edits cause
a recorded skip. The DHCP pool remains one address without gateway or DNS.

Primary management is `192.168.235.1`; fallback is `169.254.235.1`. The separate
fallback SSH service requires the actual fallback address and existing Ed25519
key, and binds its literal address. The primary Dropbear patch skips an instance
whose explicit address interface has no address, retaining interface reload
triggers. This prevents the original init script's wildcard fallback.

`test-management.py --uci PATH` uses an actual native UCI CLI and exercises 21
cases, including the real M77 then M73 defaults batches. `test-dropbear.py
--source PATH` executes the actual init function with mocked network/procd calls
and exercises 12 listener branches. `test-prepare.py TREE` copies prerequisites
into a temporary fixture and applies the actual integration twice, proving byte
idempotence and rejection of foreign prerequisites without changing the shared
tree. The upstream git directory is queried read-only in that fixture.

## Full candidate build

The coordinator must grant the shared build-tree and make lease first.

```sh
python3 lock-inputs.py
python3 prepare.py TREE --check-only
sh build.sh TREE NEW_OUTPUT 4
```

The build script holds `.m55-build.lock`, applies the fixed M78 → M81 order,
stages both local packages and the guarded management files, rebuilds changed
packages and runs the artifact audit. Earlier M73/M75 preparers are never
rerun. `input-lock.json` freezes authored sources. `audit.py` saves separate
normal kernel, full installer, sysupgrade, rootfs, configs and package manifest
hashes; checks both filesystems, CPU builtins, M79 v2 sources, WLAN default-off,
private firmware inputs and the unchanged protected partition/reservation DT.
Private firmware, binaries, credentials and full device configs stay local.

Hardware upgrade acceptance still requires actual written-volume hashes,
booted revision, preserved config/SSH identity, every protected partition read
back and hashed, and normal/rescue paths. The generated manifest starts all
these acceptance fields as false. A stage2 success line alone is insufficient.

The completed candidate audit also caught an inherited M75 defect: its full
installer reused normal boot arguments including `ubi.mtd`, allowing automatic
UBI attachment in a purported RAM entry. The dedicated M83 installer builder
changes only a private DT's chosen arguments to `rdinit=/init` with no root/UBI
parameters, and uses a distinct RAM role marker. Actual bootloader environment
arguments must match before booting it. The normal sysupgrade, Image, DTB and
kernel FIT hashes were identical before and after this repair. The native host
execution of the exact production C checker admits the completed normal image,
extracts exactly the audited kernel/rootfs hashes, and rejects the installer
even with valid board metadata appended.

Candidate `sysupgrade.bin` is 13,107,460 bytes, SHA256
`23e1f1d6e36b6bf126c722f678686159a174053dfe230cde0238a87cb7375c98`.
Full RAM installer FIT is 12,447,292 bytes, SHA256
`0a54d6e739fdfba69d8792bd402e9fbdd466e65efa36c3745d0b4d4cd95805df`;
its decompressed Image is 37,289,992 bytes. Both packages are in the manifest.

## CPU-only RAM experiment

The separately approved mini experiment reuses the exact frozen M75 normal
kernel machine code and ABI. An offline DT copy adds the actual M78 root opt-in
and safe chosen arguments. External raw newc contains the exact M81 module and
tools, same-build BusyBox/runtime libraries, wired NPU firmware and EN8811H PHY
module/firmware. Debug sections are stripped only from private ELF executable
and library copies; module bytes remain exact. PID1 does not load a module,
configure a network, mount flash, run an upgrade or change CPU frequency.

```sh
SOURCE_DATE_EPOCH=1795303547 sh build-m75-mini.sh TREE /tmp/m83-cpu-mini-new
python3 test-mini.py /tmp/m83-cpu-mini-new
python3 test-production-checker.py TREE /tmp/m83-cpu-mini-new
```

Frozen r3/r4: FIT 6,595,712 bytes, SHA256
`6b33e3e2fc0fcf2874a3f8e8229d2389966a99e2ede19c46bacd4fb42fe705c4`;
two independent builds were byte-identical. Raw newc is 2,104,832 bytes with 51
entries. CPU module SHA256 starts `e55f925a`, cycle script starts `273a8c15`.
The production C checker and Python inspector reject the mini, including an
input with a valid board metadata trailer appended. It cannot be a sysupgrade
candidate.

Reproducing r3 requires the frozen M75 build inputs, including its normal
`vmlinux.debug`, staged PHY module and runtime libraries. The shared tree has
since been rebuilt as M83; that current tree is not the original M75 input
snapshot. The two byte-identical r3/r4 builds were completed before that change.

The exact UART clock is 1,843,200 Hz. Only 115200 has a valid exact divisor among
the considered rates; 230400 actually yields 115200, and 460800/921600 round to
divisor zero. There is no high-baud attempt or UART clock mutation. Minimum wire
time for r3 is 572.5 seconds before protocol overhead.

The M84 live normal-core LMB map and exact U-Boot allocation sources underpin
`audit-mini-memory.py`. Upload is `0x90000000`, kernel load `0x80200000`;
known kernel/upload/recovery page/DT reservations/resident U-Boot do not overlap.
Default relocation predicts initrd `0x9ad50000..0x9af51e00` and padded FDT
`0x9ad4a000..0x9ad4ff97`. These are predictions, requiring actual staged bootm
relocation evidence before `prep`/`go`. Both QDMA CSR low nibbles must be zero.
Do not call the normal UBI loader after uploading the mini: it overwrites the
same upload window. No environment is saved.

`discover-management.py` reads only Windows NIC 68 IPv4 addresses and derives
source-bound SSH candidate endpoints. Re-run it after DHCP changes; never assume
the old APIPA source remains assigned, and never modify upstream NIC 16.
`m83_session.py` preserves the existing pinned host identity and private-key
authentication while binding an explicitly discovered source. `readback.py`
requires the coordinator's device lease and reads volumes by actual UBI name,
not assumed numeric IDs, plus each entire protected partition and read-only
flag. It records config-preservation/rescue acceptance separately as pending.
Four synthetic collector cases verify actual volume mismatch and protected hash
or writable-flag failures remain incomplete; none opens a device connection.

`backup.py` captures from a verified persistent `/rom` + UBIFS system, refusing
RAM defaults. Its archive verifier requires all seven original UCI configs,
rpcd, passwd/group/shadow, authorized keys, existing SSH host identity, TLS
certificate/key, every existing `/etc/ponwrt` regular file and an explicit owner
setup-token presence/keep result. Missing standard keep entries select standard
`sysupgrade -c` backup behavior; no persistent keep file is edited. `-k` merely
adds the installed-package list. The private archive is saved under
`router-root-ssh`, with before/after live hashes. Twenty-three synthetic archive
cases cover missing/changed identities, owner token and Wi-Fi plus unsafe tar
entries.

`installer-plan.py` pins the completed candidate manifest and maps its exact ELF
Image/BSS/end to physical RAM. `upload-installer.py` uploads only to an already
observed normal M73 HTTP core and does not boot it. `stage-installer.py` requires
the verified NAND-origin backup first, then stages through `bootm prep` and stops
before `go`. `verify-prepared-fdt.py` verifies both the actual transient prep
allocation and final working-FDT address/size against live LMB, kernel including
BSS, initrd, upload and DT reservations. Eight synthetic gates and an independent
review of the saved CPU mini's final working-FDT observations pass. Hardware
installation, configuration restoration and normal/rescue acceptance remain
pending; a failed Linux physical-link test must stay failed.
