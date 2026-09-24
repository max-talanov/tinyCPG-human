# Multi-Channel FES Systems: Architecture, Integration & CPG Applications
## Compex Motion, RehaStim, and Hardware-Software Integration for tinyCPG

---

## Executive Summary

**Multi-channel functional electrical stimulation (FES) systems** enable simultaneous, coordinated stimulation of multiple muscle groups—essential for restoring complex movement patterns (gait, grasp, postural control) in neurologically impaired patients. A critical architectural distinction exists between systems with **independent parallel channels** (true simultaneous delivery) versus **time-multiplexed or sequentially scanned channels** (apparent simultaneous delivery via rapid switching).

For **integration with computational models** like your tinyCPG NEST simulation, channel independence, real-time programmability, and host-PC API access are non-negotiable. This document compares leading commercial systems and maps integration pathways to your spinal CPG bilaterally-controlled lower limb model.

---

# PART 1: COMPEX MOTION – Research-Grade 4-Channel FES System

## Historical Context & Design

The Compex Motion represents a major shift from **fixed medical devices to programmable research platforms**. Developed in the early 2000s by researchers at Swiss Federal Institute of Technology Zurich and ParaCare, it was created specifically to address limitations in existing FES systems:

> "Research groups in the field of functional electrical stimulation (FES) are often confronted with the fact that existing and commercially available FES stimulators do not provide sufficient flexibility and cannot be used to perform different FES tasks."

The system was commercialized by Compex SA (Swiss manufacturer) and enhanced clinical researchers' ability to develop **custom neuroprostheses** rather than being constrained by pre-programmed therapy protocols.

---

## Hardware Architecture: 4 Independent Channels

### Core Specifications

The stimulator has four biphasic current-regulated stimulation channels and two general purpose analog input channels that can be configured to measure the output voltage of a variety of sensors such as goniometers, inclinometers, gyroscopes, or electromyographic (EMG) sensors.

**Key Feature: True Independence**

The four stimulation channels are independent, meaning each channel can simultaneously deliver **different current amplitudes, pulse widths, and frequencies** to separate motor targets. This is distinct from **multiplexed systems** where a single high-voltage source is time-divided among channels—a critical difference for complex movement coordination.

| Feature | Compex Motion |
|---------|---|
| **Number of channels** | 4 (expandable to 8, 12, 16+ via parallel cascading) |
| **Channel delivery** | **Independent (simultaneous)** |
| **Current type** | Constant-current, biphasic rectangular pulses |
| **Typical current range** | 0–100 mA per channel (limited by electrode impedance) |
| **Frequency** | Software-programmable; 0–200 Hz typical |
| **Pulse width** | Software-programmable; 10–500 µs typical |
| **Synchronization** | When multiple units cascaded, fully synchronized via inter-unit timing link |

### Scalability via Cascading

By interconnecting two or more Compex Motion stimulators, the number of stimulation channels can be increased to multiples of four channels, 8, 12, 16, 20, and so forth. When the stimulators work in parallel their stimulation sequences and stimulation timings are fully synchronized.

**Critical Advantage for CPG Integration:**
- Each 4-channel unit is independently addressable
- Multiple units synchronize via dedicated timing link (not USB, so no latency jitter)
- E.g., 3× Compex Motion units = 12 independent channels with synchronized timing for bilateral 6-muscle leg coordination (3 muscles per leg, L & R)

---

## Software: Memory Card Programming & External Sensor Integration

### Programming Model: Graphical Timeline Editor

The stimulation sequences and the control strategies are programmed and stored on exchangeable credit card-sized memory chip cards. By replacing the chip-card the function of the stimulator is changed instantaneously to provide another function or FES treatment.

The Compex Motion uses a **"drag-and-drop" graphical user interface (GUI)** on a PC to program arbitrary stimulation sequences. Key elements:

