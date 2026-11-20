# M57: original German Telekom automatic DSL configuration

The owner explicitly requires the original plug-and-play experience on their
German Telekom line, including the requested ADSL2 configuration, without
entering Internet account details. They also authorize cross-checking this
software logic against the original firmware. Automatic reconnect after
power loss is part of the desired behavior.

## Original-firmware cross-check

The read-only original SquashFS contains `web/js/ispprofileV3.json.gz` and
`web/main/qsIsp.htm`. The `DE/Telekom/Auto_DSL/config` preset and the
`qsTelekomAutoDetect` function supply exactly the same built-in PPPoE username
and password. These are fixed firmware presets, not customer account data
read from a writable partition. Their values are not published here.

The database's automatic candidates agree with its two separate explicit
Telekom DSL presets:

| Candidate | Bearer parameters | VLAN | Dial protocol |
| --- | --- | ---: | --- |
| ADSL | VPI 1, VCI 32, LLC | 7 | PPPoE |
| VDSL | PTM path | 7 | PPPoE |

The quick-setup code creates autodetection profiles and requests the backend
object `DEV2_X_TP_AUTODETECT` with state `Requested`, the preset PPP fields,
ISP identity and model. This is evidence of the original requested behavior;
the backend implementation and actual network exchange still need tracing.

The original `bin/cwmp` exists and depends on the vendor management libraries,
OpenSSL 1.1 and DSL libraries. Its presence does not prove that a particular
customer account or telephone setting was downloaded. No ACS URL was inferred
from placeholder format strings. The original `default_config.xml` has now
been decoded as AES-128-CBC using parameters derived from the pinned
`libcmm.so` AES-wrapper GOT references and relative relocations. Valid PKCS#7
padding, a byte-for-byte ciphertext re-encryption check and parsing of all
3,818 configuration elements verify this result. The vendor XML syntax uses
unquoted `val`, `instance` and `nextInstance` attributes; the inspector quotes
these before parsing and rejects DTD/entity declarations.

In this read-only factory template, `ManagementServer.EnableCWMP=0` and
`PeriodicInformEnable=0`, while an ACS URL field is populated. This does not
establish the active device's configuration after region selection or setup,
nor prove Telekom provisioning. The inspector deliberately omits the URL and
all credentials from its report. The template and the UI/database findings
remain separate evidence: automatic Internet access is not proof that personal
credentials were downloaded.

Telekom's [Easy Login explanation](https://www.telekom.de/hilfe/internet-telefonie/internet/easy-login)
describes automatic recognition of access data and fixed-line numbers through
the connection. [EasySupport](https://www.telekom.de/hilfe/geraete/service/einrichtung-support/easy-support-funktion)
describes configuration and maintenance for supported devices. The original
preset and the owner's experience are consistent with automatic line-based
access; they do not by themselves establish the exact provisioning exchange
on this VB235v. Provider eligibility, disabled Easy Login and telephone
provisioning must be assessed from actual behavior, not assumed.

## Implemented preparation

`tools/telekom_factory_profile.py` accepts only the two pinned original files,
checks their hashes and bounded gzip/JSON framing, compares the database and
UI login presets, and independently checks the explicit ADSL/VDSL profiles.
It normalizes the verified provider facts and can export the fixed login
preset into a local private directory. It never reads saved customer accounts,
contacts an ACS, starts PPPoE or changes the router. Its default report omits
the preset username/password.

```sh
python3 research/vb235v/tools/telekom_factory_profile.py /private/extracted-original-root \
  --private-output /private/new-telekom-profile \
  --report /private/telekom-profile-evidence.json
python3 -B -m unittest discover -s research/vb235v/tests -p test_telekom_factory_profile.py -v
```

Five host tests cover matching/mismatching preset sources, sensitive-value
separation, ADSL/ADSL2/ADSL2+ versus VDSL2 selection, unknown line states,
incorrect PVC/VLAN/encapsulation and duplicate JSON keys. A separate run against
the actual original files passes the hash, UI and explicit-profile checks.

`tools/check_telekom_factory_flow.js` additionally extracts and executes only
the pinned original `qsTelekomAutoDetect` function in a local JavaScript
context with modeled lock/data-model callbacks. Five replay cases cover empty
and existing profile lists, reversed completion order and failed profile-add
callbacks. They independently confirm the exact ADSL/VDSL backend parameters,
the database/UI preset match, profile replacement and the final `Requested`
transition. No browser, ACS or network backend is connected.

The replay also records that the original UI advances its completion counter
on both profile-add success and failure. A new runtime manager must report and
retry a failed profile installation rather than infer a working connection
from that UI transition. This is a source/replay finding, not a demonstrated
failure of the original device on the owner's line.

```sh
node research/vb235v/tools/check_telekom_factory_flow.js \
  /private/extracted-original-root /private/telekom-flow-evidence.json
```

The normalized profile is preparation for the runtime connection manager. It
is not installed as a working DSL service. VLAN placement between the endpoint
and native host interface remains unverified: applying VLAN7 at both ends could
produce the wrong wire format. No manual account-entry fallback is substituted
for the owner's automatic-connection requirement.

The factory-default inspection is reproducible without accessing the device:

```sh
python3 research/vb235v/tools/inspect_factory_defaults.py \
  --library /private/original/lib/libcmm.so \
  --factory-config /private/original/etc/default_config.xml \
  --output /private/factory-defaults-report.json
python3 -B -m unittest discover -s research/vb235v/tests -p test_factory_defaults.py -v
```

This requires Python `cryptography`; it accepts only the two pinned original
hashes, never loads the original library, emits only an allowlisted report and
does not export decoded configuration. Four tests cover vendor XML values,
padding errors, ambiguous management fields, entity rejection and omission of
sensitive values. The actual result is recorded in
`findings/telekom-factory-defaults.json`.

## Remaining functional acceptance

1. Boot the DSL endpoint and obtain genuine line-mode/showtime events.
2. Apply the correct original bearer profile and verify where VLAN tagging occurs.
3. Establish PPPoE on the owner's line using automatic provider configuration,
   then verify routes, DNS and actual IPv4/IPv6 connectivity.
4. Determine which account/telephone settings are obtained automatically and
   implement the corresponding verified provisioning/client behavior.
5. Repeat after link loss, service restart and a full power cycle without
   asking the owner to enter Internet credentials.

The sanitized original-file cross-check is recorded in
`findings/telekom-factory-autoconnect.json`; runtime network and telephone
validation remain explicitly false.
