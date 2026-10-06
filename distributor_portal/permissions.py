import frappe

MANAGERS = {"System Manager", "Channel Manager"}
GENERATED = {"Partner Serial", "Partner Stock Ledger", "Partner Forecast", "Territory Flag"}


def is_manager(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(MANAGERS.intersection(frappe.get_roles(user)))


def require_manager():
	if not is_manager():
		frappe.throw("Only a channel manager can perform this action", frappe.PermissionError)


def partner_names(user=None):
	user = user or frappe.session.user
	if user == "Guest":
		return []
	names = frappe.get_all(
		"Partner Portal User", filters={"user": user, "parenttype": "Channel Partner"}, pluck="parent"
	)
	return (
		frappe.get_all("Channel Partner", filters={"name": ["in", names], "active": 1}, pluck="name")
		if names
		else []
	)


def require_partner(name):
	if not name or (not is_manager() and name not in partner_names()):
		frappe.throw("You do not have access to this distributor", frappe.PermissionError)
	partner = frappe.get_doc("Channel Partner", name)
	if not partner.active:
		frappe.throw("This distributor is inactive")
	return partner


def check_app_permission():
	if frappe.session.user == "Guest":
		return False
	return is_manager() or bool(partner_names())


def has_permission(doc, user=None, permission_type=None, **kwargs):
	user = user or frappe.session.user
	ptype = permission_type or kwargs.get("ptype") or "read"
	if is_manager(user):
		return True
	if doc.doctype == "Distributor Portal Settings":
		return False
	if ptype not in ("read", "select", "print", "export") and doc.doctype in GENERATED | {"Channel Partner"}:
		return False
	name = doc.name if doc.doctype == "Channel Partner" else doc.get("channel_partner")
	return bool(name and name in partner_names(user))


def query_for(doctype, user=None):
	if is_manager(user):
		return ""
	names = partner_names(user)
	field = "name" if doctype == "Channel Partner" else "channel_partner"
	return (
		"`tab%s`.`%s` in (%s)" % (doctype, field, ",".join(frappe.db.escape(n) for n in names))
		if names
		else "1=0"
	)


def query_channel_partner(user=None):
	return query_for("Channel Partner", user)


def query_channel_outlet(user=None):
	return query_for("Channel Outlet", user)


def query_partner_serial(user=None):
	return query_for("Partner Serial", user)


def query_partner_stock_ledger(user=None):
	return query_for("Partner Stock Ledger", user)


def query_sell_out_entry(user=None):
	return query_for("Sell Out Entry", user)


def query_stock_declaration(user=None):
	return query_for("Stock Declaration", user)


def query_partner_order(user=None):
	return query_for("Partner Order", user)


def query_partner_return(user=None):
	return query_for("Partner Return", user)


def query_territory_flag(user=None):
	return query_for("Territory Flag", user)


def query_partner_forecast(user=None):
	return query_for("Partner Forecast", user)
