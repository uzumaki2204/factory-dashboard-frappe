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
    const summaryLink = document.getElementById('summary-page-link');
    const summaryUrl = new URL('/productivity-dashboard-summary', window.location.origin);
    if (deviceId) summaryUrl.searchParams.set('device_id', deviceId);
    summaryUrl.searchParams.set('lang', root.dataset.lang || 'vi');
    summaryLink.href = summaryUrl.pathname + summaryUrl.search;
    const modeStorageKey = `factoryDashboardMode:${deviceId}`;
    const drawer = document.getElementById('dashboard-device-drawer');
    const backdrop = document.getElementById('dashboard-device-backdrop');
    const panelButton = document.getElementById('device-panel-button');
    const modeStatus = document.getElementById('dashboard-mode-status');
    const modeButtons = ['single', 'dual'].map(mode => document.getElementById(`dashboard-mode-${mode}`));
    const number = value => new Intl.NumberFormat(root.dataset.lang || 'vi').format(Number(value) || 0);
    const percent = value => {
        const numeric = Number(value) || 0;
        const decimals = Math.abs(numeric - Math.round(numeric)) < .05 ? 0 : 1;
        return `${numeric.toFixed(decimals)}%`;
    };
    let timer;
    let requestSequence = 0;
    let activeDevice = Boolean(deviceId);
    summaryLink.hidden = !activeDevice;
    let selectedMode = readSavedMode();
    let currentMode = null;

    function readSavedMode() {
        try {
            const value = window.localStorage.getItem(modeStorageKey);
            return value === 'single' || value === 'dual' ? value : null;
        } catch (_) {
            return null;
        }
    }

    function saveMode(mode) {
        try {
            if (mode) window.localStorage.setItem(modeStorageKey, mode);
            else window.localStorage.removeItem(modeStorageKey);
        } catch (_) {
            // The current page can still switch modes when storage is unavailable.
        }
    }

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
        board.append(slotMatrix(row.time_slots || []));
        return board;
    }

    function renderDevice(data) {
        const device = data.device || {};
        document.getElementById('dashboard-device-name').textContent = device.name || t('ui.no_value');
        document.getElementById('dashboard-device-code').textContent = device.id || deviceId;
        document.getElementById('dashboard-device-line').textContent =
            [device.registered_line_code, device.registered_line_name].filter(Boolean).join(' - ') || t('ui.no_value');
        const supported = Array.isArray(data.supported_modes) ? data.supported_modes : [data.display_mode];
        document.getElementById('dashboard-device-modes').textContent = supported.map(mode => t(`ui.mode_${mode}`)).join(' / ');
        currentMode = data.display_mode;
        modeButtons.forEach(button => {
            const mode = button.dataset.mode;
            button.disabled = !supported.includes(mode);
            button.setAttribute('aria-pressed', String(mode === currentMode));
            button.title = button.disabled ? t('ui.mode_unavailable') : '';
        });
    }

    async function load(requestedMode = selectedMode, commitMode = false) {
        const request = ++requestSequence;
        clearTimeout(timer);
        status.textContent = t('ui.loading');
        let failure = t('ui.error');
        try {
            const url = new URL('/api/method/factory_dashboard.api.display', window.location.origin);
            url.searchParams.set('device_id', deviceId);
            url.searchParams.set('lang', root.dataset.lang || 'vi');
            if (requestedMode) url.searchParams.set('mode', requestedMode);
            const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
            const body = await response.json();
            if (request !== requestSequence) return;
            if (!response.ok) {
                failure = serverMessage(body) || failure;
                throw new Error(failure);
            }
            const data = body.message;
            if (!data || !Array.isArray(data.lines)) throw new Error(failure);
            modeStatus.textContent = '';
            if (requestedMode && data.display_mode !== requestedMode) {
                if (commitMode) modeStatus.textContent = t('ui.mode_unavailable');
                else {
                    selectedMode = null;
                    saveMode(null);
                }
            } else if (commitMode) {
                selectedMode = requestedMode;
                saveMode(selectedMode);
                modeStatus.textContent = '';
            }
            panels.replaceChildren(...data.lines.map(renderPanel));
            updateClock();
            panels.classList.toggle('dashboard-tv-panels-dual', data.display_mode === 'dual');
            renderDevice(data);
            document.getElementById('dashboard-date').textContent = displayDate(data.production_date);
            document.getElementById('dashboard-source').textContent = `${t('ui.source')}: ${t(data.defect_rate_mode === 'uqqc_input' ? 'ui.uqqc_source' : 'ui.qc_source')}`;
            document.getElementById('dashboard-updated').textContent = `${t('ui.last_updated')}: ${new Date().toLocaleString(root.dataset.lang || 'vi')}`;
            status.textContent = t('ui.status_online');
            timer = setTimeout(() => load(), Math.max(10, Number(data.refresh_seconds) || 60) * 1000);
        } catch (_) {
            if (request !== requestSequence) return;
            if (commitMode) modeStatus.textContent = failure || t('ui.mode_switch_failed');
            else panels.replaceChildren();
            status.textContent = failure;
            timer = setTimeout(() => load(), 60000);
        }
    }

    function closeDrawer() {
        if (drawer.hidden) return;
        drawer.hidden = true;
        backdrop.hidden = true;
        document.body.classList.remove('dashboard-tv-drawer-open');
        panelButton.setAttribute('aria-expanded', 'false');
        panelButton.focus();
    }

    function openDrawer() {
        if (!activeDevice) return;
        drawer.hidden = false;
        backdrop.hidden = false;
        document.body.classList.add('dashboard-tv-drawer-open');
        panelButton.setAttribute('aria-expanded', 'true');
        document.getElementById('device-panel-close').focus();
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
    document.querySelectorAll('.dashboard-tv-edge-left .dashboard-tv-edge-trigger').forEach(trigger => {
        trigger.addEventListener('click', () => trigger.parentElement.classList.toggle('is-open'));
    });
    panelButton.disabled = !activeDevice;
    panelButton.addEventListener('click', openDrawer);
    backdrop.addEventListener('click', closeDrawer);
    document.getElementById('device-panel-close').addEventListener('click', closeDrawer);
    drawer.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            event.preventDefault();
            closeDrawer();
        } else if (event.key === 'Tab') {
            const focusable = Array.from(drawer.querySelectorAll('button:not([disabled]), a[href]:not([hidden])'));
            if (!focusable.length) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
    });
    modeButtons.forEach(button => {
        button.disabled = button.dataset.mode !== 'single';
        button.addEventListener('click', () => {
            if (button.dataset.mode !== currentMode) load(button.dataset.mode, true);
        });
    });
    document.getElementById('reset-device-button').addEventListener('click', () => {
        requestSequence += 1;
        clearTimeout(timer);
        saveMode(null);
        try { window.localStorage.removeItem('factoryDashboardSession'); } catch (_) { /* Storage is optional. */ }
        selectedMode = null;
        activeDevice = false;
        summaryLink.hidden = true;
        closeDrawer();
        panelButton.disabled = true;
        currentMode = null;
        modeButtons.forEach(button => { button.disabled = true; button.setAttribute('aria-pressed', 'false'); });
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
