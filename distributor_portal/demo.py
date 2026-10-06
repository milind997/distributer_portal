"""Explicit, one-time demo dataset. Run only with bench execute; never on install."""

import json
from pathlib import Path

import frappe
from frappe.utils import add_days, add_months, get_first_day, today

from distributor_portal import api
from distributor_portal import domain as d


def seed():
	"""Populate the requested local site atomically, without ERP accounting entries."""
	if frappe.local.site != "test-com.localhost":
		raise RuntimeError("This demo dataset is restricted to test-com.localhost")
	frappe.only_for("System Manager")
	marker = Path(frappe.get_site_path("private", "distributor-demo-v1.json"))
	if marker.exists():
		return {"already_seeded": True, **json.loads(marker.read_text())}
	if frappe.db.exists("Item", "DEMO-DP-CAT6"):
		raise RuntimeError("Demo identifiers already exist; refusing to overwrite records")
	cfg = d.settings()
	company = cfg.company
	currency = frappe.db.get_value("Company", company, "default_currency")
	if not company or not cfg.price_list:
		raise RuntimeError("Configure a company and selling price list first")
	if frappe.db.get_value("Price List", cfg.price_list, "currency") != currency:
		raise RuntimeError("Company and price-list currencies must match")
	settings_before = cfg.as_dict()
	manifest = {"created_on": today(), "company": company, "records": {}}

	def create(doctype, **values):
		doc = frappe.get_doc(dict(doctype=doctype, **values)).insert()
		manifest["records"].setdefault(doctype, []).append(doc.name)
		return doc

	try:
		territory_root = frappe.db.get_value("Territory", {"is_group": 1, "parent_territory": ""}, "name")
		group_root = frappe.db.get_value(
			"Customer Group", {"is_group": 1, "parent_customer_group": ""}, "name"
		)
		item_root = frappe.db.get_value("Item Group", {"is_group": 1, "parent_item_group": ""}, "name")
		group = create(
			"Customer Group", customer_group_name="DEMO DP Distributors", parent_customer_group=group_root
		)
		item_group = create("Item Group", item_group_name="DEMO DP Products", parent_item_group=item_root)
		territories = [
			create("Territory", territory_name="DEMO DP " + city, parent_territory=territory_root).name
			for city in ("Pune", "Mumbai", "Nashik")
		]
		items = []
		for code, label, price, length in (
			("CAT6", "CAT6 UTP Cable", 6500, 305),
			("CAT6A", "CAT6A Shielded Cable", 11000, 305),
			("FIBER", "4 Core Fibre Cable", 8500, 500),
		):
			item = create(
				"Item",
				item_code="DEMO-DP-" + code,
				item_name="DEMO " + label,
				item_group=item_group.name,
				stock_uom="Nos",
				is_stock_item=1,
				has_serial_no=1,
				is_sales_item=1,
				distributor_reel_length=length,
				description="Sample product for Distributor Portal demonstrations only.",
			)
			create(
				"Item Price",
				item_code=item.name,
				price_list=cfg.price_list,
				price_list_rate=price,
				currency=currency,
				selling=1,
			)
			items.append(item)
		for index, city in enumerate(("Pune", "Mumbai", "Nashik")):
			customer = create(
				"Customer",
				customer_name="DEMO DP " + city + " Distribution",
				customer_type="Company",
				customer_group=group.name,
				territory=territories[index],
				credit_limits=[dict(company=company, credit_limit=20000 if index == 1 else 250000)],
			)
			partner = create(
				"Channel Partner",
				partner_name="DEMO " + city + " Distribution",
				customer=customer.name,
				company=company,
				territory=territories[index],
				active=1,
			)
			outlet = create(
				"Channel Outlet",
				outlet_name="DEMO " + city + " Network Store",
				channel_partner=partner.name,
				outlet_type="Dealer",
				territory=territories[index],
				pincode=("411001", "400001", "422001")[index],
				address="Demo address — sample data only",
				approval_status="Approved",
			)
			create(
				"Channel Outlet",
				outlet_name="DEMO " + city + " New Retailer",
				channel_partner=partner.name,
				outlet_type="Retailer",
				territory=territories[index],
				approval_status="Pending",
			)
			reels = []
			opening = get_first_day(add_months(today(), -6))
			for item in items:
				batch = []
				for number in range(12):
					sn = create(
						"Serial No",
						serial_no=f"{item.name}-{index + 1}-{number + 1:03}",
						item_code=item.name,
						company=company,
					)
					with d.internal():
						serial = create(
							"Partner Serial",
							serial_no=sn.name,
							channel_partner=partner.name,
							item_code=item.name,
							length_m=item.distributor_reel_length,
							status="In transit",
						)
					# Explicit demo opening inventory; no fabricated Delivery Note or ERP stock entry.
					d.write_ledger(partner.name, item.name, 1, "Receipt", serial, serial, date=opening)
					d.save_serial(serial, status="In stock", received_on=opening, last_voucher=serial.name)
					batch.append(serial)
				reels.append(batch)
			for month in range(6):
				create(
					"Sell Out Entry",
					channel_partner=partner.name,
					outlet=outlet.name,
					posting_date=add_days(add_months(opening, month), 10),
					bill_no=f"DEMO-{city}-H{month + 1}",
					items=[dict(serial_no=batch[month].name) for batch in reels],
				).submit()
			create(
				"Stock Declaration",
				channel_partner=partner.name,
				period=get_first_day(add_months(today(), -1)),
				method="Count",
				notes="DEMO month-end count; no discrepancy",
				items=[dict(item_code=item.name, counted=6, treatment="Sold, not scanned") for item in items],
			).submit()
			create(
				"Sell Out Entry",
				channel_partner=partner.name,
				outlet=outlet.name,
				posting_date=today(),
				bill_no=f"DEMO-{city}-CURRENT",
				items=[dict(serial_no=batch[6].name) for batch in reels],
			).submit()
			for order_no in range(2):
				order = create(
					"Partner Order",
					channel_partner=partner.name,
					posting_date=today(),
					required_by=add_days(today(), 14),
					po_number=f"DEMO-{city}-PO{order_no + 1}",
					note="DEMO order — sample only; do not fulfil",
					items=[dict(item_code=item.name, qty_reels=2 + order_no) for item in items],
				)
				if order_no == 0:
					order.submit()
			ret = create(
				"Partner Return",
				channel_partner=partner.name,
				posting_date=today(),
				reason="Manufacturing defect",
				description="DEMO return workflow — sample cable continuity issue",
				items=[dict(serial_no=reels[0][7].name)],
			).submit()
			if index >= 1:
				ret.advance("Received", note="DEMO receipt inspection")
			if index == 2:
				ret.advance("Inspected")
				ret.advance(
					"Decide",
					decisions={reels[0][7].name: "Approved"},
					note="DEMO approved; no accounting credit note posted",
				)
			forecast = api.generate_forecast(partner.name)
			manifest["records"].setdefault("Partner Forecast", []).append(forecast["name"])
		assert frappe.get_single("Distributor Portal Settings").as_dict() == settings_before
		manifest["counts"] = {dt: len(names) for dt, names in manifest["records"].items()}
		# Keep a visible provenance note with the dataset.
		create(
			"Comment",
			comment_type="Comment",
			reference_doctype="Channel Partner",
			reference_name=manifest["records"]["Channel Partner"][0],
			content="DEMO dataset v1: imported sample opening inventory, no ERP stock/accounting postings.",
		)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		raise
	marker.write_text(json.dumps(manifest, indent=2))
	marker.chmod(0o600)
	return {"counts": manifest["counts"], "partners": manifest["records"]["Channel Partner"]}


