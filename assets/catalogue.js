/* Pure catalogue helpers, shared by the navigator and its Node tests. */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.CpossCatalogue = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
    'use strict';

    function normalize(value) {
        return String(value).normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
            .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    }

    function externalDataUrl(value) {
        // Preserve relative URLs for Chemiscope's existing local/shared loaders.
        if (!/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(value)) return value;
        const url = new URL(value, 'https://louiseprice.github.io/CPOSS_Database/');
        if (url.hostname === 'github.com' && /^\/[^/]+\/[^/]+\/blob\//.test(url.pathname)) {
            url.hostname = 'raw.githubusercontent.com';
            url.pathname = url.pathname.replace('/blob/', '/');
            url.search = '';
        }
        if (['louiseprice.github.io', 'raw.githubusercontent.com'].includes(url.hostname)) url.protocol = 'https:';
        return url.href;
    }

    function datasetKey(value) {
        try {
            const url = new URL(externalDataUrl(value));
            let match;
            if (url.hostname === 'raw.githubusercontent.com') {
                match = url.pathname.match(/^\/LouisePrice\/CPOSS_Database\/[^/]+\/0\.Chemiscope\/([^/]+\.json)$/i);
            } else if (url.hostname === 'louiseprice.github.io') {
                match = url.pathname.match(/^\/CPOSS_Database\/0\.Chemiscope\/([^/]+\.json)$/i);
            }
            return match ? decodeURIComponent(match[1]) : null;
        } catch (_) {
            return null;
        }
    }

    function find(datasets, value) {
        const key = datasetKey(value);
        return key ? datasets.find(item => item.filename === key) || null : null;
    }

    function filter(datasets, query = '', collection = '') {
        const tokens = normalize(query).split(' ').filter(Boolean);
        return datasets.filter(item => {
            if (collection && !item.collections.includes(collection)) return false;
            const text = normalize([item.id, item.filename, item.label, item.molecule, ...item.aliases, ...item.codes].join(' '));
            const compact = text.replace(/ /g, '');
            return tokens.every(token => text.includes(token) || compact.includes(token));
        });
    }

    return { normalize, externalDataUrl, datasetKey, find, filter };
});
