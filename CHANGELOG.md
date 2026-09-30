# Changelog

Dated notes on what changed on this page and why. Newest first.

## 2026-09-30

- New README section "Checking the numbers": five of the page's summaries
  opened and read for what they are made of. `results/readme_checks.json`
  holds the numbers, `tests/test_readme_numbers.py` (five tests, no dataset
  needed) pins the page to the result files.
- **Corrected:** "no better within a species than across them" was wrong.
  Within-species drought detection is ahead in five of seven crops (mean AUC
  0.61 against 0.55), with a bootstrap interval clear of zero in pepper
  (+0.19), millet (+0.21) and sorghum (+0.14), and behind in radish (−0.13).
  The per-species range is 0.48 to 0.65, not 0.48 to 0.68.
- **Corrected:** the r = +0.25 between the index model's score and leaf water
  content was offered as proof the model reads the plant. It has the wrong
  sign for a drought score and is a between-species effect. Centred within
  species it is −0.09, negative in all six crops, about −0.5 in pepper,
  sunflower and radish.
- Qualified: the "water axis right 73%" is 86.5% at 23 °C and 60.2% at 30 °C;
  a well-watered plant in a hot room is called water-stressed 90 times in 198.
- Qualified: two of the six water indices (NDWI, 1450 nm depth) are blind to
  temperature; the other four carry heat at 29 to 48% of their water effect.
- Qualified: the narrow 531/570 pair adds +0.011 ± 0.008 to drought, not
  nothing; the 1610 nm band adds +0.023 ± 0.007.
- The five-band camera in `src/sensors.py` and `results/exp2_sensor_cascade.json`
  is now described generically (band centres and widths unchanged, no number
  moved). Three stray macOS metadata files removed from the repository.
