# EMG data requests for tinyCPG model validation

Generated from the triage table (Google Sheet, `gid=51842667`). Filter applied:
papers ≤ 20 years old (2006–2026), EMG-relevant, spinal/SCI rat, **no dataset
publicly available** (rows already marked "Available" were checked directly —
see the exclusion table at the bottom — and independently confirmed
unsuitable: single-leg-only data, uninjured animals, or kinematics/synergies
without raw EMG). The 1991 paper is out of the 20-year window and was already
flagged in the sheet as too old to pursue.

13 qualifying papers — the original 12, plus the 2021 Nature Communications
paper (moved here after directly verifying that its linked GitHub dataset
doesn't have the EMG, but the paper itself does; see the exclusion table) —
grouped into **7 emails** by *practical* point of contact, to avoid sending
the same lab multiple redundant requests.

**Before sending:** these are drafts. Fill in `[Your name]` / `[affiliation]`
/ `[contact]` in the signature block, and adjust if you want to mention
IRCCS or a specific manuscript title. I have not sent anything — these are
text for you to review, personalize, and send yourself.

## On routing around Prof. Courtine

Four of these papers trace back to Grégoire Courtine's group, but he is a
very high-profile, extremely high-volume PI and personally the least likely
of anyone on this list to read and act on a cold data request. Rather than
address him directly and hope, I restructured the request around **Marco
Bonizzato** as the primary practical contact:

- He is first author on the 2021 Nature Communications paper (the one with
  the muscle pair that matches our needs most closely) and is now an
  **independent, early-career PI** (Polytechnique Montréal) — both more
  likely to personally read a data request and more likely to still know
  exactly where that dataset lives.
- He is *already* a recipient on two other papers in this list (2025
  iScience, 2024 eLife), so this consolidates rather than adds outreach.
- For the two papers Bonizzato was not part of (2014, 2016), each already
  has its own **documented co-corresponding author** on the publication
  itself — Nikolaus Wenger (2014, now PI at Charité Berlin) and Silvestro
  Micera (2016) — who remain cc'd as the legitimate secondary contacts for
  those specific papers, with Bonizzato asked to help route/facilitate if
  he can't answer for those directly.
- The 2009 Nature Neuroscience paper turned out to have a cleaner path
  entirely outside the Courtine bottleneck: **V. Reggie Edgerton** (senior/
  last author) and **Ronaldo Ichiyama** (co-author) are both already on
  this list for their own papers, so I moved that request into the
  Edgerton email instead of routing it through Courtine's group at all.

Courtine himself is still cc'd throughout, as a courtesy and because he is
still the senior author of record, but he is no longer the primary "To" on
anything.

---

## 1. Marco Bonizzato & Marina Martinez (5 papers)
**To:** marco.bonizzato@polymtl.ca, marina.martinez@umontreal.ca
**Cc:** gregoire.courtine@epfl.ch, silvestro.micera@epfl.ch, nikolaus.wenger@charite.de
**Subject:** Data request — hindlimb EMG from your spinal cord injury / neuromodulation studies

Dear Dr. Bonizzato and Dr. Martinez,

I am writing regarding five published studies on spinal cord injury (SCI)
and neuromodulation in rats, three of which involve your own lab directly
and two of which are earlier work from Prof. Courtine's group that your
2021 paper follows on from:

- Bonizzato et al. (2021), *Multi-pronged neuromodulation intervention
  engages the residual motor circuitry to facilitate walking in a rat
  model of spinal cord injury*, Nature Communications.
- (2025), *Combining cortical and spinal stimulation maximizes the
  improvement of gait after spinal cord injury*, iScience.
- (2024), *Cortical neuroprosthesis-mediated functional ipsilateral
  control of locomotion in rats with spinal cord hemisection*, eLife.
- (2014), *Closed-loop neuromodulation of spinal sensorimotor circuits
  controls refined locomotion after complete spinal cord injury*, Science
  Translational Medicine.
- (2016), *Mechanisms Underlying the Neuromodulation of Spinal Circuits
  for Correcting Gait and Balance Deficits after Spinal Cord Injury*,
  Neuron.

We are developing a closed-loop computational model (NEST simulator) of
the two-legged rat spinal central pattern generator, in which cutaneous
and proprioceptive synapses onto the rhythm-generating half-centres
self-organise via spike-timing-dependent plasticity. The model reproduces,
qualitatively, the graded loss and epidural-stimulation-assisted recovery
of hindlimb stepping across weight-bearing conditions (full support,
partial/toe-stepping support, and fully unloaded/air-stepping) that this
body of work has characterised experimentally.

We would like to validate the model's muscle-activity predictions
quantitatively, and are therefore asking whether hindlimb flexor/extensor
EMG recordings from any of the above studies — raw or processed, ideally
spanning more than one loading or stimulation condition — might be
available to us for this purpose. We specifically noticed that the 2021
paper records tibialis anterior and medial gastrocnemius EMG (a
flexor/extensor pair) across several neuromodulation conditions per
animal; its published Source Data file contains the derived per-rat
behavioural metrics but not, as far as we can tell, the underlying raw EMG
traces — it is primarily this kind of trace-level data that would be most
useful to us. We understand the two earlier studies (2014, 2016) may sit
with Prof. Courtine's group more directly, and would be very grateful for
any help pointing us to the right current contact for those if they are
not readily at hand; we noted the 2014 paper's data-availability statement
indicating that data can be made available under a material transfer
agreement, and would be glad to follow whatever process is required.

Thank you very much for considering this request, and please let us know
if any further information about our project would be helpful.

Best regards,
[Your name]
[Your affiliation]
[Contact email]

---

## 2. V. Reggie Edgerton (3 papers)
**To:** vre@ucla.edu
**Cc:** r.m.ichiyama@leeds.ac.uk
**Subject:** Data request — hindlimb/forelimb EMG from your spinal rat stepping studies

Dear Prof. Edgerton,

I am writing regarding three of your studies on locomotor recovery in
spinal rats:

- Courtine, Gerasimenko et al. (2009), *Transformation of nonfunctional
  spinal circuits into functional states after the loss of brain input*,
  Nature Neuroscience.
- (2013), *Neuromodulation of motor-evoked potentials during stepping in
  spinal rats*, Journal of Neurophysiology.
- (2012), *Forelimb EMG-based trigger to control an electronic spinal
  bridge to enable hindlimb stepping after a complete spinal cord lesion
  in rats*, Journal of NeuroEngineering and Rehabilitation.

We are developing a closed-loop computational model (NEST simulator) of
the two-legged rat spinal central pattern generator, in which cutaneous
and proprioceptive synapses self-organise via spike-timing-dependent
plasticity, and which reproduces the graded degradation and
epidural-stimulation-assisted rescue of stepping under reduced
weight-bearing that your group's work has been central in establishing.

We would very much like to validate the model's muscle-activity
predictions against real EMG recordings, and are writing to ask whether
hindlimb (and/or forelimb, for the 2012 study) EMG data from any of these
three papers might be available to us for this purpose, in whatever form
is convenient to share.

Thank you for considering this request.

Best regards,
[Your name]
[Your affiliation]
[Contact email]

---

## 3. Michał Zawiślak (1 paper)
**To:** michal.zawiski@pw.edu.pl
**Subject:** Data request — gait/EMG data from your spinal rat measurement system

Dear Dr. Zawiślak,

I am writing regarding your paper *The System for Measuring Gait
Parameters and Rehabilitation of Spinal Rats* (2024, Acta Physica Polonica
A).

We are developing a closed-loop computational model (NEST simulator) of
the two-legged rat spinal central pattern generator, self-organising via
spike-timing-dependent plasticity, and are looking to validate its
predictions against real gait and, if available, EMG recordings from
spinal-injured rats across different weight-bearing/support conditions.

Since your paper describes a system built specifically for measuring gait
parameters in spinal rats, we wanted to ask whether any recorded datasets
(gait kinematics and/or EMG) from that system might be available for us
to use as a validation reference, even in a limited or example form.

Thank you very much for considering this, and please let me know if I can
provide any further detail about our project.

Best regards,
[Your name]
[Your affiliation]
[Contact email]

---

## 4. Mahima Sharma & M. Fallahrad (1 paper)
**To:** mahima.sharma0@gmail.com, mfallahrad@ccny.cuny.edu
**Subject:** Data request — spinal cord stimulation recordings from your ESAP study

Dear Dr. Sharma and Dr. Fallahrad,

I am writing regarding your paper *Novel Evoked Synaptic Activity
Potentials (ESAPs) Elicited by Spinal Cord Stimulation* (2023, eNeuro).

We are developing a closed-loop computational model (NEST simulator) of
the rat spinal central pattern generator, including an epidural
electrical stimulation analogue, and are seeking real physiological
recordings to validate the model's responses to spinal cord stimulation.

We noted that your custom MATLAB analysis code is available on request,
and wanted to ask whether the underlying evoked-response or EMG datasets
themselves might also be shareable for validation purposes in our
modelling work.

Thank you for considering this request.

Best regards,
[Your name]
[Your affiliation]
[Contact email]

---

## 5. David Magnuson & Anastasia Keller (1 paper)
**To:** dsmagn01@louisville.edu, anastasia.keller@ucsf.edu
**Subject:** Data request — hindlimb EMG data from your rat SCI stretch-reflex study

Dear Dr. Magnuson and Dr. Keller,

I am writing regarding your paper *Electromyographic patterns of the rat
hindlimb in response to muscle stretch after spinal cord injury* (2018,
Spinal Cord).

We are developing a closed-loop computational model (NEST simulator) of
the two-legged rat spinal central pattern generator, in which
proprioceptive and cutaneous synapses self-organise via spike-timing-dependent
plasticity, and we are seeking real hindlimb EMG recordings from
spinal-injured rats to validate the model's flexor/extensor
activity patterns quantitatively.

As your study specifically recorded hindlimb EMG in response to muscle
stretch after SCI, we wanted to ask whether the underlying EMG traces
might be available to us for this purpose, in whatever form is convenient
to share.

Thank you very much for considering this, and please let us know if
further information about our project would help.

Best regards,
[Your name]
[Your affiliation]
[Contact email]

---

## 6. Olivier Alluin & Serge Rossignol (1 paper)
**To:** olivier.alluin@aktantis.com, serge.rossignol@umontreal.ca
**Subject:** Data request — EMG/kinematic recordings from your spinal rat treadmill-training study

Dear Dr. Alluin and Prof. Rossignol,

I am writing regarding your paper *Inducing hindlimb locomotor recovery in
adult rat after complete thoracic spinal cord section using repeated
treadmill training with perineal stimulation only* (2015, Journal of
Neurophysiology).

We are developing a closed-loop computational model (NEST simulator) of
the two-legged rat spinal central pattern generator, self-organising via
spike-timing-dependent plasticity, and are seeking real hindlimb EMG
and/or kinematic recordings from spinal-transected rats across training
sessions to validate the model's predicted recovery of coordinated
stepping.

We understand from the published record that a movie of the locomotor
behaviour accompanies this study; we wanted to ask whether the underlying
EMG or kinematic datasets themselves might also be available for
validation purposes in our modelling work.

Thank you for considering this request.

Best regards,
[Your name]
[Your affiliation]
[Contact email]

---

## 7. Ronaldo M. Ichiyama (1 paper)
**To:** r.m.ichiyama@leeds.ac.uk
**Subject:** Data request — EMG data from your step-training spinal rat study

Dear Dr. Ichiyama,

I am writing regarding your paper *Step Training Reinforces Specific
Spinal Locomotor Circuitry in Adult Spinal Rats* (2008, Journal of
Neuroscience).

We are developing a closed-loop computational model (NEST simulator) of
the two-legged rat spinal central pattern generator, in which sensory
synapses onto the spinal rhythm generators self-organise via
spike-timing-dependent plasticity, and are seeking real hindlimb EMG
recordings from step-trained spinal rats to validate the model's
predicted muscle-activity patterns.

We would be very grateful if the EMG data underlying this study — or any
comparable dataset from your group's work on spinal locomotor training —
might be available to us for this purpose. (You may also see a related
request reach you as a cc on a note to Prof. Edgerton, regarding the 2009
Nature Neuroscience paper you both co-authored.)

Thank you for considering this request.

Best regards,
[Your name]
[Your affiliation]
[Contact email]

---

## Papers excluded from the request list (for reference)

| Paper | Year | Reason (verified by directly inspecting the dataset/paper, 2026-07-21) |
|---|---|---|
| EMG patterns of rat ankle extensors and flexors during treadmill locomotion and swimming | 1991 | Outside the 20-year window; sheet notes "too old to obtain data" |
| Nanogenerator Neuromodulation... (Adv. Sci. 2025) | — | Checked PMC full text directly: **rats are not spinal-injured** (acute exposed-cord stimulation in intact animals); only one unnamed, unspecified hindlimb muscle recorded (no flexor/extensor pair); the two compared conditions are stimulation-hardware types (custom nanogenerator vs. commercial stimulator), not loading or injury. Not usable for any of our metrics. |
| EMUsort Rat Datasets (Dandi) | — | Checked DANDI metadata directly: 16-channel recording is from **forelimb triceps brachii** in an intact (uninjured) rat, a single muscle with no antagonist pair, only 3 sessions all at the same treadmill speed/incline. Wrong limb, wrong muscle count, no speed variation — not usable. |
| Multi-pronged neuromodulation... (Nat Commun 2021, Bonizzato et al.) | — | The GitHub repo listed in the sheet (`M1-MLR`) contains only **cortical + midbrain neural** multi-unit data, no EMG at all. However, checking the paper itself: it *does* record tibialis anterior (flexor) + medial gastrocnemius (extensor) EMG, unilaterally, in real contusion-SCI rats, across multiple loading/neuromodulation conditions — a good match for our needs. Its Nature-hosted Source Data file (`MOESM5_ESM.xlsx`, downloaded and inspected) contains only **derived per-rat summary statistics** (step-height modulation, decoding accuracy, lesion size) for each figure, not raw EMG traces. **Requested in email 1 above** (addressed to Bonizzato directly, as first author). |
| AnMod_Neuro (GitHub homework repo) | — | Not a primary dataset; no EMG data |
| Spinal control of locomotion before/after SCI (Danner lab) | — | Dataset available (kinematics) but no EMG |
| Dataset of measured kinematics... (Zenodo) | — | Kinematics/synergies only, no EMG |
| Operation of spinal sensorimotor circuits controlling phase... | — | Dataset available but no EMG (per sheet) |
| Operation regimes of spinal circuits controlling locomotion | — | Collected from a non-rat species |
