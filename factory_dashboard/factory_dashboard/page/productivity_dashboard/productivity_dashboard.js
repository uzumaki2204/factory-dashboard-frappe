frappe.pages['productivity-dashboard'].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({ parent: wrapper, title: __('Productivity Dashboard'), single_column: true });
    const body = $(page.body);
    page.add_field({ fieldtype: 'Date', fieldname: 'production_date', label: __('Production Date'), default: frappe.datetime.get_today(), change: load });
    const device = page.add_field({ fieldtype: 'Link', fieldname: 'device_id', label: __('Factory Device'), options: 'Factory Device', change: load });
    const output = $('<div class="row"></div>').appendTo(body);
    page.set_primary_action(__('Refresh'), load);

    async function load() {
        const device_id = device.get_value();
        if (!device_id) return;
        try {
            const response = await frappe.call({ method: 'factory_dashboard.api.display', args: { device_id, production_date: page.fields_dict.production_date.get_value() } });
            output.empty();
            for (const row of response.message.lines) {
                const card = $('<div class="col-md-6 mb-3"><div class="frappe-card p-4"><h3></h3><div class="row"></div></div></div>');
                card.find('h3').text(row.line_name || row.line);
                const grid = card.find('.row');
                for (const [label, value] of [
                    [__('Output'), row.finished_quantity], [__('Target'), row.daily_target_quantity],
                    [__('QC defects'), row.defect_quantity], [__('Defect rate'), row.has_defect_rate ? `${row.defect_rate_percent}%` : row.defect_rate_unavailable_reason]
                ]) {
                    const cell = $('<div class="col-sm-6 mb-2"><div class="text-muted"></div><div class="h4"></div></div>');
                    cell.find('.text-muted').text(label);
                    cell.find('.h4').text(value);
                    grid.append(cell);
                }
                output.append(card);
            }
        } catch (error) {
            frappe.msgprint(__('Could not load dashboard.'));
        }
    }
};
