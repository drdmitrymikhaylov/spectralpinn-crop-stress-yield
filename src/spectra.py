"""Loading, quality control and physically-grounded features for leaf and
canopy reflectance spectra.

All three datasets come from EcoSIS as reflectance on a 1 nm grid; they have
been resampled once to 4 nm over 400-2400 nm, which is the range where a field
spectroradiometer has usable signal-to-noise and is exactly the range a drone
hyperspectral camera does *not* have.  That difference is the subject of
experiment 2.
"""

import numpy as np
import pandas as pd

DATASETS = {
    "milkweed": "Common Milkweed Leaf Responses to Water Stress and Elevated "
                "Temperature (Couture et al., EcoSIS)",
    "cucurbita": "Leaf and canopy spectroscopy and biochemical data of "
                 "field-grown Cucurbita pepo under two stresses (EcoSIS)",
    "crops": "Hyperspectral leaf reflectance, biochemistry, and physiology of "
             "droughted and watered crops (EcoSIS)",
}


def load(name, root="data"):
    """Return (meta DataFrame, wavelengths, reflectance)."""
    meta = pd.read_csv(f"{root}/{name}_meta.csv", low_memory=False)
    z = np.load(f"{root}/{name}_spec.npz")
    return meta, z["wl"].astype(float), z["R"].astype(float)


# ---------------------------------------------------------------- quality ---
def valid_mask(wl, R, r_max=1.0, r_min=0.0, max_jump=0.25):
    """Which spectra are physically possible.

    Three of these datasets contain rows with reflectance above 1 -- up to 6 in
    the canopy measurements -- which cannot happen for a diffusely reflecting
    leaf and means the white reference drifted or the target was in a specular
    highlight.  Left in, they dominate any model that uses absolute amplitude.

    Checks: finite everywhere; reflectance inside [r_min, r_max]; near-infrared
    plateau above the red trough (a green leaf always has one); and no
    step between adjacent 4 nm bands larger than `max_jump`, which catches
    splices between the three detectors of a field spectroradiometer.
    """
    R = np.asarray(R, float)
    ok = np.isfinite(R).all(axis=1)
    ok &= (np.nanmin(R, axis=1) >= r_min) & (np.nanmax(R, axis=1) <= r_max)
    red = R[:, (wl >= 660) & (wl <= 680)].mean(axis=1)
    nir = R[:, (wl >= 800) & (wl <= 900)].mean(axis=1)
    ok &= nir > red
    ok &= np.nanmax(np.abs(np.diff(R, axis=1)), axis=1) <= max_jump
    return ok


def qc_report(wl, R):
    R = np.asarray(R, float)
    red = R[:, (wl >= 660) & (wl <= 680)].mean(axis=1)
    nir = R[:, (wl >= 800) & (wl <= 900)].mean(axis=1)
    return {
        "n": int(len(R)),
        "non_finite": int((~np.isfinite(R).all(axis=1)).sum()),
        "above_one": int((np.nanmax(R, axis=1) > 1.0).sum()),
        "below_zero": int((np.nanmin(R, axis=1) < 0.0).sum()),
        "no_nir_plateau": int((nir <= red).sum()),
        "detector_step": int(
            (np.nanmax(np.abs(np.diff(R, axis=1)), axis=1) > 0.25).sum()),
        "passing": int(valid_mask(wl, R).sum()),
    }


# --------------------------------------------------------- preprocessing ---
def snv(X):
    """Standard normal variate: removes the multiplicative scaling that comes
    from leaf angle, distance and illumination rather than from chemistry."""
    X = np.asarray(X, float)
    return (X - X.mean(axis=1, keepdims=True)) / np.where(
        X.std(axis=1, keepdims=True) > 0, X.std(axis=1, keepdims=True), 1.0)


def derivative(X, wl, window=9, order=2, deriv=1):
    from scipy.signal import savgol_filter
    return savgol_filter(X, window_length=window, polyorder=order, deriv=deriv,
                         delta=float(np.median(np.diff(wl))), axis=1)


def at(wl, R, w0):
    """Reflectance at the band nearest w0."""
    return R[:, int(np.argmin(np.abs(wl - w0)))]


def band(wl, R, lo, hi):
    return R[:, (wl >= lo) & (wl <= hi)].mean(axis=1)


# ------------------------------------------------------------- indices ---
def indices(wl, R):
    """Published narrow-band indices, grouped by the mechanism they report.

    Keeping them separated by mechanism is the point: if heat and drought were
    spectrally distinguishable, the pigment/photoprotection group and the water
    group would respond differently to the two treatments.  Experiment 1 tests
    exactly that.
    """
    def a(w):
        return at(wl, R, w)

    eps = 1e-9
    out = {}
    # --- greenness and chlorophyll
    out["NDVI"] = (a(800) - a(670)) / (a(800) + a(670) + eps)
    out["NDRE"] = (a(790) - a(720)) / (a(790) + a(720) + eps)
    out["MTCI"] = (a(754) - a(709)) / (a(709) - a(681) + eps)
    d = derivative(R, wl)
    sel = (wl >= 680) & (wl <= 760)
    out["REP"] = wl[sel][np.argmax(d[:, sel], axis=1)]      # red edge position
    # --- photoprotection and pigments: the fast response to heat and light
    out["PRI"] = (a(531) - a(570)) / (a(531) + a(570) + eps)
    out["CRI700"] = 1.0 / (a(510) + eps) - 1.0 / (a(700) + eps)
    out["ARI"] = 1.0 / (a(550) + eps) - 1.0 / (a(700) + eps)
    out["SIPI"] = (a(800) - a(445)) / (a(800) - a(680) + eps)
    # --- water: the slow response to drought
    out["NDWI"] = (a(860) - a(1240)) / (a(860) + a(1240) + eps)
    out["NDII"] = (a(819) - a(1649)) / (a(819) + a(1649) + eps)
    out["MSI"] = a(1600) / (a(819) + eps)
    out["WBI"] = a(900) / (a(970) + eps)
    out["WATER1450"] = _depth(wl, R, 1450, 1300, 1600)
    out["WATER1940"] = _depth(wl, R, 1940, 1750, 2100)
    # --- dry matter
    out["NDNI"] = (np.log(1 / (a(1510) + eps)) - np.log(1 / (a(1680) + eps))) / \
                  (np.log(1 / (a(1510) + eps)) + np.log(1 / (a(1680) + eps)) + eps)
    out["CAI"] = 0.5 * (a(2000) + a(2200)) - a(2100)
    return out


def _depth(wl, R, centre, left, right):
    """Continuum-removed absorption depth, in absorbance."""
    A = -np.log10(np.clip(R, 1e-6, None))
    il, ic, ir = (int(np.argmin(np.abs(wl - w))) for w in (left, centre, right))
    frac = (wl[ic] - wl[il]) / (wl[ir] - wl[il])
    return A[:, ic] - (A[:, il] + frac * (A[:, ir] - A[:, il]))


INDEX_GROUPS = {
    "greenness": ["NDVI", "NDRE", "MTCI", "REP"],
    "photoprotection": ["PRI", "CRI700", "ARI", "SIPI"],
    "water": ["NDWI", "NDII", "MSI", "WBI", "WATER1450", "WATER1940"],
    "dry matter": ["NDNI", "CAI"],
}
INDEX_NAMES = [n for g in INDEX_GROUPS.values() for n in g]


def index_matrix(wl, R):
    d = indices(wl, R)
    return np.column_stack([d[n] for n in INDEX_NAMES]), INDEX_NAMES
