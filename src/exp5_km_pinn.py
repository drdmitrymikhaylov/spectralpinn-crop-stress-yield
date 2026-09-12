"""Reading water and dry matter out of a leaf spectrum with a mixing law.

Every stress classifier in this repository reads reflectance as a feature
vector.  A leaf is not a feature vector; it is a scattering slab whose
absorption is a sum over its constituents, and the Kubelka-Munk two-flux
model turns that into an equation a network can be held to:

    R = 1 / (a + b coth(b S d)),   a = 1 + K/S,   b = sqrt(a^2 - 1),
    K d = sum_i  C_i k_i(lambda),   C_i >= 0,  k_i >= 0,   S d = s sigma(lambda),

the reflectance of a scattering, absorbing layer of thickness d over a black
background (Kubelka 1948).  The thickness matters: in the near-infrared
plateau a leaf absorbs almost nothing and reflects about half, not all, of
the light, and that half is S d -- so the equation sees how much tissue
there is, and the absorbing contents come out *per unit area*, which is
what leaf mass per area and water per area are.  (A first version used the
optically-thick form f(R) = K/S; it cannot see thickness, so its
"concentrations" were ratios, and they predicted nothing per area.)

The specific absorption spectra k_i(lambda) are shared by every leaf; the
contents C_i and the scattering thickness s belong to each leaf; sigma is a
shared scattering shape.  All are learned from reflectance alone -- no
chemistry, no labels.  The physics is in the form of the equation: additive,
non-negative absorption inside a slab of finite thickness.

The test is whether the learned concentrations are the physical quantities
they are supposed to be, on a species the model never saw:

  * C_dry    against measured leaf mass per area (LMA), 665 leaves
  * C_water / (C_water + C_dry)  against relative water content (RWC), 664

with every species held out in turn (k_i and S are fitted on the other
species; only the per-leaf concentrations are fitted on the held-out one).
The comparison is a supervised PLS regression trained on the other species
and applied to the held-out one -- the usual approach, with labels.  If the
unsupervised physical decomposition transfers to a new species as well as a
regression that was trained on the target, the mixing law has bought
something.  If it does not, that is reported.

Data: EcoSIS "droughted and watered crops" -- 7 species, leaf spectra
400-2400 nm.  Only the leaf spectra that pass the quality gate are used.
"""

import json
import sys

sys.path.insert(0, 'src')

import numpy as np
import pandas as pd
import torch
from scipy.stats import pearsonr, spearmanr
from sklearn.cross_decomposition import PLSRegression

from spectra import load, valid_mask

torch.set_default_dtype(torch.float64)
torch.manual_seed(0)
WL_LO, WL_HI = 420.0, 2380.0
N_COMP = 3
COMP_NAMES = ["A", "B", "C"]          # named after the fact by where they absorb
KNOWN = {"water": [970, 1200, 1450, 1940], "pigment": [430, 500, 670],
         "dry_matter": [1720, 2100, 2300]}


def km(R):
    R = np.clip(R, 1e-3, 0.999)
    return (1 - R) ** 2 / (2 * R)


def mlp(width=48, depth=3):
    layers, d = [], 1
    for _ in range(depth):
        layers += [torch.nn.Linear(d, width), torch.nn.Tanh()]
        d = width
    layers.append(torch.nn.Linear(d, 1))
    return torch.nn.Sequential(*layers)


