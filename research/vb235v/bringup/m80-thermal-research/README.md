# M80: OEM thermal/TADC and AVS read-path research

This directory contains offline evidence checks and arithmetic models only.
It does not modify M78, the shared build tree, a running router, voltage, clocks,
fuses, or the ADC. The DTS file is a disabled review example with no installer.

## What the original firmware actually reports

The exact original kernel's `cpu-thermal` zone reads the **bandgap/BGP** sensor
(ADC mux 0). It does not read the CPU die sensor (mux 6). The actual data
structure has one bank, three possible sensors, and bank 0 points to index 0.
This is proven by exact kernel code and data, not merely the GPL driver names.
AN7583 initialization explicitly sets `thermal_efuse_valid=0` and prints
`DBG thermal Algo nonk`: the active formula uses manufacturer fixed coefficients,
not the per-device thermal calibration bits. The result is a real three-point
temperature estimate in millidegrees Celsius, but its per-die accuracy is not
established. Do not label it “factory calibrated CPU temperature”.

| Logical sensor | ADC mux | BG coefficient ×100 | Gain | Offset °C |
| --- | ---: | ---: | ---: | ---: |
| BGP / bandgap | 0 | 973 | 7440 | 294 |
| GbE | 5 | 995 | 7620 | 298 |
| CPU die | 6 | 1035 | 8390 | 344 |

The original zone uses only the first row. Although the GPL table contains
`{0,5,6}`, its callback indexes three-element arrays with the sensor value and
also adds four to nonzero values. Increasing its bank count to three would
therefore cause out-of-bounds coefficient access and wrong mux selection.
Logical coefficient indices 0/1/2 and physical mux values 0/5/6 must be distinct.

For one sensor, sample three diode modes in order:

1. Zero, diode selector 1.
2. D0, diode selector 0.
3. D1, diode selector 2.

With integer division toward zero:

```text
delta = D1 - D0
gain_denominator = trunc(delta * bg_coefficient / 100) + Zero - D1
temp_x10 = trunc(gain * delta * 10 / gain_denominator) - offset_C * 10
temperature_mC = temp_x10 * 100
```

`temperature-model.py` implements this offline using wide intermediate values,
explicit sensor/mux metadata and error checks. It rejects incomplete triplets,
inconsistent selectors, nonpositive delta/denominator, and implausible results.
Its −40…150°C diagnostic filter is an implementation proposal, not a chip
rating, accuracy statement or thermal trip policy. Synthetic test inputs prove
arithmetic only; they are not readings from this board. A valid 0°C must remain
a valid value, separate from “unavailable”.

## Register and timing contract

| Address | Register | Relevant fields / behavior |
| --- | --- | --- |
| `0x1fa20268` | SCU PLLRG_PROTECT | key `0x80`; also used by secure CPU PLL changes |
| `0x1fa202a0` | MUX_SENSOR / AVS_OUT_EN | diode bits[3:2]; AVS output-enable is bit0 and must be preserved |
| `0x1fa202e4` | MUX_TADC | ADC source bits[3:1]; reset bit4; low17 mode/control bits |
| `0x1fa202f0` | DOUT_TADC | current selected ADC output; not a Celsius register |
| `0x1fa202e0` | AVS DAC | low10 DAC code, change strobe bit16; never write for observation |
| `0x1efbd000` | PTP thermal register area | original DT resource; does not itself provide the AN7583 three-point Celsius conversion |

The exact OEM `get_thermal_ADC()` and `read_TADC()` select the diode/source,
unlock protected SCU writes, and wait 10ms when a selector changes before
reading DOUT. One full temperature acquisition normally needs approximately
30ms. The original code busy-waits while holding a spinlock. Its global
desired-mode variables and separately locked sensor/source phases do not
serialize a complete triplet against every client. A port must not inherit
that race or block a CPU for repeated 10ms spin waits.

OEM `thermal_init()` resets TADC and writes mode `0x33bc`; AVS `TADC_init()`
writes `0x33b0` and resets it. Comments mentioning `0x2ec` or protection
`0x264` disagree with the actual AN7583 defines/code (`0x2e4`/`0x268`). Use
the confirmed code and exact binary. These initialization writes must not be
replayed as if they were harmless register reads. Cold-boot ADC initialization
state is still unmeasured on our board.

Pure MMIO reads of a single current ADC output cannot reconstruct Zero/D0/D1.
No dedicated temperature-return SMC was found in the inspected exact BL31
service dispatch. Therefore a fresh meaningful temperature needs either the
existing original thermal-zone service, or a native sampler that is read-only
to users but necessarily controls ADC selectors internally. Returning the raw
ADC as degrees, or treating a previous source's sample as CPU temperature,
would be incorrect.

## Existing native 6.18 implementation