- **Timeline-based editing:** Each channel has a horizontal timeline; primitives (stimulation "events") are placed on the timeline using standard GUI metaphor
- **Primitives library:** includes pulse, pause, branch, wait-for-sensor, increment-parameter, synchronization gates, and conditional logic
- **Temporal precision:** <1 ms relative timing accuracy between channels
- **Memory chip storage:** Programs are compiled and saved to ROM chip cards, then inserted into the stimulator for autonomous operation

### External Sensor Integration (2 Analog Inputs)

The stimulator has two general purpose analog input channels that can be configured to measure the output voltage of a variety of sensors such as goniometers, inclinometers, gyroscopes, or electromyographic (EMG) sensors. For real-time EMG control of the stimulation patterns, an EMG processing algorithm with software stimulation artifact blanking was implemented.

**Closed-Loop Sensing:**

The device supports **threshold-based gating** and **value-dependent branching**:
- EMG amplitude threshold triggers stimulation onset
- Goniometer angle governs stimulation frequency/amplitude
- Pressure sensors (FSR) switch between pre-programmed sequences
- Example: Heel-strike sensor enables extensors; toe-off sensor switches to flexors (gait-triggered FES)

**Limitation:** External control is passive polling via analog thresholds on pre-programmed sequences—not true real-time external command modulation like a computer API.

---

## Comparison: Compex Motion vs. Modern Alternatives

### Compex Motion Advantages:
1. **True 4-channel independence** with simultaneous pulse generation
2. **Fully programmable** arbitrary stimulation patterns
3. **Portable, battery-powered** design suitable for clinical/home use
4. **Exchangeable memory cards** for instant protocol switching
5. **Established clinical track record** (grasping, gait, spasticity studies)
6. **Low per-unit cost** (~€6–10k for base 4-channel unit)

### Compex Motion Disadvantages:
1. **No direct computer API:** Programs compiled offline and stored on memory card; changes require reprogramming card
2. **Limited real-time closed-loop:** External sensor input is passive (threshold-based); not true command-driven
3. **Dated platform:** Original design ~2001; limited ongoing development
4. **Two analog inputs only:** Restricts multi-sensor feedback scenarios
5. **No modern documentation:** Published literature is ~20 years old; current commercial availability unclear

---

## Compex Motion & tinyCPG Integration: Feasibility & Limitations

### Scenario A: Offline Protocol Transfer (Feasible)

1. **Run tinyCPG simulation** on MareNostrum 5 or local machine; output bilateral extensor/flexor motor pool trajectories to HDF5
2. **Extract CPG timing patterns:** Parse HDF5 to identify phase relationships (e.g., L-E active 0–400ms, L-F active 400–800ms, etc.)
3. **Design Compex Motion protocol** manually in GUI using these timings
4. **Program memory card** with customized gait sequence
5. **Load card into hardware** and test on patient

**Advantage:** No custom hardware/software development; uses existing clinical tool
**Disadvantage:** Slow iteration cycle; changes to CPG → manual protocol redesign → memory card reprogramming (hours)

### Scenario B: Real-Time External Computer Control (Difficult)

**Goal:** Real-time NEST → Compex Motion feedback loop (10–20 ms latency)

**Blocker:** Compex Motion lacks host-PC API or USB control port in original design. The two analog inputs are **passive sensors**, not command inputs. To achieve real-time control would require:

1. Custom firmware modification (proprietary; not supported by manufacturer)
2. Hardware hack: Inject analog commands via DAC onto the 2-channel input ports to modulate pre-programmed sequences (non-standard, risky)
3. External relay switching: Drive the hand-switch input with Arduino GPIO (triggers discrete pre-programmed sequences only; not parameter modulation)

**Feasibility: Low** (would require substantial reverse-engineering or firmware modification)

---

# PART 2: REHASTIM (HASOMED) – Modern 8-Channel Research Platform

## Overview

