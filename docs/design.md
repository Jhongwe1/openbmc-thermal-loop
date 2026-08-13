# Closed-loop thermal-control testbed for phosphor-pid-control

Author: Chung-Wei Lan <zwwe1f@gmail.com> (Gerrit/GitHub: Jhongwe1)

Other contributors: None

Created: August 14, 2026

> This document follows OpenBMC's `docs/designs/design-template.md`.  The
> testbed is a personal project, not an OpenBMC subproject; the template is
> used because it forces the questions (alternatives, impacts) that a
> feature list does not, and because any future upstream proposal from this
> work would have to be written in exactly this shape.

## Problem Description

Validating a BMC thermal control loop without hardware is hard: injecting
sensor values from outside is open loop, so the temperature never responds
to the fan.  Under open loop the error never changes sign, the integral
never unwinds, and the one behaviour this project set out to quantify --
how much upstream's existing integral clamping is worth once saturation
clears -- cannot be observed at all.

Goals:

- Provide a closed-loop testbed in which upstream `phosphor-pid-control`
  (swampd) can be exercised, unmodified, against a plant model with
  realistic dynamics (thermal lag, dead time, fan inertia, sensor
  quantisation).
- Make every published number reproducible by anyone who clones the
  repository, without hardware, and have CI re-verify the claims.
- Quantify the effect of mechanisms upstream already has (integral
  clamping, slew limiting) rather than reimplement them.

Non-goals:

- This is not a replacement for hardware validation (see
  `limitations.md`).
- It proposes no change to `phosphor-pid-control` itself.
- Multi-zone coupling, stepwise controllers, and host-supplied thermal
  margin are out of scope.

## Background and References

`phosphor-pid-control` is a cascade controller: a thermal PID produces an
RPM setpoint, which a fan PID then tracks.  The two periods were measured
on this testbed's QEMU platform at 100 ms (inner) and 1000 ms (outer),
matching upstream's `cycleIntervalTimeMS` / `updateThermalsTimeMS`
defaults (`docs/cascade.md`, exp06).  Its `ec::pid()` already implements
integral clamping via `integralLimit` and back-calculates the integral
when slew limiting engages -- the "anti-windup" this project measures is
upstream's, not ours.

OpenBMC ships a second, unrelated fan-control stack,
`phosphor-fan-presence`: event-driven groups/triggers/actions configured
in JSON, used by IBM's `p10bmc`.  The testbed platform (`bletchley`) ships
both stacks side by side; the runtime evidence is recorded in
`docs/platform-matrix.md`.

References: openbmc/phosphor-pid-control (pinned at `c5e59550d3` for
parity testing), openbmc/dbus-sensors, openbmc/entity-manager,
openbmc/openbmc-test-automation (Robot `QEMU_CI` list).  Glossary kept
short: FOPDT (first-order-plus-dead-time process model), IMC/lambda
tuning (internal-model-control tuning with a single closed-loop
time-constant knob), windup (integral accumulation while the actuator is
saturated), back-calculation (pulling the integral back when the raw and
limited outputs differ).

## Requirements

The plant must be deterministic: the same seed must produce a
byte-identical trace, so figures can be regenerated from a clean clone
and CI can re-run experiments and compare against published claims
(`bench/claims.json`, 14 entries, each with value, tolerance, raw CSV
and figure).

The plant must perform no I/O: no clock, no filesystem, no D-Bus inside
`step()`.  This is what lets one C++ implementation serve three layers
(unit tests, host simulation, D-Bus bridge) and keeps "an L1 conclusion
holds at L2" a meaningful sentence.

The experiment design must guarantee saturation: at full fan speed and
peak load (400 W) the steady-state temperature (73 degC) must stay above
the setpoint (65 degC), otherwise the anti-windup comparison measures
nothing.  This precondition is enforced by a unit test
(`SaturationCaseHolds`), because it is an experimental-validity
constraint, not a code-correctness one.

Scale of the data: an L1 run is 1500 s at dt = 0.1 s, about 15000 rows
and under 1 MB of CSV per seed; five seeds per experiment arm.  All raw
CSVs are committed -- they are evidence, not build products.  The L2
bridge exchanges one temperature write and one PWM read per 100 ms over
a private D-Bus; no performance concern at that rate.  CI budget: the
C++ job runs in about 91 s and the experiment re-run job in about 68 s
on GitHub's ubuntu-24.04 runners.

Users of this testbed: primarily reviewers of the portfolio (they need
`git clone` + `meson test` + `python bench/...` to work and nothing
else), and the author on the next platform, where the identification
and tuning procedure is meant to be reused with new numbers.

## Proposed Design

A four-layer validation stack, one plant implementation throughout:

```
  L0  gtest/pytest      control law + plant equations     (microseconds)
  L1  bench/sim         my PI + plant, 5 seeds            (seconds)
  L2  private D-Bus     unmodified swampd binary + plant  (real time)
  L3  QEMU bletchley    full OpenBMC image, Robot QEMU_CI (minutes/boot)
```

Layers differ in what is real, not in what is measured: the same plant
serves every layer, and `bench/metrics.py` is the single definition of
every metric, so traces from different layers overlay directly and a
divergence is a finding, not an artefact.

