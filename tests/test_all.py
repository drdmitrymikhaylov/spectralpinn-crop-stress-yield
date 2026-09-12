"""Checks run before any number on the public page is believed."""

import sys

sys.path.insert(0, 'src')

import numpy as np

from sensors import SENSORS, apply_sensor, gaussian_bands
from spectra import (INDEX_GROUPS, index_matrix, indices, load, qc_report,
                     snv, valid_mask)


def test_quality_gate_catches_impossible_spectra():
    """Reflectance above 1 is not physically possible for a leaf, and these
    datasets contain such rows -- up to 6.1 in the canopy measurements."""
    for name, expect_bad in (("milkweed", False), ("cucurbita", True),
                             ("crops", True)):
        meta, wl, R = load(name)
        rep = qc_report(wl, R)
        assert rep["passing"] <= rep["n"]
        if expect_bad:
            assert rep["above_one"] > 0, (name, rep)
            assert rep["passing"] < rep["n"]
        keep = valid_mask(wl, R)
        assert R[keep].max() <= 1.0 and R[keep].min() >= 0.0


def test_every_kept_spectrum_looks_like_a_leaf():
    """A green leaf has a near-infrared plateau far above the red trough."""
    for name in ("milkweed", "cucurbita", "crops"):
        meta, wl, R = load(name)
        R = R[valid_mask(wl, R)]
        red = R[:, (wl >= 660) & (wl <= 680)].mean(axis=1)
        nir = R[:, (wl >= 800) & (wl <= 900)].mean(axis=1)
        assert (nir > red).all()
        assert np.median(nir / np.maximum(red, 1e-6)) > 3.0


def test_snv_normalises():
    X = np.random.default_rng(0).normal(0.3, 0.1, (30, 100))
    Z = snv(X)
    assert np.allclose(Z.mean(axis=1), 0, atol=1e-12)
    assert np.allclose(Z.std(axis=1), 1, atol=1e-12)


def test_indices_are_finite_and_in_range():
    meta, wl, R = load("milkweed")
    R = R[valid_mask(wl, R)]
    d = indices(wl, R)
    for k, v in d.items():
        assert np.isfinite(v).all(), k
    assert (np.abs(d["NDVI"]) <= 1).all()
    assert (np.abs(d["NDWI"]) <= 1).all()
    # the red edge must land inside the red edge
    assert (d["REP"] >= 680).all() and (d["REP"] <= 760).all()
    assert 700 <= np.median(d["REP"]) <= 730


def test_band_response_is_normalised():
    """Passing a flat spectrum through any instrument must return the same
    flat value: otherwise the sensor comparison would measure the weighting."""
    wl = np.arange(400, 2401, 4.0)
    R = 0.42 * np.ones((3, len(wl)))
    for name in SENSORS:
        centres, M = apply_sensor(wl, R, name, rng=np.random.default_rng(0))
        assert np.allclose(M, 0.42, atol=0.02), (name, M.mean())


def test_water_indices_respond_to_water_not_heat():
    """The central mechanistic claim, pinned.

    In the 2x2 factorial, the water-band indices must separate the watering
    treatments and must not separate the temperatures; the photochemical
    reflectance index must do the opposite.
    """
    from exp1_heat_vs_drought import paired_effect
    meta, wl, R = load("milkweed")
    keep = valid_mask(wl, R)
    meta, R = meta[keep].reset_index(drop=True), R[keep]
    water = (meta["Water treatment"].to_numpy() == "ws").astype(int)
    heat = (meta["Temperature"].to_numpy() == 30).astype(int)
    d = indices(wl, R)

    for nm in ("NDWI", "WATER1450"):
        dw = paired_effect(d[nm], water, heat)
        dh = paired_effect(d[nm], heat, water)
        assert abs(dw) > 0.5, (nm, dw)
        assert abs(dh) < 0.15, (nm, dh)

    dw = paired_effect(d["PRI"], water, heat)
    dh = paired_effect(d["PRI"], heat, water)
    assert dh > 3 * abs(dw), (dw, dh)