RehaStim represents the **modern successor to Compex Motion**, designed with explicit real-time computer control as a primary feature. HASOMED GmbH (Germany) manufactures a family of research-grade FES devices with open ScienceMode protocols.

### Product Generations

| Product | Channels | Control | Real-Time API | Approx. Price |
|---------|----------|---------|---|---|
| **RehaStim 1** | 8 | ScienceMode1 (USB binary protocol) | Simulink/MATLAB | €10–15k |
| **RehaStim 2** | 8 | ScienceMode2 (enhanced USB) | Simulink/MATLAB/Python | €12–18k |
| **P24 Science** | 8 | ScienceMode4 (USB-C, modern) | Simulink/MATLAB/Python/C | €14–20k |
| **I24 Science** | Implantable, 8+ | ScienceMode4 (wireless) | Simulink/MATLAB/Python/C | Custom quote |

---

## RehaStim 2: Detailed Architecture

### Hardware: 8 Independent Channels via Dual Modules

RehaStim consists of two separate stimulation modules each with four channels where each module includes a DC/DC converter cascade to produce the galvanically isolated high voltage. The stimulation pulses are then generated via discrete H-bridges.

**Key Advantage vs. Compex Motion:**
- **Dual-module design:** Each module has independent power generation (DC/DC + H-bridge per channel)
- **Full independence:** All 8 channels can run different frequencies, pulse widths, and currents simultaneously
- **Higher current capacity:** Up to 150 mA per channel typical

### Real-Time Control: ScienceMode2 Protocol

The RehaStim stimulator has 8 independent channels that can generate biphasic pulses with adjustable current amplitude and pulse width. ScienceMode allows real-time control of pulse patterns and stimulation parameters via serial communication over USB.

**Protocol Details:**

- **Transport:** USB 3.1 (future P24 Science uses USB-C)
- **Data Format:** Binary protocol with structured command/response frames
- **Latency:** <10 ms round-trip typical (soft real-time; no hard guarantees)
- **Parameter Resolution:**
  - Current: 1 mA steps, 0–255 mA range (mode-dependent)
  - Frequency: 1 Hz steps, 1–500 Hz range
  - Pulse width: 1 µs steps, 1–1000 µs range

**Modes of Operation:**

1. **Single Pulse Mode:** Deliver one pulse immediately per command (used for parameter testing, safety checks)
2. **Continuous Channel List (CCL) Mode:** Pre-upload sequence of pulses; stimulator executes autonomously at specified intervals

### Simulink Integration

An interface called ScienceMode2 enables scientists to change stimulations parameters like pulse widths and current amplitudes in real-time. Every pulse can be adjusted individually. Another interesting feature is the triggering of higher frequency pulse groups like doublets.

**MATLAB/Simulink Block:**

HASOMED provides a Simulink block that encapsulates ScienceMode2 binary protocol. Within a Simulink model:

```
[CPG Model Output]
      ↓
[Demux: Split L-E, L-F, R-E, R-F signals]
      ↓
[Signal Conditioning: normalize to 0–255 mA range]
      ↓
[Simulink RehaStim Block]
      ↓
[USB → RehaStim Hardware]
      ↓
[Surface Electrodes → Muscles]
```

**Example Simulink Control:**
- CPG generates bilateral extensor/flexor drive signals (0–1.0 normalized)
- Simulink block converts to stimulation current (0–150 mA per channel)
- Every 10 ms (100 Hz control loop), new current values sent to all 8 channels
- Timing accuracy: ±1–2 ms (adequate for biomechanics, marginal for sub-millisecond neural timing)

---

## HASOMED ScienceMode4: Modern Open Protocol

The latest standard, **ScienceMode4**, uses **open-source GitHub documentation** and provides client libraries in multiple languages:

HASOMED ScienceMode provides protocols for RehaStim1 (ScienceMode1), RehaStim2 (ScienceMode2), P24 Science (ScienceMode4), and I24 Science (implantable). A curated list of ScienceMode projects is available on GitHub.

