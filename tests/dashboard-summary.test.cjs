const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../factory_dashboard/public/js/dashboard-summary.js'), 'utf8');
const texts = require('../factory_dashboard/i18n.json').vi;

class Node {
    constructor() { this.dataset = {}; this.events = {}; this.hidden = true; this.value = ''; this.innerHTML = ''; }
    addEventListener(name, handler) { this.events[name] = handler; }
    replaceChildren(...children) { this.children = children; }
    focus() { this.focused = true; }
    set textContent(value) { this.text = String(value); }
    get textContent() { return this.text || ''; }
}

const payload = {
    generated_at: '2026-11-20T15:00:00',
    companies: [{ code: 'C', name: 'Company' }],
    factories: [{ company_code: 'C', code: 'F', name: 'Factory' }],
    products: [{ company_code: 'C', factory_code: 'F', code: 'P', name: 'Product' }],
    product_totals: [{ code: 'P', total_produced: 150, cumulative_produced: 250 }],
    entries: [{ company_code: 'C', company_name: 'Company', factory_code: 'F', factory_name: 'Factory',
        line_code: 'G', product_code: 'P', production_date: '2026-11-17',
        produced_quantity: 150, cumulative_produced: 250 }],
};

test('summary renders monthly totals, navigation, filters and day details', async () => {
    const ids = ['dashboard-texts', 'summary-back', 'summary-status', 'summary-total',
        'summary-companies', 'summary-groups', 'summary-products', 'summary-generated',
        'summary-month-label', 'summary-calendar-title', 'summary-weekdays', 'summary-calendar',
        'summary-product-totals', 'summary-matrix-head', 'summary-matrix-body', 'summary-chart',
        'summary-company', 'summary-factory', 'summary-product', 'summary-prev', 'summary-next',
        'summary-apply', 'summary-reset', 'summary-modal', 'summary-modal-title',
        'summary-modal-stats', 'summary-modal-products', 'summary-modal-companies',
        'summary-modal-lines', 'summary-modal-close'];
    const nodes = Object.fromEntries(ids.map(id => [id, new Node()]));
    nodes['dashboard-texts'].textContent = JSON.stringify(texts);
    const requests = [];
    const document = {
        activeElement: null,
        getElementById: id => nodes[id],
        querySelector: () => ({ dataset: { lang: 'vi' } }),
        createElement: () => new Node(),
        addEventListener() {},
    };
    const location = { search: '?device_id=fixture&month=2026-11', origin: 'http://fixture',
        href: 'http://fixture/productivity-dashboard-summary?device_id=fixture&month=2026-11' };
    const context = { document, location, history: { replaceState() {} },
        fetch: async url => { requests.push(String(url)); return { ok: true, json: async () => ({ message: payload }) }; },
        setTimeout: () => 1, clearTimeout() {}, URL, URLSearchParams, Intl, Date, Number,
        String, JSON, Math, Map, Set, Array };
    vm.runInNewContext(source, context);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(nodes['summary-total'].textContent, '150');
    assert.equal(nodes['summary-groups'].textContent, '1');
    assert.match(nodes['summary-product-totals'].innerHTML, /250/);
    assert.match(nodes['summary-calendar'].innerHTML, /data-day="2026-11-17"/);
    assert.equal(nodes['summary-back'].href, '/productivity-dashboard-tv?device_id=fixture&lang=vi');
    nodes['summary-calendar'].events.click({ target: { closest: () => ({ dataset: { day: '2026-11-17' } }) } });
    assert.equal(nodes['summary-modal'].hidden, false);
    assert.match(nodes['summary-modal-lines'].innerHTML, /Company/);
    nodes['summary-company'].events.change({ target: { value: 'C' } });
    nodes['summary-apply'].events.click();
    await new Promise(resolve => setImmediate(resolve));
    assert.match(requests.at(-1), /company_code=C/);
    nodes['summary-next'].events.click();
    await new Promise(resolve => setImmediate(resolve));
    assert.match(requests.at(-1), /date_from=2026-12-01/);
});
