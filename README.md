# Which crop stress a spectrum can actually see

A framework for training and validating hyperspectral stress detectors,
built around the two steps that decide whether one works in the field: telling
heat from drought, and getting from a hand-held spectrometer to a camera on a
drone.

Almost every hyperspectral crop-stress paper reports the same thing: an
accuracy, on one experiment, under a random split. That number tells you
nothing about the three questions a deployment actually turns on.

1. **Which stress is it?** "Stress detected" is not actionable. Irrigating a
   heat-stressed crop and shading a thirsty one are both wrong.
2. **Will it survive the instrument?** The calibration is built with a contact
   probe over 400 to 2400 nm. The drone carries a silicon camera that stops at
   1000 nm, or five broad filters.
3. **Is the label real?** "Droughted" describes the watering can. It does not
   promise the plant is short of water — and this repository contains a
   dataset where it wasn't.

Four experiments on three published datasets, each answering one of those.
A fifth replaces the regression with a physical model of the leaf, to see
whether the chemistry it returns survives a new crop.

---

## From field to repository

I have built crop analytics from space since 2017, from satellite yield programmes for investors and governments in emerging economies to national digital agriculture platforms designed at a scale of millions of hectares. Along the way came hyperspectral wheat classification, an Adaptive Calibration Cycle for hyperspectral sensors (2025) and plant-stress experiments published in *Agronomy* and *Plants*. This repository takes the central question of all that work, which stress light can actually see, and answers it on open data.

## Three experiments from EcoSIS

