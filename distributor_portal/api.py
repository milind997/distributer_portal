import csv
import io

import frappe
from frappe.utils import add_months, get_first_day, get_last_day, getdate, now_datetime, today

from distributor_portal import domain as d
from distributor_portal.permissions import (
	check_app_permission,
	is_manager,
	partner_names,
	require_manager,
	require_partner,
)

LISTS = {
	"stock": (
		"Partner Serial",
		[
			"name",
			"serial_no",
			"item_code",
			"batch_no",
			"length_m",
			"status",
			"received_on",
			"delivery_note",
			"channel_partner",
		],
	),
	"sales": (
		"Sell Out Entry",
		[
			"name",
			"channel_partner",
			"outlet",
			"posting_date",
			"bill_no",
			"total_reels",
			"territory_flagged",
			"docstatus",
		],
	),
	"orders": (
		"Partner Order",
		[
			"name",
			"channel_partner",
			"posting_date",
			"required_by",
			"total",
			"currency",
			"status",
			"sales_order",
			"docstatus",
		],
	),
	"declarations": (
		"Stock Declaration",
		["name", "channel_partner", "period", "method", "total_difference", "docstatus"],
	),
	"returns": (
		"Partner Return",
		["name", "channel_partner", "posting_date", "reason", "status", "credit_note", "docstatus"],
	),
	"flags": (
		"Territory Flag",
		[
			"name",
			"channel_partner",
			"serial_no",
			"holder_territory",
			"outlet_territory",
			"outlet",
			"status",
			"explanation",
			"resolution",
		],
	),
	"outlets": (
		"Channel Outlet",
		["name", "outlet_name", "channel_partner", "outlet_type", "territory", "approval_status"],
	),
	"partners": ("Channel Partner", ["name", "partner_name", "customer", "company", "territory", "active"]),
	"forecast": (
		"Partner Forecast",
		["name", "channel_partner", "period", "method", "suggested_total", "generated_on"],
	),
}


def access():
	if not check_app_permission():
		frappe.throw("Ask HQ to link your user to a distributor", frappe.PermissionError)


def scoped(partner):
	access()
	if partner:
		return require_partner(partner)
	if not is_manager():
		frappe.throw("Select your distributor", frappe.PermissionError)
	return None


@frappe.whitelist(methods=["GET"])
def bootstrap():
	access()
	filters = {} if is_manager() else {"name": ["in", partner_names()]}
	partners = frappe.get_all(
		"Channel Partner",
		filters=filters,
		fields=["name", "partner_name", "customer", "territory", "company", "active"],
		order_by="partner_name",
	)
	cfg = d.settings()
	return dict(
		user=frappe.session.user,
		full_name=frappe.db.get_value("User", frappe.session.user, "full_name"),
		manager=is_manager(),
		partners=partners,
		settings={
			k: cfg.get(k)
			for k in [
				"portal_title",
				"logo",
				"accent_colour",
				"support_email",
				"support_phone",
				"territory_rule",
				"outlet_approval_required",
				"declaration_due_day",
				"damage_window_days",
				"price_list",
				"company",
			]
		},
		today=today(),
	)


@frappe.whitelist(methods=["GET"])
def listing(view: str, partner: str = "", start: int = 0, search: str = ""):
	p = scoped(partner)
	if view not in LISTS:
		frappe.throw("Unknown list")
	if view == "partners":
		require_manager()
	dt, fields = LISTS[view]
	filters = {}
	if p:
		filters["name" if dt == "Channel Partner" else "channel_partner"] = p.name
	if dt in ("Sell Out Entry", "Stock Declaration", "Partner Return", "Partner Order"):
		filters["docstatus"] = ["!=", 2]
	or_filters = None
	if search:
		or_filters = [
			[f, "like", "%" + search[:100] + "%"]
			for f in fields
			if f in ("name", "serial_no", "item_code", "outlet_name", "partner_name", "status")
		]
	rows = frappe.get_all(
		dt,
		filters=filters,
		or_filters=or_filters,
		fields=fields,
		order_by="modified desc",
		start=max(0, start),
		limit_page_length=51,
	)
	return dict(rows=rows[:50], has_more=len(rows) > 50)