class Mixing(torch.nn.Module):
    """Finite-thickness Kubelka-Munk: K d = softplus(c_j) . k(lambda),
    S d = exp(s_j) sigma(lambda), R = 1 / (a + b coth(b S d))."""

    # where each constituent is allowed to absorb (nm).  Without this the
    # decomposition is not identifiable: two of three free components both
    # learned the water bands and neither learned dry matter (first run,
    # kept in results/exp5_km_pinn_unconstrained.txt).  These are support
    # windows, not spectra: pigments absorb in the visible, water from the
    # near-infrared overtone bands upward, dry matter (cellulose, lignin,
    # protein) from 1.5 um upward.  The shapes inside the windows are learned.
    WINDOWS = {0: (None, 780.0), 1: (880.0, None), 2: (1480.0, None)}
    ROLE = {0: "pigment", 1: "water", 2: "dry_matter"}
    ROLE_INV = {"pigment": 0, "water": 1, "dry_matter": 2}

    def __init__(self, n_leaves, n_comp=N_COMP):
        super().__init__()
        self.k_nets = torch.nn.ModuleList([mlp() for _ in range(n_comp)])
        self.s_net = mlp(width=24, depth=2)
        self.c_raw = torch.nn.Parameter(torch.randn(n_leaves, n_comp) * 0.1)
        self.s_raw = torch.nn.Parameter(torch.zeros(n_leaves, 1))

    def endmembers(self, lam_s):
        wl = lam_s * 1000.0 + 1400.0
        cols = []
        for i, n in enumerate(self.k_nets):
            k = torch.nn.functional.softplus(n(lam_s))
            lo, hi = self.WINDOWS[i]
            if lo is not None:
                k = k * torch.sigmoid((wl - lo) / 20.0)
            if hi is not None:
                k = k * torch.sigmoid((hi - wl) / 20.0)
            cols.append(k)
        return torch.cat(cols, 1)

    def scattering(self, lam_s):
        return torch.nn.functional.softplus(self.s_net(lam_s) + 1.0)

    def forward(self, lam_s, idx=None):
        K = self.endmembers(lam_s)                      # (L, n_comp)
        sig = self.scattering(lam_s).T                  # (1, L)
        c = torch.nn.functional.softplus(self.c_raw)    # (N, n_comp)
        s = torch.exp(self.s_raw)                       # (N, 1)
        if idx is not None:
            c, s = c[idx], s[idx]
        Kd = c @ K.T + 1e-6                             # (N, L)
        Sd = s * sig                                    # (N, L)
        a = 1.0 + Kd / Sd
        b = torch.sqrt(a ** 2 - 1.0 + 1e-12)
        return 1.0 / (a + b / torch.tanh(b * Sd))      # reflectance


def fit(F, lam_s, steps=2500, model=None, freeze_spectra=False, lr=1e-2):
    """Fit reflectance.  If freeze_spectra, only per-leaf C, s move."""
    N = F.shape[0]
    Y = torch.tensor(F)
    if model is None:
        model = Mixing(N)
    else:
        m2 = Mixing(N)
        m2.k_nets.load_state_dict(model.k_nets.state_dict())
        m2.s_net.load_state_dict(model.s_net.state_dict())
        model = m2
    if freeze_spectra:
        for p in list(model.k_nets.parameters()) + list(model.s_net.parameters()):
            p.requires_grad_(False)
        params = [model.c_raw, model.s_raw]
    else:
        params = list(model.parameters())
    opt = torch.optim.Adam(params, lr=lr)
    L = torch.tensor(lam_s).reshape(-1, 1)
    for it in range(steps):
        opt.zero_grad()
        pred = model(L)
        loss = torch.mean((pred - Y) ** 2 / (Y + 0.02))
        if not freeze_spectra:
            K = model.endmembers(L)
            # smoothness in wavelength: second differences of log k
            d2 = torch.diff(torch.log(K + 1e-6), n=2, dim=0)
            loss = loss + 1e-2 * torch.mean(d2 ** 2)
        loss.backward()
        opt.step()
    return model, float(loss)


def name_components(K, wl):
    """Which learned spectrum is water, pigment, dry matter -- by where each
    one absorbs relative to the others (normalised to unit area)."""
    Kn = K / K.sum(axis=0, keepdims=True)
    names, used = {}, set()
    for i in range(K.shape[1]):
        scores = {}
        for phys, bands in KNOWN.items():
            sel = np.zeros(len(wl), bool)
            for b in bands:
                sel |= np.abs(wl - b) < 25
            scores[phys] = float(Kn[sel, i].mean() / Kn[:, i].mean())
        names[i] = scores
    return names


def r2(y, yhat):
    return float(1 - np.sum((y - yhat) ** 2) / np.sum((y - y.mean()) ** 2))