**Available Client Libraries:**
- **Python wrapper:** Easy scripting for real-time closed-loop experiments
- **C/C++ library:** High-performance firmware implementations
- **MATLAB/Simulink:** Direct integration with Simulink models
- **LabVIEW:** Alternative real-time platform

**Key Advantage:** Open, documented protocol enables rapid prototyping without vendor lock-in.

---

# PART 3: OTHER MULTI-CHANNEL SYSTEMS

## Overview Table

| System | Channels | Independence | Real-Time API | Price | Key Strength |
|--------|----------|---|---|---|---|
| **Compex Motion** | 4 (expandable) | Full independent | No (memory card) | €6–10k | Clinical-proven, portable |
| **RehaStim 2** | 8 | Full independent | Yes (ScienceMode2) | €12–18k | Open Simulink integration |
| **P24 Science** | 8 | Full independent | Yes (ScienceMode4) | €14–20k | Modern USB-C, open-source |
| **Bioness L300** | 2 | Sequential | Sensor-gated only | €20–25k | Foot drop specialist |
| **Ottobock WalkAide** | 1–2 | Sequential | Sensor-gated only | €15–18k | Wearable drop foot |
| **Abbott Entellect** | 4–8 | Mixed | Proprietary app | €25–35k | BCI-ready architecture |
| **g.tec g.Estim FES** | 1 | N/A (single) | USB Simulink | €3–6k | Impedance monitoring |
| **ExoStim** | 8 | Full independent | Lab PC interface | ~€15k (research) | Modular, expandable |

---

## Multiplexing vs. Independent: Critical Technical Distinction

### True Independent Channels (Compex Motion, RehaStim, ExoStim)

Each channel has its **own current-generation circuit**. All channels can be active simultaneously with different parameters:

```
CH1: 50 mA, 20 Hz, 200 µs  (tibialis anterior)
CH2: 80 mA, 15 Hz, 250 µs  (gastrocnemius)  ← all simultaneously
CH3: 40 mA, 25 Hz, 180 µs  (rectus femoris)
CH4: 60 mA, 18 Hz, 220 µs  (biceps femoris)
```

**Advantage:** Perfect for coordinated multi-muscle activation (bilateral gait, hand grasp with finger flexors + wrist extensors)
**Disadvantage:** Higher cost (more circuitry per channel)

### Time-Multiplexed Channels (Some older FES systems)

A single high-voltage source is **rapidly switched** between channels (μs-level switching):

```
Time 0–10 µs:   CH1 active → delivers pulse to electrode 1
Time 10–20 µs:  CH2 active → delivers pulse to electrode 2
Time 20–30 µs:  CH3 active → delivers pulse to electrode 3
...repeat
```

**Advantage:** Lower cost; fewer high-voltage components
**Disadvantage:** Apparent simultaneous delivery is illusion; true independent frequency/amplitude control is limited (all channels must share timing structure)

---

# PART 4: INTEGRATING MULTI-CHANNEL FES WITH TINYCPG

## Architecture Overview: NEST ↔ FES Hardware Loop

