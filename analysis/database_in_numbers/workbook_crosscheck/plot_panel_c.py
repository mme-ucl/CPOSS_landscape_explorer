"""Draw the proposed software panel with the reviewed figure's dimensions/style."""
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

os.environ.setdefault('MPLCONFIGDIR', '/tmp/cposs-matplotlib')
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
from make_figure import count_colors, helvetica, tidy, INK
from matplotlib import pyplot as plt
from matplotlib.text import Text


def main():
    here = Path(__file__).resolve().parent
    with (here / 'proposed_panel_c_counts.csv').open() as stream:
        counts = list(csv.DictReader(stream))
    helvetica(Path('/System/Library/Fonts/Helvetica.ttc'))
    width = 0.425 * 210 / 25.4 * 72
    height = (0.596 - 0.330) * 297 / 25.4 * 72 + 5
    fig = plt.figure(figsize=(width / 72, height / 72), facecolor='white')
    fig.text(5 / width, 1 - 5 / height, 'C', fontsize=9, weight='bold', va='top')
    fig.text((5 + 0.029 * 210 / 25.4 * 72) / width, 1 - 5 / height,
             'Reported CSP software', fontsize=9, weight='bold', va='top')
    fig.text(5 / width, (0.574 - 0.330) * 297 / 25.4 * 72 / height,
             'Search and refinement programs', fontsize=7.1, color=INK)
    axes = fig.add_axes([
        ((0.244 - 0.085) * 210 / 25.4 * 72 + 5) / width,
        (0.363 - 0.330) * 297 / 25.4 * 72 / height,
        0.217 * 210 / 25.4 * 72 / width,
        0.189 * 297 / 25.4 * 72 / height,
    ])
    displayed = counts[::-1]
    values = [int(row['datasets']) for row in displayed]
    axes.barh([row['program'] for row in displayed], values, color=count_colors(values), height=0.61)
    axes.set_xlim(0, 215)
    axes.set_xticks([0, 50, 100, 150, 200])
    axes.tick_params(axis='y', length=0, labelsize=7)
    axes.set_xlabel('Datasets', labelpad=3)
    for index, value in enumerate(values):
        axes.text(value + 2.5, index, str(value), va='center', fontsize=6.5)
    tidy(axes, 'x')
    axes.spines['left'].set_visible(False)
    fig.canvas.draw()
    outside = []
    renderer = fig.canvas.get_renderer()
    for text in fig.findobj(Text):
        if text.get_visible() and text.get_text():
            bounds = text.get_window_extent(renderer)
            if bounds.x0 < -1 or bounds.y0 < -1 or bounds.x1 > fig.bbox.width + 1 or bounds.y1 > fig.bbox.height + 1:
                outside.append(text.get_text())
    if outside:
        raise AssertionError(f'Text outside panel: {outside}')
    pdf = BASE / 'output/pdf/panel_c_software_proposal.pdf'
    png = BASE / 'figures/panel_c_software_proposal.png'
    snapshot = json.loads((BASE / 'manifest.json').read_text())
    timestamp = datetime.fromisoformat(snapshot['accessed_date']).replace(tzinfo=ZoneInfo('Europe/London'))
    fig.savefig(pdf, metadata={'Title': 'Proposed panel C: reported CSP software',
                              'Author': 'CPOSS workbook crosscheck',
                              'CreationDate': timestamp, 'ModDate': timestamp})
    plt.close(fig)
    # Render the actual PDF for the preview, rather than a separate plotting path.
    import subprocess
    subprocess.run(['pdftoppm', '-r', '300', '-singlefile', '-png', str(pdf),
                    str(png.with_suffix(''))], check=True)
    print(json.dumps({'pdf': str(pdf), 'png': str(png), 'size_pt': [width, height],
                      'text_outside_panel': outside, 'datasets': int(counts[0]['denominator']), 'counts': counts}, indent=2))


if __name__ == '__main__':
    main()
