"""Compile the manuscript fragments in a disposable local document."""
import json
from pathlib import Path
import re
import shutil
import subprocess

BASE = Path(__file__).resolve().parent
TMP = BASE / 'tmp/latex'


def main():
    for executable in ['pdflatex', 'bibtex']:
        if not shutil.which(executable):
            raise RuntimeError(f'Optional LaTeX smoke test requires {executable}')
    TMP.mkdir(parents=True, exist_ok=True)
    (TMP / 'check.tex').write_text(r"""\documentclass[twocolumn]{article}
\usepackage[margin=18mm]{geometry}
\usepackage{graphicx}
\usepackage{url}
\usepackage[numbers]{natbib}
\graphicspath{{output/pdf/}}
\begin{document}
\input{results_section.tex}
\input{figure.tex}
\input{figure_supplementary.tex}
\IfFileExists{density/caption.tex}{%
\begin{figure*}[t]
\centering
\includegraphics[width=\textwidth]{cposs_omc25_csd_density_comparison.pdf}
\input{density/caption.tex}
\end{figure*}
}{}
\bibliographystyle{plainnat}
\bibliography{references}
\end{document}
""")
    latex = ['pdflatex', '-interaction=nonstopmode', '-halt-on-error',
             '-output-directory=tmp/latex', 'tmp/latex/check.tex']
    for command in [latex, ['bibtex', 'tmp/latex/check'], latex, latex]:
        run = subprocess.run(command, cwd=BASE, text=True, capture_output=True)
        if run.returncode:
            raise RuntimeError(run.stdout[-6000:] + run.stderr[-2000:])
    log = (TMP / 'check.log').read_text(errors='replace')
    failures = re.findall(r'.*(?:undefined|Overfull|^!).*', log, flags=re.MULTILINE)
    assert not failures, failures
    result = {'pdflatex_compiled': True, 'bibtex_resolved': True,
              'undefined_references': False, 'overfull_boxes': False}
    (BASE / 'latex_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
