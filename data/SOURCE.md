# Data source

Three packages downloaded from the Ecological Spectral Information System
(EcoSIS, https://ecosis.org) and reduced once by `reduce.py`: metadata kept in
full, spectra resampled from 1 nm to 4 nm over 400-2400 nm and stored float32.

- `milkweed_*` — John Couture. 2015. *Common Milkweed Leaf Responses to Water
  Stress and Elevated Temperature.* EcoSIS package
  9425d5b2-7633-45b5-9c07-6ec3323499a0.
- `cucurbita_*` — Angela C. Burnett, Shawn P. Serbin, Alistair Rogers. 2020.
  *Leaf and canopy spectroscopy and biochemical data of field-grown Cucurbita
  pepo under two stresses.* EcoSIS package
  563709f2-37c1-4b8d-b577-bf6c5cf63a94.
- `crops_*` — Angela C. Burnett, Shawn P. Serbin, Kenneth J. Davidson,
  Kim S. Ely, Alistair Rogers. 2020. *Hyperspectral leaf reflectance,
  biochemistry, and physiology of droughted and watered crops.* EcoSIS package
  5090905b-176c-4d17-bf60-59a69939eea6.

Held here for reproducibility only. EcoSIS licence fields are inconsistent
across these three packages, so the reduced data is **not** redistributed in
the public repository — cite the authors above and download from EcoSIS.

To fetch again:

    curl -sSL "https://ecosis.org/api/package/<package-id>/export?metadata=true" -o <name>.csv
