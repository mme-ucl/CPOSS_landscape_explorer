const { test } = require('node:test');
const assert = require('node:assert/strict');
const catalogue = require('../data/catalogue.json');
const report = require('../data/catalogue-report.json');
const tools = require('../assets/catalogue.js');
const datasets = catalogue.datasets;

test('catalogue contains unique HTTPS datasets and consistent collection totals', () => {
    assert.equal(new Set(datasets.map(x => x.id)).size, datasets.length);
    assert.equal(datasets.length, report.datasetCount);
    assert.equal(datasets.filter(x => x.cases.length).length, report.mappedDatasetCount);
    for (const item of datasets) {
        assert.equal(tools.datasetKey(item.url), item.filename);
        assert.ok(item.url.startsWith('https://'));
    }
    for (const collection of catalogue.collections) {
        assert.equal(tools.filter(datasets, '', collection.id).length, collection.count);
        assert.ok(collection.count > 0);
    }
});

test('search finds names, aliases, codes and dataset identifiers', () => {
    for (const query of ['aSpIrIn', 'ACSALA', 'AspirinA', 'Acetyl salicylic acid', 'ACSALA21']) {
        assert.ok(tools.filter(datasets, query).some(x => x.id === 'AspirinA'), query);
    }
    assert.ok(tools.filter(datasets, 'BTXXVI').some(x => x.id === 'BTXXVIA'));
    assert.equal(tools.filter(datasets, 'no-such-molecule-982345').length, 0);
});

test('collections include named Blind Test candidates and support combined search and overlap', () => {
    assert.ok(tools.filter(datasets, 'Azabicyclononanedione', 'BlindTest').some(x => x.id === 'AzabicyclononanedioneA'));
    assert.equal(tools.filter(datasets, 'ACSALA', 'BlindTest').length, 0);
    for (const collection of ['CPOSS209', 'Tricyclics']) {
        const matches = tools.filter(datasets, 'Carbamazepine', collection);
        assert.ok(matches.some(x => x.id === 'CarbamazepineA'));
        assert.ok(matches.some(x => x.id === 'CarbamazepineB'));
    }
});

test('raw, Pages, blob and encoded URLs identify the same dataset without matching unrelated hosts', () => {
    const urls = [
        'https://raw.githubusercontent.com/LouisePrice/CPOSS_Database/main/0.Chemiscope/AspirinA.json',
        'http://louiseprice.github.io/CPOSS_Database/0.Chemiscope/%41spirinA.json?raw=true',
        'https://github.com/LouisePrice/CPOSS_Database/blob/main/0.Chemiscope/AspirinA.json',
    ];
    for (const url of urls) assert.equal(tools.find(datasets, url).id, 'AspirinA');
    assert.equal(tools.find(datasets, 'https://example.org/AspirinA.json'), null);
    assert.equal(tools.find(datasets, 'https://louiseprice.github.io/Other/0.Chemiscope/AspirinA.json'), null);
    assert.equal(tools.externalDataUrl('./example.json'), './example.json');
    assert.equal(tools.externalDataUrl('../settings.json'), '../settings.json');
    assert.equal(tools.find(datasets, './AspirinA.json'), null);
});

test('multiple searches keep the correct case and energy model associations', () => {
    const a = datasets.find(x => x.id === 'CarbamazepineA');
    const b = datasets.find(x => x.id === 'CarbamazepineB');
    assert.equal(a.cases[0].url, b.cases[0].url);
    assert.equal(a.cases[0].search, 'A');
    assert.equal(b.cases[0].search, 'B');
    assert.deepEqual(a.cases[0].models.map(x => x.id), ['1', 'pDFT', '2']);
    assert.deepEqual(b.cases[0].models.map(x => x.id), ['1', '2']);
});

test('unmapped datasets remain searchable and have no invented case links', () => {
    for (const filename of report.unmappedDatasets) {
        const entry = tools.filter(datasets, filename).find(x => x.filename === filename);
        assert.ok(entry);
        assert.deepEqual(entry.cases, []);
    }
});

test('Urea resources retain both models with audited contents and search metadata', () => {
    const urea = datasets.find(item => item.id === 'UreaA');
    const resources = tools.resources(urea.cases[0], catalogue.archiveContents);
    assert.equal(resources.archives.length, 2);
    const pred = resources.archives.find(item => item.context.includes('CrystPred'));
    const opt = resources.archives.find(item => item.context.includes('CrystOpt'));
    assert.match(pred.context, /Model 1.*Study 20/);
    assert.match(opt.context, /Model 2.*Study 10/);
    assert.match(pred.detail, /850 RES structures.*Urea_CrystPred.xlsx/);
    assert.match(opt.detail, /793 RES structures.*Urea_CrystOpt.xlsx/);
    assert.equal(pred.label, 'Download structures + metadata (.zip)');
    assert.ok(resources.metadata.some(item => item.url.endsWith('/Urea/UreaA/UreaA.xlsx')));
});

