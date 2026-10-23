const { test } = require('node:test');
const assert = require('node:assert/strict');
const defaults = require('../assets/visualization.js');
const numeric = require('./fixtures/plot-numeric.json');
const missing = require('./fixtures/plot-missing.json');
const unsuitable = require('./fixtures/plot-unsuitable.json');
const saved = require('./fixtures/plot-saved.json');
const aspirin = require('../AspirinA.json');

function fakeApp({ failPalette = false, failLoad = false } = {}) {
    const app = {
        async load(config, data) {
            if (failLoad) throw new Error('Dataset failed to load');
            let state = defaults.merge({ target: 'structure', map: { x: { property: 'Density' }, y: { property: 'Energy' }, color: { property: 'Energy', mode: 'linear', min: -40, max: -10, palette: 'inferno' }, size: { property: '', mode: 'linear', factor: 43 } }, structure: [{ supercell: [1, 1, 1], unitCell: false }] }, data.settings);
            const listeners = [];
            const calls = [];
            this.visualizer = {
                calls,
                saveSettings: () => defaults.copy(state),
                dataset: () => defaults.copy(data),
                onSettingChange: callback => listeners.push(callback),
                applySettings(settings) {
                    calls.push(defaults.copy(settings));
                    if (failPalette && settings.map?.color?.palette === 'seismic') throw new Error('Unsupported palette');
                    const patch = defaults.copy(settings);
                    const color = patch.map?.color;
                    if (color) {
                        const propertyValues = name => {
                            const values = data.properties[name]?.values || [1];
                            return typeof values[0] === 'string' ? values.map(x => [...new Set(values)].indexOf(x)) : values;
                        };
                        const resetRange = () => {
                            const values = propertyValues(state.map.color.property).map(x => state.map.color.mode === 'log' ? Math.log10(x) : x);
                            state.map.color.min = Math.min(...values);
                            state.map.color.max = Math.max(...values);
                        };
                        // Model the relevant native handler ordering, including mode
                        // rejection on negative old data and crossing-range guards.
                        for (const key of ['mode', 'property', 'min', 'max', 'palette']) {
                            if (!Object.hasOwn(color, key)) continue;
                            const value = color[key];
                            if (key === 'mode') {
                                if (value === 'log' && propertyValues(state.map.color.property).every(x => x < 0)) continue;
                                state.map.color.mode = value;
                                resetRange();
                            } else if (key === 'property') {
                                state.map.color.property = value;
                                resetRange();
                            } else if (key === 'min') {
                                if (!(value > state.map.color.max)) state.map.color.min = value;
                            } else if (key === 'max') {
                                if (!(value < state.map.color.min)) state.map.color.max = value;
                            } else state.map.color[key] = value;
                        }
                        delete patch.map.color;
                    }
                    state = defaults.merge(state, patch);
                    for (const callback of listeners) callback(['map'], null);
                },
            };
            // The real bundle removes this field from its input during loading.
            if (data.settings) delete data.settings.map;
        },
        fetchAndLoad(data) { return this.load({}, data); },
        loadStreaming(data) { return this.load({ loadStructure: () => {} }, data); },
    };
    return app;
}

test('default patch selects native log/seismic and flip-linear without changing axes or size factor', () => {
    const before = defaults.copy(numeric);
    const plan = defaults.buildSettings(numeric);
    assert.deepEqual(plan.settings.map, {
        color: { property: 'Space Group', mode: 'log', min: 0, max: 2.37, palette: 'seismic' },
        size: { property: 'Experimental Info', mode: 'flip-linear' },
    });
    assert.deepEqual(plan.settings.structure[0].supercell, [3, 3, 3]);
    assert.deepEqual(plan.warnings, []);
    assert.deepEqual(numeric, before);
});

test('all dataset-loading entry points apply defaults after successful loading', async () => {
    for (const method of ['load', 'fetchAndLoad', 'loadStreaming']) {
        const app = fakeApp();
        defaults.install(app);
        if (method === 'load') await app.load({}, defaults.copy(numeric));
        else await app[method](defaults.copy(numeric));
        const actual = app.visualizer.saveSettings();
        assert.equal(actual.map.color.mode, 'log', method);
        assert.equal(actual.map.color.min, 0);
        assert.equal(actual.map.color.max, 2.37);
        assert.equal(actual.map.size.mode, 'flip-linear');
        assert.equal(actual.map.size.factor, 43);
        assert.equal(actual.map.x.property, 'Density');
        assert.deepEqual(actual.structure[0].supercell, [3, 3, 3]);
    }
});

