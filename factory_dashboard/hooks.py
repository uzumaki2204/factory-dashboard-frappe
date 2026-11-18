from factory_dashboard.i18n import message

app_name = "factory_dashboard"
app_title = "Factory Dashboard"
app_publisher = "Onichan"
app_description = "Productivity dashboard in Frappe Desk"
app_email = ""
app_license = "Proprietary"
required_apps = ["factory_management", "factory_productivity"]
add_to_apps_screen = [{
    "name": app_name,
    "title": message("ui.app_short_title", lang="vi"),
    "logo": "/assets/factory_dashboard/images/dashboard.svg",
    "route": "/desk/productivity-dashboard",
    "has_permission": "factory_dashboard.access.can_open",
}]
before_install = "factory_dashboard.install.before_install"
after_install = "factory_dashboard.install.after_migrate"
after_migrate = "factory_dashboard.install.after_migrate"
doctype_js = {
    "Productivity Dashboard Device Config": "public/js/productivity_dashboard_device_config.js",
}
