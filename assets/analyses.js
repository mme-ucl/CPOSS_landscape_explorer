/* Progressive enhancements: the figures, statistics and complete inventory
 * remain available in the generated HTML when JavaScript is disabled. */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else api.start(root.document, root.location);
})(typeof window !== 'undefined' ? window : globalThis, function () {
    'use strict';

    function normalize(value) {
        return String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    }

    function matches(value, query) {
        const haystack = normalize(value);
        return normalize(query).trim().split(/\s+/).every(word => haystack.includes(word));
    }

    function compare(a, b, order) {
        const byName = () => a.name.localeCompare(b.name, 'en', { numeric: true, sensitivity: 'base' });
        if (order === 'files-asc') return a.files - b.files || byName();
        if (order === 'models-desc') return b.models - a.models || b.files - a.files || byName();
        if (order === 'name-asc') return byName();
        return b.files - a.files || byName();
    }

    function returnHref(pageUrl) {
        const page = new URL(pageUrl);
        const target = new URL('./', page);
        const load = page.searchParams.get('load');
        if (load) {
            try {
                const data = new URL(load, page);
                if (['http:', 'https:'].includes(data.protocol)) target.searchParams.set('load', load);
            } catch (_) { /* A malformed selection returns to the default landscape. */ }
        }
        return target.href;
    }

    function start(doc, location) {
        const byId = id => doc.getElementById(id);
        doc.querySelectorAll('.nav-return').forEach(link => { link.href = returnHref(location.href); });

        const cards = [...doc.querySelectorAll('.figure-card')];
        const filterButtons = [...doc.querySelectorAll('[data-figure-filter]')];
        function filterFigures(filter) {
            cards.forEach(card => {
                card.hidden = !(filter === 'all' || (filter === 'earlier' ? card.dataset.earlier === 'true' : card.dataset.category === filter));
            });
            filterButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.figureFilter === filter)));
            byId('figure-count').textContent = `${cards.filter(card => !card.hidden).length} of ${cards.length} figures`;
        }
        filterButtons.forEach(button => button.addEventListener('click', () => filterFigures(button.dataset.figureFilter)));
        function revealLinkedFigure() {
            const card = cards.find(item => '#' + item.id === location.hash);
            if (card && card.hidden) { filterFigures('all'); card.scrollIntoView(); }
        }
        doc.querySelectorAll('a[href^="#figure-"]').forEach(link => link.addEventListener('click', () => filterFigures('all')));
        doc.defaultView.addEventListener('hashchange', revealLinkedFigure);
        filterFigures('all');

        const dialog = byId('figure-dialog');
        const figures = JSON.parse(byId('analysis-data').textContent).figures;
        let opener;
        doc.querySelectorAll('[data-expand]').forEach(link => link.addEventListener('click', event => {
            const figure = figures.find(item => item.id === link.dataset.expand);
            if (!figure || typeof dialog.showModal !== 'function') return;
            event.preventDefault();
            opener = link;
            byId('dialog-title').textContent = figure.title;
            byId('dialog-image').src = figure.image;
            byId('dialog-image').alt = figure.description;
            byId('dialog-description').textContent = figure.note || figure.description;
            byId('dialog-original').href = figure.image;
            byId('dialog-pdf').hidden = !figure.pdf;
            if (figure.pdf) byId('dialog-pdf').href = figure.pdf;
            else byId('dialog-pdf').removeAttribute('href');
            dialog.showModal();
        }));
        byId('dialog-close').addEventListener('click', () => dialog.close());
        dialog.addEventListener('close', () => opener?.focus({ preventScroll: true }));
        dialog.addEventListener('click', event => {
            if (event.target !== dialog) return;
            const bounds = dialog.getBoundingClientRect();
            if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
        });

        const inventory = [...doc.querySelectorAll('#inventory-table tbody tr')];
        const inventoryBody = byId('inventory-table').tBodies[0];
        const pageSize = 25;
        let page = 0;
        function renderInventory() {
            const query = byId('search-inventory').value;
            const order = byId('inventory-sort').value;
            const filtered = inventory.filter(row => matches(row.dataset.search, query));
            filtered.sort((a, b) => compare({ name: a.dataset.name, files: +a.dataset.files, models: +a.dataset.models },
                { name: b.dataset.name, files: +b.dataset.files, models: +b.dataset.models }, order));
            const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
            page = Math.min(page, pages - 1);
            inventory.forEach(row => { row.hidden = true; });
            filtered.slice(page * pageSize, (page + 1) * pageSize).forEach(row => {
                row.hidden = false;
                inventoryBody.appendChild(row);
            });
            const first = filtered.length ? page * pageSize + 1 : 0;
            const last = Math.min((page + 1) * pageSize, filtered.length);
            byId('inventory-count').textContent = `${filtered.length} of ${inventory.length} searches · showing ${first}–${last}`;
            byId('inventory-page').textContent = `Page ${page + 1} of ${pages}`;
            byId('inventory-empty').hidden = !!filtered.length;
            byId('inventory-pagination').hidden = filtered.length <= pageSize;
            byId('inventory-previous').disabled = page === 0;
            byId('inventory-next').disabled = page === pages - 1;
        }
        ['search-inventory', 'inventory-sort'].forEach(id => byId(id).addEventListener(id === 'search-inventory' ? 'input' : 'change', () => { page = 0; renderInventory(); }));
        ['previous', 'next'].forEach(direction => byId('inventory-' + direction).addEventListener('click', () => {
            page += direction === 'next' ? 1 : -1;
            renderInventory();
            byId('searches-title').scrollIntoView({ block: 'start' });
        }));
        renderInventory();

        const downloads = [...doc.querySelectorAll('[data-download]')];
        let showAll = false;
        function renderDownloads() {
            const query = byId('download-search').value.trim();
            const group = byId('download-group').value;
            const filtered = downloads.filter(row => (!group || row.dataset.group === group) && matches(row.dataset.search, query));
            const visible = showAll || query || group ? filtered : filtered.slice(0, 12);
            downloads.forEach(row => { row.hidden = !visible.includes(row); });
            byId('download-count').textContent = `${filtered.length} result tables${visible.length < filtered.length ? ` · showing ${visible.length}` : ''}`;
            byId('downloads-more').hidden = !!(query || group) || filtered.length <= 12;
            byId('downloads-more').textContent = showAll ? 'Show fewer tables' : `Show all ${filtered.length} tables`;
            byId('downloads-empty').hidden = !!filtered.length;
        }
        byId('download-search').addEventListener('input', renderDownloads);
        byId('download-group').addEventListener('change', renderDownloads);
        byId('downloads-more').addEventListener('click', () => { showAll = !showAll; renderDownloads(); });
        renderDownloads();

        if (typeof doc.defaultView.IntersectionObserver === 'function') {
            const links = [...doc.querySelectorAll('.jump-nav a')];
            const observer = new doc.defaultView.IntersectionObserver(entries => {
                const current = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
                if (!current) return;
                links.forEach(link => {
                    if (link.hash === '#' + current.target.id) link.setAttribute('aria-current', 'location');
                    else link.removeAttribute('aria-current');
                });
            }, { rootMargin: '-8% 0px -65% 0px' });
            doc.querySelectorAll('main > section').forEach(section => observer.observe(section));
        }
    }

    return { normalize, matches, compare, returnHref, start };
});