test('saved settings win and survive the native loader deleting settings.map', async () => {
    const data = defaults.copy(saved);
    const before = defaults.copy(data);
    const app = fakeApp();
    defaults.install(app);
    await app.load({}, data);
    const actual = app.visualizer.saveSettings();
    assert.deepEqual(actual.map.color, saved.settings.map.color);
    assert.deepEqual(actual.map.size, saved.settings.map.size);
    assert.equal(actual.map.x.property, 'Energy');
    assert.deepEqual(actual.structure[0].supercell, [2, 1, 1]);
    assert.deepEqual(data, before);
});

test('partial explicit settings preserve their size factor and the other defaults', () => {
    const plan = defaults.buildSettings(numeric, { map: { size: { factor: 72 } }, structure: [{ atoms: false }] });
    assert.equal(plan.settings.map.size.factor, 72);
    assert.equal(plan.settings.map.size.mode, 'flip-linear');
    assert.deepEqual(plan.settings.structure[0].supercell, [3, 3, 3]);
    assert.equal(plan.settings.structure[0].atoms, false);
    assert.deepEqual(defaults.buildSettings(numeric, { structure: [] }).settings.structure[0].supercell, [3, 3, 3]);
});

test('missing and unsuitable properties retain usable native controls with clear warnings', async () => {
    const messages = [];
    const app = fakeApp();
    defaults.install(app, value => messages.push(value));
    await app.load({}, missing);
    assert.equal(app.visualizer.saveSettings().map.color.property, 'Energy');
    assert.equal(app.visualizer.saveSettings().map.size.property, '');
    assert.equal(messages.at(-1).length, 2);
    const plan = defaults.buildSettings(unsuitable);
    assert.equal(plan.settings.map.color, undefined);
    assert.equal(plan.settings.map.size.mode, 'flip-linear');
    assert.match(plan.warnings[0], /non-positive/);
    assert.match(defaults.describe(unsuitable, plan.settings).join(' '), /uniform point size/);
});

test('categorical properties keep their original values and explain native category indices', () => {
    const data = defaults.copy(aspirin);
    const before = defaults.copy(data);
    const plan = defaults.buildSettings(data);
    assert.equal(plan.settings.map.color.mode, 'log');
    assert.equal(plan.settings.map.size.mode, 'flip-linear');
    const description = defaults.describe(data, plan.settings).join(' ');
    assert.match(description, /not physical space-group numbers/);
    assert.match(description, /log10\(0\)/);
    assert.match(description, /not numeric measurements/);
    assert.deepEqual(data, before);
    const tooMany = defaults.copy(numeric);
    tooMany.properties['Space Group'].values = Array.from({ length: 22 }, (_, i) => 'category-' + i);
    assert.equal(defaults.buildSettings(tooMany).settings.map.color, undefined);
});

test('current numeric Space Group Number field is an explicit fallback without modifying properties', () => {
    const data = defaults.copy(numeric);
    data.properties['Space Group Number'] = data.properties['Space Group'];
    delete data.properties['Space Group'];
    const before = defaults.copy(data);
    const plan = defaults.buildSettings(data);
    assert.equal(plan.settings.map.color.property, 'Space Group Number');
    assert.equal(plan.settings.map.color.mode, 'log');
    assert.match(defaults.describe(data, plan.settings).join(' '), /No space-group numbers are inferred/);
    assert.deepEqual(data, before);
    data.properties['Space Group'] = { target: 'structure', values: ['P1', 'P2', 'P3', 'P4'] };
    assert.equal(defaults.buildSettings(data).settings.map.color.property, 'Space Group');
});

