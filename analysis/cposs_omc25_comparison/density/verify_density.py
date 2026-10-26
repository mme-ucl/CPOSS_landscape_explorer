"""Verify the saved scientific graphic and density input checksums."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((BASE / 'inputs/manifest.json').read_text())
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((BASE / 'inputs' / name).read_bytes()).hexdigest() == digest
    pdf = BASE.parent / 'output/pdf/cposs_omc25_csd_density_comparison.pdf'
    reader = PdfReader(pdf)
    assert len(reader.pages) == 1
    page = reader.pages[0]
    assert abs(float(page.mediabox.width) - 7.6 * 72) < .01
    assert abs(float(page.mediabox.height) - 3.5 * 72) < .01
    names = []
    for ref in page['/Resources']['/Font'].get_object().values():
        font = ref.get_object()
        assert 'Helvetica' in font['/BaseFont']
        for descendant in font['/DescendantFonts']:
            assert '/FontFile2' in descendant.get_object()['/FontDescriptor'].get_object()
        names.append(str(font['/BaseFont']))
    objects = page['/Resources'].get('/XObject', {})
    if hasattr(objects, 'get_object'):
        objects = objects.get_object()
    assert not any(ref.get_object().get('/Subtype') == '/Image' for ref in objects.values())
    with Image.open(BASE.parent / 'figures/cposs_omc25_csd_density_comparison.png') as image:
        assert image.size == (2280, 1050)
        assert all(abs(value - 300) < .1 for value in image.info['dpi'])
    results = {'source_checksums_verified': True, 'vector_only': True, 'embedded_fonts': names,
               'png_size': [2280, 1050], 'png_dpi': 300}
    (BASE / 'verification.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
