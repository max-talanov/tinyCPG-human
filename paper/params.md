# tinyCPG parameter table

## Populations

| Parameter | Value | Units | Description | Source |
|---|---|---|---|---|
| `N_RG_E` | N_RG_TOTAL // 2 | neurons | Rhythm-generator extensor half-centre size | Rybak et al. 2015 |
| `N_RG_F` | N_RG_TOTAL - N_RG_E | neurons | Rhythm-generator flexor half-centre size | Rybak et al. 2015 |
| `N_MOTOR_E` | 100 | neurons | Extensor motor pool size | McCrea & Rybak 2008 |
| `N_MOTOR_F` | 100 | neurons | Flexor motor pool size | McCrea & Rybak 2008 |
| `N_MUS_E` | 100 | relays | Extensor muscle proxy parrot count | — |
| `N_MUS_F` | 100 | relays | Flexor muscle proxy parrot count | — |
| `N_IA_E` | 100 | neurons | Extensor Ia afferent Poisson generators | Loeb 1981; Prochazka 1999 |
| `N_IA_F` | 100 | neurons | Flexor Ia afferent Poisson generators | Loeb 1981; Prochazka 1999 |
| `N_IA_INT` | 50 | neurons | Ia inhibitory interneurons (antagonist) | Jankowska 1992 |
| `N_INE` | 50 | neurons | RG-E → InE → RG-F suppressing INs | Zhang et al. 2022 |
| `N_INF` | 50 | neurons | RG-F → InF → RG-E suppressing INs | Zhang et al. 2022 |
| `N_CUT` | 100 | neurons | Cutaneous/Group-II afferent generators | Pearson 1995; Rossignol 2006 |
| `N_BS` | 100 | neurons | Brainstem reticulospinal drive generators | Drew & Rossignol 1986 |

## Reciprocal inhibition (Zhang 2022 asymmetry)

| Parameter | Value | Units | Description | Source |
|---|---|---|---|---|
| `W_INF2RGE` | -48 | pA | InF → RG-E synaptic weight (STRONG) | Zhang et al. 2022 |
| `W_INE2RGF` | -8 | pA | InE → RG-F synaptic weight (WEAK) | Zhang et al. 2022 |
| `W_RG2INE` | 12 | pA | RG-E → InE excitatory drive | Rybak et al. 2015 |
| `W_RG2INF` | 18 | pA | RG-F → InF excitatory drive | Rybak et al. 2015 |
| `P_RG_RECIP_F` | 0.30 | prob | F→InF→E pathway connection probability | Zhang et al. 2022 |
| `P_RG_RECIP_E` | 0.15 | prob | E→InE→F pathway connection probability | Zhang et al. 2022 |

## Closed-loop Ia feedback (NEW)

| Parameter | Value | Units | Description | Source |
|---|---|---|---|---|
| `W_IA2IN` | 6 | pA | Ia afferent → reciprocal IN (closed-loop) | THIS WORK |
| `P_IA2IN` | 0.25 | prob | Ia → IN connection probability | THIS WORK |
| `W_IA_IN2INT` | 6 | pA | Ia parrot → Ia inhibitory IN | Jankowska 1992 |
| `W_IA_INT2ANT` | -10 | pA | Ia inhibitory IN → antagonist motor pool | Jankowska 1992 |

## Cutaneous reflex

| Parameter | Value | Units | Description | Source |
|---|---|---|---|---|
| `CUT_RATE_ON_HZ` | 100 | Hz | Cutaneous afferent peak firing rate | Loeb 1981; Pearson 1995 |
| `CUT_RATE_OFF_HZ` | 0 | Hz | Cutaneous baseline (off-phase) | — |

## Commissural L↔R

| Parameter | Value | Units | Description | Source |
|---|---|---|---|---|
| `W_COMM_F_INH` | -20 | pA | Flexor commissural inhibition (L↔R) | Kiehn 2016; Talpalar 2013 |
| `P_COMM_F` | 0.22 | prob | Flexor commissural connection probability | Kiehn 2016 |
| `W_COMM_E_INH` | -8 | pA | Extensor commissural inhibition (weak) | Kiehn 2016 |
| `P_COMM_E` | 0.10 | prob | Extensor commissural connection probability | Kiehn 2016 |

