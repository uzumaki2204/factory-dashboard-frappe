# Factory Dashboard

Independent Frappe 16 app for productivity display. Requires `factory_management` and `factory_productivity`. The Desk page `/app/productivity-dashboard` uses Frappe controls and cards, with no copied .NET styles. Device configuration and global defect-rate mode are DocTypes. The mode `qc_input` reads `QC Inspection Event`; `qcbrother_input` and `brother` are retained as settings but show an unavailable result until corresponding QC sources are present in Frappe.

## Install and update

Install the two required apps first. Add this repository to the bench as app `factory_dashboard`, install it on the target site, then run `bench --site <site> migrate`. Pilot should pull the `version-16` branch and run migrate on updates. The post-model-sync patch creates the `GLOBAL` settings record. Installation does not import historical data.

The manual import workbook can stage device configuration from the .NET Admin API. Existing `Factory Device` and line/group links must be mapped before Data Import.
