"""Pins the numbers in README.md to the files in results/.

Needs no dataset: it reads the README and the result JSON only, so it runs on
a fresh clone.  If a result file is regenerated and a number moves, or the
page is edited and a number is mistyped, one of these fails.

    python -m pytest tests/test_readme_numbers.py
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def load(name):
    return json.loads((ROOT / "results" / name).read_text(encoding="utf-8"))


E1, E2, E4 = (load("exp1_heat_vs_drought.json"), load("exp2_sensor_cascade.json"),
              load("exp4_species_and_time.json"))
CK = load("readme_checks.json")


def u(s):
    """The page writes a true minus sign."""
    return s.replace("-", "−")


def on_page(s):
    assert s in README, f"not on the page: {s!r}"


def test_four_class_split_by_temperature():
    a = CK["four_class_by_temperature"]
    cm = E1["four_class"]["confusion"]
    assert [sum(r) for r in cm] == a["n_per_class"] == [186, 198, 170, 181]
    cold, hot = a["water_axis_correct|23C"], a["water_axis_correct|30C"]
    # the two halves must add up to the published 73 %
    whole = (cold["right"] + hot["right"]) / (cold["n"] + hot["n"])
    assert abs(whole - E1["four_class"]["water_correct"]) < 1e-12
    on_page(f"| plants at 23 °C | {100 * cold['rate']:.1f}% | {cold['right']} of {cold['n']} |")
    on_page(f"| plants at 30 °C | {100 * hot['rate']:.1f}% | {hot['right']} of {hot['n']} |")
    on_page(f"{100 * cold['rate']:.0f}% for plants grown at 23 °C and "
            f"{100 * hot['rate']:.0f}% for")
    w = a["ww30_called_ws30"]
    assert (w["count"], w["n"], w["called_correctly"]) == (cm[1][3], sum(cm[1]), cm[1][1])
    assert w["count"] > w["called_correctly"]
    on_page(f"called water-stressed {w['count']} times out of\n{w['n']} and called "
            f"correctly {w['called_correctly']} times")
    s = a["ws30_called_ww30"]
    on_page(f"happens {s['count']} times in {s['n']} ({100 * s['rate']:.0f}%)")
    on_page(f"errors run at {100 * a['ww23_called_ws23']['rate']:.0f}% and "
            f"{100 * a['ws23_called_ww23']['rate']:.0f}%")
    on_page(f"{100 * a['heat_axis_correct|well watered']['rate']:.1f}%\nright on "
            f"well-watered plants, "
            f"{100 * a['heat_axis_correct|water stressed']['rate']:.1f}% on stressed ones")


def test_water_index_table_is_the_whole_group():
    b = CK["index_selectivity"]
    assert b["n_water_indices"] == 6 and sorted(b["heat_blind"]) == ["NDWI", "WATER1450"]
    for name, v in b["water_indices"].items():
        eff = E1["effects"][name]
        assert eff["d_water"] == v["d_water"] and eff["d_heat"] == v["d_heat"]
        heat = f"{v['d_heat']:+.2f}"
        if name in b["heat_blind"]:
            heat += f" (p = {v['p_heat']:.2f})"
        else:
            assert v["p_heat"] <= 0.001
        on_page(u(f"| {name} | {v['d_water']:+.2f} | {heat} | "
                  f"{100 * v['heat_to_water_ratio']:.0f}% |"))
    ratios = [v["heat_to_water_ratio"] for k, v in b["water_indices"].items()
              if k not in b["heat_blind"]]
    on_page(f"at {100 * min(ratios):.0f} to {100 * max(ratios):.0f}% of their water response")
    assert abs(b["permutation_p_floor"] - 1 / 2001) < 1e-12
    p = b["photoprotection"]
    on_page(f"PRI ({p['PRI']['heat_to_water_ratio']:.1f} times more heat than water) and "
            f"CRI700 ({p['CRI700']['heat_to_water_ratio']:.1f} times)")
    on_page(f"ARI ({p['ARI']['heat_to_water_ratio']:.1f}) and "
            f"SIPI ({p['SIPI']['heat_to_water_ratio']:.1f}) are not")


SHORT = {"Carolina poplar": "poplar", "cayenne pepper": "pepper",
         "common sunflower": "sunflower", "cultivated radish": "radish",
         "field pumpkin": "pumpkin", "foxtail millet": "millet", "sorghum": "sorghum"}


def test_species_table_and_the_within_species_correction():
    c = CK["species_transfer"]
    assert c["max_abs_refit_difference"] < 0.01
    clear = []
    for s, v in c["species"].items():
        # the refit behind the intervals is the published model
        for key, mine in (("full spectrum", "across_full"), ("indices", "across_indices"),
                          ("within", "within_full")):
            assert abs(E4["by_species"][f"{key}|{s}"]["auc"] - v[mine]) < 0.01
        lo, hi = v["within_minus_across_ci95"]
        diff = f"{v['within_minus_across']:+.2f} [{lo:+.2f}, {hi:+.2f}]"
        if lo > 0 or hi < 0:
            diff = f"**{diff}**"
            clear.append(SHORT[s])
        idx = "{:.2f} [{:.2f}, {:.2f}]".format(v["across_indices"], *v["across_indices_ci95"])
        if v["across_indices_ci95"][1] < 0.5:
            idx = f"**{idx}**"
        on_page(u("| {} | {} | {:.2f} [{:.2f}, {:.2f}] | {:.2f} [{:.2f}, {:.2f}] | {} | {} |".format(
            SHORT[s], v["n"], v["across_full"], *v["across_full_ci95"],
            v["within_full"], *v["within_full_ci95"], diff, idx)))
    assert clear == ["pepper", "radish", "millet", "sorghum"]
    assert c["n_species_within_ahead"] == 5
    assert c["n_species_within_ahead_ci_excludes_zero"] == 3
    assert c["n_species_within_behind_ci_excludes_zero"] == 1
    assert c["n_species_across_full_ci_excludes_half"] == 3
    on_page("ahead in five of seven crops (mean\n"
            f"{c['mean_within_full']:.2f} against {c['mean_across_full']:.2f})")
    on_page(f"(mean {c['mean_within_full']:.2f} against {c['mean_across_full']:.2f})")
    lo, hi = c["across_full_range"]
    on_page(f"{lo:.2f} to {hi:.2f} per\nspecies")
    on_page(f"The full-spectrum range is {lo:.2f} to\n{hi:.2f}.")
    assert "0.48 to 0.68 per" not in README
    assert "and no better within a species than across them" not in README
    m = c["species"]["foxtail millet"]
    on_page("on millet scores {:.2f} [{:.2f}, {:.2f}]".format(
        m["across_indices"], *m["across_indices_ci95"]))
    plants = [v["n_plants"] for v in c["species"].values()]
    on_page(f"The plants, {min(plants)} to {max(plants)} per species")
    assert abs(E4["by_species"]["full spectrum|ALL"]["auc"] - 0.567) < 5e-4


def test_score_against_water_content():
    d = CK["score_vs_rwc"]
    idx, full = d["indices"], d["full spectrum"]
    assert abs(idx["r_pooled"] - E4["physiology"]["indices"]["r_score_vs_rwc"]) < 0.01
    assert abs(full["r_pooled"] - E4["physiology"]["full spectrum"]["r_score_vs_rwc"]) < 0.01
    on_page(f"r = {idx['r_pooled']:+.2f}, has the wrong sign")
    on_page(f"species means correlate at {idx['r_between_species_means']:+.2f}")
    on_page(u(f"the pooled correlation is {idx['r_within_species']:+.2f}"))
    assert idx["n_species"] == 6 and idx["n_species_positive"] == 0
    for s, v in idx["per_species"].items():
        on_page(u("| {} | {} | {:.1f}% | {:+.2f} [{:+.2f}, {:+.2f}] |".format(
            SHORT[s], v["n"], v["mean_rwc"], v["r"], *v["r_ci95"])))
    strong = [SHORT[s] for s, v in idx["per_species"].items() if v["r_ci95"][1] < 0]
    assert strong == ["pepper", "sunflower", "radish"]
    pop = idx["per_species"]["Carolina poplar"]
    assert pop["mean_rwc"] == min(v["mean_rwc"] for v in idx["per_species"].values())
    assert pop["mean_score"] == min(v["mean_score"] for v in idx["per_species"].values())
    on_page(f"(mean RWC {pop['mean_rwc']:.1f}%) and the lowest mean score "
            f"({pop['mean_score']:.2f})")
    flat = sum(idx["per_species"][s]["n"] for s in ("field pumpkin", "Carolina poplar"))
    on_page(f"In pumpkin and poplar, {100 * flat / idx['n']:.0f}% of the leaves")
    f = full["per_species"]
    rest = [f[s]["r"] for s in f if s not in ("common sunflower", "cultivated radish")]
    on_page(u(f"{full['r_pooled']:+.2f} pooled, {full['r_within_species']:+.2f} centred, "
              f"{f['common sunflower']['r']:+.2f} in sunflower, "
              f"{f['cultivated radish']['r']:+.2f} in\nradish, and between "
              f"{min(rest):+.2f} and {max(rest):+.2f} in the other four"))


def test_sensor_gains_against_noise():
    g = CK["sensor_gains"]
    c = E2["cells"]
    base = "multispectral 5-band"
    rows = (("one band at 1610 nm", "multispectral + 1610 nm"),
            ("narrow pair at 531 and 570 nm", "multispectral + PRI pair"))
    for label, key in rows:
        cells = []
        for t in ("water stress", "heat"):
            v = g[f"{key}|{t}"]
            assert abs(v["gain"] - (c[f"{key}|{t}"]["auc"] - c[f"{base}|{t}"]["auc"])) < 1e-12
            cells.append(f"{v['gain']:+.3f} ± {v['sd_of_difference']:.3f}")
        on_page(u(f"| {label} | {cells[0]} | {cells[1]} |"))
    h = g["multispectral + PRI pair|heat"]
    on_page(f"{h['gain']:+.3f} is {h['in_sd']:.1f} sd")
    on_page(f"heat by {abs(g['multispectral + 1610 nm|heat']['in_sd']):.1f} sd in the wrong direction")
    a, b = g["multispectral + 1610 nm|water stress"], g["multispectral + PRI pair|water stress"]
    on_page(f"The right band buys {a['gain']:+.3f} ({a['in_sd']:.1f} sd), the wrong pair "
            f"{b['gain']:+.3f} ({b['in_sd']:.1f} sd)")
    on_page(f"two gains are {g['1610 nm minus PRI pair|water stress']['in_sd']:.1f} sd apart")
    assert 1.8 < a["gain"] / b["gain"] < 2.2          # "twice what the wrong pair does"
    r, rw = g["RGB minus 5-band|heat"], g["RGB minus 5-band|water stress"]
    on_page(f"on heat by {r['gain']:.3f} ({r['in_sd']:.1f} sd)")
    on_page(f"on drought by {abs(rw['gain']):.3f} ({abs(rw['in_sd']):.1f} sd)")
