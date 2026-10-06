# Human data sources for tinyCPG-human validation (PLAN.md Phase 8)

Human counterpart of `emg_data_requests.md` (rat). Order of use follows the plan:
healthy, then incomplete SCI, then complete SCI. Status as of 2026-10-05.

Items marked **(verify)** come from a search snippet or from memory and were not checked
against the source. Check them before they go into the paper or a data request.

## 1. In-house healthy data (available now)

`results/human_data/2026-09-28/{Ctr01,Ctr02}/`: two healthy controls, Delsys Trigno
Discover 2.0.1.3, recorded 2026-09-28. Per subject: `Baseline_1` (quiet standing, 34–52 s)
and `{Slow,Medium,Fast}_{1,2,3}` (one overground walking pass each, 7–20 s, 4–9 strides per leg).

| Item | Content |
|---|---|
| Sensors | 15 Trigno sensors. 8 EMG+IMU: tibialis anterior, gastrocnemius, biceps femoris short head, vastus, L and R (EMG 1259 Hz, IMU 148 Hz). 7 IMU only: foot, shank, thigh L and R, pelvis (370 Hz) |
| Format | `;` separated, decimal comma, 8 header rows; each sensor is a block of (time, value) pairs; sensor order differs between files, so parse by name |
| Not recorded | soleus, force plates or footswitches, walking speed, body height and mass (not in the files) |
| Speed labels | Slow / Medium / Fast only. Stride time, a proxy for speed, ordered correctly in both subjects |

Metrics from `scripts/cpg_human_gait_metrics.py` (medians over strides, both legs; n =
strides after dropping the first and last of each pass). Full numbers, with SDs and the
ensemble envelopes, are in `validation/human_gait_reference.json`.

| Subject | Speed | n | Stride (s) | Stance | Double support | L/R phase (%) | GA peak (% cycle) |
|---|---|---|---|---|---|---|---|
| Ctr01 | Slow | 32 | 1.33 | 0.68 | 0.35 | 49.7 | 40 |
| Ctr01 | Medium | 23 | 1.18 | 0.66 | 0.32 | 49.9 | 40 |
| Ctr01 | Fast | 9 | 1.04 | 0.64 | 0.27 | 50.1 | 40 |
| Ctr02 | Slow | 31 | 1.36 | 0.69 | 0.38 | 50.5 | 48 |
| Ctr02 | Medium | 24 | 1.09 | 0.70 | 0.40 | 49.6 | 48 |
| Ctr02 | Fast | 15 | 0.94 | 0.62 | 0.26 | 50.3 | 45 |

### Limits of this data (read before using it as an acceptance target)

- **n = 2.** The "inter-subject range" of the P8 criterion is the span of two medians.
  The comparison script also reports a band widened by the within-subject stride SD.
- **Stance and double support are IMU estimates, not measured.** Events come from the foot
  gyro (toe-off) and foot accelerometer (heel strike), with no force plate or footswitch to
  check them. Expect ±30–50 ms. The values above are 3–6 points above the usual
  literature (stance ~0.60–0.64 at comfortable speed), and double support is roughly
  2 × stance − 1, so it is the most inflated metric. A model stance of 0.59 vs. a human 0.66
  is therefore not yet a real mismatch. Treat the trends (stance falls with speed, L/R 50 %)
  as solid and the absolute stance level as provisional. A footswitch or force-plate
  recording of the same subjects would settle it.
- **Gastrocnemius stands in for soleus** (model extensor), TA for the flexor. The gastrocnemius is
  biarticular and peaks later in stance than soleus.
- **Few strides at Fast** (9 and 15), because the walkway is short and the first and last
  stride of each pass are dropped.
- **No walking speed in m/s.** If the walkway length was recorded, speed can be added.
- EMG is band-passed 20–450 Hz, rectified and low-passed at 6 Hz, then averaged over
  strides. Burst on/off uses 25 % of the ensemble peak, so it is sensitive to the baseline
  level. The peak position is more robust than on/off, especially for TA, which has two
  bursts (heel strike and swing).

## 2. Public healthy-gait datasets (to compare with and to enlarge n)