@frappe.whitelist(methods=["GET"])
def overview(partner: str = ""):
	p = scoped(partner)
	names = [p.name] if p else frappe.get_all("Channel Partner", filters={"active": 1}, pluck="name")
	data = []
	current = get_first_day(today())
	for name in names:
		partner_doc = frappe.get_doc("Channel Partner", name)
		inv = d.stock(name)
		acct = d.account(partner_doc)
		sold = d.consumption(name, current, today())
		previous = get_first_day(add_months(current, -1))
		declared = frappe.db.exists(
			"Stock Declaration", {"channel_partner": name, "period": previous, "docstatus": 1}
		)
		data.append(
			dict(
				name=name,
				partner_name=partner_doc.partner_name,
				territory=partner_doc.territory,
				stock=sum(x["qty"] for x in inv.values()),
				metres=sum(x["metres"] for x in inv.values()),
				sold=sum(sold.values()),
				in_transit=frappe.db.count(
					"Partner Serial", {"channel_partner": name, "status": "In transit"}
				),
				outstanding=acct["outstanding"],
				available=acct["available"],
				overdue=acct["overdue"],
				currency=acct["currency"],
				flags=frappe.db.count(
					"Territory Flag", {"channel_partner": name, "status": ["in", ["Open", "Explained"]]}
				),
				declaration="Submitted" if declared else "Pending",
			)
		)
	monthly = []
	for i in range(5, -1, -1):
		month = add_months(current, -i)
		end = get_last_day(month)
		sold = sum(sum(d.consumption(n, month, end).values()) for n in names)
		received = frappe.db.sql(
			"select coalesce(sum(qty_reels),0) from `tabPartner Stock Ledger` where channel_partner in %(names)s and posting_date between %(start)s and %(end)s and movement='Receipt'",
			dict(names=names or [""], start=month, end=end),
		)[0][0]
		monthly.append(dict(month=month.strftime("%b"), sold=sold, received=int(received)))
	return dict(
		partners=data,
		monthly=monthly,
		stock=sum(x["stock"] for x in data),
		in_transit=sum(x["in_transit"] for x in data),
		sold=sum(x["sold"] for x in data),
		flags=sum(x["flags"] for x in data),
		pending_declarations=sum(x["declaration"] == "Pending" for x in data),
	)


@frappe.whitelist(methods=["GET"])
def accounts(partner: str):
	p = require_partner(partner)
	data = d.account(p)
	data["ledger"] = frappe.get_all(
		"GL Entry",
		filters={"party_type": "Customer", "party": p.customer, "company": p.company, "is_cancelled": 0},
		fields=["posting_date", "voucher_type", "voucher_no", "debit", "credit"],
		order_by="posting_date desc,creation desc",
		limit_page_length=100,
	)
	return data


@frappe.whitelist(methods=["GET"])
def catalog(partner: str, search: str = ""):
	p = require_partner(partner)
	items = frappe.get_all(
		"Item",
		filters={"has_serial_no": 1, "is_sales_item": 1, "disabled": 0},
		or_filters=[
			["item_code", "like", "%" + search[:100] + "%"],
			["item_name", "like", "%" + search[:100] + "%"],
		]
		if search
		else None,
		fields=["name", "item_name", "stock_uom"],
		limit_page_length=100,
	)
	inv = d.stock(p.name)
	result = []
	for item in items:
		try:
			price = d.item_rate(item.name, p)
		except frappe.ValidationError:
			frappe.clear_messages()
			continue
		result.append(
			dict(
				item_code=item.name,
				item_name=item.item_name,
				stock=inv.get(item.name, {}).get("qty", 0),
				**price,
			)
		)
	return result


@frappe.whitelist(methods=["GET"])
def options(kind: str, partner: str = "", search: str = ""):
	p = scoped(partner)
	if kind in ("Customer", "Company", "User", "Price List", "Warehouse"):
		require_manager()
	allowed = {
		"Warehouse": {"is_group": 0, "disabled": 0},
		"Territory": {},
		"Customer": {"disabled": 0},
		"Company": {},
		"Price List": {"selling": 1, "enabled": 1},
		"User": {"enabled": 1, "name": ["not in", ["Guest", "Administrator"]]},
		"Channel Outlet": {"channel_partner": p.name if p else ""},
		"Address": {},
	}
	if kind not in allowed:
		frappe.throw("Unknown option type")
	filters = allowed[kind]
	if kind == "Address":
		if not p:
			frappe.throw("Select a distributor")
		filters = {
			"name": [
				"in",
				frappe.get_all(
					"Dynamic Link",
					filters={"parenttype": "Address", "link_doctype": "Customer", "link_name": p.customer},
					pluck="parent",
				),
			]
		}
	if search:
		filters["name"] = ["like", "%" + search[:100] + "%"] if kind != "Address" else filters.get("name")
	fields = ["name"] + (["outlet_name", "territory", "approval_status"] if kind == "Channel Outlet" else [])
	return frappe.get_all(kind, filters=filters, fields=fields, order_by="name", limit_page_length=200)


@frappe.whitelist(methods=["GET"])
def record(doctype: str, name: str):
	access()
	if doctype not in {x[0] for x in LISTS.values()} | {"Distributor Portal Settings"}:
		frappe.throw("Unsupported document")
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	if doctype not in ("Channel Partner", "Distributor Portal Settings"):
		require_partner(doc.channel_partner)
	result = doc.as_dict()
	if doctype == "Partner Serial":
		result["movements"] = frappe.get_all(
			"Partner Stock Ledger",
			filters={"serial_no": doc.name},
			fields=["posting_date", "movement", "qty_reels", "voucher_type", "voucher_no"],
			order_by="creation",
		)
	return result