def test_drought_treatment_did_not_dehydrate_the_crops():
    """The finding that explains experiment 4, pinned so it cannot be lost.

    In the multi-species drought experiment the treatment closed stomata and
    raised abscisic acid, but left leaf relative water content unchanged.  A
    reflectance spectrum measures water content.  That is why detection there
    is near chance, and it is a property of the plants, not of the model.
    """
    meta, wl, R = load("crops")
    keep = valid_mask(wl, R) & meta["Treatment"].notna().to_numpy()
    meta = meta[keep].reset_index(drop=True)
    y = (meta["Treatment"].to_numpy() == "droughted")

    rwc = meta["RWC"].to_numpy(dtype=float)
    m = np.isfinite(rwc)
    assert abs(rwc[m & y].mean() - rwc[m & ~y].mean()) < 2.0

    gs = meta["gs"].to_numpy(dtype=float)
    m = np.isfinite(gs)
    assert gs[m & y].mean() < 0.75 * gs[m & ~y].mean()

    aba = meta["ABA"].to_numpy(dtype=float)
    m = np.isfinite(aba)
    assert aba[m & y].mean() > 3 * aba[m & ~y].mean()


def test_slab_model_limits():
    """Finite-thickness Kubelka-Munk: an infinitely thick slab returns the
    classical R_inf = 1 + K/S - sqrt((K/S)^2 + 2K/S); a vanishing slab over a
    black backing reflects nothing; more absorber means less reflectance."""
    import torch
    from exp5_km_pinn import Mixing
    torch.manual_seed(0)
    m = Mixing(3)
    lam = torch.linspace(-1.0, 1.0, 50).reshape(-1, 1)
    with torch.no_grad():
        m.s_raw[0] = 8.0; m.s_raw[1] = -12.0; m.s_raw[2] = 0.0
        m.c_raw[:] = 0.5
        R = m(lam).numpy()
        K = m.endmembers(lam).numpy(); sig = m.scattering(lam).squeeze().numpy()
        c = torch.nn.functional.softplus(m.c_raw).numpy()
    ks = (c[0] @ K.T) / (np.exp(8.0) * sig)
    r_inf = 1 + ks - np.sqrt(ks ** 2 + 2 * ks)
    assert np.allclose(R[0], r_inf, atol=1e-4)
    assert R[1].max() < 1e-3
    with torch.no_grad():
        m.c_raw[2] = 3.0
        R2 = m(lam).numpy()
    assert (R2[2] <= R[2] + 1e-9).all() and R2[2].mean() < R[2].mean()


def test_slab_components_absorb_only_where_allowed():
    """Pigment has no absorption in the short-wave infrared, water none in the
    visible, dry matter none below 1.4 um -- the support windows that make
    the decomposition identifiable."""
    import torch
    from exp5_km_pinn import Mixing
    m = Mixing(1)
    wl = np.arange(400.0, 2401.0, 4.0)
    with torch.no_grad():
        K = m.endmembers(torch.tensor((wl - 1400.0) / 1000.0).reshape(-1, 1)).numpy()
    peak = K.max(axis=0) + 1e-12
    assert K[wl > 1000, m.ROLE_INV["pigment"]].max() < 1e-3 * peak[m.ROLE_INV["pigment"]]
    assert K[wl < 700, m.ROLE_INV["water"]].max() < 1e-3 * peak[m.ROLE_INV["water"]]
    assert K[wl < 1300, m.ROLE_INV["dry_matter"]].max() < 1e-3 * peak[m.ROLE_INV["dry_matter"]]


def test_slab_results_are_what_the_page_says():
    """The learned spectra land on the known bands, and the honest negative
    holds: neither the slab contents nor PLS transfer across species."""
    import json, os
    p = "results/exp5_km_pinn.json"
    if not os.path.exists(p):
        return
    d = json.load(open(p))
    wl = np.array(d["wl"]); K = np.array(d["endmembers"])
    jw = d["roles"]["water"]
    kw = K[:, jw] / K[:, jw].max()
    # water: the 1450 and 1940 nm bands are the strongest features
    assert kw[np.abs(wl - 1450) < 30].max() > 0.5 or kw[np.abs(wl - 1940) < 30].max() > 0.5
    assert abs(d["median_RWC"]["physics_r"]) < 0.4
    assert d["median_RWC"]["pls_r2"] < 0.3


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
