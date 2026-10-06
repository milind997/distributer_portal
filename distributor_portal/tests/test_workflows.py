import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_months, get_first_day, get_last_day, today

from distributor_portal import api
from distributor_portal import domain as d
from distributor_portal.permissions import require_partner


class TestDistributorWorkflows(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.tag = frappe.generate_hash(length=8)
		if not frappe.db.exists("UOM", "Nos"):
			frappe.get_doc(dict(doctype="UOM", uom_name="Nos", must_be_whole_number=1)).insert()
		year = str(get_first_day(today()).year)
		if not frappe.db.exists("Fiscal Year", year):
			frappe.get_doc(
				dict(
					doctype="Fiscal Year",
					year=year,
					year_start_date=year + "-01-01",
					year_end_date=year + "-12-31",
				)
			).insert()
		if not frappe.db.exists("Warehouse Type", "Transit"):
			frappe.get_doc(dict(doctype="Warehouse Type", name="Transit")).insert()
		if not frappe.db.exists("Company", "DP Test Company"):
			frappe.get_doc(
				dict(
					doctype="Company",
					company_name="DP Test Company",
					abbr="DPT",
					default_currency="INR",
					country="India",
					chart_of_accounts="Standard",
				)
			).insert()
		self.company = "DP Test Company"
		if not frappe.db.exists("Warehouse", "DP Fulfilment - DPT"):
			frappe.get_doc(
				dict(doctype="Warehouse", warehouse_name="DP Fulfilment", company=self.company, is_group=0)
			).insert()
		self.warehouse = "DP Fulfilment - DPT"
		for dt, field, name in [
			("Territory", "territory_name", "All Territories"),
			("Customer Group", "customer_group_name", "All Customer Groups"),
			("Item Group", "item_group_name", "All Item Groups"),
		]:
			if not frappe.db.exists(dt, name):
				frappe.get_doc(dict(doctype=dt, is_group=1, **{field: name})).insert()
		if not frappe.db.exists("Item Group", "Products"):
			frappe.get_doc(
				dict(doctype="Item Group", item_group_name="Products", parent_item_group="All Item Groups")
			).insert()
		root = (
			frappe.db.get_value("Territory", {"is_group": 1, "parent_territory": ""}, "name")
			or "All Territories"
		)
		self.territory = (
			frappe.get_doc(
				dict(doctype="Territory", territory_name="DP Pune " + self.tag, parent_territory=root)
			)
			.insert()
			.name
		)
		self.other_territory = (
			frappe.get_doc(
				dict(doctype="Territory", territory_name="DP Satara " + self.tag, parent_territory=root)
			)
			.insert()
			.name
		)
		if not frappe.db.exists("Customer Group", "DP Dealers"):
			frappe.get_doc(
				dict(
					doctype="Customer Group",
					customer_group_name="DP Dealers",
					parent_customer_group="All Customer Groups",
					is_group=0,
				)
			).insert()
		group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups"
		self.customer = frappe.get_doc(
			dict(
				doctype="Customer",
				customer_name="DP Customer " + self.tag,
				customer_type="Company",
				customer_group=group,
				territory=self.territory,
			)
		).insert()
		self.partner = frappe.get_doc(
			dict(
				doctype="Channel Partner",
				partner_name="DP Distributor " + self.tag,
				customer=self.customer.name,
				company=self.company,
				territory=self.territory,
				active=1,
			)
		).insert()
		self.outlet = frappe.get_doc(
			dict(
				doctype="Channel Outlet",
				outlet_name="DP Outlet " + self.tag,
				channel_partner=self.partner.name,
				territory=self.territory,
				approval_status="Approved",
			)
		).insert()
		self.item = frappe.get_doc(
			dict(
				doctype="Item",
				item_code="DP-CABLE-" + self.tag,
				item_name="DP CAT6 Cable",
				item_group="Products",
				stock_uom="Nos",
				is_stock_item=1,
				has_serial_no=1,
				is_sales_item=1,
				distributor_reel_length=305,
			)
		).insert()
		self.price_list = frappe.get_doc(
			dict(
				doctype="Price List",
				price_list_name="DP Price " + self.tag,
				enabled=1,
				selling=1,
				currency="INR",
			)
		).insert()
		frappe.get_doc(
			dict(
				doctype="Item Price",
				item_code=self.item.name,
				price_list=self.price_list.name,
				price_list_rate=1000,
				selling=1,
				currency="INR",
			)
		).insert()
		cfg = d.settings()
		cfg.company = self.company
		cfg.default_warehouse = frappe.db.get_value(
			"Warehouse", {"company": self.company, "is_group": 0}, "name"
		)
		cfg.price_list = self.price_list.name
		cfg.damage_photos_required = 0
		cfg.outlet_approval_required = 1
		cfg.territory_rule = "Warn and flag HQ"
		cfg.credit_rule = "Hold for Accounts approval"
		cfg.save()

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def reels(self, count=2, date=None):
		result = []
		for i in range(count):
			sn = frappe.get_doc(
				dict(
					doctype="Serial No",
					serial_no="DP-SN-" + self.tag + "-" + str(i),
					item_code=self.item.name,
					company=self.company,
				)
			).insert()
			with d.internal():
				s = frappe.get_doc(
					dict(
						doctype="Partner Serial",
						serial_no=sn.name,
						channel_partner=self.partner.name,
						item_code=self.item.name,
						length_m=305,
						status="In transit",
					)
				).insert()
			if date:
				d.write_ledger(self.partner.name, self.item.name, 1, "Receipt", s, s, date=date)
				d.save_serial(s, status="In stock", received_on=date, last_voucher=s.name)
			else:
				s.acknowledge()
			result.append(s)
		return result

	def sale(self, reels, outlet=None, date=None):
		return frappe.get_doc(
			dict(
				doctype="Sell Out Entry",
				channel_partner=self.partner.name,
				outlet=outlet or self.outlet.name,
				posting_date=date or today(),
				items=[dict(serial_no=s.name) for s in reels],
			)
		).insert()

	def user(self):
		user = frappe.get_doc(
			dict(
				doctype="User",
				email="dp-" + self.tag + "@example.invalid",
				first_name="DP Tester",
				send_welcome_email=0,
				user_type="Website User",
			)
		).insert()
		self.partner.append("portal_users", dict(user=user.name))
		self.partner.save()
		return user.name

	def test_receipt_sale_cancel_reconciles_ledger(self):
		reels = self.reels()
		self.assertEqual(d.stock(self.partner.name)[self.item.name]["qty"], 2)
		sale = self.sale([reels[0]])
		sale.submit()
		self.assertEqual(d.stock(self.partner.name)[self.item.name]["qty"], 1)
		self.assertEqual(d.consumption(self.partner.name, today(), today())[self.item.name], 1)
		sale.cancel()
		self.assertEqual(d.stock(self.partner.name)[self.item.name]["qty"], 2)
		self.assertEqual(d.consumption(self.partner.name, today(), today())[self.item.name], 0)
		self.assertEqual(
			frappe.db.count("Partner Stock Ledger", {"movement": "Reversal", "voucher_no": sale.name}), 1
		)

	def test_duplicate_scan_rejected(self):
		reels = self.reels(1)
		with self.assertRaises(frappe.ValidationError):
			self.sale([reels[0], reels[0]])

	def test_already_sold_rejected(self):
		reels = self.reels(1)
		self.sale(reels).submit()
		with self.assertRaises(frappe.ValidationError):
			self.sale(reels)

	def test_outlet_approval_required(self):
		self.outlet.approval_status = "Pending"
		self.outlet.save()
		with self.assertRaises(frappe.ValidationError):
			self.sale(self.reels(1))

	def test_territory_warning_creates_flag(self):
		self.outlet.territory = self.other_territory
		self.outlet.save()
		sale = self.sale(self.reels(1))
		sale.submit()
		self.assertTrue(sale.territory_flagged)
		flag = frappe.get_doc("Territory Flag", {"source_voucher": sale.name})
		flag.explain("Approved project requirement")
		flag.resolve("Reviewed by HQ")
		self.assertEqual(flag.status, "Accepted")

	def test_territory_block_is_enforced(self):
		self.outlet.territory = self.other_territory
		self.outlet.save()
		cfg = d.settings()
		cfg.territory_rule = "Block the sale"
		cfg.save()
		with self.assertRaises(frappe.ValidationError):
			self.sale(self.reels(1))

	def test_partner_scope_and_list_permissions(self):
		user = self.user()
		frappe.set_user(user)
		self.assertEqual(require_partner(self.partner.name).name, self.partner.name)
		with self.assertRaises(frappe.PermissionError):
			require_partner("another-partner")
		with self.assertRaises(frappe.PermissionError):
			api.listing("stock")
		self.assertEqual(len(frappe.get_list("Channel Partner")), 1)
		with self.assertRaises(frappe.PermissionError):
			api.save_settings({"safety_stock_percent": 0})

	def test_distributor_cannot_approve_outlet_or_order(self):
		user = self.user()
		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			self.outlet.approve()
		with self.assertRaises(frappe.PermissionError):
			api.submit_transaction("Channel Partner", {})

	def test_partner_sale_api(self):
		reels = self.reels(1)
		user = self.user()
		frappe.set_user(user)
		result = api.submit_transaction(
			"Sell Out Entry",
			dict(
				channel_partner=self.partner.name,
				outlet=self.outlet.name,
				posting_date=today(),
				items=[dict(serial_no=reels[0].name)],
				docstatus=1,
				ignore_permissions=True,
			),
		)
		self.assertTrue(result["name"])
		self.assertEqual(api.listing("sales", self.partner.name)["rows"][0].total_reels, 1)

	def test_generated_ledger_cannot_be_forged(self):
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				dict(
					doctype="Partner Stock Ledger",
					channel_partner=self.partner.name,
					item_code=self.item.name,
					posting_date=today(),
					qty_reels=999,
					movement="Receipt",
				)
			).insert()

	def test_ledger_is_immutable(self):
		self.reels(1)
		row = frappe.get_doc(
			"Partner Stock Ledger", {"channel_partner": self.partner.name, "movement": "Receipt"}
		)
		row.qty_reels = 900
		with d.internal():
			with self.assertRaises(frappe.ValidationError):
				row.save()

	def test_order_prices_come_from_erpnext(self):
		result = api.submit_transaction(
			"Partner Order",
			dict(
				channel_partner=self.partner.name,
				posting_date=today(),
				required_by=add_days(today(), 7),
				items=[dict(item_code=self.item.name, qty_reels=2, rate=1)],
			),
		)
		order = frappe.get_doc("Partner Order", result["name"])
		self.assertEqual(order.total, 2000)
		self.assertEqual(order.items[0].rate, 1000)
		so = order.approve()
		self.assertEqual(frappe.db.get_value("Sales Order", so, "docstatus"), 0)
		self.assertEqual(frappe.db.get_value("Sales Order", so, "distributor_partner_order"), order.name)

	def test_credit_hold_and_block(self):
		self.customer.append("credit_limits", dict(company=self.company, credit_limit=500))
		self.customer.save()
		payload = dict(
			channel_partner=self.partner.name,
			posting_date=today(),
			required_by=add_days(today(), 7),
			items=[dict(item_code=self.item.name, qty_reels=1)],
		)
		result = api.submit_transaction("Partner Order", payload)
		order = frappe.get_doc("Partner Order", result["name"])
		self.assertEqual(order.status, "Credit approval required")
		with self.assertRaises(frappe.ValidationError):
			order.approve()
		cfg = d.settings()
		cfg.credit_rule = "Block submit"
		cfg.save()
		with self.assertRaises(frappe.ValidationError):
			api.submit_transaction("Partner Order", payload)

	def test_return_workflow_and_lock(self):
		reels = self.reels(1)
		ret = frappe.get_doc(
			dict(
				doctype="Partner Return",
				channel_partner=self.partner.name,
				posting_date=today(),
				reason="Manufacturing defect",
				description="Defect",
				items=[dict(serial_no=reels[0].name)],
			)
		).insert()
		ret.submit()
		with self.assertRaises(frappe.ValidationError):
			self.sale(reels)
		ret.advance("Received")
		ret.advance("Inspected")
		ret.advance("Decide", decisions={reels[0].name: "Approved"})
		self.assertEqual(ret.status, "Approved")
		self.assertEqual(d.stock(self.partner.name)[self.item.name]["qty"], 0)

	def test_rejected_return_restores_stock(self):
		reels = self.reels(1)
		ret = frappe.get_doc(
			dict(
				doctype="Partner Return",
				channel_partner=self.partner.name,
				posting_date=today(),
				reason="Manufacturing defect",
				description="Inspection",
				items=[dict(serial_no=reels[0].name)],
			)
		).insert()
		ret.submit()
		ret.advance("Received")
		ret.advance("Inspected")
		ret.advance("Decide", decisions={reels[0].name: "Rejected"})
		self.assertEqual(frappe.db.get_value("Partner Serial", reels[0].name, "status"), "In stock")
		self.assertEqual(d.stock(self.partner.name)[self.item.name]["qty"], 1)

	def test_scan_declaration_excludes_damage_from_demand(self):
		period = get_first_day(add_months(today(), -1))
		reels = self.reels(2, date=period)
		declaration = frappe.get_doc(
			dict(
				doctype="Stock Declaration",
				channel_partner=self.partner.name,
				period=period,
				method="Scan",
				counted_serials=reels[0].serial_no,
				items=[dict(item_code=self.item.name, treatment="Damage")],
			)
		).insert()
		declaration.submit()
		self.assertEqual(d.stock(self.partner.name)[self.item.name]["qty"], 1)
		self.assertEqual(
			d.consumption(self.partner.name, period, get_last_day(period)).get(self.item.name, 0), 0
		)
		self.assertEqual(frappe.db.get_value("Partner Serial", reels[1].name, "status"), "Damaged")

	def test_count_declaration_books_unscanned_sales(self):
		period = get_first_day(add_months(today(), -1))
		reels = self.reels(2, date=period)
		declaration = frappe.get_doc(
			dict(
				doctype="Stock Declaration",
				channel_partner=self.partner.name,
				period=period,
				method="Count",
				items=[dict(item_code=self.item.name, counted=1, treatment="Sold, not scanned")],
			)
		).insert()
		declaration.submit()
		self.assertEqual(d.stock(self.partner.name)[self.item.name]["qty"], 1)
		self.assertEqual(d.consumption(self.partner.name, period, get_last_day(period))[self.item.name], 1)
		with self.assertRaises(frappe.ValidationError):
			self.sale([reels[0]])

	def test_future_movement_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.sale(self.reels(1), date=add_days(today(), 1))

	def test_forecast_is_deterministic_and_idempotent(self):
		self.reels(2, date=get_first_day(add_months(today(), -1)))
		first = api.generate_forecast(self.partner.name)
		second = api.generate_forecast(self.partner.name)
		self.assertEqual(first["name"], second["name"])
		self.assertEqual(first["suggested_total"], 0)

	def test_public_page_is_not_guest_accessible(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			api.bootstrap()

	def test_receipt_reversal_can_be_received_again(self):
		reel = self.reels(1)[0]
		reel.reload()
		reel.reverse_receipt()
		self.assertEqual(d.stock(self.partner.name)[self.item.name]["qty"], 0)
		reel.acknowledge()
		self.assertEqual(d.stock(self.partner.name)[self.item.name]["qty"], 1)

	def test_count_then_scan_does_not_double_count_demand(self):
		period = get_first_day(add_months(today(), -1))
		reels = self.reels(2, date=period)
		count = frappe.get_doc(
			dict(
				doctype="Stock Declaration",
				channel_partner=self.partner.name,
				period=period,
				method="Count",
				items=[dict(item_code=self.item.name, counted=1, treatment="Sold, not scanned")],
			)
		).insert()
		count.submit()
		scan = frappe.get_doc(
			dict(
				doctype="Stock Declaration",
				channel_partner=self.partner.name,
				period=period,
				method="Scan",
				counted_serials=reels[0].serial_no,
				items=[dict(item_code=self.item.name, treatment="Sold, not scanned")],
			)
		).insert()
		scan.submit()
		self.assertEqual(d.consumption(self.partner.name, period, get_last_day(period))[self.item.name], 1)
		self.sale([reels[0]]).submit()
		self.assertEqual(d.stock(self.partner.name)[self.item.name]["qty"], 0)

	def test_fractional_reel_order_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			api.submit_transaction(
				"Partner Order",
				dict(
					channel_partner=self.partner.name,
					required_by=add_days(today(), 7),
					items=[dict(item_code=self.item.name, qty_reels=1.5)],
				),
			)

	def test_delivery_note_hook_and_return_reversal(self):
		from distributor_portal.integration import delivery_cancel, delivery_submit

		sn = frappe.get_doc(
			dict(
				doctype="Serial No",
				serial_no="DP-DN-" + self.tag,
				item_code=self.item.name,
				company=self.company,
			)
		).insert()
		warehouse = frappe.db.get_value("Warehouse", {"company": self.company, "is_group": 0}, "name")
		doc = frappe.get_doc(
			dict(
				doctype="Delivery Note",
				customer=self.customer.name,
				company=self.company,
				posting_date=today(),
				items=[
					dict(
						item_code=self.item.name,
						qty=1,
						rate=1000,
						warehouse=warehouse,
						serial_no=sn.name,
						use_serial_batch_fields=1,
					)
				],
			)
		).insert()
		delivery_submit(doc)
		ps = frappe.get_doc("Partner Serial", {"serial_no": sn.name})
		self.assertEqual(ps.status, "In transit")
		delivery_submit(doc)
		self.assertEqual(frappe.db.count("Partner Serial", {"serial_no": sn.name}), 1)
		ps.acknowledge()
		with self.assertRaises(frappe.ValidationError):
			delivery_cancel(doc)
		ps.reverse_receipt()
		delivery_cancel(doc)
		self.assertEqual(frappe.db.get_value("Partner Serial", ps.name, "status"), "Returned")

	def test_return_transition_cannot_be_skipped(self):
		reel = self.reels(1)[0]
		ret = frappe.get_doc(
			dict(
				doctype="Partner Return",
				channel_partner=self.partner.name,
				posting_date=today(),
				reason="Manufacturing defect",
				description="Defect",
				items=[dict(serial_no=reel.name)],
			)
		).insert()
		ret.submit()
		with self.assertRaises(frappe.ValidationError):
			ret.advance("Decide", decisions={reel.name: "Approved"})

	def test_direct_status_change_cannot_approve_order(self):
		result = api.submit_transaction(
			"Partner Order",
			dict(
				channel_partner=self.partner.name,
				required_by=add_days(today(), 7),
				items=[dict(item_code=self.item.name, qty_reels=1)],
			),
		)
		order = frappe.get_doc("Partner Order", result["name"])
		order.status = "Approved"
		with self.assertRaises(frappe.PermissionError):
			order.save()

	def test_channel_manager_can_approve_without_administrator(self):
		result = api.submit_transaction(
			"Partner Order",
			dict(
				channel_partner=self.partner.name,
				required_by=add_days(today(), 7),
				items=[dict(item_code=self.item.name, qty_reels=1)],
			),
		)
		user = frappe.get_doc(
			dict(
				doctype="User",
				email="hq-" + self.tag + "@example.invalid",
				first_name="HQ Test",
				send_welcome_email=0,
				user_type="System User",
				roles=[dict(role="Channel Manager")],
			)
		).insert()
		frappe.set_user(user.name)
		order = frappe.get_doc("Partner Order", result["name"])
		with self.assertRaises(frappe.PermissionError):
			order.approve(credit_override=True)
		so = order.approve()
		self.assertTrue(so)

	def test_zero_stock_count_declaration(self):
		result = api.submit_transaction(
			"Stock Declaration",
			dict(
				channel_partner=self.partner.name,
				period=get_first_day(add_months(today(), -1)),
				method="Count",
				items=[],
			),
		)
		self.assertTrue(result["name"])

	def test_real_erpnext_dispatch_receipt_and_sell_out(self):
		frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)
		frappe.db.set_single_value("Stock Settings", "use_serial_batch_fields", 1)
		warehouse = self.warehouse
		if not frappe.db.exists("Stock Entry Type", "Material Receipt"):
			frappe.get_doc(
				dict(doctype="Stock Entry Type", name="Material Receipt", purpose="Material Receipt")
			).insert()
		serial_no = "DP-REAL-" + self.tag
		receipt = frappe.get_doc(
			dict(
				doctype="Stock Entry",
				stock_entry_type="Material Receipt",
				purpose="Material Receipt",
				company=self.company,
				posting_date=today(),
				items=[
					dict(
						item_code=self.item.name,
						qty=1,
						t_warehouse=warehouse,
						basic_rate=1000,
						serial_no=serial_no,
						use_serial_batch_fields=1,
					)
				],
			)
		)
		receipt.insert()
		receipt.submit()
		delivery = frappe.get_doc(
			dict(
				doctype="Delivery Note",
				customer=self.customer.name,
				company=self.company,
				posting_date=today(),
				items=[
					dict(
						item_code=self.item.name,
						qty=1,
						rate=1200,
						warehouse=warehouse,
						serial_no=serial_no,
						use_serial_batch_fields=1,
					)
				],
			)
		)
		delivery.insert()
		delivery.submit()
		reel = frappe.get_doc("Partner Serial", {"serial_no": serial_no})
		self.assertEqual(reel.delivery_note, delivery.name)
		self.assertEqual(reel.status, "In transit")
		self.assertEqual(api.receive_delivery(self.partner.name, delivery.name), 1)
		self.sale([reel]).submit()
		self.assertEqual(d.stock(self.partner.name)[self.item.name]["qty"], 0)
