(() => {
const DEVICE_CONFIG_DOCTYPE = "Productivity Dashboard Device Config";
const SELECTION_METHOD =
	"factory_dashboard.factory_dashboard.doctype.productivity_dashboard_device_config.productivity_dashboard_device_config.get_available_selections";

function updateScreenDescriptions(frm) {
	const isDual = frm.doc.display_mode === "dual";
	frm.set_df_property(
		"left_screen_section", "description",
		__(isDual ? "The left screen is used in dual mode." : "The left screen is used in single mode."),
	);
	frm.set_df_property(
		"right_screen_section", "description",
		__(isDual ? "The right screen is used in dual mode." : "This selection is a backup and is not shown in single mode."),
	);
}

function currentSelection(frm, side) {
	if (frm.doc[`${side}_group`]) return `group:${frm.doc[`${side}_group`]}`;
	if (frm.doc[`${side}_line`]) return `line:${frm.doc[`${side}_line`]}`;
	return "";
}

function renderSelection(frm, side, options, placeholder) {
	const $wrapper = frm.fields_dict[`${side}_selection_html`].$wrapper;
	const selectId = `dashboard-${side}-selection`;
	const label = __("Displayed Line Configuration");
	const selected = currentSelection(frm, side);
	const permission = frm.perm && frm.perm[0];
	const canEdit = !permission || Boolean(frm.doc.__islocal ? permission.create : permission.write);
	const $select = $("<select class='form-control'>")
		.attr({ id: selectId, "aria-label": label })
		.prop("disabled", !frm.doc.device || !canEdit || !options);
	$select.append($("<option>").val("").text(placeholder));
	for (const option of options || []) {
		const kind = __(option.type === "group" ? "Line Group" : "Production Line");
		const description = [option.code, option.name].filter(Boolean).join(" - ");
		$select.append($("<option>").val(option.key).text(`${kind}: ${description}`));
	}
	if (selected && !(options || []).some((option) => option.key === selected)) {
		const kind = __(selected.startsWith("group:") ? "Line Group" : "Production Line");
		$select.append($("<option>").val(selected).text(
			`${kind}: ${selected.slice(selected.indexOf(":") + 1)} (${__("Unavailable")})`,
		));
	}
	$select.val(selected);
	$select.on("change", () => {
		const value = $select.val() || "";
		const isGroup = value.startsWith("group:");
		const name = value ? value.slice(value.indexOf(":") + 1) : null;
		frm.set_value({
			[`${side}_line`]: name && !isGroup ? name : null,
			[`${side}_group`]: name && isGroup ? name : null,
		});
	});
	$wrapper.empty().append(
		$("<div class='frappe-control'>").append(
			$("<label class='control-label'>").attr("for", selectId).text(label),
			$select,
		),
	);
}

async function loadSelections(frm) {
	const request = Symbol();
	frm._dashboardSelectionRequest = request;
	if (!frm.doc.device) {
		for (const side of ["left", "right"]) renderSelection(frm, side, null, __("Select a device first"));
		return;
	}
	for (const side of ["left", "right"]) renderSelection(frm, side, null, __("Loading configurations..."));
	try {
		const response = await frappe.call({
			method: SELECTION_METHOD,
			args: { device: frm.doc.device },
			type: "GET",
		});
		if (frm._dashboardSelectionRequest !== request) return;
		const options = response.message || [];
		for (const side of ["left", "right"]) {
			renderSelection(frm, side, options, __("Select a line or line group"));
		}
	} catch (error) {
		if (frm._dashboardSelectionRequest !== request) return;
		for (const side of ["left", "right"]) {
			renderSelection(frm, side, null, __("Could not load line configurations."));
		}
	}
}

frappe.ui.form.on(DEVICE_CONFIG_DOCTYPE, {
	refresh(frm) {
		updateScreenDescriptions(frm);
		loadSelections(frm);
	},
	async device(frm) {
		frm._dashboardSelectionRequest = Symbol();
		await frm.set_value({ left_line: null, left_group: null, right_line: null, right_group: null });
		loadSelections(frm);
	},
	display_mode(frm) {
		updateScreenDescriptions(frm);
	},
});
})();
