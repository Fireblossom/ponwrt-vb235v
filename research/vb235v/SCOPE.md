# Agreed research scope

Owner requirements, clarified on 2026-11-15:

- A recovery-capable U-Boot is acceptable; the Breed implementation itself is not required.
- Hardware acceleration means NAT/packet forwarding, NPU integration, and cryptographic engines, not video decoding.
- Retain DSL connectivity, the analog telephone port, and Wi-Fi.
- Every reproducible milestone gets a separate Git commit and is published on the research branch.

Recovery is a property to test, not an absolute guarantee. A bootloader cannot recover itself if the earlier boot stages, flash, power, or physical recovery path are unusable. Preserve the original boot chain until a board-specific alternative and an appropriate recovery procedure are validated.

On 2026-11-16 the owner explicitly prioritized recovery U-Boot. Recovery development and its own installation gates now take precedence over DSL/PCS work. Requirements for validating DSL, telephone and Wi-Fi still apply to a permanent replacement Linux firmware; they do not require postponing independently validated recovery-bootloader work. See [M20](UBOOT-RAM-RECOVERY.md).

This branch currently contains research, not a supported firmware image. Progress claims distinguish source-derived findings, analysis of original artifacts, and live hardware validation.

On 2026-11-20 the owner requested complete PonWrt development and explicitly
prioritized reverse engineering the original DSL implementation where needed.
The software must also reproduce the original plug-and-play behavior on the
owner's German Telekom DSL connection, including the requested ADSL2 provider
profile and automatic connection/configuration without manually entering
Internet account credentials. Distinguish preinstalled provider parameters,
line-based authentication and actual configuration/telephone provisioning;
verify their original behavior before choosing an implementation. Do not
replace this requirement with a manual PPPoE setup screen or claim success
from DSL synchronization alone.

The owner subsequently identified COM3 as the connected TTL console and the
available Tenda SP3 as the router's actual power supply, authorizing autonomous
U-Boot entry and flashing through this path without needing the owner to hold
Reset. This does not count as validation of the physical Reset-button entry.
The Ethernet test cable is connected to a 1G LAN socket, with the workstation
using a USB hub. Test traffic must remain on that isolated USB Ethernet path.

The owner also connected the two 2.5G sockets to each other with one cable for
port-loop testing. As of 2026-11-21 the DSL cable is not connected; remind the
owner before line synchronization and automatic-dial testing. This does not
block independent driver, offline logic or isolated port-loop work.

On 2026-11-21 the owner explicitly prioritized wired Ethernet and hardware
acceleration, and requested multicore bring-up first. Validate the additional
usable ARM CPU(s) with execution and shared-memory tests, then proceed with
the wired data path and actual hardware offload. Generic four-node stock DT
templates do not establish four usable ARM cores: the captured original live
cpuinfo and ATF expose processors 0 and 1. Keep NPU processing-core counts
separate from the Linux ARM CPU topology.

On 2026-11-21 the owner deferred forwarding-throughput qualification and
prioritized the two 2.5G port drivers. Continue PHY/PCS initialization,
negotiation and isolated frame integrity work with the existing port-pair
cable. These results must not be presented as routed-throughput qualification.
Do not bridge the two sockets while they are connected to each other.

The owner subsequently deferred the requested independent-peer/cable-change
test until a later session. Keep the existing wiring and retain independent
peer negotiation, physical data integrity and 2.5G throughput as pending.
Do not interpret this deferral as cancellation of driver development or as
validation of either external port.

The owner then explicitly requested formal installation and upgrade tests
on this device. This authorizes development-system writes in the post-rescue
319-PEB body and a separately validated normal-core update for system boot.
Retain fresh backups, factory slot0, the fixed rescue block, calibration,
factory mapping tables and the first two boot blocks/environment. Preserve
the original-kernel RAM diagnostics and return-to-factory boot path. This does
not authorize reclaiming factory slot0. DSL, voice and stable dual-2.5G remain
unfinished; installation tests do not qualify a complete replacement release.

The owner then connected the workstation's 1G USB NIC to one external 2.5G
socket and requested negotiation verification and a driver fix. This resumes
an independent 1G peer test on that socket; it does not qualify 2.5G speed or
the other socket. Preserve the independent upstream workstation connection.
The owner also requested a systematic component-by-component comparison of
original and native driver behavior to identify latent problems. Compare
state ownership, reset/clock/firmware order, memory/DMA contracts, negative
paths and lifecycle recovery; distinguish measured defects, intentional
protective differences and unverified coverage.

The owner further requested an independent sub-agent audit of the complete
DSL path against the original firmware. The intended acceptance criterion is
cold power-on followed by autonomous Telekom synchronization and Internet
session establishment, without manual account entry. Offline codecs, ARM64
instruction models and provider UI replay do not satisfy that criterion.