| Dataset | What it has | Licence | Fit |
|---|---|---|---|
| Schreiber & Moissenet 2019, *Sci Data* ([paper](https://www.nature.com/articles/s41597-019-0124-4), [figshare 7734767](https://figshare.com/articles/dataset/A_multimodal_dataset_of_human_gait_at_different_walking_speeds/7734767)) | Injury-free adults, straight walkway, 5 speed bands (0–0.4, 0.4–0.8, 0.8–1.2 m/s, self-selected, fast). Motion capture, force plates, 8 EMG probes (Noraxon, 1500 Hz) | CC BY 4.0 on the current version; the first version was GPL 3.0+ | Best match: measured speed, force-plate events (checks our IMU stance), EMG. Subject count and which 8 muscles: **(verify)** |
| Lencioni et al. 2019, *Sci Data* ([paper](https://www.nature.com/articles/s41597-019-0323-z), [figshare collection](https://doi.org/10.6084/m9.figshare.c.4494755.v1)) | 50 healthy subjects aged 6–72, level walking at several velocities, toe and heel walking, stairs. Kinematics, kinetics, EMG; per-subject `.mat` | **(verify)** | Larger n and an age spread, but the age range is wider than adult-only. Muscles and speed definitions: **(verify)** |
| Fukuchi et al. 2018, *PeerJ* ([paper](https://peerj.com/articles/4640/), [figshare 5722711](https://doi.org/10.6084/m9.figshare.5722711)) | Overground and treadmill walking, kinematics and kinetics, c3d and ASCII, metadata sheet | **(verify)** | Timing only (stride, stance, double support vs. speed). **No EMG** as far as found **(verify)** |

Use: stride time, stance and double support against measured speed (Schreiber, Fukuchi)
to fix the offset of our IMU estimates; EMG timing (Schreiber, Lencioni) as a second healthy
reference. Nothing here has been downloaded yet. Each download needs the file list and
size checked first.

## 3a. In-house SCI data (available now)

`results/human_data/2026-10-05/{Exp01..Exp04}/`: four patients, recorded 2026-10-02, same Trigno
setup and file format as section 1. Conditions from the enrollment log, stored without names in
`validation/human_sci_meta.json`:

| ID | Sex, age, height | Worse side | Conditions |
|---|---|---|---|
| Exp01 | M, 46, 190 cm | right | 2 trials with support on the left (`leftsupport`), 2 without |
| Exp02 | F, 60, 159 cm | left | 6 trials, all with a walker |
| Exp03 | M, 66, 170 cm | symmetric | ankles locked at 90°; electrodes detached in trial 6 (log) |
| Exp04 | F, 66, 158 cm | right (left better) | trials 1–3 with a walker, 4–6 (`withoutsupport`) without |

Not in the log: diagnosis, injury level, ASIA grade, time since injury, walking speed, any
stimulation. "Deficit" is the only clinical information.

First look (`validation/human_sci_overview.json`, `plots/human_sci/`):
- **Slow gait:** stride 1.4 s (Exp04), 2.0 (Exp01), 2.2 (Exp03), 2.6 (Exp02) vs 0.9–1.4 s in the controls.
- **EMG asymmetry follows the worse side in Exp02 and Exp01:** Exp02's left gastrocnemius is
  almost silent (2–3 µV vs 13–16 µV on the right); Exp01 is mildly lower on the right.
- **Exp04** has the right TA about twice the left although the left leg is the better one:
  possibly compensation, not checked.
- **Exp03 EMG quality:** trials 5–6 clip at about ±5.5 mV (left TA, both gastrocnemii), and the right
  gastrocnemius has 10× the baseline noise, so the log's "trial 6" understates it: exclude trials 5–6
  for the gastrocnemii and trial 6 for left TA. Left TA also has isolated spikes in trials 2–4. Right
  TA is at the baseline noise level in all trials.
- **Healthy event detector does not carry over:** it gives double support above stance for these
  gaits, so only step-level timing is reported, and step-time asymmetry is unreliable (Exp01
  trial 2 shows 1.58 s vs 0.48 s with consistent strides).

Relevance to the model: walker or side support is partial body-weight support, so Exp04 (with vs
without walker) and Exp01 map onto the loading axis (`--ia-feedback-gain` / `--cut-feedback-gain`),
and the locked ankles in Exp03 are outside the model's ankle coupling (`MOD_ANKLE_JOINT`). One session per
patient, so no recovery time course. The enrollment log contains full names: keep it out of git.

## 3. Human SCI data (needed for P7/P8, mostly not public)

Qualitative targets set in PLAN.md P7. Raw data have to be requested.

| Condition | Target pattern | Source to request from |
|---|---|---|
| Incomplete SCI + EES + training | Stepping degrades without intervention and recovers gradually with training ± EES | Wagner et al. 2018 (*Nature*) **(verify)** |
| Complete SCI, EES frequency | ~5–15 Hz tonic extensor activity; ~25–50 Hz rhythmic E/F alternation | Minassian et al. 2004 **(verify)** |
| Rehabilitation time course | Weeks to months | Harkema et al. 2011; Angeli et al. 2018; Gill et al. 2018 **(verify)** |

What to ask for: per-muscle EMG of the same ankle pair (soleus or gastrocnemius, TA) with
stimulation frequency and amplitude, and for the training studies, the session dates. Request
drafts are not written yet; they follow the format of `emg_data_requests.md` and need
correspondence authors checked first.

## 4. How to run

```bash
python3 scripts/cpg_human_gait_metrics.py                                   # human reference only
python3 scripts/cpg_human_gait_metrics.py --model results/human_modes/<tag>/{slow,comfortable,fast}.h5
```

Writes `validation/human_gait_reference.json` and `plots/human_gait/*.png`. With `--model`
it also prints the model against the human range, per mode and metric.
