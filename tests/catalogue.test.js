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
