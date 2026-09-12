"""What each instrument in the chain actually delivers.

A stress-detection model is usually trained on the best spectra anyone can
get -- a contact probe on a leaf, under a stable lamp, over 400-2400 nm. It is
then asked to work on a drone. Four things change on the way, and they are not
equally important:

  range       almost every drone hyperspectral camera is silicon, so it stops
              near 1000 nm.  The strong water absorptions at 1450 and 1940 nm,
              and the dry-matter features beyond 2000 nm, are simply not
              measured.  A multispectral camera has five or six bands and no
              spectrum at all.
  resolution  4 nm on a spectroradiometer against 5-10 nm on a drone
              hyperspectral head and 10-40 nm wide filters on a multispectral
              one.
  noise       a contact probe fills the field of view with leaf under a strong
              lamp; a camera 30 m up integrates for milliseconds.
  scale       a leaf probe sees leaf.  A camera sees leaf, shadow, soil and
              sky.  That one is not simulated here -- experiment 3 measures it
              on real paired leaf and canopy spectra instead.

This module handles the first three by band-passing a measured spectrum
through each instrument's response.
"""

import numpy as np

# MicaSense RedEdge-P / Altum-class band centres and full widths, nm
MULTISPECTRAL = [(475, 32), (560, 27), (668, 16), (717, 12), (842, 57)]
# two candidate hardware additions, each cheap next to a hyperspectral head:
# one shortwave band for water content, and the narrow pair the photochemical
# reflectance index needs.  The stock green band is 27 nm wide at 560 nm, so a
# standard multispectral camera cannot form PRI at all.
MULTISPECTRAL_SWIR = MULTISPECTRAL + [(1610, 60)]
MULTISPECTRAL_PRI = MULTISPECTRAL + [(531, 10), (570, 10)]
MULTISPECTRAL_BOTH = MULTISPECTRAL + [(531, 10), (570, 10), (1610, 60)]


def gaussian_bands(wl, R, centres_widths, noise_snr=None, rng=None):
    """Integrate spectra through Gaussian band responses (FWHM given)."""
    wl = np.asarray(wl, float)
    R = np.asarray(R, float)
    out = np.empty((len(R), len(centres_widths)))
    for j, (c, fwhm) in enumerate(centres_widths):
        sigma = fwhm / 2.3548
        w = np.exp(-0.5 * ((wl - c) / sigma) ** 2)
        w = w / w.sum()
        out[:, j] = R @ w
    if noise_snr:
        rng = rng or np.random.default_rng(0)
        out = out + rng.normal(0, out.mean() / noise_snr, out.shape)
    return out


def resample(wl, R, lo, hi, step, fwhm=None, noise_snr=None, rng=None):
    """Band-limit and re-grid a spectrum, with an optional Gaussian response."""
    centres = np.arange(lo, hi + 1e-9, step)
    fwhm = fwhm if fwhm is not None else step
    return centres, gaussian_bands(wl, R, [(c, fwhm) for c in centres],
                                   noise_snr=noise_snr, rng=rng)


SENSORS = {
    "field spectroradiometer": dict(
        kind="grid", lo=400, hi=2400, step=4, fwhm=6, snr=1000,
        note="contact probe on a leaf, full solar-reflective range"),
    "drone hyperspectral (VNIR)": dict(
        kind="grid", lo=400, hi=1000, step=5, fwhm=8, snr=200,
        note="silicon sensor; stops before the strong water bands"),
    "drone hyperspectral + SWIR": dict(
        kind="grid", lo=400, hi=1700, step=8, fwhm=12, snr=120,
        note="a second, much more expensive sensor extends the range"),
    "multispectral 5-band": dict(
        kind="bands", bands=MULTISPECTRAL, snr=150,
        note="MicaSense RedEdge-P class: blue, green, red, red edge, NIR"),
    "multispectral + 1610 nm": dict(
        kind="bands", bands=MULTISPECTRAL_SWIR, snr=150,
        note="the same camera with one shortwave-infrared band added"),
    "multispectral + PRI pair": dict(
        kind="bands", bands=MULTISPECTRAL_PRI, snr=150,
        note="two narrow bands at 531 and 570 nm added instead"),
    "multispectral + PRI + SWIR": dict(
        kind="bands", bands=MULTISPECTRAL_BOTH, snr=150,
        note="both additions: eight bands in total"),
    "RGB": dict(
        kind="bands", bands=[(475, 90), (550, 90), (640, 90)], snr=150,
        note="an ordinary colour camera"),
}


def apply_sensor(wl, R, name, rng=None):
    """Return (band centres, measured values) for one instrument."""
    s = SENSORS[name]
    if s["kind"] == "grid":
        return resample(wl, R, s["lo"], s["hi"], s["step"], s["fwhm"],
                        noise_snr=s["snr"], rng=rng)
    centres = np.array([c for c, _ in s["bands"]], float)
    return centres, gaussian_bands(wl, R, s["bands"], noise_snr=s["snr"],
                                   rng=rng)