### Conceptual Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Your tinyCPG NEST Model (MareNostrum 5 or Local)            │
│ - Output: L-RG-E, L-RG-F, R-RG-E, R-RG-F (population rates)│
│ - Bilateral extensor/flexor antagonist pairs                 │
│ - Symmetric & asymmetric reciprocal inhibition              │
└─────────────┬───────────────────────────────────────────────┘
              │ (HDF5 spike times every 10 ms or as-needed)
              │
        ┌─────▼──────────────────────────────────┐
        │ Interface Module (Python/C++)           │
        │ - Parse CPG motor output                │
        │ - Normalize to stimulation current      │
        │ - Handle electrode impedance variability│
        └─────┬──────────────────────────────────┘
              │ (USB, ~10 ms latency, real-time loop)
              │
        ┌─────▼──────────────────────────────────┐
        │ Multi-Channel FES Hardware             │
        │ - 8 independent channels                │
        │ - True simultaneous delivery            │
        │ (RehaStim2 or P24 Science)              │
        └─────┬──────────────────────────────────┘
              │ (Current pulses via electrodes)
              │
        ┌─────▼──────────────────────────────────┐
        │ Subject/Patient/Animal Muscles         │
        │ - L tibialis anterior (CH1)            │
        │ - L gastrocnemius (CH2)                │
        │ - L rectus femoris (CH3)               │
        │ - R tibialis anterior (CH4)            │
        │ - R gastrocnemius (CH5)                │
        │ - R rectus femoris (CH6)               │
        └─────┬──────────────────────────────────┘
              │ (Muscle contractions → leg kinematics)
              │
        ┌─────▼──────────────────────────────────┐
        │ Sensory Feedback (Optional Closed-Loop)│
        │ - Force plate (GRF)                    │
        │ - Goniometer (joint angles)            │
        │ - IMU (shank/thigh acceleration)      │
        │ - EMG (remaining voluntary activity)   │
        └─────┬──────────────────────────────────┘
              │ (ADC → USB to control PC)
              │
        ┌─────▼──────────────────────────────────┐
        │ Feedback Processing (Real-Time Loop)   │
        │ - Compute proprioceptive signals       │
        │ - Drive NEST sensory inputs (afferents)│
        └──────────────────────────────────────────┘
```

---

## Detailed Integration Pathways

### Pathway 1: RehaStim 2 + MATLAB/Simulink (Recommended for Rapid Development)

**Setup:**
1. NEST simulation running (local workstation or HPC with output streaming to host PC)
2. MATLAB environment with Simulink + Real-Time Windows Target or xPC
3. RehaStim 2 connected via USB 3.1

**MATLAB/Simulink Model Structure:**

```
NEST Output Stream (UDP/TCP or named pipe from HPC)
   ↓
[Realtime UDP Receiver Block]
   ↓
[Signal Demux: separate L-E, L-F, R-E, R-F spike rates]
   ↓
[Low-Pass Filter: 10 Hz cutoff, smooth noisy rates]
   ↓
[Saturation & Normalization: 0 Hz → 0 mA, max Hz → 150 mA]
   ↓
[RehaStim ScienceMode2 Simulink Block]
   ├─ Channel 1 (L tibialis anterior): input [normalized 0–150 mA]
   ├─ Channel 2 (L gastrocnemius): input [normalized 0–150 mA]
   ├─ Channel 3 (L rectus femoris): input [normalized 0–150 mA]
   ├─ Channel 4 (R tibialis anterior): input [normalized 0–150 mA]
   ├─ Channel 5 (R gastrocnemius): input [normalized 0–150 mA]
   └─ Channel 6 (R rectus femoris): input [normalized 0–150 mA]
   ↓
[USB to RehaStim Hardware]
```

**Advantages:**
- Native MATLAB/Simulink support; HASOMED provides example blocks
- Real-time control loop at 100+ Hz
- Simultaneous 8-channel feedback via attached sensors (force plate, IMU, goniometer)

**Disadvantages:**
- Requires MATLAB license (~€4k/year); Real-Time Windows Target license additional
- Windows-only (Real-Time Kernel)
- ~10 ms latency from PC to hardware (soft real-time; no guarantees)

**Estimated Setup Time:** 4–8 weeks (includes validation of closed-loop stability)

---

### Pathway 2: RehaStim 2 + Python (Maximum Flexibility, Modern Standard)

**Setup:**
1. NEST simulation on any platform (MareNostrum 5, local Linux, Windows)
2. Python 3.8+ environment with ScienceMode4 wrapper library (open-source on GitHub)
3. RehaStim 2 connected via USB

**Python Controller Architecture:**

```python
#!/usr/bin/env python3
import numpy as np
import socket
import threading
from sciencemode4 import RehaStim2Manager  # HASOMED open-source library

