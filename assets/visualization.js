/* One scientific preset, source-preserving adaptation, and compatibility for
 * Chemiscope v1.1.0-1-g63c17cc. See README for the normalization policy. */
(function (root, factory) {
    const api = factory(typeof module === 'object' && module.exports ? require('./spacegroups.js') : root.CpossSpaceGroups);
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.CpossVisualization = api;
})(typeof globalThis === 'object' ? globalThis : this, function (groups) {
    'use strict';
    const GREY = '#aaaaaa';
    const PRESET = {
        target: 'structure',
        map: {
            x: { property: 'Density', scale: 'linear' },
            y: { property: 'Lattice Energy', scale: 'linear' },
            z: { property: '' },
            color: { property: 'Space Group Number', mode: 'log', min: 0, max: 2.37, palette: 'seismic' },
            size: { property: 'Experimental Info', mode: 'flip-linear', factor: 55 },
        },
        structure: [{ supercell: [3, 3, 3], unitCell: true }],
    };
    function freeze(value) { if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); } return value; }
    freeze(PRESET);
    function copy(value) {
        if (Array.isArray(value)) return value.map(copy);
        if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, copy(item)]));
        return value;
    }
    function merge(base, override) {
        const result = copy(base);
        for (const [key, value] of Object.entries(override || {})) {
            if (value && typeof value === 'object' && !Array.isArray(value) && result[key] && typeof result[key] === 'object' && !Array.isArray(result[key])) result[key] = merge(result[key], value);
            else result[key] = copy(value);
        }
        return result;
    }
    const missing = value => value == null || (typeof value === 'number' && !Number.isFinite(value))
        || (typeof value === 'string' && /^(?:|nan|n\/a|na|null|none|undefined|[?—–-])$/i.test(value.trim()));
    function numeric(value) {
        if (missing(value)) return NaN;
        if (typeof value === 'number') return value;
        if (typeof value === 'string' && /^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim())) {
            const number = Number(value); return Number.isFinite(number) ? number : NaN;
        }
        return NaN;
    }
    function symbolKey(value) {
        return String(value).normalize('NFKC').replace(/−/g, '-').replace(/([0-9])[\u0304\u0305]/g, '-$1').replace(/[\s_]/g, '').toLowerCase();
    }
    function spaceGroup(value) {
        const number = numeric(value);
        if (Number.isInteger(number) && number >= 1 && number <= 230) return { number, kind: 'number' };
        if (missing(value)) return { number: NaN, kind: 'missing' };
        const key = symbolKey(value);
        if (groups.ambiguous.includes(key)) return { number: NaN, kind: 'ambiguous' };
        if (Object.hasOwn(groups.symbols, key)) return { number: groups.symbols[key], kind: 'symbol' };
        return { number: NaN, kind: 'unresolved' };
    }
    function field(name, prefix) {
        const match = name.match(new RegExp('^' + prefix + '(?=$|[\\s\\d(\\[/])', 'i'));
        if (!match) return null;
        // Units follow '/', '[' or an explicitly recognized parenthesized unit.
        // Model labels such as '(PBE+TS) 2' are retained; a number in a unit is not a model.
        const rest = name.slice(match[0].length).split(/[\/\[]/)[0].replace(/\((?:g\s*cm.*|kg\s*m.*|k?j.*|kcal.*|ev.*)\)/ig, '').trim();
        const model = rest.match(/(?:^|\s)(\d+[a-z]?)(?=\s|$|\()/i)?.[1]?.toLowerCase() || '';
        const label = rest.replace(/(?:^|\s)\d+[a-z]?(?=\s|$|\()/ig, '').replace(/[()\s]/g, '').replace(/\+/g, '-').toLowerCase();
        return { name, model, label };
    }
    const modelOrder = model => model ? parseInt(model, 10) : -1;
    const compare = (a, b) => a < b ? -1 : a > b ? 1 : 0;
    function resolveAxes(properties, count) {
        const candidates = prefix => Object.entries(properties).flatMap(([name, property]) => {
            const info = field(name, prefix);
            if (!info || property.parameters || property.target !== 'structure' || !Array.isArray(property.values) || property.values.length !== count) return [];
            return [{ ...info, values: property.values.map(numeric) }];
        });
        const densities = candidates('Density'), energies = candidates('Lattice\\s+Energy');
        const pairs = [];
        for (const x of densities) for (const y of energies) {
            // Numbered models must match. For unnumbered labels require exact
            // identity; numbered labels may annotate only one of the two fields.
            if (x.model !== y.model || ((!x.model || (x.label && y.label)) && x.label !== y.label)) continue;
            const valid = x.values.reduce((n, value, i) => n + (Number.isFinite(value) && Number.isFinite(y.values[i]) ? 1 : 0), 0);
            pairs.push({ x, y, valid });
        }
        pairs.sort((a, b) => b.valid - a.valid || modelOrder(a.x.model) - modelOrder(b.x.model) || compare(a.x.model, b.x.model) || compare(a.x.name, b.x.name) || compare(a.y.name, b.y.name));
        return { chosen: pairs[0], candidates: pairs.map(pair => ({ x: pair.x.name, y: pair.y.name, model: pair.x.model, plotted: pair.valid })) };
    }
    function uniqueName(properties, wanted) {
        let name = wanted, i = 2;
        while (Object.hasOwn(properties, name)) name = `${wanted} ${i++}`;
        return name;
    }
    function prepare(source) {
        if (!groups?.symbols) throw new Error('The validated space-group lookup is unavailable.');
        const count = source.structures?.length || 0;
        const properties = { ...source.properties };
        const normalized = [];
        // Normalize scalar columns in the visualization copy only. Scientific
        // axes are numeric even when every row is missing. Unrelated text stays text.
        for (const [name, property] of Object.entries(properties)) {
            if (!Array.isArray(property.values) || property.parameters) continue;
            const values = property.values;
            const scientific = field(name, 'Density') || field(name, 'Lattice\\s+Energy');
            const numericColumn = values.some(value => Number.isFinite(numeric(value))) && values.every(value => missing(value) || Number.isFinite(numeric(value)));
            const labels = /^(?:file(?:name)?|name|label|id|code|refcode)(?=$|[\s_])/i.test(name);
            if (scientific || (!labels && numericColumn) || (values.some(value => typeof value === 'number') && values.every(value => typeof value === 'number' || missing(value)))) {
                const next = values.map(numeric);
                if (next.some((value, index) => !Object.is(value, values[index]))) normalized.push(name);
                properties[name] = { ...property, values: next };
            } else if (!values.every(value => typeof value === 'string')) {
                // Native validation disallows mixed scalar types, even on fields
                // not used in the plot. Keep their readable labels; export originals.
                properties[name] = { ...property, values: values.map(value => value == null ? '' : String(value)) };
                normalized.push(name);
            }
        }
        const axes = resolveAxes(properties, count);
        let x, y;
        if (axes.chosen) { x = axes.chosen.x.name; y = axes.chosen.y.name; }
        else {
            // An empty scientific plot is more honest than unrelated axes or a
            // cross-model pair. All structure rows remain in the selector.
            x = uniqueName(properties, 'Density (unavailable)');
            y = uniqueName(properties, 'Lattice Energy (unavailable)');
            properties[x] = { target: 'structure', values: Array(count).fill(NaN) };
            properties[y] = { target: 'structure', values: Array(count).fill(NaN) };
        }
        const sgSources = Object.entries(source.properties || {}).filter(([name, property]) => property.target === 'structure' && Array.isArray(property.values) && property.values.length === count && /^space[\s_-]*group(?:[\s_-]*(?:number|no\.?|symbol))?(?=$|[\s\d(/\[])/i.test(name));
        const sgStats = { sources: sgSources.map(([name]) => name), numeric: 0, symbols: 0, unknown: 0, conflicts: 0, unresolved: {}, numbers: {} };
        const sgValues = Array.from({ length: count }, (_, index) => {
            const found = sgSources.map(([name, property]) => ({ source: name, raw: property.values[index], ...spaceGroup(property.values[index]) }));
            const valid = found.filter(item => Number.isFinite(item.number));
            const distinct = new Set(valid.map(item => item.number));
            if (distinct.size === 1) {
                const number = valid[0].number;
                sgStats[valid.some(item => item.kind === 'number') ? 'numeric' : 'symbols']++;
                sgStats.numbers[number] = (sgStats.numbers[number] || 0) + 1;
                return number;
            }
            sgStats.unknown++;
            if (distinct.size > 1) sgStats.conflicts++;
            for (const item of found.filter(item => item.kind === 'unresolved' || item.kind === 'ambiguous' || distinct.size > 1)) {
                const key = `${item.source}: ${String(item.raw)}`;
                sgStats.unresolved[key] = (sgStats.unresolved[key] || 0) + 1;
            }
            return NaN;
        });
        // Keep the existing physical field's label when present; use a distinctly
        // named derived column if that label belongs to a different target/shape.
        const sgName = !properties['Space Group Number'] || (properties['Space Group Number'].target === 'structure' && !properties['Space Group Number'].parameters)
            ? 'Space Group Number' : uniqueName(properties, 'Space Group Number (display)');
        properties[sgName] = { target: 'structure', values: sgValues, description: 'International space-group number 1–230; validated supplied numbers or Gemmi Hermann–Mauguin symbols. Unresolved/conflicting values are NaN (grey). Original values are preserved in exported source data.' };
        const expSources = Object.entries(source.properties || {}).filter(([name, property]) => /^experimental[\s_-]*info(?:rmation)?(?=$|[\s(/\[])/i.test(name) && property.target === 'structure' && Array.isArray(property.values) && property.values.length === count && !property.parameters).sort(([a], [b]) => compare(a, b));
        const exp = expSources[0];
        const expValues = exp ? exp[1].values : Array(count).fill('');
        const numericInfo = expValues.some(value => Number.isFinite(numeric(value))) && expValues.every(value => missing(value) || Number.isFinite(numeric(value)));
        const expStats = { source: exp?.[0] || null, policy: numericInfo ? 'numeric' : 'annotation-presence', annotated: expValues.filter(value => !missing(value)).length, missing: expValues.filter(missing).length };
        const sizeName = numericInfo ? exp[0] : uniqueName(properties, 'Experimental Info (size)');
        properties[sizeName] = { target: 'structure', values: numericInfo ? expValues.map(numeric) : expValues.map(value => missing(value) ? 1 : 0), description: numericInfo ? 'Supplied numerical Experimental Info, scaled by native flip-linear; missing sizes use the native minimum.' : 'Display-only annotation score: supplied nonblank description = 0; blank/missing = 1. Native flip-linear makes annotated structures larger. A constant column uses the native uniform reference size. Original descriptions are retained.' };
        const settings = copy(PRESET);
        settings.map.x.property = x; settings.map.y.property = y;
        settings.map.color.property = sgName; settings.map.size.property = sizeName;
        const plotted = axes.chosen?.valid || 0;
        const diagnostics = { structures: count, axes: { x, y, model: axes.chosen?.x.model ?? null, plotted, missing: count - plotted, candidates: axes.candidates }, spaceGroups: sgStats, experimentalInfo: { ...expStats, field: sizeName }, normalized, ignoredInitialSettings: !!source.settings };
        // Bootstrap without embedded style or native colour/category heuristics.
        // A finite row-index helper is used only during construction if all axes
        // are missing; it is never the final plot and is excluded from exports.
        const bootstrap = copy(settings);
        bootstrap.map.color = { property: '', mode: 'linear', min: 0, max: 2.37, palette: 'seismic' };
        bootstrap.map.size = { property: '', mode: 'linear', factor: 55 };
        if (!properties[x].values.some(Number.isFinite) || !properties[y].values.some(Number.isFinite)) {
            const helper = uniqueName(properties, 'Structure index (initialization only)');
            properties[helper] = { target: 'structure', values: Array.from({ length: count }, (_, index) => index) };
            bootstrap.map.x.property = helper; bootstrap.map.y.property = helper;
        }
        return { dataset: { ...source, properties, settings: bootstrap }, source, settings, diagnostics };
    }
    function describe(prepared, settings = prepared.settings) {
        const d = prepared.diagnostics, notes = [];
        if (d.axes.model != null) notes.push(`Default axes use matching model ${d.axes.model || '(unnumbered)'} fields: ${d.axes.x}; ${d.axes.y}.`);
        else notes.push('No matching Density/Lattice Energy pair is supplied. The scientific plot is empty; structures remain selectable.');
        if (d.spaceGroups.unknown) notes.push(`${d.spaceGroups.unknown} of ${d.structures} space groups are unknown and grey${d.spaceGroups.conflicts ? ` (${d.spaceGroups.conflicts} conflicting supplied values)` : ''}.`);
        if (d.spaceGroups.symbols) notes.push(`${d.spaceGroups.symbols} Hermann–Mauguin symbols were resolved with ${groups.generator}; colour is log10 of the international number, never a category index.`);
        const e = d.experimentalInfo;
        notes.push(e.policy === 'numeric' ? 'Experimental Info uses supplied numeric values with native flip-linear sizing.' : 'Experimental Info size score: annotated = 0, blank/missing = 1. Native flip-linear makes annotated structures larger; a constant score uses uniform reference sizes. Original descriptions are retained.');
        const count = d.structures, bad = new Set(), affected = [];
        for (const axis of ['x', 'y', 'z']) {
            const option = settings.map?.[axis];
            if (!option?.property) continue;
            const values = prepared.dataset.properties[option.property]?.values;
            if (!values || !values.every(value => typeof value === 'number')) continue;
            let n = 0;
            values.forEach((value, index) => { if (!Number.isFinite(value) || (option.scale === 'log' && value <= 0)) { n++; bad.add(index); } });
            if (n) affected.push(`${option.property} (${n})`);
        }
        if (bad.size) notes.push(`${bad.size} of ${count} structures cannot be plotted on the selected axes: ${affected.join(', ')}. All ${count} remain available in the structure selector.`);
        if (d.normalized.length) notes.push('Numeric strings/missing markers were normalized only in the visualization copy. Exports retain the original properties and row order.');
        if (d.ignoredInitialSettings) notes.push('Embedded visualization settings were superseded by the global preset. Import settings after loading to apply a deliberate override.');
        return notes;
    }
    // A small instance-level shim, scoped to the derived scientific columns.
    // No bundle edits. Retain Chemiscope's native modes, palette and rendering.
    function patchNativeMap(map, prepared) {
        const options = map?._options;
        if (!options || typeof options.calculateColors !== 'function' || typeof map._getNumericColors !== 'function' || typeof options.calculateSizes !== 'function' || typeof options.valueToColor !== 'function' || typeof map._computeLOD !== 'function') throw new Error('Unsupported Chemiscope map API: the global colour compatibility layer could not be installed.');
        const sg = prepared.settings.map.color.property, size = prepared.settings.map.size.property;
        const nativeColors = options.calculateColors.bind(options);
        options.calculateColors = function (values) {
            if (this.color.property.value !== sg) return nativeColors(values);
            const mode = this.color.mode.value;
            return values.map(value => {
                if (!Number.isFinite(value)) return GREY;
                const transformed = mode === 'log' ? Math.log10(value) : mode === 'inverse' ? 1 / value : mode === 'sqrt' ? Math.sqrt(value) : mode === 'linear' ? value : 0.5;
                return Number.isFinite(transformed) ? transformed : GREY;
            });
        };
        const nativeNumeric = map._getNumericColors.bind(map);
        map._getNumericColors = function () {
            const values = nativeNumeric();
            // Native all-unknown validation needs a finite extent. These are
            // range bounds ONLY, never additional data rows or fake SG numbers.
            return options.color.property.value === sg && !values.some(Number.isFinite) ? [PRESET.map.color.min, PRESET.map.color.max] : values;
        };
        const nativeSizes = options.calculateSizes.bind(options);
        options.calculateSizes = function (values) {
            if (this.size.property.value === size && !values.some(Number.isFinite)) {
                // Native min/max asserts on an all-missing numeric size column.
                // A constant scale gives the reference uniform size, not zero data.
                return nativeSizes(values.map(() => 1));
            }
            return nativeSizes(values);
        };
        const nativeLOD = map._computeLOD.bind(map);
        map._computeLOD = function (...args) {
            if (['x', 'y'].some(axis => !this._property(options[axis].property.value).values.some(Number.isFinite))) { this._lodIndices = null; return; }
            return nativeLOD(...args);
        };
        // Native selection filtering colourizes NaN as a palette midpoint.
        // Protect unknowns when a user filters within the map settings too.
        const nativeValueToColor = options.valueToColor.bind(options);
        options.valueToColor = function (value, min, max) { return this.color.property.value === sg && !Number.isFinite(value) ? GREY : nativeValueToColor(value, min, max); };
    }
    function applySettings(visualizer, settings, nativeApply) {
        const patch = copy(settings), requested = patch.map?.color, bounds = {};
        if (requested) {
            // Set the property before transforming it: native handlers otherwise
            // attempt log10 on the old negative energy and silently reset mode.
            if (Object.hasOwn(requested, 'property')) nativeApply({ map: { color: { property: requested.property } } });
            for (const key of ['min', 'max']) if (Object.hasOwn(requested, key)) { bounds[key] = requested[key]; delete requested[key]; }
        }
        nativeApply(patch);
        const current = visualizer.saveSettings().map?.color || {};
        const order = Object.hasOwn(bounds, 'max') && bounds.min > current.max ? ['max', 'min'] : ['min', 'max'];
        for (const key of order) if (Object.hasOwn(bounds, key)) nativeApply({ map: { color: { [key]: bounds[key] } } });
    }
    function install(app, report = () => {}) {
        const originalLoad = app.load.bind(app);
        app.load = async function (config, source) {
            const prepared = prepare(source);
            const result = await originalLoad(config, prepared.dataset);
            const visualizer = app.visualizer;
            patchNativeMap(visualizer.map, prepared);
            const nativeDataset = visualizer.dataset.bind(visualizer);
            visualizer.dataset = (...args) => {
                const exported = nativeDataset(...args);
                exported.properties = copy(source.properties || {});
                if (Object.hasOwn(source, 'settings')) exported.settings = copy(source.settings);
                else delete exported.settings;
                return exported;
            };
            const nativeApply = visualizer.applySettings.bind(visualizer);
            visualizer.applySettings = settings => applySettings(visualizer, settings, nativeApply);
            visualizer.applySettings(prepared.settings);
            // A failed global preset is an error, never an unannounced energy-
            // coloured fallback. Audit and notes can inspect the applied plan.
            visualizer.cposs = { diagnostics: prepared.diagnostics, preset: copy(prepared.settings) };
            const refresh = () => { if (app.visualizer === visualizer) report(describe(prepared, visualizer.saveSettings())); };
            refresh();
            let pending = false;
            visualizer.onSettingChange?.(() => {
                if (pending) return;
                pending = true;
                queueMicrotask(() => { pending = false; refresh(); });
            });
            return result;
        };
    }
    // Parse the public files' nonstandard bare NaN without changing quoted text
    // such as molecule names, annotations, or a literal string "NaN".
    function parseJSON(text) {
        let out = '', quoted = false, escaped = false;
        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            if (quoted) { out += char; if (escaped) escaped = false; else if (char === '\\') escaped = true; else if (char === '"') quoted = false; continue; }
            if (char === '"') { quoted = true; out += char; continue; }
            if (text.slice(i, i + 3) === 'NaN' && /[\s\[:,]/.test(text[i - 1] || '[') && /[\s,\]}]/.test(text[i + 3] || ']')) { out += '1e999'; i += 2; }
            else out += char;
        }
        return JSON.parse(out, (_, value) => value === Infinity ? NaN : value);
    }
    function buildSettings(source) { const prepared = prepare(source); return { settings: prepared.settings, diagnostics: prepared.diagnostics }; }
    return { PRESET, GREY, copy, merge, missing, numeric, symbolKey, spaceGroup, prepare, resolveAxes, buildSettings, describe, patchNativeMap, applySettings, install, parseJSON };
});
