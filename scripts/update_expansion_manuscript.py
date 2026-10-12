"""Regenerate the primary results table and Delta figure from the audited expansion.

All manuscript prose remains editable and is never overwritten by this script.
This script reads saved artifacts only and makes no provider requests.
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_completed_expansion import validate_completed_collection


def main():
    current_audit = validate_completed_collection(ROOT / "analysis/bfcl/newstudy20261010_plan.json")
    directory = ROOT / "analysis/bfcl"
    saved_audit = json.loads((directory / "newstudy20261010_expansion_collection_audit.json").read_text())
    for field in ("plan_sha256", "localization_cache_sha256", "raw_file_manifest_sha256"):
        if current_audit["provenance"][field] != saved_audit["provenance"][field]:
            raise ValueError(f"Saved expansion audit is stale: {field}")
    cf = json.loads((directory / "newstudy20261010_expansion_cf_summary.json").read_text())
    cells = cf["point_estimates"]["9"]
    boot = cf["bootstrap"]["9"]["common"]
    assert cf["scope"]["task_trials"] == 640 and cf["scope"]["replay_trials"] == 5952
    # The narrative is reviewed manuscript text tied to this frozen cohort.
    # Reject changed estimates before reusing that text with regenerated displays.
    for key, expected in {"EN::gemini": (.623, .595), "EN::claude_sonnet46": (.591, .548),
                          "HI::gemini": (.628, .333)}.items():
        if tuple(round(cells[key][field], 3) for field in ("p", "T")) != expected:
            raise ValueError(f"Reviewed narrative needs updating for {key}")
    langs = ["EN", "AR", "ES", "HI", "JA", "SW", "TR", "ZH"]
    table = [r"\begin{table}[t]\centering\footnotesize",
             r"\setlength{\tabcolsep}{3pt}",
             r"\begin{tabular*}{\columnwidth}{@{\extracolsep{\fill}}llrrrr@{}}\toprule",
             r"Model & Lang. & $p$ & $T$ & $\mathrm{CF}$ & $\Delta$ \\ \midrule"]
    for model, label in (("gemini", r"\shortstack[l]{Gemini 3\\Flash Preview}"),
                         ("claude_sonnet46", r"\shortstack[l]{Claude\\Sonnet 4.6}")):
        for index, lang in enumerate(langs):
            row = cells[f"{lang}::{model}"]
            backbone = r"\multirow{8}{*}{" + label + "}" if index == 0 else ""
            factor = "ref." if lang == "EN" else f'{row["CF"]:.3f}'
            delta = "ref." if lang == "EN" else f'{row["Delta"]:+.3f}'
            table.append(f'{backbone} & {lang} & {row["p"]:.3f} & {row["T"]:.3f} & {factor} & {delta}' + r" \\")
        table.append(r"\midrule")
    table[-1] = r"\bottomrule\end{tabular*}"
    table += [r"\caption{Smoothed replay validity $p$, task success $T$, and common-baseline diagnostics at $K=9$. Each cell has twenty scenarios and two seeds ($40$ trajectories, $372$ replays). CF interpretation depends on the sign of $\log r_{\mathrm{ind}}$. Figure~\ref{fig:results} shows uncertainty for $\Delta$.}",
              r"\label{tab:cf}\end{table}"]

    figure = [r"\begin{figure}[t]\centering",
              r"\resizebox{\columnwidth}{!}{\begin{tikzpicture}[x=2.0cm,y=0.59cm]",
              r"\foreach \x in {-2,-1,0,1}{\draw[gridln] (\x,-0.5)--(\x,6.6);\node[tick,anchor=north] at (\x,-0.6){\x};}",
              r"\draw[dashed,cMut] (0,-0.5)--(0,6.6);"]
    for index, lang in enumerate(langs[1:]):
        y = 6 - index
        figure.append(fr"\node[font=\footnotesize\bfseries,anchor=east] at (-2.08,{y}){{{lang}}};")
        for model, color, offset, mark in (("gemini", "cRef", .11, "circle"),
                                            ("claude_sonnet46", "cBad", -.11, "rectangle")):
            row = boot[f"{lang}::{model}"]
            lower, upper = row["Delta_CI"]
            figure.append(fr"\draw[{color},line width=0.7pt] ({lower:.6f},{y+offset:.2f})--({upper:.6f},{y+offset:.2f});")
            figure.append(fr"\node[{mark},fill={color},inner sep=1.5pt] at ({row['Delta']:.6f},{y+offset:.2f}){{}};")
    figure += [r"\node[font=\footnotesize] at (-.5,-1.65){$\Delta$ (zero: independence baseline)};",
               r"\node[circle,fill=cRef,inner sep=1.5pt] at (-2.14,7.1){};",
               r"\node[font=\footnotesize,text=cRef,anchor=west] (geminiLegend) at (-2.00,7.1){Gemini 3 Flash Preview};",
               r"\node[rectangle,fill=cBad,inner sep=1.5pt,right=14pt of geminiLegend] (claudeLegendMarker) {};",
               r"\node[font=\footnotesize,text=cBad,right=5pt of claudeLegendMarker]{Claude Sonnet 4.6};",
               r"\end{tikzpicture}}",
               r"\caption{Log-ratio deviation at $K=9$, with percentile 95\% intervals from $5000$ paired scenario resamples. Negative values mean lower task success relative to English than the baseline predicts. These intervals are exploratory, not significance tests.}",
               r"\label{fig:results}\end{figure}"]
    generated = ROOT / "paper/generated"
    generated.mkdir(exist_ok=True)
    (generated / "newstudy20261010_main_table.tex").write_text("\n".join(table) + "\n", encoding="utf-8")
    (generated / "newstudy20261010_delta_figure.tex").write_text("\n".join(figure) + "\n", encoding="utf-8")

    print("Regenerated primary table and Delta figure from audited expansion artifacts; manuscript prose was preserved.")


if __name__ == "__main__":
    main()
