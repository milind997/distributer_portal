import math
from contextlib import contextmanager
from hashlib import sha256

import frappe
from frappe.utils import add_months, flt, get_first_day, get_last_day, getdate, today

from distributor_portal.permissions import require_partner


@contextmanager
def internal():
	old = getattr(frappe.local, "distributor_internal", False)
	frappe.local.distributor_internal = True
	try:
		yield
	finally:
		frappe.local.distributor_internal = old


def is_internal():
	return bool(getattr(frappe.local, "distributor_internal", False))


def settings():
	return frappe.get_single("Distributor Portal Settings")


def lock_partner(name):
	partner = require_partner(name)
	frappe.db.sql("select name from `tabChannel Partner` where name=%s for update", name)
	return partner


def stock(partner, as_of=None):
	rows = frappe.db.sql(
		"""select item_code, sum(qty_reels) qty, sum(qty_m) metres from `tabPartner Stock Ledger`
        where channel_partner=%s and posting_date<=%s group by item_code""",
		(partner, as_of or today()),
		as_dict=True,
	)
	return {r.item_code: dict(qty=int(r.qty), metres=flt(r.metres)) for r in rows}


def serial(name, partner, status="In stock"):
	doc = frappe.get_doc("Partner Serial", name)
	if doc.channel_partner != partner:
		frappe.throw("Reel does not belong to this distributor")
	if status and doc.status != status:
		frappe.throw(f"Reel {doc.serial_no} is {doc.status}, not {status}")
	return doc


def write_ledger(partner, item, qty, movement, voucher, serial_doc=None, date=None, metres=None, suffix=""):
	key = sha256(
		f"{voucher.doctype}:{voucher.name}:{movement}:{serial_doc.name if serial_doc else item}:{suffix}".encode()
	).hexdigest()
	if frappe.db.exists("Partner Stock Ledger", {"entry_key": key}):
		return
	with internal():
		frappe.get_doc(
			dict(
				doctype="Partner Stock Ledger",
				channel_partner=partner,
				item_code=item,
				serial_no=serial_doc.name if serial_doc else None,
				posting_date=date or voucher.get("posting_date") or today(),
				qty_reels=qty,
				qty_m=metres
				if metres is not None
				else qty * flt(serial_doc.length_m if serial_doc else reel_length(item)),
				movement=movement,
				voucher_type=voucher.doctype,
				voucher_no=voucher.name,
				entry_key=key,
			)
		).insert(ignore_permissions=True)


def reverse_ledger(voucher):
	for row in frappe.get_all(
		"Partner Stock Ledger",
		filters={"voucher_type": voucher.doctype, "voucher_no": voucher.name, "movement": ["!=", "Reversal"]},
		fields=["*"],
	):
		if frappe.db.exists("Partner Stock Ledger", {"reversal_of": row.name}):
			continue
		with internal():
			frappe.get_doc(
				dict(
					doctype="Partner Stock Ledger",
					channel_partner=row.channel_partner,
					item_code=row.item_code,
					serial_no=row.serial_no,
					posting_date=row.posting_date,
					qty_reels=-row.qty_reels,
					qty_m=-row.qty_m,
					movement="Reversal",
					voucher_type=voucher.doctype,
					voucher_no=voucher.name,
					reversal_of=row.name,
					entry_key=sha256((row.name + ":reverse").encode()).hexdigest(),
				)
			).insert(ignore_permissions=True)


def save_serial(doc, **changes):
	with internal():
		doc.update(changes)
		doc.save(ignore_permissions=True)


def inside_territory(outlet, holder):
	a = frappe.db.get_value("Territory", outlet, ["lft", "rgt"], as_dict=True)
	b = frappe.db.get_value("Territory", holder, ["lft", "rgt"], as_dict=True)
	return bool(a and b and a.lft >= b.lft and a.rgt <= b.rgt)


def reel_length(item):
	return flt(frappe.db.get_value("Item", item, "distributor_reel_length")) or 305


def item_rate(item_code, partner):
	item = frappe.get_doc("Item", item_code)
	if item.disabled or not item.is_sales_item or not item.has_serial_no:
		frappe.throw("Select an enabled serialized sales item")
	cfg = settings()
	if not cfg.price_list:
		frappe.throw("Set a selling Price List in Portal Settings first")
	pl = frappe.get_doc("Price List", cfg.price_list)
	if not pl.enabled or not pl.selling:
		frappe.throw("The portal Price List must be enabled for selling")
	prices = frappe.get_all(
		"Item Price",
		filters={"item_code": item_code, "price_list": cfg.price_list, "selling": 1},
		fields=["price_list_rate", "currency", "uom", "valid_from", "valid_upto", "customer"],
		order_by="valid_from desc, modified desc",
	)
	prices = [
		x
		for x in prices
		if (not x.valid_from or getdate(x.valid_from) <= getdate(today()))
		and (not x.valid_upto or getdate(x.valid_upto) >= getdate(today()))
		and (not x.customer or x.customer == partner.customer)
	]
	prices.sort(key=lambda x: bool(x.customer), reverse=True)
	if not prices:
		frappe.throw(f"No current selling price for {item_code} in {cfg.price_list}")
	price = prices[0]
	stock_qty = (
		reel_length(item_code) if item.stock_uom.lower() in ("meter", "metre", "meters", "metres", "m") else 1
	)
	factor = 1
	if price.uom and price.uom != item.stock_uom:
		factor = next((flt(x.conversion_factor) for x in item.uoms if x.uom == price.uom), 0)
		if factor <= 0:
			frappe.throw(f"Missing UOM conversion for {item_code}")
	rate = flt(price.price_list_rate) * stock_qty / factor
	if rate <= 0:
		frappe.throw(f"Selling price must be positive for {item_code}")
	return dict(rate=rate, stock_qty=stock_qty, stock_uom=item.stock_uom, currency=price.currency)