# 1. Initialize RehaStim hardware
stimulator = RehaStim2Manager(port='/dev/ttyUSB0')  # or 'COM3' on Windows
stimulator.connect()

# 2. Define electrode mapping (channels 1–6, muscles L/R)
CHANNELS = {
    'L_TA': 1,   # tibialis anterior
    'L_LG': 2,   # lateral gastrocnemius
    'L_RF': 3,   # rectus femoris
    'R_TA': 4,
    'R_LG': 5,
    'R_RF': 6
}

# 3. Real-time control loop: listen to NEST via UDP, command RehaStim
def control_loop():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 9999))  # Port receiving NEST output
    
    while True:
        data, addr = sock.recvfrom(1024)
        
        # Parse NEST motor output (example: "L_RGE:25.5 L_RGF:5.2 R_RGE:12.1 R_RGF:18.3")
        spike_rates = parse_nest_output(data)
        
        # Convert spike rates (Hz) to current amplitudes (mA)
        # Assumption: 10 Hz → 0 mA (baseline), 100 Hz → 120 mA (tetanus)
        currents = {
            'L_TA': max(0, (spike_rates['L_RGE'] - 10) / 90 * 120),
            'L_LG': max(0, (spike_rates['L_RGF'] - 10) / 90 * 120),
            'L_RF': max(0, (spike_rates['L_RGE'] - 10) / 90 * 100),  # co-contract with E
            'R_TA': max(0, (spike_rates['R_RGE'] - 10) / 90 * 120),
            'R_LG': max(0, (spike_rates['R_RGF'] - 10) / 90 * 120),
            'R_RF': max(0, (spike_rates['R_RGE'] - 10) / 90 * 100),
        }
        
        # Send to RehaStim via ScienceMode4 protocol
        for muscle, channel in CHANNELS.items():
            stimulator.set_amplitude(channel, int(currents[muscle]))
        
        # Optional: read feedback sensors (force plate, goniometer, IMU)
        feedback = stimulator.read_sensors()  # if connected
        # ... feed back to NEST as afferent input

