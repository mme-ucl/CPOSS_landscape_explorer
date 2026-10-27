/* Progressive enhancements: figures and statistics remain available in the
 * generated HTML when JavaScript is disabled. */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else api.start(root.document, root.location);
})(typeof window !== 'undefined' ? window : globalThis, function () {
    'use strict';

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
                card.hidden = !(filter === 'all' || card.dataset.category === filter);
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

    return { returnHref, start };
});