def account(partner):
	currency = frappe.db.get_value("Company", partner.company, "default_currency")
	customer = frappe.get_doc("Customer", partner.customer)
	credit = next((flt(x.credit_limit) for x in customer.credit_limits if x.company == partner.company), 0)
	outstanding = flt(
		frappe.db.sql(
			"""select coalesce(sum(debit-credit),0) from `tabGL Entry`
        where party_type='Customer' and party=%s and company=%s and is_cancelled=0""",
			(partner.customer, partner.company),
		)[0][0]
	)
	outstanding = max(0, outstanding)
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"customer": partner.customer, "company": partner.company, "docstatus": 1},
		fields=[
			"name",
			"posting_date",
			"due_date",
			"grand_total",
			"outstanding_amount",
			"currency",
			"is_return",
		],
		order_by="posting_date desc",
		limit_page_length=200,
	)
	overdue = flt(
		frappe.db.sql(
			"""select coalesce(sum(outstanding_amount*conversion_rate),0) from `tabSales Invoice`
        where customer=%s and company=%s and docstatus=1 and outstanding_amount>0 and due_date<%s""",
			(partner.customer, partner.company, today()),
		)[0][0]
	)
	return dict(
		currency=currency,
		limit=credit,
		unlimited=not credit,
		outstanding=outstanding,
		available=max(0, credit - outstanding) if credit else None,
		overdue=overdue,
		invoices=invoices,
	)


def assert_open_date(partner, date):
	date = getdate(date)
	if date > getdate(today()):
		frappe.throw("Future stock movements are not allowed")
	latest = frappe.db.get_value(
		"Stock Declaration", {"channel_partner": partner, "docstatus": 1}, "period", order_by="period desc"
	)
	if latest and date <= get_last_day(latest):
		frappe.throw("This month has been declared. Cancel the declaration before changing its movements")


def check_serial_items(doc, allowed="In stock"):
	if not doc.items:
		frappe.throw("Add at least one reel")
	seen = set()
	result = []
	for row in doc.items:
		if row.serial_no in seen:
			frappe.throw("A reel cannot be included twice")
		seen.add(row.serial_no)
		s = serial(row.serial_no, doc.channel_partner, allowed)
		if doc.get("posting_date") and s.received_on and getdate(doc.posting_date) < getdate(s.received_on):
			frappe.throw("Sale or return date cannot precede receipt")
		row.item_code = s.item_code
		row.length_m = s.length_m
		result.append(s)
	return result


def consumption(partner, start, end):
	rows = frappe.db.sql(
		"""select item_code, -sum(qty_reels) qty from `tabPartner Stock Ledger` l
        where channel_partner=%s and posting_date between %s and %s
        and (movement in ('Sale','Sale-Declared') or (movement='Reversal' and reversal_of in
          (select name from `tabPartner Stock Ledger` where movement in ('Sale','Sale-Declared'))))
        group by item_code""",
		(partner, start, end),
		as_dict=True,
	)
	return {r.item_code: max(0, int(r.qty)) for r in rows}


def forecast_rows(partner, period):
	cfg = settings()
	n = int(cfg.history_months or 6)
	period = get_first_day(period)
	# Forecast next month from completed months; project current remaining demand.
	current = get_first_day(today())
	history_end = add_months(current, -1)
	months = [add_months(history_end, i - n + 1) for i in range(n)]
	history = [consumption(partner.name, m, get_last_day(m)) for m in months]
	sold = consumption(partner.name, current, today())
	inventory = stock(partner.name)
	transit = {
		r.item_code: int(r.qty)
		for r in frappe.db.sql(
			"select item_code,count(*) qty from `tabPartner Serial` where channel_partner=%s and status='In transit' group by item_code",
			partner.name,
			as_dict=True,
		)
	}
	codes = sorted(set(inventory) | set(transit) | set().union(*(set(x) for x in history)))
	rows = []
	for code in codes:
		values = [h.get(code, 0) for h in history]
		weights = list(range(1, n + 1)) if cfg.forecast_method == "Weighted moving average" else [1] * n
		forecast = math.ceil(sum(a * b for a, b in zip(values, weights, strict=True)) / sum(weights))
		onhand = inventory.get(code, {}).get("qty", 0)
		incoming = transit.get(code, 0)
		projected = max(0, onhand + incoming - max(0, forecast - sold.get(code, 0)))
		safety = math.ceil(forecast * flt(cfg.safety_stock_percent) / 100)
		rows.append(
			dict(
				item_code=code,
				history=frappe.as_json(values),
				forecast_qty=forecast,
				stock_qty=onhand,
				in_transit=incoming,
				projected_qty=projected,
				safety_qty=safety,
				suggested_qty=max(0, forecast + safety - projected),
			)
		)
	return rows