def verify():
	"""Read-only reconciliation of the seeded data and public portal APIs."""
	frappe.only_for("System Manager")
	manifest = json.loads(Path(frappe.get_site_path("private", "distributor-demo-v1.json")).read_text())
	for doctype, names in manifest["records"].items():
		for name in names:
			assert frappe.db.exists(doctype, name), (doctype, name)
	results = []
	for partner in manifest["records"]["Channel Partner"]:
		stock = d.stock(partner)
		serials = frappe.get_all(
			"Partner Serial", filters={"channel_partner": partner}, fields=["item_code", "status"]
		)
		for item, balance in stock.items():
			expected = sum(
				s.item_code == item and s.status in ("In stock", "Return pending") for s in serials
			)
			assert balance["qty"] == expected, (partner, item, balance, expected)
		for view in ("stock", "sales", "orders", "declarations", "returns", "outlets", "forecast"):
			api.listing(view=view, partner=partner)
		api.overview(partner)
		api.accounts(partner)
		customer = frappe.db.get_value("Channel Partner", partner, "customer")
		assert not frappe.db.exists("GL Entry", {"party_type": "Customer", "party": customer})
		results.append(
			{
				"partner": partner,
				"serials": len(serials),
				"stock_reels": sum(v["qty"] for v in stock.values()),
				"sales": frappe.db.count("Sell Out Entry", {"channel_partner": partner}),
				"orders": frappe.get_all(
					"Partner Order", filters={"channel_partner": partner}, pluck="status"
				),
			}
		)
	return {"verified": True, "partners": results, "counts": manifest["counts"]}
