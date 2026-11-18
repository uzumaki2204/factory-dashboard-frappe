(() => {
const DEVICE_CONFIG_DOCTYPE = "Productivity Dashboard Device Config";

function updateScreenDescriptions(frm) {
	const isDual = frm.doc.display_mode === "dual";
	frm.set_df_property(
		"left_screen_section",
		"description",
		__(isDual ? "The left screen is used in dual mode." : "The left screen is used in single mode."),
	);
	frm.set_df_property(
		"right_screen_section",
		"description",
		__(isDual ? "The right screen is used in dual mode." : "This selection is a backup and is not shown in single mode."),
	);
	frm.refresh_field("left_screen_section");
	frm.refresh_field("right_screen_section");
}

function setSelectionQueries(frm) {
	frm._dashboardConfigDeviceScope = null;
	const filtersFor = () => frm._dashboardConfigDeviceScope
		? { ...frm._dashboardConfigDeviceScope, is_active: 1 }
		: { name: ["=", ""] };
	for (const field of ["left_line", "right_line", "left_group", "right_group"]) {
		frm.set_query(field, () => ({ filters: filtersFor() }));
	}

	if (frm.doc.device) {
		const selectedDevice = frm.doc.device;
		frappe.db.get_value("Factory Device", selectedDevice, ["company", "factory"]).then((result) => {
			const device = result.message;
			if (frm.doc.device !== selectedDevice || !device || !device.factory || !device.company) return;

			frm._dashboardConfigDeviceScope = { company: device.company, factory: device.factory };
		});
	}
}

frappe.ui.form.on(DEVICE_CONFIG_DOCTYPE, {
	setup(frm) {
		setSelectionQueries(frm);
	},
	refresh(frm) {
		setSelectionQueries(frm);
		updateScreenDescriptions(frm);
	},
	device(frm) {
		setSelectionQueries(frm);
	},
	display_mode(frm) {
		updateScreenDescriptions(frm);
	},
	left_line(frm) {
		if (frm.doc.left_line) frm.set_value("left_group", null);
	},
	left_group(frm) {
		if (frm.doc.left_group) frm.set_value("left_line", null);
	},
	right_line(frm) {
		if (frm.doc.right_line) frm.set_value("right_group", null);
	},
	right_group(frm) {
		if (frm.doc.right_group) frm.set_value("right_line", null);
	},
});
})();