test('numeric missing markers load as NaN without changing the source, row indices, or saved export', async () => {
    const data = defaults.copy(numeric);
    data.properties['Space Group Number'] = { target: 'structure', values: [1, 'nan', 100, 230] };
    delete data.properties['Space Group'];
    data.properties.Density.values[1] = NaN;
    const before = defaults.copy(data);
    const prepared = defaults.prepare(data);
    assert.ok(Number.isNaN(prepared.dataset.properties['Space Group Number'].values[1]));
    assert.equal(prepared.dataset.structures, data.structures);
    assert.deepEqual(data, before);
    const app = fakeApp();
    const reports = [];
    defaults.install(app, report => reports.push(report));
    await app.load({}, data);
    assert.equal(app.visualizer.saveSettings().map.color.property, 'Space Group Number');
    assert.equal(app.visualizer.saveSettings().map.color.mode, 'log');
    assert.equal(app.visualizer.saveSettings().map.color.max, 2.37);
    assert.match(reports.at(-1).join(' '), /1 of 4 structures cannot be plotted/);
    assert.match(reports.at(-1).join(' '), /1 missing space-group value appears grey/);
    assert.deepEqual(app.visualizer.dataset().properties, before.properties);
    assert.deepEqual(data, before);
    app.visualizer.applySettings({ map: { x: { property: 'Experimental Info' } } });
    await Promise.resolve();
    assert.doesNotMatch(reports.at(-1).join(' '), /cannot be plotted/);
});

test('missing-marker handling leaves text categories and unrecognized mixed strings untouched', () => {
    const data = defaults.copy(numeric);
    data.properties['Space Group'].values = [1, 'P21/c', 100, 230];
    data.properties['Experimental Info'].values = ['nan', 'known', '', 'nan'];
    const prepared = defaults.prepare(data);
    assert.equal(prepared.dataset.properties['Space Group'], data.properties['Space Group']);
    assert.equal(prepared.dataset.properties['Experimental Info'], data.properties['Experimental Info']);
    assert.equal(prepared.warnings.length, 0);
    data.properties['Experimental Info'].values = [0, NaN, 2, 3];
    assert.equal(defaults.buildSettings(data).settings.map.size, undefined);
    data.properties['Space Group'].values = [NaN, NaN, NaN, NaN];
    assert.equal(defaults.buildSettings(data).settings.map.color, undefined);
});

test('later explicit settings and user changes are reported without reapplying defaults', async () => {
    const app = fakeApp();
    defaults.install(app);
    await app.load({}, defaults.copy(numeric));
    app.visualizer.applySettings(saved.settings);
    const calls = app.visualizer.calls.length;
    await Promise.resolve();
    assert.equal(app.visualizer.calls.length, calls);
    assert.equal(app.visualizer.saveSettings().map.color.palette, 'viridis');
    assert.equal(app.visualizer.saveSettings().map.size.factor, 65);
});

test('valid explicit colour bounds above the data range are not reset by native range guards', async () => {
    const app = fakeApp();
    defaults.install(app);
    const data = { ...defaults.copy(numeric), settings: { map: { color: { min: 100, max: 200 } } } };
    await app.load({}, data);
    assert.equal(app.visualizer.saveSettings().map.color.min, 100);
    assert.equal(app.visualizer.saveSettings().map.color.max, 200);
    app.visualizer.applySettings({ map: { color: { min: 300, max: 400 } } });
    assert.equal(app.visualizer.saveSettings().map.color.min, 300);
    assert.equal(app.visualizer.saveSettings().map.color.max, 400);
    app.visualizer.applySettings({ map: { color: { min: 0, max: 2.37 } } });
    assert.equal(app.visualizer.saveSettings().map.color.min, 0);
    assert.equal(app.visualizer.saveSettings().map.color.max, 2.37);
});

test('a failed default application restores the loaded visualization; failed loads do not apply defaults', async () => {
    const reports = [];
    const app = fakeApp({ failPalette: true });
    defaults.install(app, report => reports.push(report));
    await app.load({}, defaults.copy(numeric));
    assert.equal(app.visualizer.saveSettings().map.color.property, 'Energy');
    assert.equal(app.visualizer.saveSettings().map.color.mode, 'linear');
    assert.match(reports.at(-1).join(' '), /loaded visualization was retained/);
    const failed = fakeApp({ failLoad: true });
    defaults.install(failed);
    await assert.rejects(failed.load({}, numeric), /Dataset failed to load/);
    assert.equal(failed.visualizer, undefined);
});
