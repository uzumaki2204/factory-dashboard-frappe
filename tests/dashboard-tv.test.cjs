const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const texts = require('../factory_dashboard/i18n.json').vi;
const source = fs.readFileSync(path.join(__dirname, '../factory_dashboard/public/js/dashboard-tv.js'), 'utf8');

class Element {
    constructor(id = '') {
        this.id = id;
        this.children = [];
        this.dataset = { lang: 'vi' };
        this.events = {};
        this.attributes = {};
        this.classes = new Set();
        this.classList = {
            add: name => this.classes.add(name),
            remove: name => this.classes.delete(name),
            toggle: (name, enabled) => {
                if (enabled === false) this.classes.delete(name);
                else if (enabled === true || !this.classes.has(name)) this.classes.add(name);
                else this.classes.delete(name);
            },
        };
    }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = nodes; }
    addEventListener(name, fn) { this.events[name] = fn; }
    setAttribute(name, value) { this.attributes[name] = value; }
    getAttribute(name) { return this.attributes[name]; }
    set textContent(value) { this.text = String(value); }
    get textContent() { return (this.text || '') + this.children.map(x => x.textContent).join(''); }
}

async function render(lines, mode = 'single', options = {}) {
    const ids = [
        'dashboard-texts', 'dashboard-panels', 'dashboard-status', 'dashboard-device-form',
        'dashboard-date', 'dashboard-source', 'dashboard-updated', 'fullscreen-button',
        'reset-device-button', 'dashboard-device-drawer', 'dashboard-device-backdrop',
        'device-panel-button', 'device-panel-close', 'dashboard-mode-status',
        'dashboard-mode-single', 'dashboard-mode-dual', 'dashboard-device-name',
        'dashboard-device-code', 'dashboard-device-line', 'dashboard-device-modes',
        'dashboard-device-id', 'summary-page-link',
    ];
    const nodes = Object.fromEntries(ids.map(id => [id, new Element(id)]));
    nodes['dashboard-texts'].textContent = JSON.stringify(texts);
    nodes['dashboard-device-drawer'].hidden = true;
    nodes['dashboard-device-backdrop'].hidden = true;
    nodes['dashboard-mode-single'].dataset.mode = 'single';
    nodes['dashboard-mode-dual'].dataset.mode = 'dual';
    const document = {
        activeElement: null,
        body: new Element('body'),
        getElementById: id => nodes[id],
        querySelector: () => new Element(),
        createElement: () => new Element(),
        querySelectorAll: () => [],
    };
    for (const node of Object.values(nodes)) node.focus = () => { document.activeElement = node; };
    nodes['dashboard-device-drawer'].querySelectorAll = () => [
        nodes['device-panel-close'], nodes['dashboard-mode-single'],
        nodes['dashboard-mode-dual'], nodes['summary-page-link'], nodes['reset-device-button'],
    ].filter(node => !node.disabled && !node.hidden);
    const storage = new Map(Object.entries(options.storage || {}));
    const requests = [];
    const context = {
        document,
        window: {
            location: { search: '?device_id=fixture', origin: 'http://fixture', href: 'http://fixture/productivity-dashboard-tv?device_id=fixture' },
            localStorage: {
                getItem: key => storage.get(key) ?? null,
                setItem: (key, value) => storage.set(key, value),
                removeItem: key => storage.delete(key),
            },
            history: { replaceState() {} },
        },
        fetch: async input => {
            const requested = new URL(input).searchParams.get('mode');
            requests.push(requested);
            const actual = requested === 'dual' && options.dualAvailable === false ? 'single' : requested || mode;
            return { ok: true, json: async () => ({ message: {
                lines: actual === 'dual' ? (options.dualLines || [lines[0], lines[0]]) : lines,
                display_mode: actual,
                supported_modes: options.dualAvailable === false ? ['single'] : ['single', 'dual'],
                device: { id: 'fixture', name: 'TV A', registered_line_code: '315', registered_line_name: 'C5X3' },
                production_date: '2026-11-17', defect_rate_mode: 'qc_input', refresh_seconds: 60,
            } }) };
        },
        URL, URLSearchParams, Intl, Date, Number, String, JSON, Math,
        setTimeout() {}, clearTimeout() {}, setInterval() {},
    };
    vm.runInNewContext(source, context);
    await flush();
    return { nodes, storage, requests, document };
}

async function flush() {
    await new Promise(resolve => setImmediate(resolve));
}

function find(node, cssClass) {
    return [ ...(node.className?.split(' ').includes(cssClass) ? [node] : []), ...node.children.flatMap(child => find(child, cssClass)) ];
}