if __name__ == '__main__':
    control_thread = threading.Thread(target=control_loop, daemon=True)
    control_thread.start()
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stimulator.disconnect()
```

**Advantages:**
- Cross-platform (Windows, Linux, macOS)
- Open-source; full control over protocol
- No commercial license fees
- Easy integration with other Python neurophysiology libraries (Neo, Elephant, etc.)
- GitHub community provides examples

**Disadvantages:**
- Requires moderate Python expertise
- USB latency ~10 ms (adequate for most gait studies but marginal for high-frequency neural timing)
- Less "polished" than MATLAB Simulink ecosystem

**Estimated Setup Time:** 2–4 weeks (Python expertise assumed)

---

### Pathway 3: Compex Motion + Offline Protocol Design (Lowest Cost, Slower Iteration)

**Setup:**
1. Run tinyCPG; analyze HDF5 output offline to extract bilateral gait phase timing
2. Manually design Compex Motion protocol using GUI memory card programming
3. Test on subject with card-based stimulation (no real-time tuning possible)

**Workflow:**

1. **Extract Gait Timing from NEST:**
   ```python
   import h5py
   h5 = h5py.File('cpg_run.h5', 'r')
   
   # Find L-RG-E, L-RG-F peak firing windows (e.g., L-E: 0–400 ms, L-F: 400–800 ms)
   l_rge_spikes = h5['leg_L']['rge'][:]  # population rate timeseries
   l_rgf_spikes = h5['leg_L']['rgf'][:]
   r_rge_spikes = h5['leg_R']['rge'][:]
   r_rgf_spikes = h5['leg_R']['rgf'][:]
   
   # Identify phase boundaries (zero-crossing detection, peak finding)
   ...
   ```

2. **Design Compex Motion Protocol:**
   - Open Compex Motion GUI software
   - Create 4-channel timeline:
     - CH1: L tibialis (ON during L-E phase)
     - CH2: L gastrocnemius (ON during L-F phase)
     - CH3: R tibialis (ON during R-E phase)
     - CH4: R gastrocnemius (ON during R-F phase)
   - Use built-in timing primitives: pulse trains, wait-for-event, branch conditions
   - Compile to memory card

3. **Test & Iterate:**
   - Load card into hardware
   - Observe subject gait pattern
   - If sub-optimal, redesign protocol and reprogram card (time-consuming)

**Advantages:**
- **Lowest capital cost:** Compex Motion ~€6–10k (vs. RehaStim ~€15k+)
- **No computer dependency:** Portable, battery-powered; works in clinic/field
- **Proven clinical track record:** Used in published rehabilitation studies

**Disadvantages:**
- **Slow iteration:** Design → program → test → redesign cycle is ~1 hour per iteration
- **No closed-loop feedback:** Cannot adjust in real-time based on muscle response
- **Limited real-time parameters:** Stuck with pre-programmed sequences; cannot vary on-the-fly based on CPG dynamics
- **Two sensor inputs only:** Cannot process rich sensory feedback

**Estimated Setup Time:** 1–2 weeks (design + testing on patient/animal)

---

# PART 5: PRACTICAL DECISION MATRIX FOR tinyCPG INTEGRATION

| Requirement | RehaStim 2 + Simulink | RehaStim 2 + Python | Compex Motion |
|-------------|---|---|---|
| **Real-time closed-loop CPG ↔ FES** | ✅ Yes | ✅ Yes | ❌ No |
| **Independent 8-channel simultaneous delivery** | ✅ Yes | ✅ Yes | ⚠️ 4 channels |
| **NEST integration latency <20 ms** | ✅ ~10 ms | ✅ ~10 ms | N/A (offline) |
| **Programmable arbitrary waveforms** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Sensory feedback (force, EMG, IMU)** | ✅ Full 8-ch recording | ⚠️ Custom implementation | ❌ 2-channel analog only |
| **Cost (hardware)** | €12–18k | €12–18k | €6–10k |
| **Cost (software)** | €4k/year (MATLAB) | Free (open-source) | Free (GUI included) |
| **Learning curve** | Moderate (Simulink) | Moderate (Python) | Low (GUI) |
| **Development timeline** | 4–8 weeks | 2–4 weeks | 1–2 weeks |
| **Production deployment readiness** | ✅ High | ✅ High | ✅ High |
| **Academic publication potential** | ✅ Cutting-edge setup | ✅ Cutting-edge setup | ⚠️ Older platform |

---

## Recommendation for Your Research Context

**If your goal is rapid validation of CPG model → FES mapping:**
→ **RehaStim 2 + Python pathway** (optimal cost/complexity/capability balance)

**If you have existing MATLAB infrastructure & require publication in bioengineering venues:**
→ **RehaStim 2 + Simulink pathway** (easier peer-review acceptance, more mature tooling)

**If you need maximum cost savings & can tolerate slower iteration cycles:**
→ **Compex Motion + offline protocol** (suitable for initial clinical feasibility studies before moving to real-time platform)

---

## tinyCPG-Specific Integration Considerations

### 1. Handling Variable Spike Timing from NEST

Your `cpg_2legs_fast.py` outputs **RG-E/RG-F population firing rates** (spikes/second in 10 ms bins). For FES command:

**Biological Constraint:** Ia afferent feedback via `MOD_IA_LOOP` operates on ~10 ms timescale (conduction delays + synaptic integration). Higher temporal resolution FES commands (e.g., 1 ms updates) are biologically implausible unless you're modeling peripheral reflex loops.

**Practical approach:**
- Downsample CPG output to 100 Hz (10 ms bins) for FES command generation
- Higher-frequency NEST dynamics (0.2–1 ms resolution kernel) are preserved in spike train but averaged for stimulation
- This matches typical clinical FES protocols: 20–50 Hz stimulation frequency

### 2. Mapping CPG Output to Stimulation Current

Your NEST model outputs **Hz (spike rate)** from RG populations. Conversion to **mA (stimulation current):**

```
f_Hz = RG population spike rate (0–100+ Hz typical)

