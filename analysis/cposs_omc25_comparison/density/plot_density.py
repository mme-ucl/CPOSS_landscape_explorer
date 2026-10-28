"""Publication density comparison: unit-area densities and conditional CDFs."""
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
    keys = ['CPOSS_single_system_balanced', 'OMC25_last_frames', 'CSD_organic']
    normalization = {}
    for key in keys:
        data = hist[hist.population == key]
        edges = np.r_[data.bin_left_g_cm3.to_numpy(), data.bin_right_g_cm3.iloc[-1]]
        density = data.probability_density_cm3_g.to_numpy()
        area = float(np.sum(density * np.diff(edges)))
        assert np.isclose(area, 1, atol=1e-10), (key, area)
        normalization[key] = {'density_integral': area}
        axes[0].stairs(density, edges, color=COLOURS[key], lw=1.45, zorder=3 if key.startswith('CPOSS') else 2)
        if key.startswith('CPOSS'):
            axes[0].stairs(density, edges, color=COLOURS[key], fill=True, alpha=.07, lw=0)
        else:
            cumulative = np.r_[0, np.cumsum(data.probability_mass)]
            cumulative[-1] = 1
            normalization[key]['cdf_endpoint'] = float(cumulative[-1])
            axes[1].plot(edges, cumulative, color=COLOURS[key], lw=1.55)
    for key in ['CPOSS_single_system_balanced']:
        data = curves[curves.population == key]
        assert np.isclose(data.cumulative_fraction.iloc[-1], 1, atol=1e-10)
        normalization[key]['cdf_endpoint'] = float(data.cumulative_fraction.iloc[-1])
        axes[1].step(np.r_[.8, data.density_g_cm3, 2.4], np.r_[0, data.cumulative_fraction, 1],
                     where='post', color=COLOURS[key], lw=1.55)
    handles = [Line2D([], [], color=COLOURS[key], lw=2,
                      label=label)
               for key, label in [('CPOSS_single_system_balanced', 'CPOSS'),
                                  ('OMC25_last_frames', 'OMC25 relaxed'),
                                  ('CSD_organic', 'Organic CSD')]]
    fig.legend(handles=handles, frameon=False, ncol=3, loc='upper center', bbox_to_anchor=(.53, .955),
               columnspacing=2.5, handlelength=2.5)
    axes[0].set_ylabel(r'Probability density (cm$^3$ g$^{-1}$)')
    axes[1].set_ylabel('Cumulative probability')
    axes[1].set_ylim(-.02, 1.03)
    axes[1].set_yticks([0, .25, .5, .75, 1])
    axes[0].set_ylim(bottom=0)
    for ax, letter, title in zip(axes, ['A', 'B'], ['Density distributions', 'Cumulative distributions']):
        ax.set_xlim(.8, 2.4)
        ax.set_xticks(np.arange(.8, 2.41, .2))
        ax.set_xlabel(r'Crystal density (g cm$^{-3}$)')
        ax.grid(axis='y', color=GRID, lw=.55)
        ax.set_axisbelow(True)
        ax.tick_params(length=3, width=.65)
        ax.set_title(title, loc='left', pad=10)
        ax.text(-.13, 1.07, letter, transform=ax.transAxes, weight='bold', fontsize=11, va='center')
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
                  'actual_fonts': sorted(fonts), 'out_of_bounds_text': outside, 'png_dpi': 300,
                  'plotted_populations': keys, 'normalization': normalization,
                  'embedded_comments': False, **font}
    (BASE / 'figure_validation.json').write_text(json.dumps(validation, indent=2) + '\n')
    print(json.dumps(validation, indent=2))


if __name__ == '__main__':
    main()