test('resource selection is case-specific and clears for unmapped/local data', () => {
    const a = datasets.find(item => item.id === 'CarbamazepineA');
    const b = datasets.find(item => item.id === 'CarbamazepineB');
    const aUrls = tools.resources(a.cases[0]).archives.map(item => item.url);
    const bUrls = tools.resources(b.cases[0]).archives.map(item => item.url);
    assert.ok(aUrls.length && bUrls.length);
    assert.ok(bUrls.every(url => !aUrls.includes(url)));
    assert.deepEqual(tools.resources(null), { archives: [], metadata: [] });
    assert.deepEqual(tools.resources({ models: [] }), { archives: [], metadata: [] });
    const page = { models: [{ id: '1', downloads: ['https://example.org/data.zip'] }] };
    const single = tools.resources(page).archives;
    assert.equal(single.length, 1);
    assert.equal(single[0].label, 'Download structures (.zip)');
    assert.match(single[0].detail, /has not been checked/);
    assert.equal(tools.resources({ models: [{ id: '2', downloads: ['javascript:alert(1)', 'https://example.org/page.html'] }] }).archives.length, 0);
});

test('formula metadata is source-backed per case and absent for unmapped datasets', () => {
    assert.equal(datasets.filter(item => item.formulas.length).length, report.formulaDatasetCount);
    assert.deepEqual(datasets.filter(item => !item.formulas.length).map(item => item.filename), report.datasetsWithoutFormula);
    for (const item of datasets) {
        assert.deepEqual(item.formulas, [...new Set(item.cases.map(page => page.formula).filter(Boolean))]);
        if (!item.cases.length) assert.deepEqual(item.formulas, []);
    }
    assert.deepEqual(datasets.find(item => item.id === 'AspirinA').formulas, ['C9 H8 O4']);
});

test('plain, spaced, lowercase and subscript formula queries return identical complete matches', () => {
    const expected = tools.filter(datasets, 'C9H8O4').map(item => item.id);
    assert.ok(expected.includes('AspirinA'));
    for (const query of ['C9 H8 O4', 'c9h8o4', 'C₉H₈O₄', '\t c₉ h₈ o₄ \n']) {
        assert.deepEqual(tools.filter(datasets, query).map(item => item.id), expected, query);
    }
});

function formulaEntry(id, formulas, collections = []) {
    return { id, filename: id + '.json', label: id, molecule: '', aliases: [], codes: [], collections, ...(formulas ? { formulas } : {}) };
}

test('one formula returns every search and molecule, respecting the collection filter', () => {
    const input = [formulaEntry('AlphaA', ['C9 H8 O4'], ['BlindTest']), formulaEntry('AlphaB', ['C9 H8 O4']), formulaEntry('DifferentA', ['C9 H8 O4'], ['BlindTest']), formulaEntry('UnmappedA')];
    assert.deepEqual(tools.filter(input, 'C₉H₈O₄').map(item => item.id), ['AlphaA', 'AlphaB', 'DifferentA']);
    assert.deepEqual(tools.filter(input, 'C9 H8 O4', 'BlindTest').map(item => item.id), ['AlphaA', 'DifferentA']);
    assert.deepEqual(tools.filter(input, 'C9H8O4', 'CPOSS209'), []);
    assert.equal(tools.filter(input, 'UnmappedA')[0].id, 'UnmappedA');
    const carbamazepine = datasets.find(item => item.id === 'CarbamazepineA');
    const matches = tools.filter(datasets, carbamazepine.formulas[0], 'CPOSS209');
    assert.ok(matches.some(item => item.id === 'CarbamazepineA'));
    assert.ok(matches.some(item => item.id === 'CarbamazepineB'));
});

test('formula matching preserves counts, components, charges, coefficients, parentheses and element order', () => {
    const input = [
        formulaEntry('Plain', ['C9 H8 O4']),
        formulaEntry('DifferentCount', ['C9 H8 O40']),
        formulaEntry('Hydrate', ['C9 H8 O4 . H2 O']),
        formulaEntry('Salt', ['C4 H7 N2 O2 S1+ . Cl- . H2 O']),
        formulaEntry('Coefficient', ['2(C7 H6 O4) - H2 O1']),
        formulaEntry('Reordered', ['H8 C9 O4']),
    ];
    const ids = query => tools.filter(input, query).map(item => item.id);
    assert.deepEqual(ids('C9H8O4'), ['Plain']);
    assert.deepEqual(ids('C9H8O40'), ['DifferentCount']);
    assert.deepEqual(ids('c9h8o4.h2o'), ['Hydrate']);
    assert.deepEqual(ids('C9H8O4H2O'), []);
    assert.deepEqual(ids('C4H7N2O2S1+.Cl-.H2O'), ['Salt']);
    assert.deepEqual(ids('C4H7N2O2S1.Cl.H2O'), []);
    assert.deepEqual(ids('2(C7H6O4)-H2O1'), ['Coefficient']);
    assert.deepEqual(ids('C7H6O4-2(H2O1)'), []);
    assert.deepEqual(ids('H8C9O4'), ['Reordered']);
    assert.deepEqual(ids('C9H8O'), []);
    assert.deepEqual(ids('C9H8O4.H2O1'), []);
});

test('formula matching does not alter tokenized name, REFCODE or dataset-code search', () => {
    const input = [formulaEntry('AlphaA', ['C9 H8 O4']), formulaEntry('AlphaB')];
    input[0].label = 'Alpha — Search A'; input[0].aliases = ['Résumé molecule']; input[0].codes = ['ABCDEF01'];
    for (const query of ['resume molecule', 'ABCDEF01', 'Alpha A', 'AlphaA']) {
        assert.ok(tools.filter(input, query).some(item => item.id === 'AlphaA'), query);
    }
    assert.equal(tools.filter(input, 'no such molecule').length, 0);
    assert.equal(tools.filter(input, '').length, 2);
});
