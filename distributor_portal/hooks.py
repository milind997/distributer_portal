app_name = "distributor_portal"
app_title = "Distributor Portal"
app_publisher = "Local Development"
app_description = "Distributor inventory, sell-out and replenishment"
app_email = "dev@example.invalid"
app_license = "mit"
required_apps = ["erpnext"]
app_icon_url = "/assets/distributor_portal/logo.svg"
app_icon_title = "Distributor Portal"
app_icon_route = "/distributor"
add_to_apps_screen = [
	{
		"name": "distributor_portal",
		"title": "Distributor Portal",
		"logo": app_icon_url,
		"route": "/distributor",
		"has_permission": "distributor_portal.permissions.check_app_permission",
	}
]
website_route_rules = [{"from_route": "/distributor/<path:app_path>", "to_route": "distributor"}]
before_install = "distributor_portal.setup.roles"
after_install = "distributor_portal.setup.after_install"
after_migrate = "distributor_portal.setup.after_install"
doc_events = {
	"Delivery Note": {
		"on_submit": "distributor_portal.integration.delivery_submit",
		"on_cancel": "distributor_portal.integration.delivery_cancel",
	}
}
scheduler_events = {"daily": ["distributor_portal.tasks.daily"]}

permission_query_conditions = {
	"Channel Partner": "distributor_portal.permissions.query_channel_partner",
	"Channel Outlet": "distributor_portal.permissions.query_channel_outlet",
	"Partner Serial": "distributor_portal.permissions.query_partner_serial",
	"Partner Stock Ledger": "distributor_portal.permissions.query_partner_stock_ledger",
	"Sell Out Entry": "distributor_portal.permissions.query_sell_out_entry",
	"Stock Declaration": "distributor_portal.permissions.query_stock_declaration",
	"Partner Order": "distributor_portal.permissions.query_partner_order",
	"Partner Return": "distributor_portal.permissions.query_partner_return",
	"Territory Flag": "distributor_portal.permissions.query_territory_flag",
	"Partner Forecast": "distributor_portal.permissions.query_partner_forecast",
}
has_permission = {
	"Distributor Portal Settings": "distributor_portal.permissions.has_permission",
	"Channel Partner": "distributor_portal.permissions.has_permission",
	"Channel Outlet": "distributor_portal.permissions.has_permission",
	"Partner Serial": "distributor_portal.permissions.has_permission",
	"Partner Stock Ledger": "distributor_portal.permissions.has_permission",
	"Sell Out Entry": "distributor_portal.permissions.has_permission",
	"Stock Declaration": "distributor_portal.permissions.has_permission",
	"Partner Order": "distributor_portal.permissions.has_permission",
	"Partner Return": "distributor_portal.permissions.has_permission",
	"Territory Flag": "distributor_portal.permissions.has_permission",
	"Partner Forecast": "distributor_portal.permissions.has_permission",
}