All three are open leaf- and canopy-level spectra with treatment labels and
measured plant traits, from [EcoSIS](https://ecosis.org). Reflectance was
resampled once to 4 nm over 400 to 2400 nm.

| dataset | n | design | what it answers |
|---|---|---|---|
| Common milkweed under water stress and elevated temperature (J. Couture, 2015) | 735 | 2×2 factorial: well-watered / water-stressed × 23 °C / 30 °C, 5 populations, 4 growth rooms, 2 blocks | can the two stresses be told apart |
| Cucurbita pepo under two stresses, leaf **and** canopy (A. C. Burnett, S. P. Serbin, A. Rogers, 2020) | 627 | drought / control / sink manipulation, 19 field plots, both measurement scales on the same plots | the hand-held-to-drone step |
| Droughted and watered crops (A. C. Burnett, S. P. Serbin, K. J. Davidson, K. S. Ely, A. Rogers, 2020) | 2 406 | 7 species, droughted / watered, days 0 to 28, with leaf water content, stomatal conductance, ABA and proline | transfer across crops, and whether the label is real |

**Quality control first.** All three contain spectra that a leaf cannot
produce: reflectance above 1, up to 6.1 in the canopy measurements, and
detector-splice steps. 112 of 715 Cucurbita and 56 of 2 462 crop spectra fail
a four-part physical check and are dropped before anything is fitted. Left in,
they dominate any model that uses absolute amplitude.

---

## Can a spectrum tell heat from drought?

![two stresses](figures/01_two_stresses.png)

The milkweed experiment crosses watering with temperature, so each effect can
be estimated inside the levels of the other. The right panel puts every index
on those two axes. Anything off the diagonal is selective.

The mechanistic prediction holds cleanly:

| index | reports | d, water | d, heat |
|---|---|---|---|
| WBI | water | −1.05 | +0.30 |
| NDWI | water | −0.92 | −0.02 (p = 0.73) |
| WATER1450 | water | −0.60 | −0.02 (p = 0.75) |
| PRI | photoprotection | +0.36 | **+1.15** |
| CRI700 | pigments | −0.33 | −0.88 |
| NDRE, MTCI, REP | greenness | +1.3 to +1.5 | +0.8 to +0.9 |

NDWI and the 1450 nm band depth move with water and, to within the resolution
of 735 samples, not with temperature. The other four water indices do carry
heat, at 29 to 48% of their water response (see
[Checking the numbers](#checking-the-numbers)). PRI — the xanthophyll-cycle index at 531 nm
against 570 nm — moves three times more with temperature than with water.
Greenness indices move with both. That is why "stress detected" is all a
greenness-based system can say.

![split matters](figures/02_split_matters.png)

**And here the tidy story breaks.** Building a classifier from just the water
group does not make it a water detector. It predicts heat at AUC 0.88 and
water at 0.68. The photoprotection group behaves the same way. Heat is simply
the easier target in this experiment, whatever you feed the model. A
selective marker is not automatically a sufficient feature set, which is worth
knowing before designing a camera around one index.

**The split matters more than the features.** Temperature was applied per
growth room, and rooms are nested inside temperature, so a model can score on
the room instead of the plant. Splitting by source population leaves that
confound intact and gives AUC 0.999 for heat. Splitting by block puts the test
on a *different pair of rooms* at the same two temperatures and gives 0.982.
The signal survives, which is the evidence that it is heat and not furniture.
Water stress, applied inside every room, carries no such confound: 0.933 →
0.879 across the two splits.

Four-class accuracy (watering × temperature), split by block: **0.653** against
0.25 for chance. The water axis is right 73% of the time and the temperature
axis 91%. The 73% is two numbers: 87% for plants grown at 23 °C and 60% for
plants grown at 30 °C. Under heat the water call is wrong four times in ten.

---

## What survives the instrument?

![sensor cascade](figures/03_sensor_cascade.png)

The same two questions asked of eight instruments, everything else held fixed.
Each instrument is modelled by its band centres, band widths and noise. A flat
spectrum passes through all of them unchanged, which is what makes the
comparison about the instrument rather than about the weighting.

| instrument | bands | water stress | heat |
|---|---|---|---|
| field spectroradiometer, 400 to 2400 nm | 501 | 0.881 | 0.982 |
| drone hyperspectral, VNIR only | 121 | 0.831 | 0.906 |
| drone hyperspectral + SWIR | 163 | 0.839 | 0.958 |
| multispectral, 5 bands | 5 | 0.817 | 0.694 |
| multispectral + 1610 nm | 6 | **0.839** | 0.684 |
| multispectral + 531/570 pair | 7 | 0.828 | **0.803** |
| multispectral + both | 8 | 0.845 | 0.789 |
| RGB | 3 | 0.802 | 0.725 |

Two things here were not what I expected.

**Drought is the robust one.** Cutting the range at 1000 nm loses both
strong water absorptions, yet it costs drought detection only 0.05 AUC. Water
content also changes the broad shape of the near-infrared plateau, and five
broad bands capture that. Heat loses more (0.076), and a five-band camera
loses 0.29.

**Heat is fragile because PRI needs narrow bands.** The photochemical
reflectance index compares 531 nm with 570 nm, 39 nm apart. A multispectral
camera's green band is 27 nm wide and centred at 560 nm, so it cannot form PRI
at all. Adding two 10 nm bands at 531 and 570 recovers 0.11 AUC of heat
detection and adds 0.01 to drought, which is inside the noise of the five
draws. Adding one 1610 nm band recovers 0.02 of drought and does nothing for
heat.

That is the cleanest result in this repository, because it is an intervention
rather than a correlation. Each hardware addition buys back the stress its
mechanism predicts. For heat that is exact. For drought it is a matter of
degree: the right band buys twice what the wrong pair does, not everything
against nothing.

**The design rule.** If the mission is irrigation scheduling, five bands plus
one shortwave band is enough and a hyperspectral head is not worth its weight.
If the mission is heat or light stress, no multispectral camera will do it.
You need either narrow bands placed on the xanthophyll feature or a
hyperspectral sensor.

---

## Does a leaf calibration survive a camera above the row?

![leaf to canopy](figures/04_leaf_to_canopy.png)

A contact probe fills its field of view with one flat leaf under its own lamp.
A camera above the row sees that leaf at whatever angle it grew, plus the
leaves beneath it, plus shadow, plus soil. The Cucurbita experiment measured
both on the same plots on the same days, so the step can be measured.

Drought against control, split by plot, 95% bootstrap intervals:

| | full spectrum | indices |
|---|---|---|
| leaf → leaf | 0.648 [0.59, 0.70] | 0.627 [0.57, 0.69] |
| canopy → canopy | 0.747 [0.61, 0.86] | 0.817 [0.70, 0.92] |
| **leaf → canopy** | **0.521 [0.36, 0.67]** | **0.817 [0.71, 0.91]** |
| leaf → canopy, standardised | 0.365 [0.23, 0.51] | 0.811 [0.70, 0.91] |

Three things follow.

**The canopy carries more drought signal than the leaf**, not less. Drought
changes leaf angle, wilting and exposed soil. All of that is in a canopy
view and none of it is in a contact measurement. The field leaf-level number
(0.65) is also far below the growth-chamber number for milkweed (0.88), which
is the usual gap between a controlled experiment and a field.

**A full-spectrum model does not survive the scale change.** It lands at
chance, while an index model transfers at the same accuracy it achieves when
trained on canopy data directly. The indices were defined by mechanism before
any fitting. The full-spectrum model fitted whatever separated the leaf
classes, including things that exist only in a contact measurement.

**The obvious fix makes it worse.** Standardising each measurement mode to its
own mean and variance is the cheapest domain adaptation there is. It drops the
full-spectrum transfer from 0.52 to 0.37, reliably backwards. Scaling does not
align two distributions that differ in shape, and a mis-specified correction
is worse than none.

The confuser stays hard. Separating drought from a sink manipulation (fruit
removal — stressed but not thirsty) and control reaches 0.52 at leaf scale and
0.50 at canopy, against 0.33 for chance.

---

## Was the drought label real?

![what the spectrum sees](figures/05_what_the_spectrum_sees.png)

Leave-one-species-out drought detection across pumpkin, pepper, poplar,
radish, sunflower, sorghum and millet: **AUC 0.567** pooled, 0.48 to 0.65 per
species. Trained and tested inside one species it is better in five of the
seven (mean 0.61 against 0.55) and clearly better in pepper, millet and
sorghum, so what signal there is belongs to the crop and does not travel
(see [Checking the numbers](#checking-the-numbers)). Detection does not
improve with time into the treatment either: 0.55 on day 0, 0.61 at days
8 to 14, 0.55 at days 15 to 21.

A team with only the label and the spectra would conclude the model needs more
data, or a deeper architecture. The physiology says otherwise:

| what the treatment did | droughted | watered | Cohen's d |
|---|---|---|---|
| leaf relative water content | 79.1% | 79.9% | **−0.09** |
| stomatal conductance | 0.188 | 0.294 | −0.61 |
| abscisic acid | 1614 | 339 | +0.36 |
| proline | 2.72 | 1.87 | +0.25 |

The plants were genuinely droughted. They shut their stomata, flooded
themselves with ABA and accumulated proline. And they **held their leaf water
content constant**, which is textbook isohydric regulation, trading gas
exchange to protect hydration.

Reflectance in this range measures water content and pigments. The one thing
the treatment did not change is the one thing the instrument measures. Asked
to predict the physiological states directly, from median splits taken within
species so the crop cannot be guessed, the spectrum manages AUC 0.56 for water
content, 0.58 for stomatal conductance and 0.57 for ABA. Simply knowing the
treatment label predicts conductance at 0.71. The spectrum adds nothing.

One detail rescues the method's honour, though not the one first written
here. The pooled correlation of the index model's score with measured water
content, r = +0.25, has the wrong sign for a drought score and comes from
differences between species. Inside a species the correlation is negative in
all six crops that have water content, and near −0.5 in pepper, sunflower and
radish: a leaf drier than the norm for its species gets a higher drought
score. The treatment label correlates with water content at −0.05. In three
crops the spectral model is reading the plant. The label is not.

**The rule this gives the framework:** before training on a treatment label,
check what the treatment did to the quantity your instrument measures. If the
label moved and that quantity did not, no model will close the gap. The right
deliverable is then a specification change — a thermal camera for stomatal
closure, or fluorescence for photosystem state — not a bigger network.

---

## Does a physical model of the leaf transfer where regression did not?

![slab model](figures/06_slab_model.png)

Everything above reads the spectrum with indices or a regression. Neither is a
model of the leaf. The last experiment asks what changes when the leaf is
modelled, and whether the chemistry that comes out survives the same
leave-one-species-out test that broke the regression.

A leaf is a scattering, absorbing layer of finite thickness. Its reflectance
follows the Kubelka–Munk solution for a slab over a dark backing,

    R(λ) = 1 / (a + b·coth(b·S·d)),   a = 1 + K/S,   b = √(a² − 1),
    K·d = Σᵢ Cᵢ kᵢ(λ),                 S·d = s·σ(λ),

with three absorbing constituents at contents Cᵢ per unit area, a scattering
thickness s per leaf, and specific absorption spectra kᵢ(λ) and a scattering
spectrum σ(λ) that are small networks of wavelength. All of it is learned
jointly from the 2 344 crop leaf spectra alone; **no measured water content or
mass per area enters the fit at any point.** The physics-informed part is
strict. The network can only produce reflectance through that equation, so the
per-leaf numbers it returns are contents and a thickness, not features.

Two things had to be fixed before the decomposition meant anything, and both
are recorded because they are the usual failure modes of this kind of model.
The optically-thick form of Kubelka–Munk (the one behind the familiar
(1−R)²/2R transform) is blind to thickness by construction, so it cannot
separate "more water" from "more leaf". The finite-slab form can. And with
three unconstrained constituents, two of them learned the water bands and none
learned dry matter. The decomposition is not identifiable from reflectance
alone. Each constituent was therefore given a **support window** — pigments
below 780 nm, water above 880 nm, dry matter above 1 480 nm — and only the
shapes inside the windows are learned.

**What the fit produces.** The slab reproduces the spectra (root-mean-square
residual about 0.015 in reflectance), and the learned spectra land where the
chemistry says they should. The water constituent peaks at 1 448 and 1 928 nm
with shoulders at 970 and 1 200 nm, the pigment constituent fills the visible
and switches off at the red edge, and the dry-matter constituent occupies the
short-wave infrared beyond 1 500 nm. Reflectance alone, with no label,
recovers the absorption bands of water. That part works.

**What it does not produce is chemistry that transfers.** Within a species the
water content does correlate with measured relative water content, but the
sign changes from crop to crop: +0.56 in radish, +0.39 in sorghum, −0.14 in
pumpkin. Leaving each species out in turn, fitting the endmembers on the other
six and reading the held-out leaves' water fraction against their measured
RWC gives r = +0.57 on sunflower, −0.54 on pumpkin, −0.57 on sorghum, and a
median of **−0.13** over the seven. Dry matter against leaf mass per area:
median **+0.08**.

The regression baseline does not do better where it counts. A ten-component
PLS trained with the labels of six species reaches a median correlation of
+0.54 with RWC on the seventh, but its median R² is **−0.33**. It ranks the
leaves of a new crop better than chance and predicts their values worse than
the mean. For LMA the picture is the same (r +0.38, R² −1.70).

The physical reading of the negative is the one the label section already
gave. Relative water content in this experiment varies by 2 to 5 points within
a species, because the crops were isohydric, and a 2 % change in the water
band is inside what the leaf's own thickness, surface and internal structure
do to the same band. The slab model separates water from thickness in
principle. On leaves whose water barely moved it separates them into
species-specific scatter. A model can be physically right and still have
nothing to read.

**What this adds to the framework:** a decomposition that returns *named*
quantities with the units of a leaf, so that when it fails the failure can be
read. Here it says that the water signal a new species presents is dominated
by its structure, not its hydration. That is the diagnosis a regression cannot
give.

---

## Bottom line

| # | Finding | Evidence |
|---|---------|----------|
| 1 | Heat and drought move **different** parts of the spectrum. NDWI and the 1450 nm water band respond to water with no detectable temperature effect (d = −0.02, p = 0.73). PRI responds to temperature three times more strongly than to water (d = 1.15 vs 0.36). | heat vs drought |
| 2 | But mechanism does not equal prediction. A classifier built only on water indices predicts *heat* better (AUC 0.88) than it predicts water (0.68). Selectivity of a marker and sufficiency for a decision are different properties. | heat vs drought |
| 3 | **Drought needs range; heat needs resolution.** Cutting to a silicon drone camera costs heat 0.08 AUC and drought 0.05. A five-band multispectral camera costs heat 0.29. Adding one 1610 nm band buys back drought (+0.02) and nothing else; adding the narrow 531/570 pair buys back heat (+0.11) and half as much drought (+0.01, inside the noise). | instrument |
| 4 | Going from a leaf probe to a canopy view destroys a full-spectrum model (AUC 0.52, chance) but not an index model (0.82). Physically-defined indices cross the scale change; a fitted spectral model does not. | leaf to canopy |
| 5 | Standardising the two measurement modes to their own means makes the full-spectrum transfer **worse**, not better (0.52 → 0.37). The obvious domain correction is the wrong one. | leaf to canopy |
| 6 | Across seven crops, leave-one-species-out drought detection is 0.567 — barely above chance — and does not improve from day 0 to day 28. | label |
| 7 | The reason is in the plants, not the model. The drought treatment cut stomatal conductance by 36% and raised ABA five-fold while leaving leaf water content **unchanged** (79.1% vs 79.9%). Reflectance measures water content. The stress was real, expensive and spectrally invisible. | label |
| 8 | A physics-informed slab model (finite-thickness Kubelka–Munk with learned absorption spectra) recovers the water bands at 1 448 and 1 928 nm from reflectance alone, with no chemistry label. Its per-leaf water content still does not transfer across species (median r −0.13 with RWC). Neither does PLS trained with labels (median R² −0.33). The failure is in the leaves, not the estimator. | slab model |

---

## Checking the numbers

Added 30 September 2026. Every headline above is one summary per question.
This section opens five of them and reads what they are made of. Two
statements on this page did not survive and are corrected in place, three
hold with a qualification. `results/readme_checks.json` holds every number
below and `tests/test_readme_numbers.py` pins the page to it.

**1. "The water axis is right 73% of the time" is two numbers.** The
four-class confusion matrix, split by the temperature the plant grew at:

| | water call right | |
|---|---|---|
| plants at 23 °C | 86.5% | 308 of 356 |
| plants at 30 °C | 60.2% | 228 of 379 |

A well-watered plant in a hot room is called water-stressed 90 times out of
198 and called correctly 87 times. The reverse error, a stressed hot plant
called well-watered, happens 53 times in 181 (29%). At 23 °C the same two
errors run at 13% and 11%. The temperature call has no such weakness: 86.7%
right on well-watered plants, 94.9% on stressed ones. So the classifier
separates heat from drought in one direction only. It recognises heat
whatever the watering. Under heat it can no longer say whether the plant is
short of water, and that is exactly the case the top of this page calls the
expensive mistake: irrigating a heat-stressed crop.

**2. Two of the six water indices are blind to temperature, not the group.**
The index table above lists three of the six. All of them, with the heat
effect as a share of the water effect:

| index | d, water | d, heat | heat / water |
|---|---|---|---|
| NDWI | −0.92 | −0.02 (p = 0.73) | 3% |
| WATER1450 | −0.60 | −0.02 (p = 0.75) | 4% |
| WBI | −1.05 | +0.30 | 29% |
| WATER1940 | +0.69 | +0.29 | 42% |
| NDII | −0.93 | −0.41 | 44% |
| MSI | +0.95 | +0.46 | 48% |

The four lower rows respond to heat at p ≤ 0.001 (with 2 000 shuffles the
smallest possible p is 0.0005). The two indices built on a band near 1600 nm,
NDII and MSI, carry almost half as much heat as water. The 1940 nm depth moves
the opposite way from the 1450 nm depth under water stress. I have not
explained that and do not build on it. The photoprotection group splits the
same way: PRI (3.2 times more heat than water) and CRI700 (2.6 times) are
selective, ARI (0.8) and SIPI (1.3) are not. The claim that survives is about
NDWI, the 1450 nm band and PRI by name, which is what the test suite pins.

**3. Across species against within species, on the same leaves.** AUC with
95% intervals from 2 000 bootstrap resamples of leaves, stratified by
treatment:

| species | n | across species | within species | within − across | index model, across |
|---|---|---|---|---|---|
| poplar | 411 | 0.65 [0.59, 0.70] | 0.69 [0.64, 0.74] | +0.04 [−0.02, +0.10] | 0.67 [0.62, 0.73] |
| pepper | 498 | 0.49 [0.44, 0.54] | 0.68 [0.64, 0.73] | **+0.19 [+0.12, +0.27]** | 0.60 [0.55, 0.65] |
| sunflower | 172 | 0.53 [0.44, 0.61] | 0.48 [0.39, 0.57] | −0.05 [−0.16, +0.07] | 0.51 [0.42, 0.59] |
| radish | 214 | 0.60 [0.53, 0.68] | 0.47 [0.39, 0.55] | **−0.13 [−0.23, −0.03]** | 0.65 [0.58, 0.72] |
| pumpkin | 864 | 0.60 [0.56, 0.64] | 0.66 [0.62, 0.70] | +0.06 [−0.00, +0.11] | 0.54 [0.50, 0.58] |
| millet | 96 | 0.48 [0.36, 0.60] | 0.68 [0.57, 0.79] | **+0.21 [+0.04, +0.36]** | **0.30 [0.20, 0.40]** |
| sorghum | 151 | 0.49 [0.40, 0.59] | 0.63 [0.53, 0.72] | **+0.14 [+0.02, +0.25]** | 0.61 [0.51, 0.70] |

This page said detection is "no better within a species than across them".
**That was wrong.** Within a species it is ahead in five of seven crops (mean
0.61 against 0.55), with an interval clear of zero in pepper, millet and
sorghum, and behind in radish. A drought signal exists inside those three
crops and does not reach them from the other six. Across species only poplar,
radish and pumpkin can be told from a coin. The full-spectrum range is 0.48 to
0.65. The 0.68 printed before is not in the results file. And the index model
on millet scores 0.30 [0.20, 0.40], reliably backwards: whatever six other
crops teach it about drought, millet does the opposite. The intervals resample
leaves. The plants, 16 to 25 per species, were measured repeatedly, so the
true intervals are wider.

**4. The correlation with water content had the wrong sign and the wrong
source.** The page offered r = +0.25 between the index model's score and
measured relative water content as proof that the model reads the plant. The
score is the probability of *droughted*, so a model reading water should give
a negative correlation. The +0.25 is a between-species number. Poplar has the
driest leaves (mean RWC 64.8%) and the lowest mean score (0.26), and the six
species means correlate at +0.24. With each species centred on its own mean
the pooled correlation is −0.09, and it is negative in every one:

| species | n with RWC | mean RWC | r (index score, RWC) |
|---|---|---|---|
| poplar | 125 | 64.8% | −0.02 [−0.20, +0.15] |
| pepper | 96 | 86.5% | −0.49 [−0.63, −0.32] |
| sunflower | 61 | 79.8% | −0.55 [−0.70, −0.34] |
| radish | 48 | 90.3% | −0.56 [−0.73, −0.33] |
| pumpkin | 312 | 81.0% | −0.02 [−0.13, +0.09] |
| sorghum | 62 | 82.0% | −0.23 [−0.45, +0.02] |

So the rescue stands, on other evidence than the one offered. In pepper,
sunflower and radish a leaf drier than the norm for its species gets a higher
drought score, at about −0.5. In pumpkin and poplar, 62% of the leaves with a
water measurement, there is nothing. The full-spectrum model shows the same
pattern more weakly: −0.03 pooled, −0.04 centred, −0.45 in sunflower, −0.56 in
radish, and between −0.18 and +0.02 in the other four. Millet has no water
content measured.

**5. The sensor gains against their noise.** Each cell of the instrument table
is the mean of five noise draws. Gain over the five-band camera, ± the sd of
the difference over those draws:

| added to the five-band camera | drought | heat |
|---|---|---|
| one band at 1610 nm | +0.023 ± 0.007 | −0.011 ± 0.010 |
| narrow pair at 531 and 570 nm | +0.011 ± 0.008 | +0.109 ± 0.010 |

The heat column is not in doubt: +0.109 is 10.7 sd, and the 1610 nm band moves
heat by 1.0 sd in the wrong direction. The drought column is thinner than "buys
back exactly the stress its mechanism predicts, and only that one" allowed.
The right band buys +0.023 (3.2 sd), the wrong pair +0.011 (1.4 sd), and the
two gains are 1.8 sd apart. One thing the table showed and the text passed
over: a plain RGB camera beats the five-band camera on heat by 0.030 (3.0 sd)
and trails it on drought by 0.015 (2.2 sd). RGB is the one instrument here not
normalised per spectrum, since it has three bands, so it keeps absolute
brightness. That may be what helps. I have not separated the two. These sd
cover sensor noise only. The split is the same two blocks every time, so they
say nothing about a different pair of rooms.

---

## Not shown here

- **No field imagery.** The canopy spectra are spectroradiometer
  measurements from above the plot, not drone images. Registration, mixed
  pixels, view-angle effects, atmospheric correction and flight-line
  radiometric matching are all real problems this framework does not touch.
- **Three experiments, not a survey.** The heat result rests on one species in
  one growth-chamber study at two temperatures. The block split is the
  strongest available control, not a perfect one: an instrument difference
  shared by both hot rooms would still pass it.
- **The sensor cascade is a simulation** of band response and noise applied to
  measured spectra. It captures range, resolution and noise. It does not
  capture the optics, the calibration chain or the flight.
- **Small canopy sample.** 86 canopy spectra survive quality control, hence
  the wide bootstrap intervals in the leaf-to-canopy table.
- **Heat means 30 °C here**, a mild elevation. Severe heat that causes actual
  dehydration would look different, and probably easier.
- **The isohydric result is about these species under this treatment.** An
  anisohydric crop that lets its water potential fall would be visible to the
  same instrument.

---

## How this was run

The first version went up on 9 September 2026 with the four regression
experiments. The slab model and the open physics core followed on
12 September. The three datasets all came down from EcoSIS without trouble;
Zenodo, tried for other data, kept timing out. The raw CSVs were over 40 MB
and would not stage into the analysis container, so I reduced them on my
laptop to 4 nm and float32 first. That is the resampling the data
section describes.

The heat result was the one that had to be caught. Under a split by source
population the AUC came out at 0.999, which is too good, and the reason was
that growth rooms are nested inside temperature. The block split, at 0.982,
is what is reported. The slab model needed two rebuilds before its
decomposition meant anything: the optically thick form was replaced by the
finite slab, and the unconstrained three-constituent fit, whose log I kept,
was replaced by the support-window version. The final fit is 2 500 global
steps plus 2 000 and 800 for each of the seven held-out species, about 25
minutes on a laptop CPU.

---

## Reproduce

The physics core is public in this repository:

- `src/spectra.py` — data loading, the four-part quality gate, the index
  library grouped by mechanism, SNV
- `src/sensors.py` — the instrument simulator (band response, range, noise)
- `src/exp5_km_pinn.py` — the finite-thickness Kubelka–Munk slab model with
  learned absorption spectra, support windows, within-species and
  leave-one-species-out evaluation against PLS
- `tests/test_all.py` — the ten checks below

The experiment scripts for the first four sections (split schemes, transfer
protocols, the physiological validation of the labels) are held in a private
repository. `results/` holds every number on this page as JSON, and
`tests/test_readme_numbers.py` checks the page against those files. It needs
no dataset, so it runs on a fresh clone.

```
pip install -r requirements.txt
python -m pytest tests/test_readme_numbers.py   # page against results/, no data needed
python tests/test_all.py
python src/exp5_km_pinn.py      # ~25 min on a laptop CPU
```

Ten checks, all passing:

- the quality gate rejects reflectance above 1 and detector-splice steps, and
  every spectrum it keeps has a near-infrared plateau at least three times the
  red trough
- every instrument in the cascade returns a flat spectrum unchanged, so the
  sensor comparison measures the sensor and not the band weighting
- the red edge position lands inside the red edge, with a median at 700 to
  730 nm
- SNV output has zero mean and unit deviation per spectrum
- **the mechanism claim is pinned**: NDWI and the 1450 nm band separate the
  watering treatments (|d| > 0.5) and not the temperatures (|d| < 0.15); PRI
  does the reverse by a factor of three
- **the isohydric finding is pinned**: in the crops experiment the treatment
  must leave water content within 2 points, cut conductance by at least a
  quarter, and triple ABA
- the slab model reduces to the classical Kubelka–Munk R∞ for an infinitely
  thick leaf, to zero for a vanishing one, and reflects less when more
  absorber is added
- each learned constituent absorbs only inside its support window, so the
  three cannot swap roles
- **the slab result is pinned**: the water constituent's strongest band is at
  1 450 or 1 940 nm, and neither its held-out correlation with RWC (|median r|
  < 0.4) nor PLS's held-out R² (< 0.3) is allowed to look like a success

---

## Dataset credit and licence

Documentation, figures and result files: CC BY 4.0. Source code in `src/` and
`tests/`: MIT.

The three datasets belong to their authors and are distributed through the
Ecological Spectral Information System (EcoSIS). Cite them, not this page:

- John Couture. 2015. *Common Milkweed Leaf Responses to Water Stress and
  Elevated Temperature.* Data set, EcoSIS.
- Angela C. Burnett, Shawn P. Serbin, Alistair Rogers. 2020. *Leaf and canopy
  spectroscopy and biochemical data of field-grown Cucurbita pepo under two
  stresses.* Data set, EcoSIS.
- Angela C. Burnett, Shawn P. Serbin, Kenneth J. Davidson, Kim S. Ely,
  Alistair Rogers. 2020. *Hyperspectral leaf reflectance, biochemistry, and
  physiology of droughted and watered crops.* Data set, EcoSIS.
