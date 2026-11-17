(() => {
    'use strict';

    const texts = JSON.parse(document.getElementById('dashboard-texts').textContent);
    const t = key => texts[key] || '';
    const root = document.querySelector('.dashboard-tv');
    const panels = document.getElementById('dashboard-panels');
    const status = document.getElementById('dashboard-status');
    const form = document.getElementById('dashboard-device-form');
    const params = new URLSearchParams(window.location.search);
    const deviceId = (params.get('device_id') || '').trim();
    const number = value => new Intl.NumberFormat(root.dataset.lang || 'vi').format(Number(value) || 0);
    let timer;

    function element(tag, className, value) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (value !== undefined && value !== null) node.textContent = String(value);
        return node;
    }

    function metric(label, value, unit = '') {
        const card = element('div', 'dashboard-tv-metric');
        card.append(element('span', 'dashboard-tv-metric-label', label));
        card.append(element('strong', 'dashboard-tv-metric-value', `${value}${unit}`));
        return card;
    }

    function lineDetail(row) {
        const detail = element('div', 'dashboard-tv-line-detail');
        detail.append(element('strong', '', row.line_name || row.line));
        detail.append(element('span', '', `${t('ui.product')}: ${row.product_code || t('ui.no_value')}`));
        detail.append(element('span', '', `${t('ui.defects')}: ${number(row.defect_quantity)}`));
        detail.append(element('span', '', `${t('ui.defect_rate')}: ${row.has_defect_rate ? `${number(row.defect_rate_percent)}%` : t('ui.no_value')}`));
        return detail;
    }

    function slotTable(rows) {
        const table = element('table', 'dashboard-tv-slots');
        const head = element('thead');
        const heading = element('tr');
        [t('ui.time_slot'), t('ui.slot_output'), t('ui.cumulative')].forEach(label => heading.append(element('th', '', label)));
        head.append(heading);
        table.append(head);
        const body = element('tbody');
        rows.forEach(row => {
            const tr = element('tr');
            const range = row.start_time && row.end_time ? ` ${row.start_time.slice(0, 5)}–${row.end_time.slice(0, 5)}` : '';
            [row.label + range, number(row.quantity), number(row.cumulative_quantity)].forEach(value => tr.append(element('td', '', value)));
            body.append(tr);
        });
        table.append(body);
        return table;
    }

    function serverMessage(body) {
        try {
            const messages = JSON.parse(body._server_messages || '[]');
            return messages.length ? (JSON.parse(messages[0]).message || '') : '';
        } catch (_) {
            return '';
        }
    }

    function renderPanel(row) {
        const section = element('section', 'dashboard-tv-panel frappe-card');
        const header = element('div', 'dashboard-tv-panel-header');
        header.append(element('h2', '', row.line_name || row.line || t('ui.line')));
        if (row.product_code) header.append(element('span', 'dashboard-tv-product', row.product_code));
        section.append(header);
        if (!row.report_count) section.append(element('p', 'dashboard-tv-note', t('ui.no_report')));
        const grid = element('div', 'dashboard-tv-metrics');
        grid.append(metric(t('ui.output'), number(row.finished_quantity)));
        grid.append(metric(t('ui.target'), number(row.daily_target_quantity)));
        grid.append(metric(t('ui.achievement'), number(row.achievement_rate_percent), '%'));
        grid.append(metric(t('ui.defects'), number(row.defect_quantity)));
        grid.append(metric(t('ui.quality_checked'), number(row.qc_total_quantity)));
        grid.append(metric(t('ui.defect_rate'), row.has_defect_rate ? number(row.defect_rate_percent) : t('ui.no_value'), row.has_defect_rate ? '%' : ''));
        section.append(grid);
        if (!row.has_defect_rate) section.append(element('p', 'dashboard-tv-note', row.defect_rate_unavailable_reason || t('ui.no_quality_data')));
        const meta = element('div', 'dashboard-tv-meta');
        if (row.planned_quantity) meta.append(element('span', '', `${t('ui.plan')}: ${number(row.planned_quantity)}`));
        if (row.worker_count) meta.append(element('span', '', `${t('ui.worker_count')}: ${number(row.worker_count)}`));
        if (row.line_leader_name) meta.append(element('span', '', `${t('ui.line_leader')}: ${row.line_leader_name}`));
        if (row.technical_leader_name) meta.append(element('span', '', `${t('ui.technical_leader')}: ${row.technical_leader_name}`));
        section.append(meta);
        if (row.mixed_products) {
            const details = element('div', 'dashboard-tv-line-details');
            row.line_details.forEach(detail => details.append(lineDetail(detail)));
            section.append(details);
        }
        if (row.time_slots && row.time_slots.length) section.append(slotTable(row.time_slots));
        return section;
    }

    async function load() {
        clearTimeout(timer);
        status.textContent = t('ui.loading');
        let failure = t('ui.error');
        try {
            const url = new URL('/api/method/factory_dashboard.api.display', window.location.origin);
            url.searchParams.set('device_id', deviceId);
            const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
            const body = await response.json();
            if (!response.ok) {
                failure = serverMessage(body) || failure;
                throw new Error(failure);
            }
            const data = body.message;
            if (!data || !Array.isArray(data.lines)) throw new Error(failure);
            panels.replaceChildren(...data.lines.map(renderPanel));
            panels.classList.toggle('dashboard-tv-panels-dual', data.display_mode === 'dual');
            document.getElementById('dashboard-date').textContent = data.production_date || '';
            document.getElementById('dashboard-source').textContent = `${t('ui.source')}: ${t(data.defect_rate_mode === 'uqqc_input' ? 'ui.uqqc_source' : 'ui.qc_source')}`;
            document.getElementById('dashboard-updated').textContent = `${t('ui.last_updated')}: ${new Date().toLocaleString(root.dataset.lang || 'vi')}`;
            status.textContent = t('ui.status_online');
            timer = setTimeout(load, Math.max(10, Number(data.refresh_seconds) || 60) * 1000);
        } catch (_) {
            panels.replaceChildren();
            status.textContent = failure;
            timer = setTimeout(load, 60000);
        }
    }

    form.addEventListener('submit', event => {
        event.preventDefault();
        const value = document.getElementById('dashboard-device-id').value.trim();
        if (!value) return;
        const url = new URL(window.location.href);
        url.searchParams.set('device_id', value);
        window.location.assign(url);
    });
    document.getElementById('refresh-button').addEventListener('click', load);
    document.getElementById('fullscreen-button').addEventListener('click', () => {
        if (document.fullscreenElement) document.exitFullscreen();
        else document.documentElement.requestFullscreen();
    });
    if (deviceId) load();
    else form.hidden = false;
})();
