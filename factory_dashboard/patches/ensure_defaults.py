from factory_dashboard.install import after_migrate


def execute():
    after_migrate()
