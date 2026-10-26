"""Verify saved PDF geometry/fonts/vector content, PNG resolution, and checksums."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent


def main():
    figures = []
    for stem in ['cposs_omc25_comparison', 'cposs_omc25_multicomponent']:
        pdf = BASE / 'output/pdf' / (stem + '.pdf')
        reader = PdfReader(pdf)
        assert len(reader.pages) == 1
        page = reader.pages[0]
        assert abs(float(page.mediabox.width) - 7.6 * 72) < .01
        assert abs(float(page.mediabox.height) - 3.05 * 72) < .01
        fonts = []
        for value in page['/Resources']['/Font'].get_object().values():
            font = value.get_object()
            assert 'Helvetica' in font['/BaseFont'], font['/BaseFont']
            for descendant in font['/DescendantFonts']:
                descriptor = descendant.get_object()['/FontDescriptor'].get_object()
                assert '/FontFile2' in descriptor, 'Font not embedded'
            fonts.append(str(font['/BaseFont']))
        objects = page['/Resources'].get('/XObject', {})
        if hasattr(objects, 'get_object'):
            objects = objects.get_object()
        assert not any(value.get_object().get('/Subtype') == '/Image' for value in objects.values()), 'Rasterized plot in vector PDF'
        with Image.open(BASE / 'figures' / (stem + '.png')) as img:
            assert img.size == (2280, 915), img.size
            assert all(abs(value - 300) < .1 for value in img.info['dpi'])
        text = page.extract_text()
        assert all(label in text for label in ['Elemental prevalence', 'Molecular size', 'Molar mass'])
        figures.append({'stem': stem, 'pages': 1, 'embedded_fonts': fonts, 'vector_only': True,
                        'png_size': [2280, 915], 'png_dpi': 300})
    manifest = json.loads((BASE / 'inputs/manifest.json').read_text())
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((BASE / 'inputs' / name).read_bytes()).hexdigest() == digest
    validation = json.loads((BASE / 'analysis_validation.json').read_text())
    assert hashlib.sha256((BASE / 'inputs/atomic_weights.json').read_bytes()).hexdigest() == validation['atomic_weights_sha256']
    checks = {'verified_figures': figures, 'frozen_inputs_checked': len(manifest['files'])}
    (BASE / 'verification.json').write_text(json.dumps(checks, indent=2) + '\n')
    paths = [p for p in BASE.rglob('*') if p.is_file() and 'tmp' not in p.relative_to(BASE).parts
             and '__pycache__' not in p.parts and p.name != 'SHA256SUMS.txt']
    (BASE / 'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' +
                                               str(p.relative_to(BASE)) + '\n' for p in sorted(paths)))
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
