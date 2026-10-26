"""Publication density comparison: normalized histograms and conditional CDFs."""
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))
from plot import configure_fonts, plt, INK, GRID, MUTED
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib import font_manager
import numpy as np
import pandas as pd

COLOURS = {'CPOSS_single_records': '#5B2A86', 'OMC25_last_frames': '#D56E16',
           'CSD_organic': '#667780', 'CPOSS_single_system_balanced': '#5B2A86'}


def main():
    font = configure_fonts(Path('/System/Library/Fonts/Helvetica.ttc'))
    hist = pd.read_csv(BASE / 'tables/density_histograms_common_bins.csv')
    curves = pd.read_csv(BASE / 'tables/cposs_density_ecdfs.csv')
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.5))
    fig.subplots_adjust(left=.08, right=.985, bottom=.20, top=.72, wspace=.28)
    keys = ['CPOSS_single_records', 'OMC25_last_frames', 'CSD_organic']
    for key in keys:
        data = hist[hist.population == key]
        edges = np.r_[data.bin_left_g_cm3.to_numpy(), data.bin_right_g_cm3.iloc[-1]]
        axes[0].stairs(data.percent_per_bin, edges, color=COLOURS[key], lw=1.45, zorder=3 if key.startswith('CPOSS') else 2)
        if key.startswith('CPOSS'):
            axes[0].stairs(data.percent_per_bin, edges, color=COLOURS[key], fill=True, alpha=.07, lw=0)
        else:
            axes[1].plot(edges, np.r_[0, np.cumsum(data.percent_per_bin)], color=COLOURS[key], lw=1.55)
    for key, linestyle in [('CPOSS_single_records', '-'), ('CPOSS_single_system_balanced', (0, (3, 2)))]:
        data = curves[curves.population == key]
        axes[1].step(np.r_[.8, data.density_g_cm3, 2.4], np.r_[0, 100 * data.cumulative_fraction, 100],
                     where='post', color=COLOURS[key], linestyle=linestyle, lw=1.55)
    handles = [Line2D([], [], color=COLOURS[key], lw=2,
                      label=label, linestyle=(0, (3, 2)) if key.endswith('balanced') else '-')
               for key, label in [('CPOSS_single_records', 'CPOSS records'),
                                  ('OMC25_last_frames', 'OMC25 relaxed (paper histogram)'),
                                  ('CSD_organic', 'Organic CSD (paper histogram)'),
                                  ('CPOSS_single_system_balanced', 'CPOSS, equal weight per system')]]
    fig.legend(handles=handles, frameon=False, ncol=2, loc='upper center', bbox_to_anchor=(.53, .985),
               columnspacing=2.5, handlelength=2.5, labelspacing=.9)
    axes[0].set_ylabel('Records per 0.02 g/cm³ bin (%)')
    axes[1].set_ylabel('Cumulative records (%)')
    axes[1].set_ylim(-2, 103)
    axes[1].set_yticks([0, 25, 50, 75, 100])
    axes[0].set_ylim(bottom=0)
    for ax, letter, title in zip(axes, ['A', 'B'], ['Density distributions', 'Cumulative distributions']):
        ax.set_xlim(.8, 2.4)
        ax.set_xticks(np.arange(.8, 2.41, .2))
        ax.set_xlabel('Crystal density (g/cm³)')
        ax.grid(axis='y', color=GRID, lw=.55)
        ax.set_axisbelow(True)
        ax.tick_params(length=3, width=.65)
        ax.set_title(title, loc='left', pad=10)
        ax.text(-.13, 1.07, letter, transform=ax.transAxes, weight='bold', fontsize=11, va='center')
    coverage = pd.read_csv(BASE / 'tables/cposs_density_window_coverage.csv').iloc[0]
    fig.text(.53, .035, f'CPOSS: {int(coverage.records_in_window):,} records in the shared window; '
             f'{int(coverage.systems_all)} molecular systems. All curves normalized over 0.8-2.4 g/cm³.',
             ha='center', color=MUTED, fontsize=7)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    outside, fonts = [], set()
    for text in fig.findobj(Text):
        if text.get_visible() and text.get_text():
            box = text.get_window_extent(renderer)
            if box.x0 < -1 or box.y0 < -1 or box.x1 > fig.bbox.width + 1 or box.y1 > fig.bbox.height + 1:
                outside.append(text.get_text())
            file = font_manager.findfont(text.get_fontproperties(), fallback_to_default=False)
            fonts.add(font_manager.FontProperties(fname=file).get_name())
    assert not outside, outside
    assert fonts == {'Helvetica'}
    pdf = BASE.parent / 'output/pdf/cposs_omc25_csd_density_comparison.pdf'
    png = BASE.parent / 'figures/cposs_omc25_csd_density_comparison.png'
    fig.savefig(pdf, metadata={'Title': 'CPOSS, OMC25 and CSD density distributions', 'CreationDate': None, 'ModDate': None})
    fig.savefig(png, dpi=300)
    plt.close(fig)
    validation = {'vector_pdf': str(pdf), 'png': str(png), 'size_inches': [7.6, 3.5],
                  'actual_fonts': sorted(fonts), 'out_of_bounds_text': outside, 'png_dpi': 300, **font}
    (BASE / 'figure_validation.json').write_text(json.dumps(validation, indent=2) + '\n')
    print(json.dumps(validation, indent=2))


if __name__ == '__main__':
    main()