The plant exposes two outputs by design: `step()` returns the full
measurement chain (dead time, lag, noise, quantisation) for L1, while
`sensedAnalog()` stops before noise and quantisation for L2/L3, where
the real tmp421 model performs quantisation -- otherwise quantisation
would happen twice and the layers could not be compared.

At L2 the bridge publishes the plant temperature on a private D-Bus
(with a minimal mock ObjectMapper, the same approach upstream's own
`dbushelper_mock.hpp` uses), and the unmodified swampd binary -- same
version as the QEMU image, `c5e59550d3` -- closes the loop through the
same file-backed PWM path the sysfs writer uses.

Claims are wired to CI in two classes: simulation experiments are
re-run and re-compared on every push; QEMU experiments cannot run in CI,
so CI re-derives their published numbers from the raw logs committed in
git (recompute), guarding the analysis code rather than the measurement.

## Alternatives Considered

Open-loop injection only.  The simplest approach: push sensor values
over D-Bus, watch the PWM output.  Rejected because it cannot measure
what this project is for -- with no feedback the error never changes
sign, so windup is visible but the value of anti-windup (recovery speed
once saturation clears) is not.  This rejection is why the plant model
exists at all.

Using the stepwise controller instead of PID.  swampd also ships a
lookup-table `stepwise` controller; real platforms often run stepwise
below the PID region and take the max within a zone.  Simpler to
validate, but it has no integral path, and the integral path is the
subject under measurement.

Using the phosphor-fan-presence event-driven stack.  A genuinely
different design (groups, triggers, actions; no feedback law), and what
p10bmc uses in production.  Not chosen because the question here is
specifically about PID feedback behaviour; bletchley ships both stacks,
so the choice was available and deliberate.

Reimplementing `ec::pid()` in Python for comparison.  Rejected: a
reimplementation differs in floating-point and compiler behaviour, so
any divergence could not be attributed to the algorithm.  Instead the
parity test compiles upstream's own `pid/ec/pid.cpp` into the test
binary via a pinned meson subproject; 144 parameter combinations match
step-for-step to 1e-12, and the one combination that legitimately
diverges (slew limiting with feed-forward) is kept as a documented
finding rather than patched over.

Ziegler-Nichols tuning instead of IMC/lambda.  Rejected twice over: its
design target (quarter-amplitude decay, roughly 25 % overshoot) trades
stability for speed, while a fan loop's cost function is acoustic
stability; and practically, slew limiting plus output saturation prevent
the clean sustained oscillation Ku and Tu require, so the method cannot
even be executed on this loop.

## Impacts

- API impact: none.  Nothing upstream is modified; the testbed consumes
  upstream interfaces as a black box.
- Security impact: the private D-Bus policy (`harness/obmcbus.conf`)
  allows all names and message types.  It is a test fixture and must
  never be deployed on a real system; the file says so.
- Documentation impact: seven configuration fields present in upstream's
  `pid/buildjson.cpp` were undocumented in `configure.md`; a
  documentation patch is under review (Gerrit 93470).  A dead include in
  the Robot `QEMU_CI` list is likewise under review (Gerrit 93469).
- Performance impact: L1 runs much faster than real time.  L2 cannot --
  swampd's loop periods hang off the wall clock -- so a 1500 s
  experiment takes 25 real minutes; L2 therefore runs one seed and the
  statistics (5 seeds) come from L1.  This split is stated wherever L2
  numbers appear.
- Developer impact: the repository builds with meson and tests with
  gtest/pytest, matching upstream's toolchain, so upstream contributors
  need no new tools to reproduce it.
- Upgradability impact: the parity test pins upstream at `c5e59550d3`
  (the version inside the QEMU image, recorded in the wrap file).  When
  the pin moves, the divergence case must be re-examined; the pin is
  never moved implicitly.

### Organizational

- Does this proposal require a new repository?  No.
- Who will be the initial maintainer(s)?  Not applicable -- personal
  testbed, maintained by the author.
- Which repositories are expected to be modified?  None by this design.
  Upstream changes that fell out of the work went to `openbmc/docs`
  (93470) and `openbmc/openbmc-test-automation` (93469), reviewed by
  those repositories' OWNERS.

## Testing

Each layer tests a different claim at a different iteration cost:

| Layer | Runs on          | Under test                      | Output      |
| ----- | ---------------- | ------------------------------- | ----------- |
| L0    | `meson test`     | plant equations, my PI, parity  | 32 gtest    |
|       |                  | against upstream `ec::pid()`    | + 146 pytest|
| L1    | `./build/sim`    | my PI + plant, 5 seeds          | Fig 1/2/3/5 |
| L2    | private D-Bus    | unmodified swampd + plant       | Fig 3 (L2), |
|       |                  |                                 | Fig 4       |
| L3    | QEMU bletchley   | full image, official Robot list | Fig 6, exp10|

The tests are themselves tested: `tools/mutation_check.sh` plants 66
known bugs one at a time and requires every one to turn some test red
(66/66 as of 2026-08-13).  CI runs three jobs -- C++ build + tests,
experiment re-run with claim assertions (rerun for simulation
experiments, recompute from committed raw logs for QEMU experiments),
and upstream's own `run-unit-test-docker.sh` against
phosphor-pid-control master.  The README links four CI runs that prove
the red path: parameter drift, clamp removal, and claim inflation each
turn exactly the expected job red, and the final revert returns green.
