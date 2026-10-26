const { test } = require('node:test');
const assert = require('node:assert/strict');
const tools = require('../assets/analyses.js');

test('inventory searches combine words across molecule, formula, alias and scientist fields', () => {
    const search = 'AspirinA Aspirin — Search A C9H8O4 ACSALA Louise S. Price';
    assert.equal(tools.matches(search, 'PRICE aspirin'), true);
    assert.equal(tools.matches(search, 'c9h8o4 acsala'), true);
    assert.equal(tools.matches(search, 'Aspirin missing'), false);
    assert.equal(tools.matches('Résumé molecule', 'resume'), true);
    assert.equal(tools.matches(search, '  '), true);
});

test('inventory sorting is numeric with deterministic molecule-name ties', () => {
    const rows = [{ name: 'B', files: 100, models: 2 }, { name: 'A', files: 100, models: 1 }, { name: 'C', files: 9, models: 3 }];
    const sort = order => rows.slice().sort((a, b) => tools.compare(a, b, order)).map(r => r.name);
    assert.deepEqual(sort('files-desc'), ['A', 'B', 'C']);
    assert.deepEqual(sort('files-asc'), ['C', 'A', 'B']);
    assert.deepEqual(sort('models-desc'), ['C', 'B', 'A']);
    assert.deepEqual(sort('name-asc'), ['A', 'B', 'C']);
});

test('return navigation preserves the selected landscape on project Pages subpaths', () => {
    const base = 'https://example.org/CPOSS_landscape_explorer/analyses.html';
    const load = 'https://louiseprice.github.io/CPOSS_Database/0.Chemiscope/AspirinA.json';
    const result = new URL(tools.returnHref(base + '?load=' + encodeURIComponent(load) + '#density-comparison'));
    assert.equal(result.pathname, '/CPOSS_landscape_explorer/');
    assert.equal(result.searchParams.get('load'), load);
    assert.equal(result.hash, '');
    assert.equal(new URL(tools.returnHref(base + '?load=javascript:alert(1)')).search, '');
    assert.equal(tools.returnHref(base), 'https://example.org/CPOSS_landscape_explorer/');
});
