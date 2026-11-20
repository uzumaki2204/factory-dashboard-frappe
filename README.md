# Factory Dashboard

Independent Frappe 16 app for productivity display. Requires `factory_management` and `factory_productivity`. The Desk page `/app/productivity-dashboard` is an administrative preview. The full-screen TV page is `/productivity-dashboard-tv?device_id=<Factory Device name>`. The device must be approved and assigned a production line. Without a `Productivity Dashboard Device Config`, the TV shows its home line in single mode. In single mode, the Left Screen selection is displayed and Right Screen remains a backup; in dual mode, both screen selections are displayed. Each screen can use an active production line or a valid two-line group in the device's factory. The TV page refreshes according to `Productivity Dashboard Settings.refresh_seconds`.

`Productivity Dashboard Settings.defect_rate_mode` accepts `qc_input` or `uqqc_input`. QC reads `QC Inspection Event` for QC1 devices and uses received quantity with signed defect events. UQQC reads `UQQC Inspection Event` and uses defect quantity divided by pass plus defect quantity, excluding rework. Quality figures are scoped to the active product, production date and configured lines. The presentation uses Frappe styling.

On the TV page, the device drawer can switch between Single and Dual when both screen selections are valid. The choice is saved in that browser for the current device and does not change the managed device configuration. Empty report and QC notes are hidden on TV. A combined panel displays its aggregate KPIs and time slots without a separate list of its source lines.

The TV control at the left edge opens `/productivity-dashboard-summary?device_id=<Factory Device name>`. This monthly view shows production KPIs, calendar, product totals, daily matrix, chart and per-day details. Its read-only API requires an approved device and summarizes all companies and factories, as in the .NET Dashboard Summary. Output is the sum of report time-slot quantities; cumulative totals include all historical reports within the selected company, factory and product filters. The page refreshes every five minutes.

## Install and update

Install the two required apps first. Add this repository to the bench as app `factory_dashboard`, install it on the target site, then run `bench --site <site> migrate` and `bench build --app factory_dashboard`. Pilot should pull the `version-16` branch and run migrate and build on updates. Post-model-sync patches create the `GLOBAL` settings record, replace retired source modes with `qc_input`, migrate legacy device selections into Left and Right Screen, and refresh the two-selector device form. Installation does not import historical data.

The manual import workbook can stage device configuration from the .NET Admin API. Existing `Factory Device` and line/group links must be mapped before Data Import.
