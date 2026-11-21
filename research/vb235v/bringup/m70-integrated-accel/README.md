# M70: integrated RAM acceleration image

M70 combines the two ARM CPUs, NPU firmware, M69 flowtable cleanup, private
Wi-Fi calibration, native netifd/wpad station userspace and EIP93 crypto.
External MDIO is exposed only for bounded discovery. EN8811H firmware and its
driver are packaged for the following port milestone; M70 has no external PHY
nodes. This is a storage-free development image, not a persistent replacement
firmware. DSL, voice and permanent installation remain separate work.

After preparing/building M68 on the pinned PonWrt revision:

```sh
sh build.sh /path/to/ponwrt /private/npu-input-directory /private/board-eeprom.bin 8
sh build_probes.sh /path/to/ponwrt /path/to/new-probe-output
```

The NPU directory must contain the original files in `private-inputs.json`.
The EEPROM must match the captured board calibration. Inputs are size/hash
checked and copied locally; they are not redistributed. Do not put Wi-Fi
credentials or development SSH private keys into the image. Probe generation
needs Python cryptography on the host. Wireless defaults to disabled, with no
AP interface definitions. Enable only an explicitly configured network.

The Windows station fixture uses the console-pinned connection format from
M69 and a private JSON file with `password` and `networks` (two objects with
`band` equal to `2g`/`5g`, plus `ssid`). It connects only these supplied networks,
does not bridge them, and restores configuration afterward. This fixture
currently accepts SSIDs containing letters, digits, spaces, underscore, dot
or hyphen. Keep its output directory private.

```sh
python station_fixture.py --connection /private/connection.json \
  --credentials /private/stations.json --output /private/new-results
```

Explicit `ifup` is required after each preceding `ifdown`; changing the Wi-Fi
section alone does not reactivate a manually stopped netifd network.

On this board, native combined EIP93 authenc decrypt accepted modified tags.
Correct encryption and valid decryption alone would have missed the failure.
The board-specific patch excludes native combined AEAD registration while
retaining EIP93 AES and hash/HMAC. Linux generic authenc composes those hardware
primitives and verifies the tag. This is measured behavior of this board/driver
combination, not a claim about every EIP93 device. The initial experimental
image was retired locally.

The diagnostic selects exact driver names and compares large requests with
independent host-generated results. Its 34 cases cover AES ECB/CBC/CTR with
128/192/256-bit keys, SHA256, HMAC-SHA256 and generic authenc using hardware
AES/HMAC, with 12/16/32-byte tags. Every vector runs with aligned contiguous and
unaligned split scatterlists. Authenc also corrupts AAD, ciphertext and the
first/last tag bytes and requires -EBADMSG. Requests exceed the driver's small
request software thresholds; hardware interrupt activity is recorded. These
checks do not establish throughput or complete VPN/IPsec support.

Cold boot uses the installed recovery's authenticated RAM upload. Verify
FIT/CRC and quiescent QDMA before handoff. No flash writer or saveenv is involved.
The M69 physical-wire suite compares software controls against hardware flow
indications, CPU bypass and repeated cleanup. Do not infer port throughput from
the 100M management link or from zero PPE byte counters when hardware statistics
collection is disabled.
