"""Publication figures from the cleaned CSV tables; all curves are exact ECDFs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', '/tmp/cposs-omc25-matplotlib')
import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager, pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
import numpy as np
import pandas as pd
from fontTools.ttLib import TTCollection

BASE = Path(__file__).resolve().parent
INK = '#243340'
MUTED = '#52616C'
GRID = '#E1E6EA'
COLOURS = {'CPOSS_single_verified': '#5B2A86', 'OMC25_train': '#D56E16',
           'CPOSS_multicomponent_formula_units': '#287D89'}
LABELS = {'CPOSS_single_verified': 'CPOSS single component', 'OMC25_train': 'OMC25 training',
          'CPOSS_multicomponent_formula_units': 'CPOSS formula units'}


def configure_fonts(path):
    if not path.exists():
        raise FileNotFoundError('Helvetica is required; supply --font with a licensed Helvetica font file')
    dest = BASE / 'tmp/fonts'
    dest.mkdir(parents=True, exist_ok=True)
    paths = []
    if path.suffix.lower() == '.ttc':
        collection = TTCollection(str(path))
        for font in collection.fonts:
            family, style = font['name'].getDebugName(1), font['name'].getDebugName(2)
            if family == 'Helvetica' and style in {'Regular', 'Bold', 'Oblique', 'Bold Oblique'}:
                target = dest / ('Helvetica-' + style.replace(' ', '') + '.ttf')
                font.save(target)
                paths.append(target)
    else:
        paths = [path] + [p for p in path.parent.glob('Helvetica*.ttf') if p != path]
    for candidate in paths:
        font_manager.fontManager.addfont(str(candidate))
    for weight in ['normal', 'bold']:
        resolved = font_manager.findfont(font_manager.FontProperties(family='Helvetica', weight=weight), fallback_to_default=False)
        assert font_manager.FontProperties(fname=resolved).get_name() == 'Helvetica'
    plt.rcParams.update({'font.family': 'Helvetica', 'font.size': 8.2,
                         'axes.labelsize': 8.5, 'axes.titlesize': 9.2,
                         'xtick.labelsize': 7.8, 'ytick.labelsize': 7.8,
                         'legend.fontsize': 7.6, 'axes.spines.top': False,
                         'mathtext.fontset': 'custom', 'mathtext.rm': 'Helvetica',
                         'mathtext.it': 'Helvetica:italic', 'mathtext.bf': 'Helvetica:bold',
                         'axes.spines.right': False, 'axes.edgecolor': MUTED,
                         'axes.linewidth': .65, 'text.color': INK, 'axes.labelcolor': INK,
                         'xtick.color': MUTED, 'ytick.color': MUTED,
                         'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
                         'savefig.facecolor': 'white', 'axes.unicode_minus': False})
    return {'family': 'Helvetica', 'font_source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def ecdf(ax, frame, variable, colour, linestyle='-', width=1.55):
    x, counts = np.unique(frame[variable].to_numpy(), return_counts=True)
    y = 100 * np.cumsum(counts) / len(frame)
    # Explicit zero baseline and post-step jumps, including the exact maximum.
    ax.step(np.r_[0, x], np.r_[0, y], where='post', color=colour,
            linestyle=linestyle, linewidth=width, solid_capstyle='butt')


def make_figure(populations, stem, font_info):
    element = pd.read_csv(BASE / 'tables/elemental_prevalence.csv')
    elements = element[element.population == 'OMC25_train'].element.tolist()
    fig, axes = plt.subplots(1, 3, figsize=(7.60, 3.05), gridspec_kw={'width_ratios': [1.16, 1, 1]})
    fig.subplots_adjust(left=.075, right=.987, bottom=.19, top=.78, wspace=.40)
    handles = [Line2D([], [], color=COLOURS[name], lw=3,
                      label=f'{LABELS[name]} (n = {len(frame):,})') for name, frame in populations.items()]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.53, .986),
               ncol=len(handles), frameon=False, handlelength=1.8, columnspacing=1.6)
    x = np.arange(len(elements))
    width = .77 / len(populations)
    for index, (name, frame) in enumerate(populations.items()):
        values = element[element.population == name].set_index('element').loc[elements, 'prevalence_percent'].to_numpy()
        positions = x + (index - (len(populations) - 1) / 2) * width
        positive = values > 0
        axes[0].bar(positions[positive], values[positive], width=width * .89,
                    color=COLOURS[name], zorder=3)
        axes[0].plot(positions[~positive], np.full((~positive).sum(), .027),
                     transform=axes[0].get_xaxis_transform(), linestyle='none',
                     marker='x', markersize=3.5, markeredgewidth=.8,
                     color=COLOURS[name], zorder=4)
        for variable, linestyle in [('atom_count', '-'), ('heavy_atom_count', (0, (3, 1.8)))]:
            ecdf(axes[1], frame, variable, COLOURS[name], linestyle)
        ecdf(axes[2], frame, 'molar_mass_g_mol', COLOURS[name])
    axes[0].set_yscale('log')
    axes[0].set_ylim(.09, 150)
    axes[0].set_xlim(-.7, len(elements) - .3)
    axes[0].set_xticks(x, elements)
    axes[0].yaxis.set_major_locator(FixedLocator([.1, 1, 10, 100]))
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:g}'))
    axes[0].yaxis.set_minor_locator(NullLocator())
    axes[0].set_ylabel('Containing molecular records (%)')
    axes[0].set_xlabel('Element')
    for ax in axes:
        ax.grid(axis='y', color=GRID, linewidth=.55, zorder=0)
        ax.tick_params(length=3, width=.65, pad=3)
        ax.set_axisbelow(True)
    for ax in axes[1:]:
        ax.set_ylim(-2, 104)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_ylabel('Cumulative records (%)')
    max_atoms = max(frame.atom_count.max() for frame in populations.values())
    max_mass = max(frame.molar_mass_g_mol.max() for frame in populations.values())
    axes[1].set_xlim(0, np.ceil(max_atoms / 20) * 20)
    axes[1].set_xticks(np.arange(0, axes[1].get_xlim()[1] + 1, 40))
    axes[1].set_xlabel('Atoms per molecule' if len(populations) == 2 else 'Atoms per molecule / formula unit')
    axes[2].set_xlim(0, np.ceil(max_mass / 100) * 100)
    mass_step = max(200, np.ceil(axes[2].get_xlim()[1] / 400) * 100)
    axes[2].set_xticks(np.arange(0, axes[2].get_xlim()[1] + 1, mass_step))
    axes[2].set_xlabel(r'Molar mass (g mol$^{-1}$)')
    axes[1].legend(handles=[Line2D([], [], color=INK, lw=1.5, label='All atoms'),
                            Line2D([], [], color=INK, lw=1.5, linestyle=(0, (3, 1.8)), label='Non-H atoms')],
                   loc='lower right', frameon=False, borderaxespad=.4)
    for ax, letter, title in zip(axes, 'ABC', ['Elemental prevalence', 'Molecular size', 'Molar mass']):
        ax.set_title(title, pad=11, loc='left')
        ax.text(-.17, 1.075, letter, transform=ax.transAxes, fontweight='bold', fontsize=11,
                ha='left', va='center')
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bounds = fig.bbox
    outside, families = [], set()
    for text in fig.findobj(Text):
        if not text.get_visible() or not text.get_text():
            continue
        box = text.get_window_extent(renderer)
        if box.x0 < -1 or box.y0 < -1 or box.x1 > bounds.width + 1 or box.y1 > bounds.height + 1:
            outside.append(text.get_text())
        resolved = font_manager.findfont(text.get_fontproperties(), fallback_to_default=False)
        families.add(font_manager.FontProperties(fname=resolved).get_name())
    assert not outside, f'Text outside figure: {outside}'
    assert families == {'Helvetica'}, families
    pdf = BASE / 'output/pdf' / (stem + '.pdf')
    png = BASE / 'figures' / (stem + '.png')
    pdf.parent.mkdir(parents=True, exist_ok=True)
    png.parent.mkdir(exist_ok=True)
    fig.savefig(pdf, metadata={'Title': 'CPOSS and OMC25 chemical content',
                               'Creator': 'Reproducible CPOSS-OMC25 comparison',
                               'CreationDate': None, 'ModDate': None})
    fig.savefig(png, dpi=300)
    plt.close(fig)
    return {'stem': stem, 'size_inches': [7.6, 3.05], 'png_dpi': 300,
            'actual_font_families': sorted(families), 'out_of_bounds_text': outside,
            'population_counts': {name: len(frame) for name, frame in populations.items()}, **font_info}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', type=Path, default=Path('/System/Library/Fonts/Helvetica.ttc'))
    args = parser.parse_args()
    font = configure_fonts(args.font)
    primary = pd.read_csv(BASE / 'tables/cposs_primary_molecules.csv')
    omc = pd.read_csv(BASE / 'tables/omc25_train_molecules.csv')
    multi = pd.read_csv(BASE / 'tables/cposs_multicomponent_formula_units.csv')
    checks = [make_figure({'CPOSS_single_verified': primary, 'OMC25_train': omc},
                          'cposs_omc25_comparison', font),
              make_figure({'CPOSS_single_verified': primary, 'CPOSS_multicomponent_formula_units': multi,
                           'OMC25_train': omc}, 'cposs_omc25_multicomponent', font)]
    (BASE / 'figure_validation.json').write_text(json.dumps(checks, indent=2) + '\n')
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
