(() => {
    'use strict';

    const root = document.querySelector('.summary-page');
    const texts = JSON.parse(document.getElementById('dashboard-texts').textContent);
    const t = key => texts[key] || '';
    const $ = id => document.getElementById(id);
    const params = new URLSearchParams(location.search);
    const deviceId = (params.get('device_id') || '').trim();
    const lang = root.dataset.lang || 'vi';
    const number = value => new Intl.NumberFormat(lang).format(Number(value) || 0);
    const escape = value => String(value ?? '').replace(/[&<>"']/g, character =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
    const dateKey = (year, month, day) => `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const today = new Date();
    const defaultMonth = dateKey(today.getFullYear(), today.getMonth() + 1, 1).slice(0, 7);
    const initialMonth = /^\d{4}-(0[1-9]|1[0-2])$/.test(params.get('month') || '') ? params.get('month') : defaultMonth;
    const state = {
        month: initialMonth, company: params.get('company_code') || '',
        factory: params.get('factory_code') || '', product: params.get('product_code') || ''
    };
    if (!state.company) state.factory = '';
    let draft = { ...state };
    let payload = null;
    let selectedDate = '';
    let timer;
    let sequence = 0;
    let previousFocus = null;

    const tvUrl = new URL('/productivity-dashboard-tv', location.origin);
    if (deviceId) tvUrl.searchParams.set('device_id', deviceId);
    tvUrl.searchParams.set('lang', lang);
    $('summary-back').href = tvUrl.pathname + tvUrl.search;

    function setStatus(key) { $('summary-status').textContent = key ? t(key) : ''; }
    function option(value, label) { const node = document.createElement('option'); node.value = value; node.textContent = label; return node; }
    function monthDates(month) {
        const [year, part] = month.split('-').map(Number);
        const last = new Date(year, part, 0).getDate();
        return [dateKey(year, part, 1), dateKey(year, part, last), year, part, last];
    }
    function monthLabel(month) {
        const [, , year, part] = monthDates(month);
        return `${t('ui.summary_month')} ${part}/${year}`;
    }
    function shiftMonth(delta) {
        const [, , year, month] = monthDates(state.month);
        const next = new Date(year, month - 1 + delta, 1);
        state.month = dateKey(next.getFullYear(), next.getMonth() + 1, 1).slice(0, 7);
        draft.month = state.month;
        Object.assign(state, draft);
        selectedDate = '';
        closeModal();
        load();
    }
    function updateUrl() {
        const url = new URL(location.href);
        url.searchParams.set('month', state.month);
        for (const [key, value] of [['company_code', state.company], ['factory_code', state.factory], ['product_code', state.product]]) {
            if (value) url.searchParams.set(key, value);
            else url.searchParams.delete(key);
        }
        history.replaceState(null, '', url);
    }
    function selectOptions(id, values, selected, emptyLabel) {
        const node = $(id);
        node.replaceChildren(option('', t(emptyLabel)), ...values.map(row => option(row.code, row.name ? `${row.code} - ${row.name}` : row.code)));
        node.value = values.some(row => row.code === selected) ? selected : '';
    }
    function syncOptions() {
        if (!payload) return;
        selectOptions('summary-company', payload.companies || [], draft.company, 'ui.all_companies');
        const factories = (payload.factories || []).filter(row => !draft.company || row.company_code === draft.company);
        if (!factories.some(row => row.code === draft.factory)) draft.factory = '';
        selectOptions('summary-factory', factories, draft.factory, 'ui.all_factories');
        $('summary-factory').disabled = !draft.company;
        const products = (payload.products || []).filter(row =>
            (!draft.company || row.company_code === draft.company) &&
            (!draft.factory || row.factory_code === draft.factory));
        const distinct = [...new Map(products.map(row => [row.code, row])).values()].sort((a, b) => a.code.localeCompare(b.code));
        if (!distinct.some(row => row.code === draft.product)) draft.product = '';
        selectOptions('summary-product', distinct, draft.product, 'ui.all_products');
    }
    function rowsForDay(day) { return (payload?.entries || []).filter(row => row.production_date === day); }
    function dailyTotals() {
        const map = new Map();
        for (const row of payload?.entries || []) {
            if (!map.has(row.production_date)) map.set(row.production_date, []);
            map.get(row.production_date).push(row);
        }
        return map;
    }
    function renderOverview() {
        const entries = payload.entries || [];
        $('summary-total').textContent = number(entries.reduce((total, row) => total + Number(row.produced_quantity || 0), 0));
        $('summary-companies').textContent = number(new Set(entries.map(row => row.company_code)).size);
        $('summary-groups').textContent = number(new Set(entries.map(row => `${row.company_code}|${row.factory_code}|${row.line_code}`)).size);
        $('summary-products').textContent = number(new Set(entries.map(row => row.product_code)).size);
        $('summary-generated').textContent = `${t('ui.summary_generated')} ${new Date(payload.generated_at).toLocaleString(lang)}`;
    }
    function renderCalendar() {
        const [, , year, month, last] = monthDates(state.month);
        $('summary-month-label').textContent = monthLabel(state.month);
        $('summary-calendar-title').textContent = monthLabel(state.month);
        $('summary-weekdays').innerHTML = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'].map(day =>
            `<span>${escape(t(`ui.weekday_${day}`))}</span>`).join('');
        const totals = dailyTotals();
        const blanks = (new Date(year, month - 1, 1).getDay() + 6) % 7;
        const cells = Array.from({ length: blanks }, () => '<div class="summary-calendar-blank"></div>');
        for (let day = 1; day <= last; day += 1) {
            const key = dateKey(year, month, day);
            const entries = totals.get(key) || [];
            const total = entries.reduce((sum, row) => sum + Number(row.produced_quantity || 0), 0);
            const products = new Map();
            for (const row of entries) products.set(row.product_code, (products.get(row.product_code) || 0) + Number(row.produced_quantity || 0));
            const top = [...products].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0];
            const groups = new Set(entries.map(row => `${row.company_code}|${row.factory_code}|${row.line_code}`)).size;
            cells.push(`<button type="button" class="summary-day${entries.length ? ' has-data' : ''}${key === selectedDate ? ' selected' : ''}" data-day="${key}" ${entries.length ? '' : 'disabled'} aria-label="${escape(`${day} ${monthLabel(state.month)}: ${number(total)} ${t('ui.summary_total_output')}`)}"><strong>${String(day).padStart(2, '0')}</strong><span>${escape(top?.[0] || t('ui.no_value'))}</span><b>${entries.length ? number(total) : t('ui.no_value')}</b><small>${entries.length ? `${number(groups)} ${escape(t('ui.summary_groups_short'))} · ${number(products.size)} ${escape(t('ui.summary_products_short'))}` : ''}</small></button>`);
        }
        $('summary-calendar').innerHTML = cells.join('');
    }
    function emptyRow(columns) { return `<tr><td colspan="${columns}" class="summary-empty">${escape(t('ui.summary_empty'))}</td></tr>`; }
    function renderProductTotals() {
        const rows = payload.product_totals || [];
        $('summary-product-totals').innerHTML = rows.length ? rows.map(row =>
            `<tr><td>${escape(row.code)}</td><td>${number(row.total_produced)}</td><td>${number(row.cumulative_produced)}</td></tr>`).join('') : emptyRow(3);
    }
    function renderMatrix() {
        const [, , , , days] = monthDates(state.month);
        const columns = Array.from({ length: days }, (_, index) => index + 1);
        $('summary-matrix-head').innerHTML = `<tr><th>${escape(t('ui.summary_company'))}</th><th>${escape(t('ui.product'))}</th><th>${escape(t('ui.summary_group_count'))}</th>${columns.map(day => `<th>${day}</th>`).join('')}<th>${escape(t('ui.summary_total_output'))}</th><th>${escape(t('ui.summary_cumulative'))}</th></tr>`;
        const grouped = new Map();
        for (const entry of payload.entries || []) {
            const key = [entry.company_code, entry.factory_code, entry.product_code, entry.line_code].join('|');
            if (!grouped.has(key)) grouped.set(key, { entry, days: new Map(), total: 0 });
            const row = grouped.get(key);
            const day = Number(entry.production_date.slice(-2));
            row.days.set(day, (row.days.get(day) || 0) + Number(entry.produced_quantity || 0));
            row.total += Number(entry.produced_quantity || 0);
        }
        $('summary-matrix-body').innerHTML = grouped.size ? [...grouped.values()].map(({ entry, days: values, total }) =>
            `<tr><td>${escape(entry.company_name)}</td><td>${escape(entry.product_code)}</td><td>${escape(entry.line_code)}</td>${columns.map(day => `<td>${values.has(day) ? number(values.get(day)) : ''}</td>`).join('')}<td>${number(total)}</td><td>${number(entry.cumulative_produced)}</td></tr>`).join('') : emptyRow(days + 5);
    }
    function renderChart() {
        const [, , year, month, days] = monthDates(state.month);
        const totals = dailyTotals();
        const values = Array.from({ length: days }, (_, index) => {
            const date = dateKey(year, month, index + 1);
            return (totals.get(date) || []).reduce((sum, row) => sum + Number(row.produced_quantity || 0), 0);
        });
        const peak = Math.max(...values, 1);
        const points = values.map((value, index) => `${40 + index * 25},${170 - value / peak * 130}`).join(' ');
        $('summary-chart').innerHTML = values.some(Boolean) ? `<svg viewBox="0 0 ${Math.max(850, 80 + days * 25)} 210" role="img" aria-label="${escape(t('ui.summary_chart'))}"><line x1="40" y1="170" x2="${40 + (days - 1) * 25}" y2="170" stroke="#b7c8d3"/><polyline fill="none" stroke="#23617a" stroke-width="3" points="${points}"/>${values.map((value, index) => `<circle cx="${40 + index * 25}" cy="${170 - value / peak * 130}" r="${dateKey(year, month, index + 1) === selectedDate ? 6 : 3}" fill="#246c89"><title>${index + 1}/${month}: ${number(value)}</title></circle>`).join('')}</svg>` : `<p class="summary-empty">${escape(t('ui.summary_empty'))}</p>`;
    }
    function tableRows(items, columns, cells) {
        return items.length ? items.map(item => `<tr>${cells(item).map(cell => `<td>${escape(cell)}</td>`).join('')}</tr>`).join('') : emptyRow(columns);
    }
    function openDay(day) {
        const entries = rowsForDay(day);
        if (!entries.length) return;
        selectedDate = day;
        renderCalendar();
        renderChart();
        $('summary-modal-title').textContent = `${t('ui.summary_day_detail')} ${day.split('-').reverse().join('/')}`;
        const products = new Map();
        const companies = new Map();
        for (const row of entries) {
            const quantity = Number(row.produced_quantity || 0);
            products.set(row.product_code, (products.get(row.product_code) || 0) + quantity);
            const key = `${row.company_code}|${row.product_code}`;
            const value = companies.get(key) || { company: row.company_name, product: row.product_code, quantity: 0 };
            value.quantity += quantity;
            companies.set(key, value);
        }
        $('summary-modal-stats').textContent = `${t('ui.summary_total_output')}: ${number(entries.reduce((sum, row) => sum + Number(row.produced_quantity || 0), 0))} · ${t('ui.summary_group_count')}: ${number(new Set(entries.map(row => row.line_code)).size)} · ${t('ui.summary_product_count')}: ${number(products.size)}`;
        $('summary-modal-products').innerHTML = tableRows([...products], 2, item => [item[0], number(item[1])]);
        $('summary-modal-companies').innerHTML = tableRows([...companies.values()], 3, item => [item.company, item.product, number(item.quantity)]);
        $('summary-modal-lines').innerHTML = tableRows(entries, 5, row => [row.company_name, row.factory_name, row.line_code, row.product_code, number(row.produced_quantity)]);
        previousFocus = document.activeElement;
        $('summary-modal').hidden = false;
        $('summary-modal-close').focus();
    }
    function closeModal() {
        if ($('summary-modal').hidden) return;
        $('summary-modal').hidden = true;
        previousFocus?.focus();
    }
    function render() {
        renderOverview(); renderCalendar(); renderProductTotals(); renderMatrix(); renderChart(); syncOptions();
    }
    async function load() {
        const request = ++sequence;
        clearTimeout(timer);
        setStatus('ui.loading');
        const [dateFrom, dateTo] = monthDates(state.month);
        const query = new URLSearchParams({ device_id: deviceId, date_from: dateFrom, date_to: dateTo,
            company_code: state.company, factory_code: state.factory, product_code: state.product, lang });
        try {
            const response = await fetch(`/api/method/factory_dashboard.api.productivity_summary?${query}`, { cache: 'no-store', credentials: 'same-origin' });
            const body = await response.json();
            if (request !== sequence) return;
            if (!response.ok || !body.message) {
                let detail = '';
                try {
                    const messages = JSON.parse(body._server_messages || '[]');
                    detail = messages.length ? JSON.parse(messages[0]).message || '' : '';
                } catch (_) { /* Use the translated fallback below. */ }
                throw new Error(detail || t('ui.summary_load_failed'));
            }
            payload = body.message;
            if (!selectedDate || !rowsForDay(selectedDate).length) selectedDate =
                (payload.entries || []).map(row => row.production_date).sort().at(-1) || '';
            render(); updateUrl(); setStatus('ui.status_online');
        } catch (error) {
            if (request !== sequence) return;
            $('summary-status').textContent = error.message || t('ui.summary_load_failed');
        } finally {
            if (request === sequence) timer = setTimeout(load, 300000);
        }
    }
    $('summary-company').addEventListener('change', event => { draft.company = event.target.value; draft.factory = ''; draft.product = ''; syncOptions(); });
    $('summary-factory').addEventListener('change', event => { draft.factory = event.target.value; draft.product = ''; syncOptions(); });
    $('summary-product').addEventListener('change', event => { draft.product = event.target.value; });
    $('summary-prev').addEventListener('click', () => shiftMonth(-1));
    $('summary-next').addEventListener('click', () => shiftMonth(1));
    $('summary-apply').addEventListener('click', () => { Object.assign(state, draft); selectedDate = ''; closeModal(); load(); });
    $('summary-reset').addEventListener('click', () => { Object.assign(state, { company: '', factory: '', product: '' }); draft = { ...state }; selectedDate = ''; closeModal(); load(); });
    $('summary-calendar').addEventListener('click', event => { const button = event.target.closest('[data-day]'); if (button) openDay(button.dataset.day); });
    $('summary-modal').addEventListener('click', event => { if (event.target.closest('[data-close], #summary-modal-close')) closeModal(); });
    document.addEventListener('keydown', event => {
        if ($('summary-modal').hidden) return;
        if (event.key === 'Escape') closeModal();
        if (event.key === 'Tab') { event.preventDefault(); $('summary-modal-close').focus(); }
    });
    load();
})();
