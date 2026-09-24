# Spinal Cord Plasticity as a Learning Specification

Companion document to [`CLAUDE.md`](CLAUDE.md). It asks what a bio-plausible
learning rule in `cpg_2legs_fast.py` should look like if the specification
comes from **published spinal-cord plasticity data** rather than from generic
machine-learning practice, in service of the current debug goal —
"keep alternating when BS drops from 60 to 20 Hz, relying on Ia closed-loop
feedback instead of the brainstem."

Scope is deliberately narrow: **spinal cord only**. The evidence is
predominantly rat; where a claim rests on another species — cat for the
task-specific locomotor training results, mouse for the acquisition/recall
interneuron dissociation, human for the intermittent-hypoxia walking trials,
bullfrog for one homeostatic-upscaling result — the reference list says so,
because the transfer to rat is an assumption rather than a finding. Where a
term from the
hippocampal synaptic-tagging-and-capture (STC) literature is used — "tag",
"capture", "plasticity-related proteins" — it is used as familiar shorthand
for a shape that the *spinal* literature documents independently, not as a
source of evidence. No claim here rests on a hippocampal result.

The short version: the spinal cord has its own, independently documented
version of the same computational problem — a fast, decaying change that
becomes permanent only if a separate, slower gating signal arrives in time.
**§1** lays out the timescales of that machinery in **motor** circuits,
healthy and after injury. **§2** covers the gating signals that decide what
gets kept, led by the serotonergic one, which is both the best-documented and
the most directly therapeutic. **§3** treats **nociceptive** (dorsal-horn)
plasticity separately: it runs the same two-phase machinery, but on a
different pathway, with a different gate, toward a different outcome, and
mixing it into the motor account obscures more than it explains. **§4** maps
the result onto the three plastic pathways already in this model.
Implementation is deliberately out of scope — see the separate plan.

## 1. Motor-circuit plasticity: timescales

Everything in this section is **motor**: rhythm-generating interneurons,
motoneurons, and the afferent pathways that drive them. Dorsal-horn
nociceptive plasticity is a different pathway with a different gating signal
and is treated on its own in §3 — the two are never mixed in one table or one
chart here, even where they share molecular machinery. §1.1 and §1.2 split
the motor processes by outcome (adaptive vs. after-injury), using the same
columns, axis and scale so the two are directly comparable.

### 1.1 Healthy / adaptive processes

![Twelve healthy motor-circuit plasticity processes on one logarithmic time axis from 1ms to twelve weeks, one round-capped bar per Table 1a row, each labelled with its reference numbers in a colour matching its own bar, sorted fastest-onset-first top to bottom and colored by mechanism family along a fast-to-slow hue ramp — blue for NMDAR/AMPAR induction and short-term plasticity, teal for serotonergic CPG gating, green for Grau's contingent spinal instrumental learning, olive for the two-phase E-LTP/L-LTP cascade in motor circuits, orange for Wolpaw's two-phase H-reflex conditioning, brick red for homeostatic AMPAR upscaling, mauve for Côté's activity-dependent step-training, and purple for de Leon/Roy/Edgerton's contested task-specific spinal locomotor learning — bar position marks onset, length marks characteristic duration.](spinal_timescale_healthy.png)

*Fig. 1a — The twelve rows of Table 1a, one bar each, in the same order, sorted by onset: baseline physiology (induction, short-term plasticity, acute serotonergic gating) plus every motor mechanism whose documented outcome is functional preservation or recovery. Bracketed numbers on each bar are the same reference keys as Table 1a's Refs column. The two olive bars are the two-phase LTP cascade in its motor instantiation; the same cascade on the nociceptive pathway is §3, kept out of this chart on purpose. Palette, capsule bars and colour-matched row labels follow the companion hippocampal timescale figure; one colour per mechanism family, so a family reads identically in Fig. 1b. Bars are drawn with round caps shortened by the cap radius, so a bar's outer extent still marks its true onset and duration; a bar whose span is narrower than one cap (here, step-training) is drawn at that floor and is therefore slightly overstated.*