The prepared pinned PonWrt tree already contains `AIROHA_THERMAL`, with
`402-01`, `402-02`, `402-03`, `402-05`, `402-06`, and `402-07` thermal patches.
Its exact prepared `drivers/thermal/airoha_thermal.c` SHA256 is
`f3a6fbd810e3779c41684b9f868ed65d804ffa2c5529bec3fc6588e5bd6618f6`.
It is compiled, but the VB235v DT chain has no thermal child or zones. The
existing `chip_scu` syscon in `an7583-tplink_vb235v-ram-lan.dts` is sufficient
to parent the native thermal device. A new thermal driver need not be invented.

The native candidate already uses sparse coefficient tables indexed safely by
physical mux, registers three optional zones, locks the whole diode triplet,
sleeps 10–11ms per selection, checks source/diode selection after sampling,
and retries a mismatched transaction at most three times. The included patch
descriptions report AN7583/Nokia testing; that is not validation on this VB235v.

Remaining issues before relying on it here:

* `airoha_get_thermal_ADC()` discards `regmap_field_read()` errors and can return
  an undefined stack value. Several protection/mux read/write errors are also
  discarded. All must propagate errors; a failed restoration should disable
  future acquisition, rather than report a temperature.
* Conversion still uses signed `int` products. Use signed64 intermediates,
  checked denominator and sample bounds. Zero-only denominator rejection does
  not address negative or unreasonable samples.
* Its mutex covers thermal readers only. AVS and M78 secure PLL SMC changes
  share the ADC or PLLRG_PROTECT resource without this mutex. The driver holds
  the protection key open over its settle sleep; another secure clock operation
  may relock it, and restoring a sampled key can restore a transient value.
  Start observation with M78 transitions disabled. A future combined controller
  or explicit cross-component serialization is needed before concurrent use.
* It assumes TADC initialization rather than establishing the original reset/
  mode contract. First read-only state inspection and cold-boot comparison
  should decide whether initialization is already guaranteed by retained BL31.

## AVS voltage read path is a separate calibration problem

The exact OEM `readout_efuse()` ABI is SMC `0x82000001`, x1 `0x44414552`
(`READ`), x2 a **32-bit physical DMA buffer**, x3 `256`. The resulting
2048-bit image is sliced little-endian by `get_phy_efuse()`. Do not substitute
`0x82000303`, which is the different PHY-load service, or send user pointers.
The EFUSE service also contains programming operations; only this proven READ
operation belongs in an eventual strictly bounded reader.

For AVS voltage calibration, take 32 bits starting at bit841:

```text
low = low16(efuse_word) >> 4
high = high16(efuse_word) >> 4
slope = ((1000000 / (high-low)) + 5) / 10
adc = raw_vcore_adc >> 4
voltage_mV = ((adc-low) * slope + 50000 + 50) / 100
```

The OEM rejects/falls back when the word is zero/all-ones, high≤low, low=0 or
slope=0. Its fallback is low1536/slope97 with `EF_OK_flag=0`; do not present
that as calibrated voltage. The offline model rejects missing calibration.
`AVS_Get_Vcore()` selects ADC mux2 and may perform SCU writes and wait10ms,
despite being called GET. It also expects calibration globals to be initialized.

The GPL thermal helper's bit39/745/777/809 names do not match all corresponding
field names in `phy_efuse_def.h`; the active AN7583 temperature path ignores
them. A new per-die temperature calibration formula cannot be inferred from
those field names alone. The exact source's EFUSE output buffer also uses
`DMA_TO_DEVICE` despite secure firmware producing output; direction/cache
handling, allocation/alignment, buffer bounds and 32-bit addressing need
independent verification before porting that helper. None was invoked here.

## Minimal observation recommendation and gates

For original-system cross-checks, read existing `/sys/class/thermal/thermal_zone*/type`
and `/temp`, record type and timestamp, and label the original `cpu-thermal`
value BGP. This performs no new user-directed register writes, although the
original driver's service internally changes the ADC mux.

For PonWrt, first keep the frontend value unavailable/null until a successful
complete measurement exists. Do not display missing data as 0°C. Prepare a
demand-only BGP zone0 using the existing driver after its error/arithmetic
handling is hardened; no polling, trips, cooling maps, voltage interface or
automatic shutdown is required for this initial diagnostic interface. The
disabled DTS example shows the concrete node layout. Registration or reading
an enabled zone may itself invoke acquisition, so enabling it is a hardware
test step even with polling-delay0.

Begin with M78 `allow_transitions=N`; compare BGP against original under a
similar stable boot condition and record raw coherent triplets plus selectors
in private evidence. Confirm readings change plausibly over warmup and dual-core
load, remain stable with simultaneous diagnostic reads, and preserve networking.
Only then add GBE/CPU zones with correct physical mux maps and label their
calibration limits. Establish shared SCU/AVS/SMC ownership before testing
temperature acquisition concurrently with frequency or voltage transitions.
Thermal trip temperatures and automatic cooling/shutdown need their own
board-specific validation; neither the original passive125°C nor another
board's reference trips establish safe VB235v operating limits.

Offline checks:

```sh
python3 research/vb235v/bringup/m80-thermal-research/test-model.py
python3 research/vb235v/bringup/m80-thermal-research/verify-evidence.py /path/to/TP
```
