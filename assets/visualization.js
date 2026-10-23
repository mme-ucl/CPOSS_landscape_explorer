/* Load defaults and missing-value compatibility for the bundled Chemiscope. */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.CpossVisualization = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
    'use strict';
    const color = { property: 'Space Group', mode: 'log', min: 0, max: 2.37, palette: 'seismic' };
    const size = { property: 'Experimental Info', mode: 'flip-linear' };
    const structure = { supercell: [3, 3, 3], unitCell: true };

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

    function prepare(dataset) {
        const properties = { ...dataset.properties };
        const warnings = [];
        const originals = {};
        for (const [name, property] of Object.entries(properties)) {
            const values = property.values;
            // Only recognize missing markers in an otherwise numeric column.
            // Text-only categories and unrecognized mixed values stay untouched.
            const missing = value => value === null || (typeof value === 'string' && /^nan$/i.test(value.trim()));
            if (!Array.isArray(values) || !values.some(value => typeof value === 'number') || !values.some(missing)
                || !values.every(value => typeof value === 'number' || missing(value))) continue;
            const count = values.filter(missing).length;
            originals[name] = property;
            properties[name] = { ...property, values: values.map(value => missing(value) ? NaN : value) };
            warnings.push(`${name}: ${count} missing marker${count === 1 ? '' : 's'} treated as NaN for display; saved datasets preserve source values.`);
        }
        return { dataset: { ...dataset, properties }, originals, warnings };
    }

    function inspect(dataset, name, target = 'structure') {
        const property = dataset.properties?.[name];
        if (!property) return { usable: false, reason: 'is missing' };
        if (target === 'structure' && property.target !== 'structure') return { usable: false, reason: 'is not a structure property' };
        const values = property.values;
        if (!Array.isArray(values) || !values.length) return { usable: false, reason: 'has no values' };
        const type = typeof values[0];
        if (!['number', 'string'].includes(type) || !values.every(value => typeof value === type)) return { usable: false, reason: 'has unsupported or mixed values' };
        const finite = type === 'number' ? values.filter(Number.isFinite) : values;
        if (type === 'number' && (!finite.length || values.some(value => !Number.isFinite(value) && !Number.isNaN(value)))) return { usable: false, reason: 'has no usable finite range' };
        const distinct = new Set(finite).size;
        // This bundle's string interner accepts category indices 0 through 20.
        if (type === 'string' && distinct > 21) return { usable: false, reason: 'has too many categories for this Chemiscope version' };
        let minimum = Infinity;
        let maximum = -Infinity;
        if (type === 'number') {
            for (const value of finite) { minimum = Math.min(minimum, value); maximum = Math.max(maximum, value); }
            if (!Number.isFinite(maximum - minimum)) return { usable: false, reason: 'has a non-finite numeric range' };
        }
        return { usable: true, type, missing: values.length - finite.length, constant: distinct === 1, minimum, maximum };
    }

    function buildSettings(dataset, explicit = {}) {
        const defaults = { map: {}, structure: [copy(structure)] };
        const warnings = [];
        const target = explicit.target || (dataset.environments && Object.values(dataset.properties || {}).some(property => property.target === 'atom') ? 'atom' : 'structure');
        // Current public datasets use this numeric field; older files retain
        // the exact requested "Space Group" property. Never synthesize either.
        const sourceColor = !dataset.properties?.[color.property] && typeof dataset.properties?.['Space Group Number']?.values?.[0] === 'number'
            ? { ...color, property: 'Space Group Number' } : color;
        for (const [group, desired] of [['color', sourceColor], ['size', size]]) {
            const specified = explicit.map?.[group];
            // An explicitly selected other property does not need this default.
            if (specified && Object.hasOwn(specified, 'property') && specified.property !== desired.property) continue;
            const info = inspect(dataset, desired.property, target);
            const logarithmic = group === 'color' && (!specified?.mode || specified.mode === 'log');
            if (!info.usable || (group === 'size' && info.missing) || (logarithmic && info.type === 'number' && info.minimum <= 0)) {
                const reason = !info.usable ? info.reason : info.missing && group === 'size' ? 'has missing sizes that this Chemiscope version cannot scale' : 'contains non-positive values, so log10 is undefined';
                warnings.push(`${desired.property} ${reason}; its plot default was skipped.`);
                continue;
            }
            defaults.map[group] = copy(desired);
        }
        const settings = merge(defaults, explicit);
        if (Array.isArray(explicit.structure)) settings.structure = explicit.structure.length ? explicit.structure.map(item => merge(structure, item)) : [copy(structure)];
        return { settings, warnings };
    }

    function describe(dataset, settings) {
        const messages = [];
        const target = settings.target || 'structure';
        const currentColor = settings.map?.color;
        const currentSize = settings.map?.size;
        if ([color.property, 'Space Group Number'].includes(currentColor?.property)) {
            const info = inspect(dataset, currentColor.property, target);
            if (currentColor.property === 'Space Group Number' && !dataset.properties?.[color.property]) messages.push('Colour uses the supplied Space Group Number field. No space-group numbers are inferred.');
            if (info.usable && info.missing && !info.constant) messages.push(`${info.missing} missing space-group value${info.missing === 1 ? ' appears' : 's appear'} grey.`);
            if (info.usable && info.type === 'string') messages.push(`Space Group colours use Chemiscope's category indices, not physical space-group numbers.${currentColor.mode === 'log' && !info.constant ? ' log10(0) for the first category is undefined; native handling is retained.' : ''}`);
            if (info.usable && info.constant) messages.push('Space Group is constant; Chemiscope uses a uniform colour.');
        }
        if (currentSize?.property === size.property) {
            const info = inspect(dataset, size.property, target);
            if (info.usable && info.type === 'string') messages.push('Experimental Info sizes use category indices, not numeric measurements.');
            if (info.usable && info.constant) messages.push('Experimental Info is constant; Chemiscope uses a uniform point size.');
        }
        const axes = ['x', 'y', 'z'].map(axis => settings.map?.[axis]).filter(axis => axis?.property);
        const count = target === 'structure' ? dataset.structures?.length : dataset.environments?.length;
        if (count && axes.length) {
            const missing = new Set();
            const affected = [];
            for (const axis of axes) {
                const values = dataset.properties?.[axis.property]?.values;
                if (!values || !values.some(value => typeof value === 'number')) continue;
                let bad = 0;
                values.forEach((value, index) => {
                    if (!Number.isFinite(value) || (axis.scale === 'log' && value <= 0)) { missing.add(index); bad++; }
                });
                if (bad) affected.push(`${axis.property} (${bad})`);
            }
            if (missing.size) messages.push(`${missing.size} of ${count} ${target === 'structure' ? 'structures' : 'environments'} cannot be plotted on the selected axes: ${affected.join(', ')}. All ${count} remain available in the structure selector; choose axes with complete values to plot them.`);
        }
        return messages;
    }

    function applySettings(visualizer, settings, nativeApply) {
        const patch = copy(settings);
        const requested = patch.map?.color;
        const bounds = {};
        if (requested) {
            // Native post-load handlers otherwise transform the old property first
            // (often a negative lattice energy), then reset log mode to linear.
            if (Object.hasOwn(requested, 'property')) nativeApply({ map: { color: { property: requested.property } } });
            for (const key of ['min', 'max']) {
                if (Object.hasOwn(requested, key)) {
                    bounds[key] = requested[key];
                    delete requested[key];
                }
            }
        }
        nativeApply(patch);
        const current = visualizer.saveSettings().map?.color || {};
        // The native range controls reject min > current max. Move max first
        // when necessary, so valid explicit limits are never silently reset.
        const order = Object.hasOwn(bounds, 'max') && bounds.min > current.max ? ['max', 'min'] : ['min', 'max'];
        for (const key of order) {
            if (Object.hasOwn(bounds, key)) nativeApply({ map: { color: { [key]: bounds[key] } } });
        }
    }

    function install(app, report = () => {}) {
        const originalLoad = app.load.bind(app);
        app.load = async function (config, dataset) {
            // Chemiscope removes settings.map during initialization. Protect the
            // caller's settings and preserve them for the post-load override.
            const explicit = copy(dataset.settings || {});
            const prepared = prepare(dataset);
            const input = { ...prepared.dataset, ...(dataset.settings ? { settings: copy(explicit) } : {}) };
            const result = await originalLoad(config, input);
            const visualizer = app.visualizer;
            const baseline = copy(visualizer.saveSettings());
            const plan = buildSettings(prepared.dataset, explicit);
            plan.warnings.unshift(...prepared.warnings);
            // Save the source properties, rather than the compatibility copy.
            // Delegate structure materialization/settings to the native exporter.
            if (visualizer.dataset && Object.keys(prepared.originals).length) {
                const nativeDataset = visualizer.dataset.bind(visualizer);
                visualizer.dataset = (...args) => {
                    const exported = nativeDataset(...args);
                    for (const [name, property] of Object.entries(prepared.originals)) exported.properties[name] = copy(property);
                    return exported;
                };
            }
            const nativeApply = visualizer.applySettings.bind(visualizer);
            // Settings files and ?settings= use this same public method later.
            // Order their explicit values safely too, without reapplying defaults.
            visualizer.applySettings = settings => applySettings(visualizer, settings, nativeApply);
            try {
                visualizer.applySettings(plan.settings);
            } catch (error) {
                visualizer.applySettings(baseline);
                plan.warnings.push(`Plot defaults could not be applied; the loaded visualization was retained (${error.message}).`);
            }
            const refresh = () => {
                if (app.visualizer === visualizer) report([...plan.warnings, ...describe(prepared.dataset, visualizer.saveSettings())]);
            };
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

    return { copy, merge, prepare, inspect, buildSettings, describe, install };
});
