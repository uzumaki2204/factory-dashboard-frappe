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
    const percent = value => {
        const numeric = Number(value) || 0;
        const decimals = Math.abs(numeric - Math.round(numeric)) < .05 ? 0 : 1;
        return `${numeric.toFixed(decimals)}%`;
    };
    let timer;

    function element(tag, className, value) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (value !== undefined && value !== null) node.textContent = String(value);
        return node;
    }

    function displayDate(value) {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value || ''))) return t('ui.no_value');
        const [year, month, day] = value.split('-');
        return `${day}/${month}/${year}`;
    }

    function field(label, value) {
        const row = element('div', 'dashboard-tv-field');
        row.append(element('span', 'dashboard-tv-field-label', label));
        row.append(element('strong', 'dashboard-tv-field-value', value));
        return row;
    }

    function kpi(label, value, tone, reason) {
        const cell = element('div', 'dashboard-tv-kpi');
        cell.append(element('span', 'dashboard-tv-kpi-label', label));
        const result = element('strong', `dashboard-tv-kpi-value dashboard-tv-kpi-value-${tone}`, value);
        if (reason) result.title = reason;
        cell.append(result);
        return cell;
    }

    function lineDetail(row) {
        const detail = element('div', 'dashboard-tv-line-detail');
        detail.append(element('strong', '', row.line_code || row.line_name || row.line));
        detail.append(element('span', '', row.product_code || t('ui.no_value')));
        detail.append(element('span', '', `${t('ui.defects')}: ${number(row.defect_quantity)}`));
        detail.append(element('span', '', `${t('ui.defect_rate')}: ${row.has_defect_rate ? percent(row.defect_rate_percent) : t('ui.no_value')}`));
        return detail;
    }

    function slotMatrix(rows) {
        const matrix = element('section', 'dashboard-tv-slots');
        const heading = element('div', 'dashboard-tv-slot-heading');
        [t('ui.time_slot'), t('ui.slot_output'), t('ui.cumulative')].forEach(label => heading.append(element('span', '', label)));
        matrix.append(heading);
        const body = element('div', 'dashboard-tv-slot-body');
        const visibleRows = rows.filter(row => row.is_visible);
        if (!visibleRows.length) body.append(element('p', 'dashboard-tv-empty', t(rows.length ? 'ui.slots_not_started' : 'ui.no_slots')));
        visibleRows.forEach(row => {
            const item = element('div', `dashboard-tv-slot-row${row.is_current ? ' is-current' : ''}`);
            const label = row.start_time && row.end_time
                ? `${row.start_time.slice(0, 5)} - ${row.end_time.slice(0, 5)}`
                : row.label || t('ui.no_value');
            item.append(element('strong', 'dashboard-tv-slot-time', label || t('ui.no_value')));
            item.append(element('strong', 'dashboard-tv-slot-quantity', number(row.quantity)));
            item.append(element('strong', 'dashboard-tv-slot-cumulative', number(row.cumulative_quantity)));
            body.append(item);
        });
        matrix.append(body);
        return matrix;
    }

    function updateClock() {
        const value = new Date().toLocaleString(root.dataset.lang || 'vi');
        document.querySelectorAll('.dashboard-tv-clock').forEach(node => { node.textContent = value; });
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
        const board = element('section', 'dashboard-tv-board');
        const head = element('div', 'dashboard-tv-head');
        const line = element('div', 'dashboard-tv-head-cell');
        line.append(element('strong', 'dashboard-tv-line-code', row.line_name || row.line_code || row.line || t('ui.no_value')));
        const lineMeta = element('div', 'dashboard-tv-fields');
        lineMeta.append(field(t('ui.line_leader'), row.line_leader_name || t('ui.no_value')));
        lineMeta.append(field(t('ui.technical_leader'), row.technical_leader_name || t('ui.no_value')));
        lineMeta.append(field(t('ui.worker_count'), number(row.worker_count)));
        lineMeta.append(element('strong', 'dashboard-tv-clock'));
        line.append(lineMeta);
        const plan = element('div', 'dashboard-tv-head-cell');
        plan.append(element('strong', 'dashboard-tv-product-code', row.product_code || t('ui.no_value')));
        const planMeta = element('div', 'dashboard-tv-fields');
        planMeta.append(field(t('ui.plan_start'), displayDate(row.plan_start_date)));
        planMeta.append(field(t('ui.plan_end'), displayDate(row.plan_shipment_date)));
        planMeta.append(field(t('ui.plan_quantity'), number(row.planned_quantity)));
        planMeta.append(field(t('ui.produced'), number(row.finished_quantity)));
        plan.append(planMeta);
        head.append(line, plan);
        board.append(head);
        const kpis = element('div', 'dashboard-tv-kpis');
        kpis.append(kpi(t('ui.daily_target'), number(row.daily_target_quantity), 'blue'));
        kpis.append(kpi(t('ui.defect_rate'), row.has_defect_rate ? percent(row.defect_rate_percent) : t('ui.no_value'), 'green', row.defect_rate_unavailable_reason));
        kpis.append(kpi(t('ui.current_target'), number(row.current_target_quantity), 'blue'));
        kpis.append(kpi(t('ui.achievement'), percent(row.achievement_rate_percent), 'green'));
        board.append(kpis);
        if (!row.report_count || !row.has_defect_rate) {
            board.append(element('div', 'dashboard-tv-data-note', !row.report_count ? t('ui.no_report') : row.defect_rate_unavailable_reason || t('ui.no_quality_data')));
        }
        if (row.mixed_products) {
            const details = element('div', 'dashboard-tv-line-details');
            row.line_details.forEach(detail => details.append(lineDetail(detail)));
            board.append(details);
        }
        board.append(slotMatrix(row.time_slots || []));
        return board;
    }

    async function load() {
        clearTimeout(timer);
        status.textContent = t('ui.loading');
        let failure = t('ui.error');
        try {
            const url = new URL('/api/method/factory_dashboard.api.display', window.location.origin);
            url.searchParams.set('device_id', deviceId);
            url.searchParams.set('lang', root.dataset.lang || 'vi');
            const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
            const body = await response.json();
            if (!response.ok) {
                failure = serverMessage(body) || failure;
                throw new Error(failure);
            }
            const data = body.message;
            if (!data || !Array.isArray(data.lines)) throw new Error(failure);
            panels.replaceChildren(...data.lines.map(renderPanel));
            updateClock();
            panels.classList.toggle('dashboard-tv-panels-dual', data.display_mode === 'dual');
            document.getElementById('dashboard-date').textContent = displayDate(data.production_date);
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
    document.getElementById('fullscreen-button').addEventListener('click', () => {
        if (document.fullscreenElement) document.exitFullscreen();
        else document.documentElement.requestFullscreen();
    });
    document.querySelectorAll('.dashboard-tv-edge-trigger').forEach(trigger => {
        trigger.addEventListener('click', () => trigger.parentElement.classList.toggle('is-open'));
    });
    document.getElementById('reset-device-button').addEventListener('click', () => {
        clearTimeout(timer);
        window.localStorage.removeItem('factoryDashboardSession');
        const url = new URL(window.location.href);
        url.searchParams.delete('device_id');
        window.history.replaceState({}, '', url);
        panels.replaceChildren();
        document.getElementById('dashboard-device-id').value = '';
        form.hidden = false;
        document.getElementById('dashboard-device-id').focus();
    });
    setInterval(updateClock, 1000);
    if (deviceId) load();
    else form.hidden = false;
})();
