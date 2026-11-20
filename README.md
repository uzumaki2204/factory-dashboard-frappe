# Factory Dashboard

Independent Frappe 16 app for productivity display. Requires `factory_management` and `factory_productivity`. The Desk page `/app/productivity-dashboard` is an administrative preview. The full-screen TV page is `/productivity-dashboard-tv?device_id=<Factory Device name>`. The device must be approved and assigned a production line. Without a `Productivity Dashboard Device Config`, the TV shows its home line in single mode. In single mode, the Left Screen selection is displayed and Right Screen remains a backup; in dual mode, both screen selections are displayed. Each screen can use an active production line or a valid two-line group in the device's factory. The TV page refreshes according to `Productivity Dashboard Settings.refresh_seconds`.

`Productivity Dashboard Settings.defect_rate_mode` accepts `qc_input` or `uqqc_input`. QC reads `QC Inspection Event` for QC1 devices and uses received quantity with signed defect events. UQQC reads `UQQC Inspection Event` and uses defect quantity divided by pass plus defect quantity, excluding rework. Quality figures are scoped to the active product, production date and configured lines. The presentation uses Frappe styling.

On the TV page, the device drawer can switch between Single and Dual when both screen selections are valid. The choice is saved in that browser for the current device and does not change the managed device configuration. Empty report and QC notes are hidden on TV; per-line QC figures appear only when that line has a report and checked quantity.

## Install and update

Install the two required apps first. Add this repository to the bench as app `factory_dashboard`, install it on the target site, then run `bench --site <site> migrate` and `bench build --app factory_dashboard`. Pilot should pull the `version-16` branch and run migrate and build on updates. Post-model-sync patches create the `GLOBAL` settings record, replace retired source modes with `qc_input`, migrate legacy device selections into Left and Right Screen, and refresh the two-selector device form. Installation does not import historical data.

The manual import workbook can stage device configuration from the .NET Admin API. Existing `Factory Device` and line/group links must be mapped before Data Import.
