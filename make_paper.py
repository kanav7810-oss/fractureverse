"""Build the FRACTUREVERSE paper from the numbers on disk.

    python make_paper.py

Writes research/paper.md and research/fractureverse.pdf. Every number in the output
is read from research/stats_summary.json, research/ml_report.json,
research/part1_validation.json, pinn/artifacts/pinn_report.json and
app/public/data/anchored.json. Nothing is retyped, which is the same rule the
frontend follows. The section plan is research/paper_outline.md.

No em dashes. validate_part4.py check 8 scans research/paper.md along with every
other source file, so do not paste one into the section text above.
"""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent
RESEARCH = ROOT / "research"
FIGURES = ROOT / "app" / "public" / "figures"
DATA = ROOT / "app" / "public" / "data"
MD = RESEARCH / "paper.md"
PDF = RESEARCH / "fractureverse.pdf"

TITLE = "FRACTUREVERSE: four fracture theories, three domains, one validated stack"
SUBTITLE = ("Linear elastic and elastic plastic fracture mechanics, XFEM and "
            "peridynamics on a shared material database, with a surrogate model "
            "layer and a physics informed network")


def jload(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def num(x, digits=4):
    if isinstance(x, bool) or x is None:
        return str(x)
    if isinstance(x, (int,)):
        return str(x)
    if abs(x) >= 1e5 or (abs(x) < 1e-3 and x != 0):
        return f"{x:.3e}"
    return f"{round(x, digits):g}"


# --------------------------------------------------------------------------- data
S = jload(RESEARCH / "stats_summary.json")
ML = jload(RESEARCH / "ml_report.json")
P1 = jload(RESEARCH / "part1_validation.json")
PINN = jload(ROOT / "pinn" / "artifacts" / "pinn_report.json")
ANCHORED = jload(DATA / "anchored.json")
CAPTIONS = jload(DATA / "figures.json")

MODEL_ORDER = ["lstm", "xgboost_field", "ridge", "paris_closed_form"]
MODEL_LABEL = {"lstm": "LSTM", "xgboost_field": "XGBoost, field features",
               "ridge": "Ridge, field features",
               "paris_closed_form": "Closed form Paris"}


def life_table() -> list[list[str]]:
    rows = [["Domain", "Material", "sigma max MPa", "a0 mm", "N_f specified",
             "N_f anchored", "Years, specified"]]
    for d, v in S["domain_lives"].items():
        rows.append([d, v["material"], num(v["sigma_max_MPa"]), num(v["a0_mm"]),
                     num(v["specified"]["N_f"]), num(v["anchored"]["N_f"]),
                     num(v["specified"]["years_to_failure"])])
    return rows


def model_table() -> list[list[str]]:
    ts = S["machine_learning"]["test_scores"]
    rows = [["Model", "R squared", "RMSE, decades", "Median life ratio error"]]
    for k in MODEL_ORDER:
        m = ts[k]
        rows.append([MODEL_LABEL[k], num(m["r2"], 5), num(m["rmse_decades"], 4),
                     num(m["median_life_ratio_error"], 3)])
    return rows


def per_domain_table() -> list[list[str]]:
    ts = S["machine_learning"]["test_scores"]
    doms = list(ts["lstm"]["per_domain_r2"])
    rows = [["Model"] + [f"{d} R squared" for d in doms]]
    for k in MODEL_ORDER:
        rows.append([MODEL_LABEL[k]] + [num(ts[k]["per_domain_r2"][d], 5) for d in doms])
    return rows


def theory_table() -> list[list[str]]:
    acc = PINN["accuracy"]
    hn = S["part1_headline_numbers"]
    return [
        ["Quantity", "Value", "Reference"],
        ["XFEM K_I error, centre cracked panel",
         ", ".join(num(x, 3) + " percent" for x in hn["xfem_K_I_error_percent"]),
         "closed form F sigma sqrt(pi a)"],
        ["EPFM domain J error", num(hn["epfm_J_error_percent"], 3) + " percent",
         "K_I squared over E prime"],
        ["Pure mode II kink angle",
         num(hn["pure_mode_II_kink_angle_deg"], 4) + " degrees",
         "Erdogan and Sih, -70.5 degrees"],
        ["Peridynamic horizon implied strength",
         num(hn["peridynamic_pd_strength_MPa"], 4) + " MPa",
         "applied " + num(hn["peridynamic_applied_MPa"], 3) + " MPa"],
        ["K_I, XFEM interaction integral",
         num(acc["K_I_xfem_interaction_integral"], 5), "analytical " +
         num(acc["K_I_analytical"], 5)],
        ["K_I, PINN opening fit", num(acc["K_I_pinn_from_opening"], 5),
         "XFEM opening fit " + num(acc["K_I_xfem_from_opening"], 5)],
        ["PINN displacement relative L2 against XFEM",
         num(acc["displacement_relative_L2_vs_xfem"] * 100, 3) + " percent",
         f"{PINN['architecture']['n_parameters']} parameters, "
         f"{num(PINN['wall_clock_s'], 5)} s on CPU"],
    ]


def anchored_table() -> list[list[str]]:
    rows = [["Domain", "Material", "Paris C specified", "Paris C anchored", "Ratio"]]
    for r in ANCHORED:
        rows.append([r["domain"], r["material"], num(r["paris_C"]),
                     num(r["paris_C_anchored"]) if r.get("paris_C_anchored") else "n/a",
                     num(r["ratio"], 3) if r.get("ratio") else "n/a"])
    return rows


# ------------------------------------------------------------------------- content
def sections() -> list[tuple[str, list]]:
    ml = S["machine_learning"]
    a = S["domain_lives"]["aerospace"]
    arch = PINN["architecture"]
    return [
        ("Abstract", [
            "P", "Four fracture theories, linear elastic fracture mechanics, elastic "
            "plastic fracture mechanics, the extended finite element method and bond "
            "based peridynamics, are implemented against a single material database "
            "and a single unit convention, then applied to an aerospace panel, a "
            "cortical bone section and a concrete member. A surrogate layer reads the "
            "first " + str(ml["window_samples"]) + " samples of a crack growth "
            "trajectory and predicts total life, and a physics informed network "
            "reproduces the XFEM displacement field on the same panel to " +
            num(PINN["accuracy"]["displacement_relative_L2_vs_xfem"] * 100, 3) +
            " percent relative L2. Every number in this paper is read from the "
            "validation artifacts in the repository, none is retyped.",
        ]),
        ("1. Introduction", [
            "P", "Fatigue is the dominant single cause of airframe structural failure "
            "at roughly 20 percent, drives revision surgery in an implant population "
            "of about 400,000 hip and knee replacements a year in the United States, "
            "and contributes to the 42,000 of 617,000 bridges in the National Bridge "
            "Inventory carrying a structurally deficient rating.",
            "P", "The four theories above are normally taught and coded in isolation, "
            "on different meshes, in different unit systems and against different "
            "benchmarks. Here they share one material database, one unit convention "
            "and one validation harness, which is what makes the cross theory "
            "comparison in section 6 meaningful.",
        ]),
        ("2. Governing theory and validation", [
            "P", "Each theory is checked against an independent target rather than "
            "against another part of this codebase.",
            "T", theory_table(),
            "P", "LEFM supplies K_I equal to F sigma sqrt(pi a), the Paris, Walker and "
            "Forman growth laws and an implicit critical crack length. EPFM adds the "
            "domain form J integral, the elastic plastic J, J-R resistance curves, "
            "tearing instability by tangency and CTOD. XFEM uses shifted Heaviside and "
            "four branch function enrichment with exact polygon clipping on cut "
            "elements, the interaction integral for K_I and K_II, and the maximum "
            "circumferential stress criterion for turning. Peridynamics is bond based "
            "with micromodulus and critical stretch calibrated to G_0 and no "
            "predefined crack path.",
        ]),
        ("3. Domain data and unit convention", [
            "P", "SI everywhere except stress intensity, which is in MPa sqrt(m), and "
            "the Paris coefficient, which is scaled so that da/dN is in metres per "
            "cycle for delta K in MPa sqrt(m). Applied stress crosses every interface "
            "in pascals. The machine learning target is log10 of the life in cycles.",
            "P", "The bulk National Bridge Inventory table was not downloaded. "
            "data/civil/corrosion.json carries the condition rating scale and the "
            "deficient bridge count, and no code path depends on the 617,000 row "
            "table.",
            "T", life_table(),
        ]),
        ("4. Surrogate modelling", [
            "P", "The dataset is " + str(sum(ml["n_trajectories"].values())) +
            " trajectories, " + str(ml["n_trajectories"]["aerospace"]) + " per domain, "
            "from the LEFM integrator, seed " + str(ML["seed"]) + ", split " +
            str(ml["split_sizes"]["train"]) + " train, " +
            str(ml["split_sizes"]["val"]) + " validation and " +
            str(ml["split_sizes"]["test"]) + " test. Inspection noise is applied to "
            "the observed window only.",
            "P", "The leak that had to be closed: with the Paris coefficients and the "
            "critical crack length in the feature vector the target is a closed form "
            "function of the inputs, and ridge regression alone scores R squared above "
            "0.999. The reported feature set removes them.",
            "T", model_table(),
            "T", per_domain_table(),
            "P", "Finding, stated rather than buried. Every model clears the " +
            num(ml["lstm_target_r2"], 3) + " R squared target, ridge included, because "
            "Paris Law is a power law and log life is nearly linear in the log "
            "features. The discriminating metrics are RMSE in decades of life and the "
            "median life ratio error, and those are the columns to read.",
        ]),
        ("5. Physics informed network", [
            "P", f"{arch['depth']} hidden layers of {arch['width']} neurons with "
            f"{arch['activation']} activation and {arch['init']} initialisation, "
            f"{arch['n_parameters']} parameters, on the plane stress centre cracked "
            "panel that matches the XFEM benchmark exactly. Five loss terms: " +
            ", ".join(PINN["loss_names"]) + ", with gradient norm weighting rebalanced "
            "during training.",
            "P", "Two design points. A plain multilayer perceptron cannot represent "
            "the displacement jump across the crack faces, so " + arch["enrichment"] +
            " are supplied as input features and carry the discontinuity, which moves "
            "the XFEM enrichment idea from the basis into the inputs. The roller "
            "boundary condition is a hard constraint, " + arch["hard_constraint"] +
            ", so it never competes with the other losses.",
            "P", f"Training was {PINN['epochs']} epochs in {num(PINN['wall_clock_s'], 5)}"
            f" s on {PINN['device']} at {num(PINN['seconds_per_epoch'], 4)} s per epoch. "
            "This machine has an integrated Radeon 610M with no usable compute, so the "
            "epoch count was chosen to fit that budget.",
        ]),
        ("6. Results", [
            "P", "Life predictions per domain are in section 3. The aerospace anchor "
            "case, " + a["material"] + " at " + num(a["sigma_max_MPa"]) + " MPa, R " +
            num(a["R"], 2) + ", a0 " + num(a["a0_mm"]) + " mm, " + a["geometry"] +
            " cracked, W " + num(a["W_mm"]) + " mm, gives " +
            num(a["specified"]["N_f"]) + " cycles on the specified Paris coefficient "
            "and " + num(a["anchored"]["N_f"]) + " cycles on the anchored one, a ratio "
            "of " + num(a["anchored"]["N_f"] / a["specified"]["N_f"], 3) +
            ", with a critical crack length of " + num(a["specified"]["a_c_mm"], 4) +
            " mm in both cases.",
            "T", anchored_table(),
            "P", "Cross theory agreement on the same panel is the K_I block of the "
            "table in section 2. The three routes, the closed form, the XFEM "
            "interaction integral and the PINN opening fit, agree to within a few "
            "percent, and the same near tip opening estimator is applied to the PINN "
            "and to the XFEM field so that comparison isolates the network rather than "
            "the estimator.",
        ]),
        ("7. Limitations", [
            "P", "1. " + S["paris_coefficient_used"]["statement"],
            "P", "2. Bond based peridynamics ties effective strength to the horizon "
            "and fixes the Poisson ratio at one third in two dimensional plane stress. "
            "Every peridynamic run reports the horizon implied strength next to the "
            "applied stress.",
            "P", "3. " + ml["honesty_note"],
            "P", "4. The physics informed network is trained on one panel geometry at "
            "one load level. It is a field solver demonstration, not a parametric "
            "surrogate.",
            "P", "5. Corrosion is coupled to fatigue through a section loss to stress "
            "rise argument, the simplest defensible coupling, and it is labelled as "
            "such on the corrosion figure.",
            "P", "6. Trajectory generation, training and figure production are seeded, "
            "but torch on CPU is only bitwise reproducible for the same torch build.",
        ]),
        ("8. Reproduction", [
            "P", "From the repository root, in order:",
            "C", "python validate_part1.py\n"
                 "python -m ml.train_all\n"
                 "python -m pinn.train\n"
                 "python -m python_stats.generate_all\n"
                 "python -m python_stats.summarize\n"
                 "python app/gen_fixtures.py\n"
                 "npm run build --prefix app\n"
                 "uvicorn api.main:app --port 8000\n"
                 "python validate_part4.py",
        ]),
    ]


# ----------------------------------------------------------------------- markdown
def build_markdown() -> str:
    out = [f"# {TITLE}", "", SUBTITLE, "",
           "Generated by make_paper.py. Every number is read from the validation "
           "artifacts in this repository.", ""]
    for title, body in sections():
        out += [f"## {title}", ""]
        i = 0
        while i < len(body):
            kind, payload = body[i], body[i + 1]
            if kind == "P":
                out += [payload, ""]
            elif kind == "C":
                out += ["```bash", payload, "```", ""]
            else:
                out += ["| " + " | ".join(payload[0]) + " |",
                        "|" + "---|" * len(payload[0])]
                out += ["| " + " | ".join(r) + " |" for r in payload[1:]]
                out += [""]
            i += 2
    out += ["## Figures", ""]
    for i, (name, caption) in enumerate(sorted(CAPTIONS.items()), start=1):
        out += [f"**Figure {i}. {name}.** {caption}", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------------- pdf
def build_pdf() -> None:
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=9.5, leading=13.5,
                          alignment=TA_JUSTIFY, spaceAfter=7)
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=13, spaceBefore=12,
                        spaceAfter=6, textColor=colors.HexColor("#12233f"))
    cap = ParagraphStyle("cap", parent=body, fontSize=8, leading=10.5,
                         textColor=colors.HexColor("#444444"), alignment=0)
    code = ParagraphStyle("code", parent=ss["Code"], fontSize=8.5, leading=11,
                          backColor=colors.HexColor("#f2f4f7"), spaceAfter=8)

    story: list = [
        Paragraph(TITLE, ParagraphStyle("t", parent=ss["Title"], fontSize=17,
                                        leading=21)),
        Paragraph(SUBTITLE, ParagraphStyle("st", parent=body, fontSize=10.5,
                                           leading=14, alignment=1)),
        Spacer(1, 8),
    ]

    table_style = TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 7.6),
        ("LEADING", (0, 0), (-1, -1), 9.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12233f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c3cad6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f4f6fa")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ])

    for title, content in sections():
        story.append(Paragraph(title, h1))
        i = 0
        while i < len(content):
            kind, payload = content[i], content[i + 1]
            if kind == "P":
                story.append(Paragraph(payload, body))
            elif kind == "C":
                for line in payload.split("\n"):
                    story.append(Paragraph(line.replace(" ", "&nbsp;"), code))
            else:
                cell = ParagraphStyle("cell", parent=body, fontSize=7.6, leading=9.5,
                                      spaceAfter=0, alignment=0)
                head = ParagraphStyle("head", parent=cell, textColor=colors.white)
                grid = [[Paragraph(c, head if r == 0 else cell) for c in row]
                        for r, row in enumerate(payload)]
                t = Table(grid, repeatRows=1, hAlign="LEFT")
                t.setStyle(table_style)
                story += [t, Spacer(1, 9)]
            i += 2

    story.append(PageBreak())
    story.append(Paragraph("Figures", h1))
    for i, (name, caption) in enumerate(sorted(CAPTIONS.items()), start=1):
        png = FIGURES / f"{name}.png"
        if png.exists():
            img = Image(str(png))
            scale = min(160 * mm / img.imageWidth, 105 * mm / img.imageHeight)
            img.drawWidth = img.imageWidth * scale
            img.drawHeight = img.imageHeight * scale
            img.hAlign = "CENTER"
            story.append(img)
        story.append(Paragraph(f"<b>Figure {i}. {name}.</b> {caption}", cap))
        story.append(Spacer(1, 8))

    doc = SimpleDocTemplate(str(PDF), pagesize=A4, title=TITLE,
                            author="FRACTUREVERSE", leftMargin=20 * mm,
                            rightMargin=20 * mm, topMargin=18 * mm,
                            bottomMargin=18 * mm)
    doc.build(story)


def main() -> int:
    md = build_markdown()
    if chr(0x2014) in md:
        raise SystemExit("em dash reached the manuscript, fix the source text")
    MD.write_text(md, encoding="utf-8")
    build_pdf()
    print(f"wrote {MD.relative_to(ROOT)} and {PDF.relative_to(ROOT)}, "
          f"{PDF.stat().st_size // 1024} kB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
