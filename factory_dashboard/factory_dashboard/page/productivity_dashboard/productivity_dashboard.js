frappe.pages['productivity-dashboard'].on_page_load = async function (wrapper) {
    const catalog = await frappe.call({ method: 'factory_dashboard.api.translations', args: { lang: frappe.boot.lang || 'vi' } });
    const texts = catalog.message || {};
    const t = key => texts[key] || '';
    const page = frappe.ui.make_app_page({ parent: wrapper, title: t('ui.title'), single_column: true });
    const body = $(page.body);
    page.add_field({ fieldtype: 'Date', fieldname: 'production_date', label: t('ui.date'), default: frappe.datetime.get_today(), change: load });
    const device = page.add_field({ fieldtype: 'Link', fieldname: 'device_id', label: t('ui.device'), options: 'Factory Device', change: load });
    const output = $('<div class="row"></div>').appendTo(body);
    page.set_primary_action(t('ui.refresh'), load);
    page.add_button(t('ui.open_tv'), () => {
        const deviceId = device.get_value();
        if (!deviceId) {
            frappe.msgprint(t('ui.device_prompt'));
            return;
        }
        window.open(`/productivity-dashboard-tv?device_id=${encodeURIComponent(deviceId)}`, '_blank', 'noopener');
    });

    async function load() {
        const device_id = device.get_value();
        if (!device_id) return;
        try {
            const response = await frappe.call({ method: 'factory_dashboard.api.display', args: { device_id, production_date: page.fields_dict.production_date.get_value() } });
            output.empty();
            for (const row of response.message.lines) {
                const card = $('<div class="col-md-6 mb-3"><div class="frappe-card p-4"><h3></h3><div class="row"></div></div></div>');
                card.find('h3').text([row.line_name || row.line, row.product_code].filter(Boolean).join(' · '));
                const grid = card.find('.row');
                for (const [label, value] of [
                    [t('ui.output'), row.finished_quantity], [t('ui.target'), row.daily_target_quantity],
                    [t('ui.defects'), row.defect_quantity], [t('ui.defect_rate'), row.has_defect_rate ? `${row.defect_rate_percent}%` : row.defect_rate_unavailable_reason]
                ]) {
                    const cell = $('<div class="col-sm-6 mb-2"><div class="text-muted"></div><div class="h4"></div></div>');
                    cell.find('.text-muted').text(label);
                    cell.find('.h4').text(value);
                    grid.append(cell);
                }
                output.append(card);
            }
        } catch (error) {
            frappe.msgprint(t('ui.error'));
        }
    }
};