@frappe.whitelist(methods=["POST"])
def submit_transaction(doctype: str, data: dict):
	access()
	allowed = {
		"Sell Out Entry",
		"Partner Order",
		"Partner Return",
		"Stock Declaration",
		"Channel Outlet",
		"Channel Partner",
	}
	if doctype not in allowed:
		frappe.throw("Unsupported transaction")
	if doctype == "Channel Partner":
		require_manager()
	else:
		require_partner(data.get("channel_partner"))
	# Only editable schema fields; never accept flags, ownership, status, or server totals.
	meta = frappe.get_meta(doctype)
	safe = {}
	for field in meta.fields:
		if field.read_only or field.fieldtype in ("Section Break", "Column Break", "Tab Break"):
			continue
		if field.fieldname in data:
			safe[field.fieldname] = data[field.fieldname]
	if "items" in safe:
		for row in safe["items"]:
			for key in ("qty_reels", "counted"):
				if row.get(key) is not None and float(row[key]) != int(float(row[key])):
					frappe.throw("Reel quantities must be whole numbers")
		childmeta = frappe.get_meta(meta.get_field("items").options)
		safe["items"] = [
			{
				f.fieldname: r.get(f.fieldname)
				for f in childmeta.fields
				if not f.read_only and f.fieldname not in ("decision",)
			}
			for r in safe["items"]
		]
	if doctype == "Channel Partner":
		safe["portal_users"] = [{"user": r.get("user")} for r in safe.get("portal_users", [])]
	doc = frappe.get_doc(dict(doctype=doctype, **safe))
	doc.insert()
	if meta.is_submittable:
		doc.submit()
	return dict(name=doc.name, status=doc.get("status"))


@frappe.whitelist(methods=["GET"])
def scan(serial_no: str, partner: str, for_return: bool = False):
	require_partner(partner)
	name = frappe.db.get_value("Partner Serial", {"serial_no": serial_no, "channel_partner": partner}, "name")
	if not name:
		frappe.throw("This reel is not in your stock. Check its label or contact HQ")
	s = d.serial(name, partner, None if for_return else "In stock")
	if for_return and s.status not in ("In stock", "Damaged"):
		frappe.throw("Only stock or damaged reels can be returned")
	return dict(name=s.name, serial_no=s.serial_no, item_code=s.item_code, length_m=s.length_m)


@frappe.whitelist(methods=["GET"])
def declaration_preview(partner: str, period: str):
	require_partner(partner)
	inv = d.stock(partner, get_last_day(period))
	return [
		dict(item_code=k, expected=v["qty"], counted=v["qty"], treatment="Sold, not scanned")
		for k, v in inv.items()
		if v["qty"]
	]


@frappe.whitelist(methods=["POST"])
def generate_forecast(partner: str):
	p = d.lock_partner(partner)
	period = get_first_day(add_months(today(), 1))
	key = p.name + ":" + str(period)
	name = frappe.db.get_value("Partner Forecast", {"period_key": key}, "name")
	doc = frappe.get_doc("Partner Forecast", name) if name else frappe.new_doc("Partner Forecast")
	doc.update(
		dict(
			channel_partner=p.name,
			period=period,
			period_key=key,
			generated_on=now_datetime(),
			method=d.settings().forecast_method,
		)
	)
	doc.set("items", d.forecast_rows(p, period))
	doc.suggested_total = sum(x.suggested_qty for x in doc.items)
	with d.internal():
		doc.save(ignore_permissions=True)
	return doc.as_dict()


@frappe.whitelist(methods=["POST"])
def receive_delivery(partner: str, delivery_note: str):
	d.lock_partner(partner)
	names = frappe.get_all(
		"Partner Serial",
		filters={"channel_partner": partner, "delivery_note": delivery_note, "status": "In transit"},
		pluck="name",
	)
	if not names:
		frappe.throw("No reels await receipt for this delivery")
	for name in names:
		frappe.get_doc("Partner Serial", name).acknowledge()
	return len(names)


@frappe.whitelist(methods=["POST"])
def save_settings(data: dict):
	require_manager()
	doc = d.settings()
	allowed = {x.fieldname for x in frappe.get_meta(doc.doctype).fields if not x.read_only}
	doc.update({k: v for k, v in data.items() if k in allowed})
	doc.save()
	return doc.as_dict()


@frappe.whitelist(methods=["GET"])
def export_stock(partner: str):
	require_partner(partner)
	rows = frappe.get_all(
		"Partner Serial", filters={"channel_partner": partner}, fields=LISTS["stock"][1], order_by="serial_no"
	)
	output = io.StringIO()
	writer = csv.writer(output)
	writer.writerow(LISTS["stock"][1])
	for row in rows:
		values = [str(row.get(k) or "") for k in LISTS["stock"][1]]
		writer.writerow(["'" + v if v.startswith(("=", "+", "-", "@")) else v for v in values])
	frappe.response.filename = "distributor-stock.csv"
	frappe.response.filecontent = output.getvalue()
	frappe.response.type = "download"
