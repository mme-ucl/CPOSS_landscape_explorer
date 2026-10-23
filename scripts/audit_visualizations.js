#!/usr/bin/env node
/* Run after audit_visualizations.py. No dependencies beyond Node 18+. */
const fs = require('node:fs');
const path = require('node:path');
const v = require('../assets/visualization.js');
const root = path.resolve(__dirname, '..');
const input = path.resolve(process.argv[2] || path.join(root, 'tests/.audit-data'));
const manifest = JSON.parse(fs.readFileSync(path.join(input, 'manifest.json')));
const datasets = manifest.datasets.map(entry => {
    if (entry.error) return entry;
    try {
        const source = v.parseJSON(fs.readFileSync(path.join(input, entry.file), 'utf8'));
        const prepared = v.prepare(source);
        const errors = [];
        if (prepared.dataset.structures !== source.structures) errors.push('Structure array changed');
        for (const [name, property] of Object.entries(prepared.dataset.properties)) {
            if (property.target === 'structure' && property.values.length !== entry.structures) errors.push('Row count: ' + name);
            if (!property.parameters && !property.values.every(value => typeof value === typeof property.values[0])) errors.push('Mixed types: ' + name);
        }
        const sg = prepared.dataset.properties[prepared.settings.map.color.property].values;
        if (!sg.every(number => Number.isNaN(number) || (Number.isInteger(number) && number >= 1 && number <= 230))) errors.push('Invalid normalized SG');
        return { ...entry, ...prepared.diagnostics, preset: prepared.settings, adaptationErrors: errors };
    } catch (error) { return { ...entry, error: error.message }; }
});
const report = {
    sourceTree: manifest.sourceTree,
    preset: v.PRESET,
    mapping: { generator: require('../assets/spacegroups').generator, source: require('../assets/spacegroups').source },
    scope: 'Every original property row adapted; SHA-verified sources; every geometry row checked in Python. Native rendering is recorded separately by tests/native-audit.html.',
    summary: {
        catalogueDatasets: datasets.length,
        structures: datasets.reduce((n, d) => n + (d.structures || 0), 0),
        adaptationFailures: datasets.filter(d => d.error || d.adaptationErrors?.length).length,
        geometryFailures: datasets.filter(d => d.geometryFailures?.length).length,
        datasetsWithMissingAxes: datasets.filter(d => d.axes && !d.axes.plotted).map(d => d.id),
        datasetsWithUnknownSpaceGroups: datasets.filter(d => d.spaceGroups?.unknown).length,
        unknownSpaceGroups: datasets.reduce((n, d) => n + (d.spaceGroups?.unknown || 0), 0),
        datasetsWithoutSpaceGroupField: datasets.filter(d => d.spaceGroups && !d.spaceGroups.sources.length).map(d => d.id),
    },
    datasets,
};
fs.mkdirSync(path.join(root, 'reports'), { recursive: true });
fs.writeFileSync(path.join(root, 'reports/visualization-audit.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report.summary, null, 2));
process.exitCode = report.summary.adaptationFailures || report.summary.geometryFailures ? 1 : 0;
