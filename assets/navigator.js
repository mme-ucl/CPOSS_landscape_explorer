(function () {
    'use strict';
    const catalogueTools = window.CpossCatalogue;
    const byId = id => document.getElementById(id);
    const state = { datasets: [], matches: [], active: -1, current: null, page: null, loading: false, preview: false };
    let app;

    function resizeViewer() {
        requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
    }

    function stopLoading() {
        byId('loading').style.display = 'none';
        byId('loading-progress').textContent = '';
        const main = byId('chemiscope-container');
        main.style.opacity = '1';
        main.onclick = null;
    }

    function displayError(error) {
        stopLoading();
        const display = byId('error-display');
        display.hidden = false;
        display.style.display = 'block';
        display.querySelector('p').textContent = String(error);
        display.querySelector('details p').textContent = error?.stack || '';
    }

    function openResults() {
        byId('dataset-browser').hidden = false;
        byId('dataset-search').setAttribute('aria-expanded', 'true');
    }

    function closeResults() {
        byId('dataset-browser').hidden = true;
        byId('dataset-search').setAttribute('aria-expanded', 'false');
        byId('dataset-search').removeAttribute('aria-activedescendant');
        state.active = -1;
    }

    function activateResult(index) {
        if (!state.matches.length) return;
        state.active = Math.max(0, Math.min(index, state.matches.length - 1));
        const rows = byId('dataset-results').children;
        for (let i = 0; i < rows.length; i++) rows[i].setAttribute('aria-selected', String(i === state.active));
        const row = rows[state.active];
        byId('dataset-search').setAttribute('aria-activedescendant', row.id);
        row.scrollIntoView({ block: 'nearest' });
    }

    function renderResults() {
        state.active = -1;
        byId('dataset-search').removeAttribute('aria-activedescendant');
        const collection = byId('dataset-collection').value;
        state.matches = catalogueTools.filter(state.datasets, byId('dataset-search').value, collection);
        const selected = byId('dataset-collection').selectedOptions[0];
        const collectionLabel = selected?.dataset.label || 'All datasets';
        byId('dataset-results-count').textContent = `${state.matches.length} of ${state.datasets.length} datasets · ${collectionLabel}`;
        const list = byId('dataset-results');
        list.replaceChildren();
        list.setAttribute('aria-busy', String(state.loading));
        const fragment = document.createDocumentFragment();
        state.matches.forEach((item, index) => {
            const row = document.createElement('li');
            row.id = `dataset-option-${index}`;
            row.setAttribute('role', 'option');
            row.setAttribute('aria-selected', 'false');
            row.setAttribute('aria-disabled', String(state.loading));
            const name = document.createElement('span');
            name.className = 'cposs-result-name';
            name.textContent = item.label;
            const detail = document.createElement('span');
            detail.className = 'cposs-result-code';
            detail.textContent = [item.id, item.codes.slice(0, 3).join(', '), state.current?.id === item.id ? 'Currently displayed' : '', !item.cases.length ? 'Database page not mapped' : ''].filter(Boolean).join(' · ');
            row.append(name, detail);
            row.addEventListener('mousedown', event => event.preventDefault());
            row.addEventListener('click', () => selectDataset(item));
            fragment.appendChild(row);
        });
        list.appendChild(fragment);
        byId('dataset-empty').hidden = state.matches.length > 0;
        const source = byId('collection-source');
        source.hidden = !collection;
        if (collection) source.href = selected.dataset.source;
    }

    function refreshPreview() {
        const frame = byId('case-preview-frame');
        byId('database-preview').hidden = !state.preview;
        byId('cposs-workspace').classList.toggle('is-preview-open', state.preview);
        byId('toggle-preview').setAttribute('aria-expanded', String(state.preview));
        byId('toggle-preview').textContent = state.preview ? 'Close page preview' : 'Preview beside landscape';
        if (state.preview && state.page) {
            if (frame.getAttribute('src') !== state.page.url) {
                byId('preview-status').textContent = 'Loading the database page. If it stays blank or is blocked, ';
                frame.src = state.page.url;
            }
            frame.title = `Molecule database page: ${state.page.molecule}`;
            byId('preview-external-link').href = state.page.url;
        } else {
            frame.removeAttribute('src');
        }
        resizeViewer();
    }

    function setPage(page) {
        state.page = page;
        byId('case-page-link').hidden = !page;
        byId('case-page-unavailable').hidden = Boolean(page);
        byId('toggle-preview').disabled = !page;
        if (page) byId('case-page-link').href = page.url;
        else {
            byId('case-page-link').removeAttribute('href');
            state.preview = false;
        }
        refreshPreview();
    }

    function setCurrent(url, fallbackLabel, local = false) {
        state.current = local ? null : catalogueTools.find(state.datasets, url);
        const label = state.current?.label || fallbackLabel || 'No dataset loaded';
        byId('cposs-dataset-name').textContent = label;
        document.title = `CPOSS CSP Landscape Navigator — ${label}`;
        byId('cposs-load-status').textContent = state.current ? state.current.id : (local ? 'Local dataset' : 'External dataset');
        const pages = state.current?.cases || [];
        const select = byId('case-page-select');
        select.replaceChildren();
        pages.forEach((page, index) => {
            const option = new Option(`${page.molecule}${page.search ? ' — Search ' + page.search : ''}`, String(index));
            select.appendChild(option);
        });
        select.hidden = pages.length < 2;
        setPage(pages[0] || null);
        renderResults();
    }

    function filenameLabel(value) {
        try {
            return decodeURIComponent(new URL(value, location.href).pathname.split('/').pop()).replace(/\.json(?:\.gz)?$/i, '') || 'External dataset';
        } catch (_) {
            return value;
        }
    }

    function applyDefaultStructureSettings() {
        app.visualizer.applySettings({ structure: [{ supercell: [3, 3, 3], unitCell: true }] });
    }

    async function loadUrl(url, { updateUrl = false, settingsUrl = null } = {}) {
        if (state.loading) return;
        state.loading = true;
        byId('cposs-load-status').textContent = `Loading ${filenameLabel(url)}…`;
        renderResults();
        try {
            let settings;
            if (settingsUrl) {
                const response = await fetch(catalogueTools.externalDataUrl(settingsUrl));
                if (!response.ok) throw new Error('Unable to load the shared visualization settings.');
                settings = await response.json();
            }
            await app.fetchAndLoad(catalogueTools.externalDataUrl(url), {});
            applyDefaultStructureSettings();
            if (settings) app.visualizer.applySettings(settings);
            setCurrent(url, filenameLabel(url));
            if (updateUrl) {
                const pageUrl = new URL(location.href);
                pageUrl.searchParams.set('load', url);
                pageUrl.searchParams.delete('settings');
                history.replaceState(null, '', pageUrl.href);
            }
        } catch (error) {
            displayError(error);
            byId('cposs-load-status').textContent = 'Unable to load dataset. Choose another result or try again.';
        } finally {
            state.loading = false;
            stopLoading();
            renderResults();
            resizeViewer();
        }
    }

    function selectDataset(item) {
        if (state.loading) return;
        closeResults();
        loadUrl(item.url, { updateUrl: true });
    }

    async function loadCatalogue() {
        const response = await fetch('data/catalogue.json');
        if (!response.ok) throw new Error('The dataset catalogue could not be loaded. Serve this folder over HTTP (see README).');
        const catalogue = await response.json();
        if (catalogue.schemaVersion !== 1 || !Array.isArray(catalogue.datasets) || !catalogue.datasets.length) throw new Error('The dataset catalogue is empty or unsupported.');
        state.datasets = catalogue.datasets.slice().sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true, sensitivity: 'base' }));
        for (const collection of catalogue.collections) {
            const option = new Option(`${collection.label} (${collection.count})`, collection.id);
            option.dataset.label = collection.label;
            option.dataset.source = collection.sourceUrl;
            byId('dataset-collection').appendChild(option);
        }
        byId('dataset-search').disabled = false;
        byId('dataset-collection').disabled = false;
        renderResults();
        return catalogue;
    }

    function bindBrowser() {
        const input = byId('dataset-search');
        input.addEventListener('input', () => { renderResults(); openResults(); });
        input.addEventListener('focus', openResults);
        input.addEventListener('keydown', event => {
            const isOpen = !byId('dataset-browser').hidden;
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                openResults();
                const first = event.key === 'ArrowDown' ? 0 : state.matches.length - 1;
                activateResult(!isOpen || state.active < 0 ? first : state.active + (event.key === 'ArrowDown' ? 1 : -1));
            } else if ((event.key === 'Home' || event.key === 'End') && isOpen && state.active >= 0) {
                event.preventDefault();
                activateResult(event.key === 'Home' ? 0 : state.matches.length - 1);
            } else if (event.key === 'Enter' && isOpen && state.matches.length) {
                event.preventDefault();
                selectDataset(state.matches[Math.max(0, state.active)]);
            } else if (event.key === 'Escape') {
                closeResults();
            } else if (event.key === 'Tab') {
                closeResults();
            }
        });
        byId('dataset-collection').addEventListener('change', () => { renderResults(); input.focus(); openResults(); });
        byId('reset-filters').addEventListener('click', () => {
            input.value = '';
            byId('dataset-collection').value = '';
            renderResults();
            input.focus();
            openResults();
        });
        document.addEventListener('click', event => {
            if (!event.target.closest('.cposs-search') && !event.target.closest('#dataset-collection') && !event.target.closest('#reset-filters')) closeResults();
        });
        byId('case-page-select').addEventListener('change', event => setPage(state.current.cases[Number(event.target.value)]));
        byId('toggle-preview').addEventListener('click', () => { state.preview = !state.preview; refreshPreview(); });
        byId('close-preview').addEventListener('click', () => {
            state.preview = false;
            refreshPreview();
            byId('toggle-preview').focus();
        });
        byId('case-preview-frame').addEventListener('load', () => {
            byId('preview-status').textContent = 'If the page is blank or embedding is blocked, ';
        });
        byId('case-preview-frame').addEventListener('error', () => {
            byId('preview-status').textContent = 'The preview is unavailable. Please ';
        });
    }

    function bindScrollBands() {
        document.querySelectorAll('.scroll-band-left, .scroll-band-right').forEach(band => {
            band.addEventListener('click', event => {
                event.stopPropagation();
                event.preventDefault();
                band.style.pointerEvents = 'none';
                let hit = document.elementFromPoint(event.clientX, event.clientY);
                while (hit?.shadowRoot?.elementFromPoint) {
                    const deeper = hit.shadowRoot.elementFromPoint(event.clientX, event.clientY);
                    if (!deeper || deeper === hit) break;
                    hit = deeper;
                }
                band.style.pointerEvents = '';
                if (hit && hit !== band) hit.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window, clientX: event.clientX, clientY: event.clientY, button: event.button || 0 }));
            });
        });
    }

    async function start() {
        window.addEventListener('error', event => { if (event.error) displayError(event.error); });
        window.addEventListener('unhandledrejection', event => displayError(event.reason));
        app = new Chemiscope.ChemiscopeApp('chemiscope-container');
        // Keep Chemiscope's file/streaming loader and settings UI; update metadata only
        // after a local dataset has successfully loaded, without matching by filename.
        const originalLoad = app.load.bind(app);
        app.load = async function (...args) {
            const result = await originalLoad(...args);
            if (!state.loading) {
                const url = new URL(location.href);
                url.searchParams.delete('load');
                url.searchParams.delete('settings');
                history.replaceState(null, '', url.href);
                setCurrent(null, app.dataset || 'Local dataset', true);
            }
            resizeViewer();
            return result;
        };
        bindBrowser();
        bindScrollBands();
        let previousHeight = 0;
        new ResizeObserver(() => {
            const height = Math.ceil(document.querySelector('.cposs-header').getBoundingClientRect().height);
            if (height !== previousHeight) {
                previousHeight = height;
                document.documentElement.style.setProperty('--header-height', `${height}px`);
                resizeViewer();
            }
        }).observe(document.querySelector('.cposs-header'));
        let catalogue;
        try { catalogue = await loadCatalogue(); }
        catch (error) {
            byId('dataset-results-count').textContent = 'Dataset catalogue unavailable';
            displayError(error);
        }
        const embedded = byId('standalone-json-data');
        const url = new URL(location.href);
        if (embedded) {
            if (embedded.textContent.trim()) {
                const data = JSON.parse(embedded.textContent.replace(/\bNaN\b/g, '"***NaN***"'), (_, value) => value === '***NaN***' ? NaN : value);
                state.loading = true;
                try {
                    await app.load({}, data);
                    applyDefaultStructureSettings();
                    if (data.settings) app.visualizer.applySettings(data.settings);
                    setCurrent(null, data.meta?.name?.trim() || 'Embedded dataset', true);
                } finally { state.loading = false; stopLoading(); renderResults(); }
            } else stopLoading();
        } else if (url.searchParams.has('load')) {
            await loadUrl(url.searchParams.get('load'), { settingsUrl: url.searchParams.get('settings') });
        } else if (catalogue) {
            await loadUrl(catalogue.datasets[0].url);
        } else {
            stopLoading();
        }
    }

    document.addEventListener('DOMContentLoaded', () => start().catch(displayError));
})();
