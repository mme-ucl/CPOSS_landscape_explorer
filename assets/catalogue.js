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

    function resources(page, contents = {}) {
        const archives = [];
        const metadata = [];
        const safeResource = (value, extensions) => {
            try {
                const url = new URL(value);
                return url.protocol === 'https:' && extensions.test(url.pathname) ? url.href : null;
            } catch (_) { return null; }
        };
        for (const model of page?.models || []) {
            for (const value of model.downloads || []) {
                const url = safeResource(value, /\.zip$/i);
                if (!url) continue;
                const filename = decodeURIComponent(new URL(url).pathname.split('/').pop());
                // CrystPred/CrystOpt is read from the actual linked filename.
                const kind = filename.match(/_(CrystPred|CrystOpt)\.zip$/i)?.[1];
                const context = [`Model ${model.id}`, kind, model.studyId ? `Study ${model.studyId}` : ''].filter(Boolean).join(' · ');
                const audit = contents[url];
                const hasMetadata = Boolean(audit?.metadataFiles?.length);
                archives.push({ url, filename, context, label: `Download structures${hasMetadata ? ' + metadata' : ''} (.zip)`,
                    detail: audit ? `${audit.structureCount} ${audit.structureFormat.toUpperCase()} structures${hasMetadata ? ' + ' + audit.metadataFiles.map(name => name.split('/').pop()).join(', ') : ''}` : 'Archive contents supplied by the database; metadata inclusion has not been checked.' });
            }
        }
        for (const item of page?.metadataDownloads || []) {
            const url = safeResource(item.url, /\.(xlsx|csv|tsv)$/i);
            if (url && !metadata.some(item => item.url === url)) metadata.push({ url, label: item.label || decodeURIComponent(new URL(url).pathname.split('/').pop()) });
        }
        return { archives, metadata };
    }

    return { normalize, externalDataUrl, datasetKey, find, filter, resources };
});