def main():
    meta, wl, R = load("crops")
    ok = valid_mask(wl, R) & (meta["Paired_Spectra"] == "leaf").values
    sel = (wl >= WL_LO) & (wl <= WL_HI)
    wl_s, R = wl[sel], R[ok][:, sel]
    meta = meta[ok].reset_index(drop=True)
    F = np.clip(R, 1e-3, 0.999)          # the model predicts reflectance itself
    lam_s = (wl_s - 1400.0) / 1000.0
    species = meta["Common Name"].values
    rwc = meta["RWC"].values.astype(float)
    lma = meta["Leaf mass per area"].values.astype(float)
    print(f"{len(R)} leaf spectra, {len(set(species))} species")

    # --- one fit on everything, to look at the endmembers
    m_all, loss_all = fit(F, lam_s)
    with torch.no_grad():
        K_all = m_all.endmembers(torch.tensor(lam_s).reshape(-1, 1)).numpy()
        S_all = m_all.scattering(torch.tensor(lam_s).reshape(-1, 1)).squeeze().numpy()
    naming = name_components(K_all, wl_s)
    print(f"global fit loss {loss_all:.4f}")
    for i, sc in naming.items():
        print(f"  component {i}: " + ", ".join(f"{k} {v:.2f}" for k, v in sc.items()))
    # assign: each physical role to the component with the highest score, greedily
    role_of = {v: k for k, v in Mixing.ROLE.items()}
    print("  roles (fixed by support window):", role_of)

    # --- within species: do the contents track the chemistry at all?
    c_all = torch.nn.functional.softplus(m_all.c_raw).detach().numpy()
    s_all = torch.exp(m_all.s_raw).detach().squeeze().numpy()
    out_within = {}
    for sp in sorted(set(species)):
        k = species == sp
        row = {"n": int(k.sum())}
        for target, y in (("RWC", rwc), ("LMA", lma)):
            kk = k & np.isfinite(y)
            if kk.sum() < 15:
                continue
            cw, cd, cp = c_all[kk, role_of["water"]], c_all[kk, role_of["dry_matter"]], c_all[kk, role_of["pigment"]]
            row[target] = {"r_water": float(pearsonr(cw, y[kk])[0]),
                           "r_dry": float(pearsonr(cd, y[kk])[0]),
                           "r_pigment": float(pearsonr(cp, y[kk])[0]),
                           "r_thickness": float(pearsonr(s_all[kk], y[kk])[0]),
                           "r_water_fraction": float(pearsonr(cw / (cw + cd + 1e-9), y[kk])[0])}
        out_within[sp] = row
        print(f"  within {sp:18s}: " + "  ".join(
            f"{t}: water {row[t]['r_water']:+.2f} dry {row[t]['r_dry']:+.2f} thick {row[t]['r_thickness']:+.2f}"
            for t in ("RWC", "LMA") if t in row))

    # --- leave-one-species-out
    out = {"n": int(len(R)), "roles": role_of, "wl": wl_s.tolist(),
           "endmembers": K_all.tolist(), "scattering": S_all.tolist(),
           "naming_scores": naming, "within": out_within, "loso": {}}
    for sp in sorted(set(species)):
        te = species == sp; tr = ~te
        m_tr, _ = fit(F[tr], lam_s, steps=2000)
        m_te, _ = fit(F[te], lam_s, steps=800, model=m_tr, freeze_spectra=True, lr=3e-2)
        with torch.no_grad():
            K_tr = m_tr.endmembers(torch.tensor(lam_s).reshape(-1, 1)).numpy()
            c_te = torch.nn.functional.softplus(m_te.c_raw).numpy()
            s_te = torch.exp(m_te.s_raw).squeeze().numpy()
        roles = role_of
        cw = c_te[:, roles["water"]]; cd = c_te[:, roles["dry_matter"]]
        frac_w = cw / (cw + cd + 1e-9)          # water share of the absorbing contents
        res = {"n_test": int(te.sum())}
        # PLS baselines trained on the other species (with labels)
        X = np.log(1.0 / np.clip(R, 1e-3, None))
        for target, y, phys_feat, label in (("RWC", rwc, frac_w, "water_fraction"),
                                           ("LMA", lma, cd, "dry_matter_per_area")):
            mtr = tr & np.isfinite(y); mte = te & np.isfinite(y)
            if mte.sum() < 15 or mtr.sum() < 30:
                continue
            pls = PLSRegression(n_components=10).fit(X[mtr], y[mtr])
            yhat = pls.predict(X[mte]).ravel()
            feat = phys_feat[np.isfinite(y[te])]
            res[target] = {
                "physics_r": float(pearsonr(feat, y[mte])[0]),
                "physics_rho": float(spearmanr(feat, y[mte])[0]),
                "pls_r": float(pearsonr(yhat, y[mte])[0]),
                "pls_r2": r2(y[mte], yhat),
                "sd_target": float(np.std(y[mte])),
            }
        out["loso"][sp] = res
        line = f"  {sp:18s} n={te.sum():4d}"
        for target in ("RWC", "LMA"):
            if target in res:
                r = res[target]
                line += (f" | {target}: physics r {r['physics_r']:+.2f} (rho {r['physics_rho']:+.2f})"
                         f"  PLS r {r['pls_r']:+.2f} R2 {r['pls_r2']:+.2f}")
        print(line)

    # pooled summary
    for target in ("RWC", "LMA"):
        rows = [v[target] for v in out["loso"].values() if target in v]
        if rows:
            out[f"median_{target}"] = {k: float(np.median([r[k] for r in rows]))
                                       for k in ("physics_r", "physics_rho", "pls_r", "pls_r2")}
            print(f"median over species, {target}: " + ", ".join(
                f"{k} {v:+.2f}" for k, v in out[f"median_{target}"].items()))
    with open("results/exp5_km_pinn.json", "w") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
