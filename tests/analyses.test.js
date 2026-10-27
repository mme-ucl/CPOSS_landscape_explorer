const { test } = require('node:test');
const assert = require('node:assert/strict');
const tools = require('../assets/analyses.js');

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
