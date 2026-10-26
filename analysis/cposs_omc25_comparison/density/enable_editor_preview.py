"""Make the existing fragment previewable without changing how a paper inputs it."""
from pathlib import Path
import re

FILE = Path(__file__).resolve().parent.parent / 'results_section.tex'
PREFIX = r"""% BEGIN STANDALONE PREVIEW PREAMBLE
% When input into a paper, its class already defines \subsection and this is skipped.
\ifdefined\subsection
\else
  \documentclass[11pt]{article}
  \usepackage[margin=20mm]{geometry}
  \usepackage{graphicx}
  \usepackage{url}
  \newcommand{\CPOSSStandalonePreview}{}
  \begin{document}
\fi
% END STANDALONE PREVIEW PREAMBLE

"""
FOOTER = r"""
% BEGIN STANDALONE PREVIEW FOOTER
% Only the editor's standalone preview includes these figures and reference.
\ifdefined\CPOSSStandalonePreview
  \begin{figure}[p]
    \centering
    \includegraphics[width=\textwidth]{output/pdf/cposs_omc25_comparison.pdf}
    \input{caption.tex}
  \end{figure}
  \begin{figure}[p]
    \centering
    \includegraphics[width=\textwidth]{output/pdf/cposs_omc25_csd_density_comparison.pdf}
    \input{density/caption.tex}
  \end{figure}
  \begin{thebibliography}{1}
    \bibitem{gharakhanyan2026omc25}
    V.~Gharakhanyan et al.,
    Open Molecular Crystals 2025 (OMC25) dataset and models,
    \textit{Scientific Data} (2026).
    \url{https://doi.org/10.1038/s41597-026-06628-2}.
  \end{thebibliography}
  \end{document}
\fi
% END STANDALONE PREVIEW FOOTER
"""


def main():
    text = FILE.read_text()
    for part in ['PREAMBLE', 'FOOTER']:
        text = re.sub(r'% BEGIN STANDALONE PREVIEW ' + part + r'.*?% END STANDALONE PREVIEW ' + part + r'\n?',
                      '', text, flags=re.S)
    FILE.write_text(PREFIX + text.strip() + '\n' + FOOTER)


if __name__ == '__main__':
    main()
