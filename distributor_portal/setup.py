import json

import frappe

from distributor_portal.schema import SCHEMAS

PARTNER_WRITE = {"Channel Outlet", "Sell Out Entry", "Stock Declaration", "Partner Order", "Partner Return"}
READ_ONLY = {"Partner Serial", "Partner Stock Ledger", "Partner Forecast", "Territory Flag"}


def roles():
	for name, desk in [("Channel Partner", 0), ("Channel Manager", 1)]:
		if not frappe.db.exists("Role", name):
			frappe.get_doc(dict(doctype="Role", role_name=name, desk_access=desk)).insert(
				ignore_permissions=True
			)


def bootstrap_schema():
	roles()
	pending = list(SCHEMAS)
	ordered = []
	all_names = {x["name"] for x in SCHEMAS}
	while pending:
		ready = [
			x
			for x in pending
			if all(
				f.get("options") not in all_names
				or f.get("options") == x["name"]
				or f.get("options") in {v["name"] for v in ordered}
				for f in x["fields"]
				if f["fieldtype"] in ("Link", "Table")
			)
		]
		if not ready:
			raise RuntimeError("Circular schema dependencies")
		for x in ready:
			ordered.append(x)
			pending.remove(x)
	for definition in ordered:
		d = dict(definition)
		if not d["istable"]:
			d["permissions"] = [
				dict(
					role=r,
					read=1,
					write=1,
					create=1,
					delete=0,
					submit=d["is_submittable"],
					cancel=d["is_submittable"],
					report=1,
					export=1,
				)
				for r in ["System Manager", "Channel Manager"]
			]
			if d["name"] != "Distributor Portal Settings":
				d["permissions"].append(
					dict(
						role="Channel Partner",
						read=1,
						write=int(d["name"] in PARTNER_WRITE),
						create=int(d["name"] in PARTNER_WRITE),
						submit=d["is_submittable"],
						export=1,
					)
				)
		if not frappe.db.exists("DocType", d["name"]):
			frappe.get_doc(d).insert(ignore_permissions=True)
	after_install()
	frappe.db.commit()


def after_install():
	roles()
	if not frappe.db.exists("DocType", "Distributor Portal Settings"):
		return
	from frappe.permissions import add_permission, update_permission_property

	for doctype, rights in {
		"Sales Order": ("read", "create", "write", "select"),
		"Customer": ("read", "select"),
		"Item": ("read", "select"),
		"Company": ("read", "select"),
		"Warehouse": ("read", "select"),
		"Price List": ("read", "select"),
		"Territory": ("read", "select"),
	}.items():
		if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": "Channel Manager"}):
			add_permission(doctype, "Channel Manager", ptype="read")
			for right in rights:
				update_permission_property(doctype, "Channel Manager", 0, right, 1)
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Item": [
				dict(
					fieldname="distributor_reel_length",
					label="Distributor Reel Length (m)",
					fieldtype="Float",
					insert_after="has_serial_no",
					default="305",
				)
			],
			"Sales Order": [
				dict(
					fieldname="distributor_partner_order",
					label="Distributor Partner Order",
					fieldtype="Link",
					options="Partner Order",
					read_only=1,
					insert_after="customer",
				)
			],
		}
	)
	shortcuts = [
		dict(type="URL", label="Open Distributor Portal", url="/distributor", icon="package"),
		dict(type="DocType", label="Channel Partners", link_to="Channel Partner"),
		dict(type="DocType", label="Portal Settings", link_to="Distributor Portal Settings"),
	]
	if not frappe.db.exists("Workspace", "Distributor Portal"):
		frappe.get_doc(
			dict(
				doctype="Workspace",
				label="Distributor Portal",
				title="Distributor Portal",
				module="Distributor Portal",
				app="distributor_portal",
				public=1,
				icon="package",
				shortcuts=shortcuts,
				roles=[dict(role="Channel Manager"), dict(role="System Manager")],
				content=json.dumps(
					[dict(id="title", type="header", data=dict(text="Distributor Portal", col=12))]
					+ [
						dict(id="s" + str(i), type="shortcut", data=dict(shortcut_name=s["label"], col=4))
						for i, s in enumerate(shortcuts)
					]
				),
			)
		).insert(ignore_permissions=True)
	if frappe.db.exists("DocType", "Desktop Icon"):
		if frappe.db.exists("Desktop Icon", "Open Distributor Portal"):
			frappe.delete_doc("Desktop Icon", "Open Distributor Portal", ignore_permissions=True)
		if frappe.db.exists("Desktop Icon", "Distributor Portal"):
			icon = frappe.get_doc("Desktop Icon", "Distributor Portal")
		else:
			icon = frappe.new_doc("Desktop Icon")
		icon.update(
			dict(
				label="Distributor Portal",
				icon_type="App",
				link_type="External",
				link="/distributor",
				app="distributor_portal",
				logo_url="/assets/distributor_portal/logo.svg",
				standard=1,
				hidden=0,
			)
		)
		icon.save(ignore_permissions=True)
	cfg = frappe.get_single("Distributor Portal Settings")
	if not cfg.price_list:
		price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
		if price_list and frappe.db.exists("Price List", price_list):
			cfg.price_list = price_list
			cfg.save(ignore_permissions=True)
	frappe.clear_cache()