I_mA = a₀ + a₁ * f_Hz + a₂ * (f_Hz)²

Example calibration (biologically plausible):
- 0 Hz → 0 mA (no stimulation)
- 20 Hz (resting background) → 10 mA (subthreshold)
- 50 Hz (typical active) → 80 mA (strong contraction)
- 100+ Hz (maximal) → 120 mA (tetanic, saturated)
```

**Non-linearity is expected:** Muscle force follows a sigmoid relationship to stimulation current; biological neural systems use frequency modulation (not linear amplitude mapping).

### 3. Accounting for Electrode Impedance Variability

One major issue in **hardware-in-the-loop validation** is that actual impedance varies across subjects and sessions (skin prep, electrode contact, sweat, etc.). Your stimulation current may differ significantly from commanded current.

**Solutions:**
- **Impedance measurement:** RehaStim & g.Estim FES include built-in impedance checks; record these at session start
- **Feedback adjustment:** If you have muscle sensors (EMG, force plate), implement closed-loop gain adaptation: if observed muscle force is lower than expected, increase stimulation current to compensate
- **Assume ±20% variability** in your modeling/prediction accuracy

---

## Regulatory & Ethical Considerations

### If Testing on Human Subjects:

- **FDA/CE medical device oversight:** RehaStim 2 and Compex Motion are medical devices (if used clinically) or unregulated research tools (if used in research labs)
- **IRB approval required:** Any human testing protocol requires institutional review
- **Informed consent:** Subjects must understand they are receiving FES controlled by an experimental CPG model

### If Testing on Animal Models:

- **IACUC approval:** Animal use protocol must be approved
- **Pain monitoring:** Stimulation parameters (current, frequency) must not cause nociceptor activation (pain)
  - Typical safe range: 1–2 mA sensory, 20–80 mA motor without distress behavior

---

## Conclusion & Implementation Roadmap

The Compex Motion has four biphasic current-regulated stimulation channels and has two input channels that can be configured to measure the output voltage of a variety of sensors. The number of stimulation channels can be expanded in multiples of four channels (8, 12, 16, …) by interconnecting two or more Compex Motion stimulators, and when working in parallel their stimulation sequences and stimulation timings are fully synchronized.

For **your tinyCPG project** seeking to validate bilateral extensor/flexor coordination in a hardware-embodied system:

**Phase 1 (Proof of Concept, 2–4 months):**
- Use RehaStim 2 + Python pathway for real-time closed-loop experiments
- Validate CPG output mapping to muscle forces on a single animal/patient
- Establish baseline movement quality (gait speed, step symmetry, energy expenditure if possible)

**Phase 2 (Optimization, 3–6 months):**
- Tune CPG parameters (STDP weights, drive levels, reciprocal inhibition ratios) based on observed kinematics/dynamics
- Add sensory feedback loop: proprioceptive input (Ia length feedback) closes the loop
- Validate asymmetric reciprocal inhibition hypothesis (`MOD_ZHANG_ASYM`)

**Phase 3 (Dissemination, ongoing):**
- Publish hardware-in-the-loop results validating biologically plausible CPG architecture
- Open-source Python control code + CPG parameter sets
- Provide pathway for other research groups to replicate

**Estimated total project cost:** €20–30k (hardware + some personnel time for integration engineering)

This represents a **high-value, publishable research direction** combining computational neuroscience (NEST) with translational rehabilitation science (FES).