const row = {
    line_code: '315', line_name: 'C5X3', product_code: '216F012B', report_count: 1,
    daily_target_quantity: 519, current_target_quantity: 434, finished_quantity: 270,
    qc_total_quantity: 100, defect_quantity: 0,
    has_defect_rate: true, defect_rate_percent: 0, achievement_rate_percent: 62.21,
    time_slots: [
        { label: 'Ca 1', start_time: '07:30', end_time: '09:30', quantity: 80, cumulative_quantity: 80, is_visible: true },
        { label: 'Ca 6', start_time: '18:30', end_time: '20:30', quantity: 0, cumulative_quantity: 80, is_visible: false },
    ],
};

test('TV shows line name, four KPIs and only visible slots', async () => {
    const { nodes } = await render([row]);
    assert.equal(nodes['summary-page-link'].href, '/productivity-dashboard-summary?device_id=fixture&lang=vi');
    const board = nodes['dashboard-panels'];
    assert.equal(find(board, 'dashboard-tv-line-code')[0].textContent, 'C5X3');
    assert.deepEqual(find(board, 'dashboard-tv-kpi-value').map(x => x.textContent), ['519', '0%', '434', '62.2%']);
    assert.equal(find(board, 'dashboard-tv-slot-row').length, 1);
    assert.equal(find(board, 'dashboard-tv-slot-time')[0].textContent, '07:30 - 09:30');
});

test('mixed group has no missing-data banner or source-line rows', async () => {
    const missing = { ...row, report_count: 0, qc_total_quantity: 0, time_slots: row.time_slots.map(x => ({ ...x, is_visible: false })) };
    const combined = { ...missing, mixed_products: true, line_details: [
        { ...missing, line_code: '314', qc_total_quantity: 100 },
        { ...missing, line_code: '315', report_count: 1 },
        { ...row, line_code: '316' },
    ] };
    const { nodes } = await render([combined], 'dual', { dualLines: [combined, combined] });
    assert.equal(nodes['dashboard-panels'].children.length, 2);
    for (const board of nodes['dashboard-panels'].children) {
        assert.equal(find(board, 'dashboard-tv-data-note').length, 0);
        assert.equal(find(board, 'dashboard-tv-line-details').length, 0);
        assert.equal(find(board, 'dashboard-tv-line-detail').length, 0);
        assert.equal(board.children.length, 3);
        assert.equal(find(board, 'dashboard-tv-empty')[0].textContent, texts['ui.slots_not_started']);
    }
});

test('drawer switches modes locally and remains keyboard accessible', async () => {
    const { nodes, storage, requests, document } = await render([row]);
    nodes['device-panel-button'].events.click();
    assert.equal(nodes['dashboard-device-drawer'].hidden, false);
    assert.equal(document.activeElement, nodes['device-panel-close']);
    nodes['dashboard-mode-dual'].events.click();
    await flush();
    assert.equal(storage.get('factoryDashboardMode:fixture'), 'dual');
    assert.equal(requests.at(-1), 'dual');
    assert.equal(nodes['dashboard-mode-dual'].getAttribute('aria-pressed'), 'true');
    assert.equal(nodes['dashboard-panels'].classes.has('dashboard-tv-panels-dual'), true);
    document.activeElement = nodes['device-panel-close'];
    nodes['dashboard-device-drawer'].events.keydown({ key: 'Tab', shiftKey: true, preventDefault() {} });
    assert.equal(document.activeElement, nodes['reset-device-button']);
    nodes['dashboard-device-drawer'].events.keydown({ key: 'Escape', preventDefault() {} });
    assert.equal(nodes['dashboard-device-drawer'].hidden, true);
    assert.equal(document.activeElement, nodes['device-panel-button']);
});

test('saved mode is restored when the TV page loads again', async () => {
    const { nodes, storage, requests } = await render([row], 'single', {
        storage: { 'factoryDashboardMode:fixture': 'dual' },
    });
    assert.equal(requests[0], 'dual');
    assert.equal(storage.get('factoryDashboardMode:fixture'), 'dual');
    assert.equal(nodes['dashboard-mode-dual'].getAttribute('aria-pressed'), 'true');
});

test('stale saved Dual choice falls back to Single and clears browser storage', async () => {
    const { nodes, storage, requests } = await render([row], 'single', {
        dualAvailable: false, storage: { 'factoryDashboardMode:fixture': 'dual' },
    });
    assert.equal(requests[0], 'dual');
    assert.equal(storage.has('factoryDashboardMode:fixture'), false);
    assert.equal(nodes['dashboard-mode-single'].getAttribute('aria-pressed'), 'true');
    assert.equal(nodes['dashboard-mode-dual'].disabled, true);
});

test('reset device clears its saved mode', async () => {
    const { nodes, storage } = await render([row], 'single', {
        storage: { 'factoryDashboardMode:fixture': 'single' },
    });
    nodes['reset-device-button'].events.click();
    assert.equal(storage.has('factoryDashboardMode:fixture'), false);
    assert.equal(nodes['dashboard-device-form'].hidden, false);
    assert.equal(nodes['device-panel-button'].disabled, true);
});