## Brainstem drive

| Parameter | Value | Units | Description | Source |
|---|---|---|---|---|
| `BS_REGULAR_HZ` | 60 | Hz | Tonic reticulospinal drive rate (20–80 Hz bio) | Drew & Rossignol 1986 |
| `BS_RATE_BASE_HZ` | 0 | Hz | Baseline BS rate before STDP shaping | — |
| `BS_NOISE_STD_HZ` | 0 | Hz | Gaussian noise on tonic BS | — |

## Izhikevich neurons

| Parameter | Value | Units | Description | Source |
|---|---|---|---|---|
| `RGF_A` | 0.02 | — | RG-F Izhikevich a (intrinsic-bursting set) | Izhikevich 2003 (IB) |
| `RGF_B` | 0.2 | — | RG-F Izhikevich b | Izhikevich 2003 (IB) |
| `RGF_C` | -55 | mV | RG-F Izhikevich c (post-spike reset) | Izhikevich 2003 (IB) |
| `RGF_D` | 4 | — | RG-F Izhikevich d (recovery jump) | Izhikevich 2003 (IB) |
| `I_E_RGE` | 1 | pA | Extensor tonic input current | — |
| `I_E_RGF` | 0.9 | pA | Flexor tonic input current | — |

## STDP plasticity

| Parameter | Value | Units | Description | Source |
|---|---|---|---|---|
| `TAU_PLUS` | 20 | ms | STDP positive time constant | Bi & Poo 1998 |
| `LAMBDA` | 0.001 | — | STDP learning rate | Morrison et al. 2007 |
| `ALPHA` | 0.95 | — | STDP asymmetry (LTD / LTP ratio) | Bi & Poo 1998 |
| `MU_PLUS` | 0.4 | — | STDP positive nonlinearity exponent | Morrison et al. 2007 |
| `MU_MINUS` | 0.4 | — | STDP negative nonlinearity exponent | Morrison et al. 2007 |
| `WMAX` | 120 | pA | STDP weight ceiling (CUT→RG) | — |
| `WMAX_BS` | 30 | pA | STDP weight ceiling (BS→RG) | THIS WORK |

## Activation + force (Hill-like proxies)

| Parameter | Value | Units | Description | Source |
|---|---|---|---|---|
| `TAU_ACT_RISE_MS` | 20 | ms | Activation rise time constant | Zajac 1989; Winters 1995 |
| `TAU_ACT_DECAY_MS` | 20 | ms | Activation decay time constant | Zajac 1989 |
| `ACT_SAT_K` | 0.02 | — | Activation saturation slope | Winters 1995 |
| `ACT_GATE_POWER` | 2 | — | RG-rate gate exponent | THIS WORK |
| `ACT_MAX` | 1.2 | a.u. | Activation ceiling | — |
| `TAU_FORCE_RISE_MS` | 30 | ms | Force rise time constant | Zajac 1989 |
| `TAU_FORCE_DECAY_MS` | 30 | ms | Force decay (relaxation) time constant | Zajac 1989 |
| `FORCE_MAX` | 25 | a.u. | Force ceiling | — |
| `FORCE_SAT_K` | 1 | — | Force saturation slope | — |
| `TAU_LENGTH_MS` | 260 | ms | Muscle length filter time constant | — |
| `L0` | 1 | a.u. | Resting muscle length | — |
| `SHORTEN_GAIN` | 0.010 | — | Force → shortening coefficient | — |
| `STRETCH_GAIN` | 0.35 | — | CUT → extensor stretch coefficient | — |

## Ia spindle rate-coding (NEW)

| Parameter | Value | Units | Description | Source |
|---|---|---|---|---|
| `IA_BASE_HZ` | 10 | Hz | Ia baseline firing rate | Prochazka 1999 |
| `IA_K_FORCE` | 6 | Hz/F | Ia → force sensitivity | Prochazka 1999 |
| `IA_K_STRETCH` | 250 | Hz/L | Ia → stretch sensitivity | Prochazka 1999 |
| `IA_RATE_MAX_HZ` | 500 | Hz | Ia ceiling rate | Prochazka 1999 |