| Process | Refs | What it is | Time constant | Site / pathway | What it constrains for a spiking-network model |
|---|---|---|---|---|---|
| NMDAR/AMPAR-dependent synaptic induction | — | The basic ionotropic-glutamate-receptor gating that every mechanism below is built on top of. | ms-scale, same coincidence physics as everywhere else in CNS | Ubiquitous (dorsal horn, motoneuron) | The fast coincidence-detection floor every mechanism below is built on — general CNS physiology, not spinal-specific. |
| Short-term plasticity (facilitation/depression) | — | Transient, non-associative changes in synaptic efficacy that decay within a single behavioral episode, leaving no lasting trace. | ~10 ms–1 s | Ubiquitous (receptor deactivation and vesicle-pool kinetics) | Not spinal-specific either, but still a real constraint: this is why a millisecond-scale coincidence window exists at all, underneath every pathway-specific mechanism below. |
| Serotonergic (5-HT) neuromodulatory gating of CPG excitability — acute | [[22]](#ref-22)[[23]](#ref-23) | Moment-to-moment 5-HT release from descending brainstem projections that sets whether the CPG's rhythm-generating interneurons can burst at all, independent of any lasting weight change. | Seconds (state-dependent gating of whether rhythmic bursting can occur at all) | Brainstem-to-spinal monoaminergic projections onto CPG interneurons and motoneurons | The model's tonic `BS_REGULAR_HZ` drive is a generic reticulospinal proxy; the literature's actual candidate for "descending drive that gates whether the spinal rhythm-generator can run" is specifically serotonergic/noradrenergic. |
| Spinal instrumental learning — **contingent** (adaptive) | [[1]](#ref-1)[[2]](#ref-2) | Response-contingent training (e.g., a limb flexion that terminates shock) that changes spinal reflex output for hours to days, entirely below a complete spinal transection. | Acquisition within a single session (tens of minutes); consolidation requires new protein synthesis over the following hours | Interneuron + motoneuron circuits caudal to a complete spinal transection — no brain involvement (Grau et al.) | The adaptive half of a bidirectional gate — see §1.2 for what the identical training produces when the outcome is uncontrollable instead. |
| Early-phase LTP in spinal **motor** circuits (E-LTP) | [[1]](#ref-1)[[4]](#ref-4)[[6]](#ref-6) | NMDAR-dependent, protein-synthesis-independent early potentiation, induced in motor/interneuron circuits by contingent training. In transected rats, intrathecal MK-801 blocks *induction of the learning* while leaving the shock-elicited motor response intact, i.e. the NMDAR-dependence belongs to the plasticity, not the reflex [[1]](#ref-1)[[4]](#ref-4). Independently documented in intact motor pathways as corticospinal-tract LTP onto spinal interneurons and motor pools [[6]](#ref-6). | Minutes to induce; decays within hours unless stabilized | Interneuron/motoneuron circuits caudal to a transection; corticospinal-tract terminations onto spinal interneurons | **This is what makes the model's "tag" a motor-circuit mechanism rather than an import from the pain literature.** The same two-phase machinery also runs on the nociceptive pathway (§3) — same molecules, different pathway, different outcome. |
| Late-phase LTP in spinal **motor** circuits (L-LTP) | [[1]](#ref-1)[[4]](#ref-4)[[7]](#ref-7) | Protein-synthesis-dependent stabilization of the row above into a lasting change in spinal reflex output. Instrumental learning elevates BDNF, CaMKII, CREB and synapsin I in the lumbar cord, with the BDNF/CREB/CaMKII increases **proportional to learning performance** — the canonical late-phase consolidation cascade, in motor circuits. | Onset within hours; persists ≥24 h (metaplastic effects still measurable a day post-training) | Same circuits caudal to the transection (Grau et al.) | The motor-circuit "capture" step. Its gating signal, BDNF, is supplied by the serotonergic mechanism in §2.1 and is also what the nociceptive pathway draws on (§3) — a **shared resource, not a pathway-specific signal**, which is the strongest single justification for the model's per-leg shared `prp_pool` rather than per-synapse gating. |
| H-reflex operant conditioning, Phase I | [[8]](#ref-8) | The first, small, rapidly-developing component of operant conditioning of the monosynaptic stretch reflex, visible within 1-2 days of daily training. | 1–2 days; small magnitude | Ia-afferent → motoneuron monosynaptic pathway + interneurons (Wolpaw) | The fast, labile component of a two-phase learning process running entirely on the pathway this model calls `Ia→RG`. |
| Homeostatic AMPAR **upscaling** after deafferentation / chronic inactivity | [[24]](#ref-24)[[27]](#ref-27) | A compensatory, cell-wide increase in motoneuron AMPAR-mediated synaptic strength that partly offsets a chronic loss of afferent drive. | Hours–days; mediated by synaptic insertion of GluA2-lacking, Ca²⁺-permeable AMPA receptors | Motoneurons below an injury or period of inactivity | The literature's own mechanism for "what happens when descending/afferent drive is chronically reduced" is an active receptor-composition change with its own kinetics — not a static gain multiplier. Directly relevant to why the model's `--wmax-ia-unloaded` gain-based unloading-rescue attempts plateaued (see [CLAUDE.md](CLAUDE.md), "Core architecture fix" section). |
| Activity-dependent step-training neurotrophin upregulation | [[14]](#ref-14)[[15]](#ref-15) | Repeated, task-specific locomotor training that raises BDNF/NT-3/NT-4 in the lumbar cord below an injury, with the training *type*, not just its amount, determining the outcome. | Daily training over days–weeks; **task-specific** (step-training and cycle-training produce different BDNF/NT-3/NT-4 profiles and different dorsal-horn/intermediate-gray neuron counts) | Lumbar spinal cord below a lesion [[14]](#ref-14) | Argues against a single generic "activity level" gate — the training *modality*, not just its amount, sets what gets reinforced. Directly relevant to this model's distinction between `--cut-trigger force` (stance-loading-driven) and the paced-clock modes. |
| Serotonergic gating — chronic, **training-restored** | [[22]](#ref-22)[[23]](#ref-23) | The same slow, injury-driven change in CPG serotonin sensitivity as §1.2's untreated case, but partly reversed by locomotor training and serotonergic agonists. | Days–weeks | Brainstem-to-spinal monoaminergic projections | Its *sensitivity*, not just its rate, changes with training — a second, slower plasticity axis this model does not yet represent (flagged here, not addressed by the plan in §3). |
| H-reflex operant conditioning, Phase II | [[8]](#ref-8)[[9]](#ref-9) | The slow, large, multi-site component of H-reflex conditioning — altered motoneuron firing threshold, GABAergic terminal density, and interneuron properties — that consolidates over weeks of continued training. | 6–7 weeks; large, stable; **multi-site** | Same pathway | Demonstrated to correct locomotor asymmetry after spinal cord injury when combined with training — the closest published result to the model's own stated rehab goal. |
| Task-specific spinal locomotor learning (train-to-stand vs. train-to-step) | [[11]](#ref-11)[[12]](#ref-12); contested by [[13]](#ref-13) | Complete-transection cats trained daily to either stand or step relearn specifically the trained task — stand-trained cats stand well but step poorly, and step-trained cats step well but stand poorly — the clearest behavioral demonstration that the isolated lumbar CPG itself, not just a single reflex pathway, can be shaped by training [[11]](#ref-11), framed explicitly as spinal motor learning by [[12]](#ref-12). **Contested**: a later study found both standing and locomotion recover under non-task-specific stimulation, or with no training at all, attributing recovery to a general return of spinal circuit excitability rather than task-specific activity-dependent encoding [[13]](#ref-13) — an open controversy, not resolved here. | Daily training, ~8–12 weeks to a stable task-specific outcome | Lumbar locomotor CPG circuitry below a complete thoracic spinal transection (cat) | The strongest available evidence that a CPG core like this model's `RG-E`/`RG-F` — not just an afferent pathway — is a legitimate target for a "trained skill" framing. But the Harnie et al. 2019 contestation means this row shouldn't be read as an uncontested green light for CPG-level consolidation the way Wolpaw's Ia→motoneuron pathway is (§3's `Ia→RG` mapping stands on Wolpaw's result specifically, not on this one). |

*Table 1a — The twelve rows plotted in Fig. 1a above: baseline physiology plus every mechanism whose documented outcome in the cited literature is functional preservation or recovery. Three rows (spinal instrumental learning, homeostatic AMPAR upscaling, the serotonergic chronic axis) are one half of a bidirectional mechanism whose maladaptive counterpart is in Table 1b. The two LTP rows and the instrumental-learning row describe the **same experiments at different levels**: instrumental learning is the behavioral phenomenon, the LTP rows are its synaptic substrate. They are listed separately because §4 maps onto the synaptic level, not the behavioral one — not because they are independent findings.*

### 1.2 Pathological motor-circuit processes (after spinal cord injury)

![Three pathological motor-circuit plasticity processes on the same logarithmic time axis as Fig. 1a, one round-capped bar per Table 1b row with its reference numbers, labels colour-matched to their bars, hatched to distinguish them from the healthy set and colored by the same mechanism-family scheme — green for Grau's non-contingent maladaptive suppression, brick red for KCC2-loss-driven homeostatic downscaling failure, and teal for untreated chronic serotonergic dysregulation.](spinal_timescale_pathological.png)

*Fig. 1b — The three rows of Table 1b, one bar each, in the same order, on the same axis, scale, color scheme and reference keys as Fig. 1a — and at identical row pitch and bar thickness, so the two are directly comparable but never rendered as one mixed chart. Every row here has a counterpart in Fig. 1a in the same color: the pathology is a different *outcome* of the same machinery, not an extra mechanism. Chronic pain is absent by design — it is a nociceptive-pathway outcome and lives in §3.*

| Process | Refs | What it is | Time constant | Site / pathway | What it constrains for a spiking-network model |
|---|---|---|---|---|---|
| Spinal instrumental learning — **non-contingent** (maladaptive) | [[1]](#ref-1)[[3]](#ref-3)[[5]](#ref-5) | The same training paradigm as §1.1's contingent case, but with the shock uncontrollable instead of response-produced. | Same acquisition/consolidation window as the contingent case — the outcome, not the timing, differs | Same circuits (Grau et al.) | An active, protein-synthesis-dependent **suppression** of future learning capacity, not merely an absence of learning — a bidirectional gate, not a one-way accumulator. |
| Homeostatic **downscaling failure** (KCC2 loss, spasticity) | [[25]](#ref-25)[[26]](#ref-26) | Instead of excitation scaling down to compensate for hyperactivity, motoneuron KCC2 (which sets the Cl⁻ gradient underlying GABA/glycine inhibition) is chronically **downregulated** after SCI, producing spasticity. | Onset within hours of injury; partial training-driven recovery over weeks | Motoneuron membrane Cl⁻ transporters, below a spinal cord injury | The spinal-specific evidence that "homeostatic compensation" is not automatically adaptive — it can fail in the *opposite* direction from §1.1's upscaling row, and, critically, that failure is training-reversible [[25]](#ref-25) (see Fig. 2b), not fixed. |
| Serotonergic gating — chronic, **untreated** | [[22]](#ref-22)[[23]](#ref-23) | The same injury-driven change in CPG serotonin sensitivity as §1.1's training-restored case, left to persist. | Days–weeks, and beyond without intervention | Brainstem-to-spinal monoaminergic projections | The pathological anchor for the same axis §1.1 shows can be treated — the two rows differ only in whether training happened, exactly like the KCC2 row above. |

*Table 1b — The three rows plotted in Fig. 1b above: the motor-circuit processes whose documented outcome after injury is degraded function. **Every one pairs with a Table 1a row** (instrumental learning directly; homeostatic scaling via §1.3; the serotonergic axis via its training-restored counterpart) — there is no mechanism here that the healthy cord does not also run; only the gating signal and the outcome differ (§2.4). Chronic/neuropathic pain is deliberately absent: it belongs to the nociceptive pathway, which is §3.*

### 1.3 Bidirectional homeostatic scaling: upscaling and downscaling

The upscaling row above is one direction of a bidirectional mechanism —
chronic silencing drives synaptic **upscaling**, chronic hyperactivity drives
synaptic **downscaling**, the same AMPAR-trafficking toolkit running in
opposite directions to hold network activity near a set point [[24]](#ref-24). The rat spinal cord shows the upscaling side cleanly (deafferentation
→ GluA2-lacking, Ca²⁺-permeable AMPAR insertion in motoneurons, already in
the table). The downscaling side is more interesting than a simple mirror
image: after SCI, the dominant documented failure mode is not "excitatory
synapses fail to scale down" but **inhibitory efficacy itself collapsing** —
KCC2, the potassium-chloride cotransporter that keeps the Cl⁻ reversal
potential hyperpolarized enough for GABA/glycine to inhibit, is
downregulated in motoneuron membranes after SCI [[25]](#ref-25),
functionally a failed downscaling response — excitability stays elevated
because the compensatory brake never engages — and a well-established
mechanistic account of post-SCI spasticity.

**This closes the loop with the document's rehab framing rather than sitting
outside it**: the same Boulenguez-line literature reports that locomotor
training partially restores KCC2 expression and reduces spasticity, i.e. the
homeostatic failure is *training-reversible*, not fixed — precisely the
"does training restore lost function" question this whole document exists to
give a mechanistic answer to, on a completely different pathway (chloride
homeostasis) than the tag-and-capture story in §2.

![Two-panel chart: (a) synaptic AMPAR weight rising smoothly from baseline to a compensated plateau over about three days after deafferentation (healthy upscaling); (b) motoneuron KCC2/inhibitory efficacy dropping sharply at spinal cord injury, then either staying flat at the reduced floor with no training (dashed red, spasticity persists) or partially recovering toward baseline over several weeks with locomotor training (solid green) (pathological downscaling failure).](spinal_scaling_dynamics.png)

*Fig. 2 — Bidirectional homeostatic scaling. **(2a) Healthy** (left): the upscaling response to deafferentation — a single, reliably-reported trajectory; there is no "blocked" condition in the cited literature, so only one trace is shown. **(2b) Pathological** (right): KCC2 loss (downscaling failure) after SCI, training vs. none — both traces take the identical acute post-injury drop; they diverge only in whether locomotor training is applied afterward, which is the spinal analog of "capture" rescuing an otherwise-lost trace. Curve shapes are illustrative (exponential fits to the qualitative time course each citation reports), not digitized data.*

### 1.4 Which of Table 1a's rows are motor-skill-formation mechanisms specifically

Table 1a's scope statement is "baseline physiology plus every mechanism whose
documented outcome is functional preservation or recovery" — deliberately
broader than "motor skill formation." Checking the twelve rows against the
narrower definition that this document's spinal-only scope forces (a
lasting, practice- or contingency-dependent change in **spinal** circuit
output, demonstrated without the brain driving it — typically below a
complete transection) sorts them into four groups, not one:

| Process | Refs | Category | Why |
|---|---|---|---|
| Spinal instrumental learning — contingent (Grau) | [[1]](#ref-1)[[2]](#ref-2) | **Core skill-formation mechanism** | A trained, lasting, contingency-gated change in spinal reflex output — the literal definition. |
| H-reflex conditioning, Phase I | [[8]](#ref-8) | **Core skill-formation mechanism** | A trained, lasting change in a spinal reflex, by construction. |
| H-reflex conditioning, Phase II | [[8]](#ref-8)[[9]](#ref-9) | **Core skill-formation mechanism** | The consolidated, multi-site version of the same trained change. |
| Task-specific spinal locomotor learning (de Leon/Roy/Edgerton) | [[11]](#ref-11)[[12]](#ref-12)[[13]](#ref-13) | **Core skill-formation mechanism — contested** | The only row directly about the CPG's own output pattern, not an afferent pathway or a withdrawal reflex; but its task-specificity claim is itself disputed [[13]](#ref-13), see Table 1a — counted here as core, flagged as unsettled, not a second confirmed Wolpaw-grade result. |
| E-LTP / L-LTP in motor circuits | [[1]](#ref-1)[[4]](#ref-4)[[6]](#ref-6)[[7]](#ref-7) | **Substrate of skill formation, not a separate skill** | These two rows are the synaptic machinery the Grau and Wolpaw rows above run on, not an independent behavioral phenomenon — counted here once, as substrate, to avoid double-counting the same experiments at two levels of description. Distinct from the generic NMDAR/AMPAR row below in that this is the *two-phase, consolidation-gated* form specifically, which is what §4 maps onto. |
| Homeostatic AMPAR upscaling | [[24]](#ref-24)[[27]](#ref-27) | Enabling/compensatory | Restores lost excitability after deafferentation; carries no information about *which* pattern was learned. |
| Serotonergic gating, chronic (training-restored) | [[22]](#ref-22)[[23]](#ref-23) | Enabling/compensatory | Gates whether the CPG can burst at all; same reasoning as its acute counterpart. |
| Step-training neurotrophin upregulation (Côté) | [[14]](#ref-14)[[15]](#ref-15) | Molecular correlate, not the mechanism itself | Row is framed as a BDNF/NT-3/NT-4 readout; the actual skill-refinement outcome — multisegmental network reorganization and reduced muscle co-contraction with training — isn't named. Flagged as a content gap here, not corrected in Table 1a itself. |
| NMDAR/AMPAR-dependent induction | — | Basic substrate | Generic coincidence-detection floor every mechanism above (skill-forming or not) runs on top of. |
| Short-term plasticity | — | Basic substrate | Same — a physics constraint, not a learning mechanism. |
| Serotonergic gating, acute | [[22]](#ref-22)[[23]](#ref-23) | Basic substrate | Gates *whether* bursting can occur, not *which* pattern is learned. |

Net: **4 of the 12 rows are motor-skill-formation mechanisms in the strict
spinal-specific sense (one of them contested); the other 8 are the
substrate, enabling or compensatory processes those mechanisms operate
within.** This doesn't make Fig. 1a wrong — its stated scope already
includes prerequisites, not just the skill-encoding step — but a reader
treating "healthy spinal plasticity processes" as synonymous with "how the
spinal cord forms a motor skill" would still overcount, and one of the four
core rows shouldn't be leaned on as settled evidence either way. Note the
two motor-circuit LTP rows are the *substrate* of the Grau and Wolpaw
mechanisms rather than additional skills — they raise the denominator
without raising the numerator, by design.

**Caveat — a tempting addition, checked and left out.** The spinal motor
primitives / muscle synergies framework (force-field modules the spinal cord
combines to build movements — Bizzi, Giszter and colleagues; structurally
close to this model's own extensor/flexor half-center split) looks like a
natural missing row. Checked
directly before proposing it: the primitives themselves are reported as
largely fixed and conserved from early development rather than something
training forms anew — "motor primitives are determined in early
development and are then robustly conserved into adulthood"
[[34]](#ref-34) — with
training/injury changing the excitatory/inhibitory *recruitment weighting*
of primitives, not the primitives' own structure
[[35]](#ref-35).
That reweighting is arguably already covered by the homeostatic-scaling and
serotonergic-gating rows already in the table. **Not added as a row** — it
would misrepresent something conserved/fixed as a plasticity process with
its own induction timescale. Note the contrast with the two LTP rows added
above: those earned a place because the *mechanism* is documented running in
spinal motor circuits with its own induction and consolidation kinetics,
whereas motor primitives are reported as a fixed developmental substrate
that training recruits rather than forms. It remains a useful *structural*
analogy for the model's RG-E/RG-F architecture, not a literature-grounded
addition to Table 1a.

*(Broader locomotor-training review consulted for this check, beyond the
Côté citation already in Table 1a:
[[15]](#ref-15),
which documents the multisegmental-reorganization/reduced-co-contraction
outcome flagged as the Côté-row gap above.)*

## 2. What gates motor consolidation

§1 establishes that motor circuits run a two-phase change — fast NMDAR-
dependent induction, slow protein-synthesis-dependent stabilization. This
section is about the signal that decides **which** changes survive the
transition. Three gates are documented, and they operate at different
levels: a neuromodulatory one (§2.1) that supplies the raw material for
consolidation, a behavioral one (§2.2) that sets its sign, and a structural
one (§2.3) that shows what a fully consolidated trace looks like weeks
later. §2.4 lists the adaptive and maladaptive settings of each.

The acquisition/retention division of labor these gates imply is not only
inferential: in mouse spinal circuits, acquiring a sensorimotor adaptation and
recalling it depend on *different* interneuron classes — dorsal-horn
interneurons for acquisition, Renshaw cells for retention and recall [[10]](#ref-10). A
model that keeps the labile and the stable component in separate state
variables, as `--consolidate` does, is matching a real dissociation rather
than only a convenient abstraction.

A terminology note, since it recurs below: no spinal-cord literature uses
the phrase "synaptic tagging and capture." That framework was developed in
hippocampus, and is used here only as compact vocabulary for a
division of labor the spinal literature demonstrates in its own terms — a
labile change that decays unless a separately-supplied, diffusible resource
stabilizes it.

### 2.1 Serotonergic gating: the supply side of consolidation

Elsewhere in this document serotonin appears as an excitability knob — it
sets whether the CPG can burst at all (§1.1). That undersells it. **5-HT is
also the best-documented trigger for lasting, protein-synthesis-dependent
plasticity in spinal motor circuits**, and the mechanism has a tag/capture
division of labor built into it.

The model system is phrenic long-term facilitation (pLTF): episodic hypoxia
drives episodic serotonin release onto phrenic motoneurons, producing a
lasting increase in motor output. Its requirements are explicit —
**spinal serotonin-receptor activation and new protein synthesis**
[[16]](#ref-16), with cervical 5-HT2A *and* 5-HT2B both necessary [[17]](#ref-17), signalling through newly synthesised **BDNF** and its
receptor **TrkB**. 5-HT7 receptors form a second, PKA-dependent pathway that
*constrains* pLTF rather than driving it [[18]](#ref-18)[[19]](#ref-19) — the gate is not a single
monotonic knob.

Two features make this the closest biological match to what `--consolidate`
implements:

- **Induction and maintenance are dissociable.** 5-HT2 receptor activation is
  necessary to *induce* pLTF but not to *maintain* it once established. That
  is the tag/capture split stated in the literature's own experimental terms:
  the gating signal is required at the moment of stabilization and dispensable
  afterwards — exactly the relationship between the model's `prp_pool`
  crossing threshold and the resulting frozen `baseline`.
- **The resource is supplied separately from the thing being trained.** This
  is clearest in the therapeutic form. Acute intermittent hypoxia (AIH)
  supplies episodic 5-HT → BDNF/TrkB systemically, and by itself it is not a
  motor skill. Its effect on behavior depends on being **paired with
  task-specific training**: AIH plus ladder-walking training produces
  near-complete recovery of ladder walking in rats with incomplete SCI, with
  the gain persisting weeks past treatment [[21]](#ref-21), and daily AIH plus walking
  training improves walking speed and endurance in humans with chronic
  incomplete SCI [[20]](#ref-20). The neuromodulator supplies availability; the training
  decides which synapses use it.

That second point is this document's warrant for modelling the resource as
**supplied independently of the synapses that use it** — an accumulator fed
by events, not a per-synapse variable. (§3 supplies the complementary
evidence that the resource is also *finite*, from two processes depleting
each other.) Together they justify the model's per-leg `prp_pool` rather than
independent per-synapse gating. The supply-side account also predicts
something the model reproduces: a resource supplied too freely
consolidates whatever happens to be active, which is over-consolidation
(§4's leg-synchronization failure mode), while a resource never supplied
leaves every trace to decay (§4's inert configurations).

### 2.2 Contingency gating: the sign of consolidation

In transected rats, response-contingent training (a limb flexion that
terminates shock) produces NMDAR/BDNF/protein-synthesis-dependent
potentiation that outlasts the session [[1]](#ref-1)[[2]](#ref-2). The
gate is **bidirectional and set by contingency, not activity level**:
identical, uncontrollable shock produces the opposite outcome — active,
protein-synthesis-dependent suppression of future learning, via group-I
mGluR/PKC signaling, not merely an absence of reinforcement (Ferguson et al. 2008) [[3]](#ref-3).

This is what makes the gate a *decision* rather than an accumulator, and it
is the direct justification for the model treating a genuine force-threshold
bout ending and a failsafe-forced one as opposite-signed evidence rather than
as "reinforced" and "not reinforced."

### 2.3 Structural consolidation: what a kept trace becomes

H-reflex operant conditioning in rats — training the monosynaptic
Ia-afferent-to-motoneuron reflex directly — shows a fast, small Phase I
(1–2 days) and a slow, large, multi-site Phase II (6–7 weeks: motoneuron
firing threshold, GABAergic terminal density, interneuron changes)
[[8]](#ref-8). Up-conditioning
**corrects locomotor asymmetry after spinal cord injury in rats** — the
closest published result to this model's own debug goal, achieved by
consolidating exactly the `Ia→RG` pathway this model represents.

**Synthesis.** The three gates act on the same underlying two-phase change at
different points: 5-HT/BDNF supplies the resource, contingency sets the sign,
and continued training determines how far the structural change goes. None of
them is a simple accumulator — each has a documented setting in which it
makes function *worse*, which §2.4 lists.

### 2.4 Adaptive and maladaptive settings of each gate

Every mechanism in §1-2 is two-directional except H-reflex conditioning,
for which the cited literature documents no maladaptive counterpart. The two
tables below list the same mechanisms twice, by outcome.

#### Healthy / adaptive directions

| Mechanism | Refs | What the adaptive direction looks like |
|---|---|---|
| Homeostatic scaling (§1.1) | [[24]](#ref-24)[[27]](#ref-27) | Upscaling after deafferentation restores excitability lost to reduced afferent drive |
| Spinal instrumental learning (Grau, §1.1) | [[1]](#ref-1)[[2]](#ref-2) | Contingent (response-produced) outcome → NMDAR/BDNF/protein-synthesis-dependent potentiation that outlasts the session |
| Two-phase LTP: E-LTP → L-LTP (§1.1 motor rows) | [[1]](#ref-1)[[4]](#ref-4)[[6]](#ref-6)[[7]](#ref-7) | NMDAR-dependent induction in motor/interneuron circuits, consolidated by a protein-synthesis- and BDNF-dependent late phase, producing a lasting adaptive change in spinal reflex output — BDNF/CREB/CaMKII rising in proportion to how well the animal learned (Grau et al.); corticospinal-tract LTP documented separately in intact motor pathways |
| Serotonergic gating (§2.1) | [[16]](#ref-16)[[17]](#ref-17)[[20]](#ref-20)[[21]](#ref-21) | Episodic 5-HT2 activation → new BDNF/TrkB signalling → lasting facilitation of spinal motor output; paired with task-specific training it produces durable locomotor recovery after incomplete SCI in rats and humans |
| H-reflex conditioning (§1.1) | [[8]](#ref-8)[[9]](#ref-9) | Up-conditioning corrects locomotor asymmetry after SCI in rats |

*Table 2a — The adaptive direction of each two-directional mechanism from §1-2. Pairs row-for-row with Table 2b except the last, H-reflex conditioning, where Table 2b leaves a gap rather than inventing a counterpart the cited literature doesn't document.*

#### Pathological / maladaptive directions

| Mechanism | Refs | What the maladaptive direction looks like |
|---|---|---|
| Homeostatic scaling (§1.2) | [[25]](#ref-25)[[26]](#ref-26) | **Downscaling failure**: KCC2 loss after SCI leaves inhibition too weak, producing spasticity [[25]](#ref-25) — training partially reverses it |
| Spinal instrumental learning (Grau, §1.2) | [[3]](#ref-3)[[5]](#ref-5) | Non-contingent (uncontrollable) outcome at the *identical* intensity → active, protein-synthesis-dependent **suppression** of future learning capacity [[3]](#ref-3) |
| Two-phase LTP: E-LTP → L-LTP | [[28]](#ref-28)[[29]](#ref-29)[[30]](#ref-30)[[31]](#ref-31)[[32]](#ref-32) | The *same* two-phase cascade run on the nociceptive pathway instead, where its consolidated outcome is chronic pain — treated separately in §3, and shown there to compete with motor learning for the same resource |
| Serotonergic gating (§1.2, §2.1) | [[22]](#ref-22)[[23]](#ref-23) | Persistently altered CPG sensitivity to 5-HT if left untreated after injury; and, on the supply side, a resource delivered without paired training consolidates whatever is active rather than what was trained |
| H-reflex conditioning | — | *No entry* — no specific pathological counterpart in the literature cited here (also why Table 1b has no H-reflex row) |

*Table 2b — The maladaptive direction, where the cited literature documents one. Gate signal and target synapse determine the outcome, not a separate "adaptive" vs. "maladaptive" machinery — §4 closes the loop with `cpg_2legs_fast.py`'s own observed failure modes.*

### 2.5 Maladaptive plasticity after spinal cord injury: synthesis

Table 2b's rows are not independent side effects — in rat SCI models
they are commonly reported together, a pattern the literature calls
**maladaptive plasticity**: retention rules that persist but now degrade
function because injury changed the gating signal or target synapse, not
because plasticity itself changed kind — *"maladaptive spinal plasticity
opposes spinal learning and recovery in spinal cord injury"* [[5]](#ref-5),
i.e. the same machinery that §2 credits with adaptive learning, in its own
field's account of why recovery sometimes fails.

1. **Spasticity** via KCC2 loss [[25]](#ref-25).
2. **Impaired further learning** under uncontrollable training [[3]](#ref-3)[[5]](#ref-5).
3. **Altered serotonergic sensitivity** if left untreated [[22]](#ref-22)[[23]](#ref-23).
4. **Central/neuropathic pain** — the one item on this list that is not a
   motor-circuit process. It belongs to the nociceptive pathway (§3), and is
   listed here only because the SCI literature reports it alongside the other
   three in the same animals.

None is a separate disease process — each is the Table 2a mechanism tipped
toward the maladaptive branch by what the lesion changed, matching the
general rat SCI literature's multiple-hit picture (motoneurons,
interneurons, and afferents concurrently, not one dominant cause).

**Consequence.** `--consolidate` (`cpg_2legs_fast.py`) is exactly this
retention rule, and inherited the same double edge — tuned one way it
reproduces Table 2a's outcomes, tuned another it reproduces Table 2b's, with
direct model-level counterparts found empirically (§4, closing paragraph).

## 3. Nociceptive-circuit plasticity, and why it is kept separate

Everything above concerns motor circuits. The dorsal horn runs the *same*
two-phase machinery on a different pathway, and this section is deliberately
walled off from §1-2 so that the shared molecules are not mistaken for a
shared function.

**The mechanism.** Dorsal-horn E-LTP [[28]](#ref-28) behaves like a
decaying tag: NMDAR-dependent, present within minutes at C-fiber synapses,
gone within hours unless converted to L-LTP — a discrete regime change that is
blocked by protein-synthesis inhibitors [[29]](#ref-29) and gated by spinal **D1/D5
dopamine** receptors [[30]](#ref-30) or exogenous BDNF [[31]](#ref-31). Consolidated, its outcome is
central sensitization: the standard cellular model of hyperalgesia and chronic
pain [[32]](#ref-32). (The wider
pain literature treats sensitization proportionate to real injury as
protective, and only sensitization outlasting or exceeding it as maladaptive
[[33]](#ref-33) — a distinction this document notes but does not rely on.)

**Same machinery, different gate.** Note the gating signal differs from §2.1's:
the motor side is gated serotonergically (5-HT2 → BDNF), the nociceptive side
dopaminergically (D1/D5 → BDNF), with BDNF the common downstream currency.
That asymmetry is why "the spinal cord consolidates via mechanism X" is not a
well-formed statement — the pathway and its gate have to be named together.

**The two compete for the same resource.** Ferguson, Huie, Crown & Grau (2012) [[4]](#ref-4)
tested cross-talk directly in transected rats and found it in both directions:
prior instrumental training changes how much central sensitization a later
formalin injection produces, and prior formalin sensitization impairs spinal
learning measured a day later. They frame this as bidirectional
metaplasticity — controllable stimulation produces plasticity that *both*
promotes future learning *and* limits nociceptive sensitization, with BDNF
implicated in the protective effect; uncontrollable stimulation does the
reverse.

**Why this matters for the model, despite being out of scope behaviorally.**
`cpg_2legs_fast.py` has no nociceptive pathway and models no pain. But the
competition result is this document's only direct evidence that the
consolidation resource is **finite** — two processes that never meet
anatomically still deplete each other, which only happens if they draw on a
common, exhaustible pool. §2.1 establishes that the resource is supplied
separately from the synapses that use it; this section establishes that there
is a limited amount of it. Both are needed to justify a shared per-leg
`prp_pool` with a threshold, and that is why this section exists at all.

## 4. Mapping onto the tinyCPG architecture

This model already has three standing plastic pathways
(`BS→RG`, `CUT→RG`, `Ia→RG` — see [CLAUDE.md](CLAUDE.md), "Core architecture
fix" and `MOD_IA_RG_STDP`), each currently a single-timescale STDP weight
bounded only by a fixed `Wmax`. §2's synthesis suggests each is missing a
second, slower component:

- **`Ia→RG-E`/`Ia→RG-F`** maps most directly onto Wolpaw's H-reflex
  conditioning: same pathway (afferent-to-motor-circuit), same fast/slow
  two-phase shape, and — uniquely among the three pathways — literature
  evidence that consolidating exactly this pathway restores locomotor
  symmetry under reduced/altered descending drive, which is this model's own
  debug goal. This is also the pathway currently deliberately kept
  weight-capped (`WMAX_IA=10`) to avoid saturating into tonic co-excitation
  (see CLAUDE.md's `MOD_IA_RG_STDP` note) — a fixed cap is exactly the kind of
  static limit that a genuine consolidation mechanism (a cap that *rises* only
  after demonstrated stable, successful use, per Phase I→II) would replace
  with something bio-plausible instead of hand-tuned.
- **`CUT→RG-E`** maps onto the Grau contingency literature (§2.2)
  functionally — a stance bout that resolves via
  genuine force-threshold crossing is the "successful, contingent" case, and
  one that only ends via the failsafe timeout (`--cut-max-stance-ms`) is
  structurally the "forced/non-contingent" case those experiments show
  produces active suppression, not just an absence of reinforcement. That
  reframes the model's own `frac_at_cap` diagnostic — already used throughout
  the force-triggered-CUT tuning rounds to flag disguised-clock results — as a
  candidate for the literal biological gate signal, not just a
  post-hoc correctness check. Note the model's `CUT` is a cutaneous
  paw-contact afferent, not a nociceptor: the mapping is to the contingency
  gate, not to §3's nociceptive consolidation, even though a cutaneous
  afferent is anatomically the nearer neighbour of the two.
- **`BS→RG`** remains the weakest fit of the three. The closest supporting
  evidence is corticospinal-tract LTP — a
  descending projection onto spinal interneurons and motor pools that does
  undergo LTP (§1.1's motor E-LTP row) — which is a genuine descending-drive
  precedent, though the model's `BS` is a reticulospinal tonic proxy rather
  than a corticospinal one, so the mapping is by analogy across two different
  descending systems. The serotonergic acute/chronic receptor-sensitivity
  axis is a separate, slower mechanism and not a tag/capture story at all.
  Applying consolidation to `BS→RG` for architectural uniformity is still a
  modeling choice rather than a literature-mandated one — which is why the
  implementation logs `BS→RG` bookkeeping for measurement symmetry but never
  writes it back.

Implementation (state variables, update equations, where in
`cpg_2legs_fast.py`'s sim loop this would live) is intentionally left to the
separate implementation plan, not this document.

**§2.4's healthy/pathological duality is not just biological framing — it
recurs as literal, measured failure modes once `--consolidate` was actually
built and tuned** (see [CLAUDE.md](CLAUDE.md), "Tag-and-capture
consolidation"). Two of Table 2b's four documented maladaptive directions
have a direct model-level counterpart, found empirically, not predicted in
advance by this document:

- **Cap-domination** (`frac_at_cap` near 1.0 — the failsafe timer, not
  genuine sensory feedback, driving every stance/swing transition) is the
  model's own version of the homeostatic-downscaling failure above: a
  positive-feedback loop (`CUT→RG-E→force_e→CUT`) that never releases,
  structurally the same shape as excitation that never gets scaled back down
  because the compensatory brake (there, KCC2; here, a capture gate tuned
  too permissively) never engages.
- **Leg-synchronization** (corr(F-E_L,F-E_R) flipping positive — both legs'
  `CUT→RG-E` consolidating to the same stable plateau instead of staying
  desynchronized) is a direct instance of over-consolidation: capturing too
  easily and too often erased exactly the kind of run-to-run,
  synapse-to-synapse asymmetry that real tag/capture leaves intact (§2's
  "labile, spontaneously-decaying" tag is *supposed* to preserve variability
  between reinforcement events, not average it away).

Both were found by tuning `--consolidate`'s gain/threshold constants after
implementation, the same way the biology's own pathological directions were
found by perturbing (not designing) real spinal circuits — the retention
rule was neutral machinery in both cases; the tuning (or the lesion) is what
picked adaptive or maladaptive.

## References

Every entry below was verified against PubMed (author list, year, journal,
volume and pages). Numbers are the citation keys used in the tables and
figures above, and each bracketed number in the text links to its entry
here.

**Spinal instrumental learning and metaplasticity (Grau lab)**

1. <a id="ref-1"></a>Grau, J.W. (2014). [Learning from the spinal cord: how the study of spinal cord plasticity informs our view of learning](https://pubmed.ncbi.nlm.nih.gov/23973905/). *Neurobiol. Learn. Mem.* 108:155-171. PMID 23973905.
2. <a id="ref-2"></a>Crown, E.D. & Grau, J.W. (2001). [Preserving and restoring behavioral potential within the spinal cord using an instrumental training paradigm](https://pubmed.ncbi.nlm.nih.gov/11495955/). *J. Neurophysiol.* 86(2):845-855. PMID 11495955.
3. <a id="ref-3"></a>Ferguson, A.R., Bolding, K.A., Huie, J.R., Hook, M.A., Santillano, D.R., Miranda, R.C. & Grau, J.W. (2008). [Group I metabotropic glutamate receptors control metaplasticity of spinal cord learning through a protein kinase C-dependent mechanism](https://pubmed.ncbi.nlm.nih.gov/19005059/). *J. Neurosci.* 28(46):11939-11949. PMID 19005059.
4. <a id="ref-4"></a>Ferguson, A.R., Huie, J.R., Crown, E.D. & Grau, J.W. (2012). [Central nociceptive sensitization vs. spinal cord training: opposing forms of plasticity that dictate function after complete spinal cord injury](https://pubmed.ncbi.nlm.nih.gov/23060820/). *Front. Physiol.* 3:396. PMID 23060820.
5. <a id="ref-5"></a>Ferguson, A.R., Huie, J.R., Crown, E.D., Baumbauer, K.M., Hook, M.A., Garraway, S.M., Lee, K.H., Hoy, K.C. & Grau, J.W. (2012). [Maladaptive spinal plasticity opposes spinal learning and recovery in spinal cord injury](https://pubmed.ncbi.nlm.nih.gov/23087647/). *Front. Physiol.* 3:399. PMID 23087647.

**LTP in spinal motor pathways**

6. <a id="ref-6"></a>Amer, A., Xia, J., Smith, M. & Martin, J.H. (2021). [Spinal cord representation of motor cortex plasticity reflects corticospinal tract LTP](https://pubmed.ncbi.nlm.nih.gov/34934000/). *PNAS* 118(52):e2113192118. PMID 34934000.
7. <a id="ref-7"></a>Adkins, D.L., Boychuk, J., Remple, M.S. & Kleim, J.A. (2006). [Motor training induces experience-specific patterns of plasticity across motor cortex and spinal cord](https://pubmed.ncbi.nlm.nih.gov/16959909/). *J. Appl. Physiol.* 101(6):1776-1782. PMID 16959909.

**H-reflex operant conditioning (Wolpaw lab)**

8. <a id="ref-8"></a>Wolpaw, J.R. (2010). [What can the spinal cord teach us about learning and memory?](https://pubmed.ncbi.nlm.nih.gov/20889964/) *Neuroscientist* 16(5):532-549. PMID 20889964. (Source for the Phase I / Phase II two-phase account and its multi-site substrate.)
9. <a id="ref-9"></a>Chen, Y., Chen, X.Y., Jakeman, L.B., Chen, L., Stokes, B.T. & Wolpaw, J.R. (2006). [Operant conditioning of H-reflex can correct a locomotor abnormality after spinal cord injury in rats](https://pubmed.ncbi.nlm.nih.gov/17135415/). *J. Neurosci.* 26(48):12537-12543. PMID 17135415.

**Spinal sensorimotor adaptation and locomotor training**

10. <a id="ref-10"></a>(mouse) Lavaud, S., Bichara, C., D'Andola, M., Yeh, S.-H. & Takeoka, A. (2024). [Two inhibitory neuronal classes govern acquisition and recall of spinal sensorimotor adaptation](https://pubmed.ncbi.nlm.nih.gov/38603479/). *Science* 384(6692):194-201. PMID 38603479.
11. <a id="ref-11"></a>(cat) de Leon, R.D., Hodgson, J.A., Roy, R.R. & Edgerton, V.R. (1998). [Full weight-bearing hindlimb standing following stand training in the adult spinal cat](https://pubmed.ncbi.nlm.nih.gov/9658030/). *J. Neurophysiol.* 80(1):83-91. PMID 9658030.
12. <a id="ref-12"></a>Edgerton, V.R., Roy, R.R., de Leon, R., Tillakaratne, N. & Hodgson, J.A. (1997). [Does motor learning occur in the spinal cord?](https://journals.sagepub.com/doi/10.1177/107385849700300510) *The Neuroscientist* 3(5):287-294. (Not indexed in PubMed; verified via publisher DOI.)
13. <a id="ref-13"></a>(cat) Harnie, J., Doelman, A., de Vette, E., Audet, J., Desrochers, E., Gaudreault, N. & Frigon, A. (2019). [The recovery of standing and locomotion after spinal cord injury does not require task-specific training](https://pubmed.ncbi.nlm.nih.gov/31825306/). *eLife* 8:e50134. PMID 31825306.
14. <a id="ref-14"></a>Côté, M.-P., Azzam, G.A., Lemay, M.A., Zhukareva, V. & Houlé, J.D. (2011). [Activity-dependent increase in neurotrophic factors is associated with an enhanced modulation of spinal reflexes after spinal cord injury](https://pubmed.ncbi.nlm.nih.gov/21083432/). *J. Neurotrauma* 28(2):299-309. PMID 21083432.
15. <a id="ref-15"></a>Smith, A.C. & Knikou, M. (2016). [A review on locomotor training after spinal cord injury: reorganization of spinal neuronal circuits and recovery of motor function](https://pubmed.ncbi.nlm.nih.gov/27293901/). *Neural Plast.* 2016:1216258. PMID 27293901.

**Serotonergic gating of spinal motor consolidation**

16. <a id="ref-16"></a>Baker-Herman, T.L. & Mitchell, G.S. (2002). [Phrenic long-term facilitation requires spinal serotonin receptor activation and protein synthesis](https://pubmed.ncbi.nlm.nih.gov/12122082/). *J. Neurosci.* 22(14):6239-6246. PMID 12122082.
17. <a id="ref-17"></a>Tadjalli, A. & Mitchell, G.S. (2019). [Cervical spinal 5-HT2A and 5-HT2B receptors are both necessary for moderate acute intermittent hypoxia-induced phrenic long-term facilitation](https://pubmed.ncbi.nlm.nih.gov/31219768/). *J. Appl. Physiol.* 127(2):432-443. PMID 31219768.
18. <a id="ref-18"></a>Hoffman, M.S. & Mitchell, G.S. (2011). [Spinal 5-HT7 receptor activation induces long-lasting phrenic motor facilitation](https://pubmed.ncbi.nlm.nih.gov/21242254/). *J. Physiol.* 589(6):1397-1407. PMID 21242254.
19. <a id="ref-19"></a>Hoffman, M.S. & Mitchell, G.S. (2013). [Spinal 5-HT7 receptors and protein kinase A constrain intermittent hypoxia-induced phrenic long-term facilitation](https://pubmed.ncbi.nlm.nih.gov/23850591/). *Neuroscience* 250:632-643. PMID 23850591.
20. <a id="ref-20"></a>(human) Hayes, H.B., Jayaraman, A., Herrmann, M., Mitchell, G.S., Rymer, W.Z. & Trumbower, R.D. (2014). [Daily intermittent hypoxia enhances walking after chronic spinal cord injury: a randomized trial](https://pubmed.ncbi.nlm.nih.gov/24285617/). *Neurology* 82(2):104-113. PMID 24285617.
21. <a id="ref-21"></a>(human/rat review) Tan, A.Q., Barth, S. & Trumbower, R.D. (2020). [Acute intermittent hypoxia as a potential adjuvant to improve walking following spinal cord injury: evidence, challenges, and future directions](https://pubmed.ncbi.nlm.nih.gov/33738145/). *Curr. Phys. Med. Rehabil. Rep.* 8(3):188-198. PMID 33738145.
22. <a id="ref-22"></a>Ghosh, M. & Pearse, D.D. (2014). [The role of the serotonergic system in locomotor recovery after spinal cord injury](https://pubmed.ncbi.nlm.nih.gov/25709569/). *Front. Neural Circuits* 8:151. PMID 25709569.
23. <a id="ref-23"></a>Sławińska, U., Miazga, K. & Jordan, L.M. (2014). [The role of serotonin in the control of locomotor movements and strategies for restoring locomotion after spinal cord injury](https://pubmed.ncbi.nlm.nih.gov/24993627/). *Acta Neurobiol. Exp.* 74(2):172-187. PMID 24993627.

**Homeostatic scaling**

24. <a id="ref-24"></a>Turrigiano, G.G. (2008). [The self-tuning neuron: synaptic scaling of excitatory synapses](https://pubmed.ncbi.nlm.nih.gov/18984155/). *Cell* 135(3):422-435. PMID 18984155. (General framework; the only non-spinal primary source retained, and used only where §1.3 specializes it to spinal cord.)
25. <a id="ref-25"></a>Boulenguez, P., Liabeuf, S., Bos, R., Bras, H., Jean-Xavier, C., Brocard, C., Stil, A., Darbon, P., Cattaert, D., Delpire, E., Marsala, M. & Vinay, L. (2010). [Down-regulation of the potassium-chloride cotransporter KCC2 contributes to spasticity after spinal cord injury](https://pubmed.ncbi.nlm.nih.gov/20190766/). *Nat. Med.* 16(3):302-307. PMID 20190766.
26. <a id="ref-26"></a>Huie, J.R., Stuck, E.D., Lee, K.H., Irvine, K.A., Beattie, M.S., Bresnahan, J.C., Grau, J.W. & Ferguson, A.R. (2015). [AMPA receptor phosphorylation and synaptic colocalization on motor neurons drive maladaptive plasticity below complete spinal cord injury](https://pubmed.ncbi.nlm.nih.gov/26668821/). *eNeuro* 2(5). PMID 26668821.
27. <a id="ref-27"></a>(bullfrog) Santin, J.M., Vallejo, M. & Hartzler, L.K. (2017). [Synaptic up-scaling preserves motor circuit output after chronic, natural inactivity](https://pubmed.ncbi.nlm.nih.gov/28914603/). *eLife* 6:e30005. PMID 28914603.

**Nociceptive (dorsal-horn) plasticity — §3 only**

28. <a id="ref-28"></a>Sandkühler, J. & Liu, X. (1998). [Induction of long-term potentiation at spinal synapses by noxious stimulation or nerve injury](https://pubmed.ncbi.nlm.nih.gov/9749775/). *Eur. J. Neurosci.* 10(7):2476-2480. PMID 9749775.
29. <a id="ref-29"></a>Hu, N.-W., Zhang, H.-M., Hu, X.-D., Li, M.-T., Zhang, T., Zhou, L.-J. & Liu, X.-G. (2003). [Protein synthesis inhibition blocks the late-phase LTP of C-fiber evoked field potentials in rat spinal dorsal horn](https://pubmed.ncbi.nlm.nih.gov/12740398/). *J. Neurophysiol.* 89(5):2354-2359. PMID 12740398.
30. <a id="ref-30"></a>Yang, H.-W., Zhou, L.-J., Hu, N.-W., Xin, W.-J. & Liu, X.-G. (2005). [Activation of spinal D1/D5 receptors induces late-phase LTP of C-fiber-evoked field potentials in rat spinal dorsal horn](https://pubmed.ncbi.nlm.nih.gov/15829590/). *J. Neurophysiol.* 94(2):961-967. PMID 15829590.
31. <a id="ref-31"></a>Zhou, L.-J., Zhong, Y., Ren, W.-J., Li, Y.-Y., Zhang, T. & Liu, X.-G. (2008). [BDNF induces late-phase LTP of C-fiber evoked field potentials in rat spinal dorsal horn](https://pubmed.ncbi.nlm.nih.gov/18565512/). *Exp. Neurol.* 212(2):507-514. PMID 18565512.
32. <a id="ref-32"></a>Ruscheweyh, R., Wilder-Smith, O., Drdla, R., Liu, X.-G. & Sandkühler, J. (2011). [Long-term potentiation in spinal nociceptive pathways as a novel target for pain therapy](https://pubmed.ncbi.nlm.nih.gov/21443797/). *Mol. Pain* 7:20. PMID 21443797.
33. <a id="ref-33"></a>Woolf, C.J. (2011). [Central sensitization: implications for the diagnosis and treatment of pain](https://pubmed.ncbi.nlm.nih.gov/20961685/). *Pain* 152(3 Suppl):S2-S15. PMID 20961685.

**Motor primitives (§1.4 caveat — cited to rule an addition out, not in)**

34. <a id="ref-34"></a>Yang, Q., Logan, D. & Giszter, S.F. (2019). [Motor primitives are determined in early development and are then robustly conserved into adulthood](https://pubmed.ncbi.nlm.nih.gov/31138689/). *PNAS* 116(24):12025-12034. PMID 31138689.
35. <a id="ref-35"></a>Giszter, S.F. (2015). [Motor primitives — new data and future questions](https://pubmed.ncbi.nlm.nih.gov/25912883/). *Curr. Opin. Neurobiol.* 33:156-165. PMID 25912883.
