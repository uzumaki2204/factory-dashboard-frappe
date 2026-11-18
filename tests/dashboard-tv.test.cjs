const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const texts = require('../factory_dashboard/i18n.json').vi;
const source = fs.readFileSync(path.join(__dirname, '../factory_dashboard/public/js/dashboard-tv.js'), 'utf8');

class Element {
    constructor() { this.children = []; this.dataset = { lang: 'vi' }; this.events = {}; this.classList = { toggle() {} }; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = nodes; }
    addEventListener(name, fn) { this.events[name] = fn; }
    set textContent(value) { this.text = String(value); }
    get textContent() { return (this.text || '') + this.children.map(x => x.textContent).join(''); }
}

async function render(lines, mode = 'single') {
    const nodes = Object.fromEntries(['dashboard-texts', 'dashboard-panels', 'dashboard-status', 'dashboard-device-form', 'dashboard-date', 'dashboard-source', 'dashboard-updated', 'fullscreen-button', 'reset-device-button'].map(id => [id, new Element()]));
    nodes['dashboard-texts'].textContent = JSON.stringify(texts);
    const context = {
        document: { getElementById: id => nodes[id], querySelector: () => new Element(), createElement: () => new Element(), querySelectorAll: () => [] },
        window: { location: { search: '?device_id=fixture', origin: 'http://fixture' } },
        fetch: async () => ({ ok: true, json: async () => ({ message: { lines, display_mode: mode, production_date: '2026-11-17', defect_rate_mode: 'qc_input', refresh_seconds: 60 } }) }),
        URL, URLSearchParams, Intl, Date, Number, String, JSON, Math,
        setTimeout() {}, clearTimeout() {}, setInterval() {},
    };
    vm.runInNewContext(source, context);
    await new Promise(resolve => setImmediate(resolve));
    return nodes;
}

function find(node, cssClass) {
    return [ ...(node.className?.split(' ').includes(cssClass) ? [node] : []), ...node.children.flatMap(child => find(child, cssClass)) ];
}

const row = {
    line_code: '315', line_name: 'C5X3', product_code: '216F012B', report_count: 1,
    daily_target_quantity: 519, current_target_quantity: 434, finished_quantity: 270,
    has_defect_rate: true, defect_rate_percent: 0, achievement_rate_percent: 62.21,
    time_slots: [
        { label: 'Ca 1', start_time: '07:30', end_time: '09:30', quantity: 80, cumulative_quantity: 80, is_visible: true },
        { label: 'Ca 6', start_time: '18:30', end_time: '20:30', quantity: 0, cumulative_quantity: 80, is_visible: false },
    ],
};

test('TV shows line name, four correct KPIs, formatted percent and only visible slots', async () => {
    const nodes = await render([row]);
    const board = nodes['dashboard-panels'];
    assert.equal(find(board, 'dashboard-tv-line-code')[0].textContent, 'C5X3');
    assert.deepEqual(find(board, 'dashboard-tv-kpi-value').map(x => x.textContent), ['519', '0%', '434', '62.2%']);
    assert.equal(find(board, 'dashboard-tv-slot-row').length, 1);
    assert.equal(find(board, 'dashboard-tv-slot-time')[0].textContent, '07:30 - 09:30');
    assert.equal(find(board, 'dashboard-tv-slot-cumulative')[0].textContent, '80');
});

test('dual panels render independently without adding left and right values', async () => {
    const nodes = await render([row, { ...row, line_name: 'C6X3', daily_target_quantity: 0 }], 'dual');
    assert.equal(nodes['dashboard-panels'].children.length, 2);
    assert.equal(find(nodes['dashboard-panels'].children[1], 'dashboard-tv-kpi-value')[0].textContent, '0');
});

test('missing report displays localized note and no future rows', async () => {
    const nodes = await render([{ ...row, report_count: 0, time_slots: row.time_slots.map(x => ({ ...x, is_visible: false })) }]);
    assert.equal(find(nodes['dashboard-panels'], 'dashboard-tv-data-note')[0].textContent, texts['ui.no_report']);
    assert.equal(find(nodes['dashboard-panels'], 'dashboard-tv-empty')[0].textContent, texts['ui.slots_not_started']);
});
