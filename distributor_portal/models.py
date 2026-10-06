import re

import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, flt, get_first_day, get_last_day, getdate, today

from distributor_portal import domain as d
from distributor_portal.permissions import is_manager, require_manager, require_partner


class DistributorPortalSettings(Document):
	def validate(self):
		require_manager()
		for field in ("declaration_due_day", "forecast_day"):
			if not 1 <= int(self.get(field) or 0) <= 28:
				frappe.throw("Due and generation days must be between 1 and 28")
		if not 1 <= int(self.history_months or 0) <= 24:
			frappe.throw("History months must be between 1 and 24")
		if not 0 <= flt(self.safety_stock_percent) <= 200:
			frappe.throw("Safety stock must be between 0 and 200 percent")
		if int(self.minimum_order_reels or 0) < 1 or int(self.damage_window_days or 0) < 1:
			frappe.throw("Minimum quantity and damage window must be positive")
		if self.accent_colour and not re.fullmatch(r"#[0-9a-fA-F]{6}", self.accent_colour):
			frappe.throw("Use a six-digit hex accent colour")


class ChannelPartner(Document):
	def validate(self):
		require_manager()
		seen = set()
		for row in self.portal_users:
			if row.user in seen:
				frappe.throw("Duplicate portal user")
			if row.user == "Guest":
				frappe.throw("Guest cannot be a portal user")
			seen.add(row.user)

	def on_update(self):
		for row in self.portal_users:
			user = frappe.get_doc("User", row.user)
			if "Channel Partner" not in [r.role for r in user.roles]:
				user.append("roles", dict(role="Channel Partner"))
				user.save(ignore_permissions=True)


class PartnerDocument(Document):
	def validate(self):
		require_partner(self.channel_partner)
		old = self.get_doc_before_save()
		if old and old.channel_partner != self.channel_partner:
			frappe.throw("The distributor cannot be changed")

	def on_trash(self):
		if self.docstatus:
			frappe.throw("Submitted records cannot be deleted")


class ChannelOutlet(PartnerDocument):
	def validate(self):
		super().validate()
		old = self.get_doc_before_save()
		if not is_manager():
			if self.is_new():
				self.approval_status = "Pending" if d.settings().outlet_approval_required else "Approved"
			elif old and self.approval_status != old.approval_status:
				frappe.throw("HQ must approve outlets", frappe.PermissionError)
			elif old and any(self.get(k) != old.get(k) for k in ("territory", "pincode", "address")):
				self.approval_status = "Pending" if d.settings().outlet_approval_required else "Approved"

	@frappe.whitelist(methods=["POST"])
	def approve(self):
		require_manager()
		self.approval_status = "Approved"
		self.save()
		return self.name


class GeneratedDocument(Document):
	def validate(self):
		if not d.is_internal():
			frappe.throw("This record is maintained by portal workflows", frappe.PermissionError)

	def on_trash(self):
		frappe.throw("Audit records cannot be deleted", frappe.PermissionError)


class PartnerStockLedger(GeneratedDocument):
	def validate(self):
		super().validate()
		if not self.is_new():
			frappe.throw("Stock ledger is immutable; use a reversing movement")


class PartnerSerial(GeneratedDocument):
	@frappe.whitelist(methods=["POST"])
	def acknowledge(self):
		d.lock_partner(self.channel_partner)
		self.reload()
		if self.status != "In transit":
			frappe.throw("Only in-transit reels can be received")
		d.assert_open_date(self.channel_partner, today())
		d.write_ledger(
			self.channel_partner,
			self.item_code,
			1,
			"Receipt",
			self,
			self,
			date=today(),
			suffix=str(
				frappe.db.count(
					"Partner Stock Ledger",
					{"voucher_type": self.doctype, "voucher_no": self.name, "movement": "Receipt"},
				)
			),
		)
		d.save_serial(self, status="In stock", received_on=today(), last_voucher=self.name)
		return self.name

	@frappe.whitelist(methods=["POST"])
	def reverse_receipt(self):
		require_manager()
		d.lock_partner(self.channel_partner)
		self.reload()
		d.assert_open_date(self.channel_partner, self.received_on or today())
		if self.status != "In stock" or self.last_voucher != self.name:
			frappe.throw("Reverse subsequent reel movements before undoing receipt")
		d.reverse_ledger(self)
		d.save_serial(self, status="In transit", received_on=None, last_voucher=self.delivery_note)
		return self.name


class SellOutEntry(PartnerDocument):
	def validate(self):
		super().validate()
		if self.docstatus == 2:
			return
		partner = d.lock_partner(self.channel_partner)
		d.assert_open_date(self.channel_partner, self.posting_date)
		outlet = frappe.get_doc("Channel Outlet", self.outlet)
		if outlet.channel_partner != self.channel_partner:
			frappe.throw("The outlet belongs to another distributor")
		if outlet.approval_status != "Approved":
			frappe.throw("HQ must approve this outlet before sales can be recorded")
		self.territory_flagged = int(not d.inside_territory(outlet.territory, partner.territory))
		if self.territory_flagged and d.settings().territory_rule == "Block the sale":
			frappe.throw("This outlet is outside your territory; the configured policy blocks the sale")
		reels = d.check_serial_items(self)
		inv = d.stock(self.channel_partner)
		for item in {r.item_code for r in reels}:
			known = frappe.db.count(
				"Partner Serial",
				{"channel_partner": self.channel_partner, "item_code": item, "status": "In stock"},
			)
			if inv.get(item, {}).get("qty", 0) < known:
				frappe.throw(
					"Unverified counted stock exists. Submit a scan declaration before recording further serial sales"
				)
		self.total_reels = len(reels)

	def on_submit(self):
		partner = require_partner(self.channel_partner)
		for s in d.check_serial_items(self):
			d.write_ledger(self.channel_partner, s.item_code, -1, "Sale", self, s)
			d.save_serial(
				s, status="Sold", sold_to=self.outlet, sold_on=self.posting_date, last_voucher=self.name
			)
			if self.territory_flagged and d.settings().territory_rule == "Warn and flag HQ":
				with d.internal():
					frappe.get_doc(
						dict(
							doctype="Territory Flag",
							channel_partner=self.channel_partner,
							serial_no=s.name,
							outlet=self.outlet,
							holder_territory=partner.territory,
							outlet_territory=frappe.db.get_value("Channel Outlet", self.outlet, "territory"),
							source_voucher=self.name,
							explanation=self.explanation,
							status="Explained" if self.explanation else "Open",
						)
					).insert(ignore_permissions=True)

	def on_cancel(self):
		d.lock_partner(self.channel_partner)
		d.assert_open_date(self.channel_partner, self.posting_date)
		for row in self.items:
			s = d.serial(row.serial_no, self.channel_partner, "Sold")
			if s.last_voucher != self.name:
				frappe.throw("A reel has moved since this sale")
			d.save_serial(
				s, status="In stock", sold_to=None, sold_on=None, last_voucher="Cancelled " + self.name
			)
		d.reverse_ledger(self)
		for name in frappe.get_all("Territory Flag", filters={"source_voucher": self.name}, pluck="name"):
			with d.internal():
				flag = frappe.get_doc("Territory Flag", name)
				flag.status = "Action taken"
				flag.resolution = "Source sale cancelled"
				flag.save(ignore_permissions=True)


class StockDeclaration(PartnerDocument):
	def validate(self):
		super().validate()
		if self.docstatus == 2:
			return
		d.lock_partner(self.channel_partner)
		self.period = get_first_day(self.period)
		end = get_last_day(self.period)
		if frappe.db.exists(
			"Partner Serial", {"channel_partner": self.channel_partner, "status": "Return pending"}
		):
			frappe.throw("Complete pending returns before declaring stock")
		if end >= getdate(today()):
			frappe.throw("Only completed months can be declared")
		latest = frappe.db.get_value(
			"Stock Declaration",
			{"channel_partner": self.channel_partner, "docstatus": 1},
			"period",
			order_by="period desc",
		)
		previous = frappe.db.get_value(
			"Stock Declaration",
			{"channel_partner": self.channel_partner, "period": self.period, "docstatus": 1},
			["name", "method"],
			as_dict=True,
		)
		reconciling = bool(previous and previous.method == "Count" and self.method == "Scan")
		if latest and getdate(latest) >= self.period and not reconciling:
			frappe.throw(
				"Declare months in chronological order; a count declaration may be followed by a scan reconciliation"
			)
		self.period_key = self.channel_partner + ":" + str(self.period) + (":scan" if reconciling else "")
		inv = d.stock(self.channel_partner, end)
		seen = set()
		counted = set((self.counted_serials or "").split())
		if self.method == "Scan":
			if len(counted) != len((self.counted_serials or "").split()):
				frappe.throw("Duplicate serials in count")
			# Historical counts cannot be reconstructed once reels moved after month-end.
			if frappe.db.exists(
				"Partner Stock Ledger",
				{"channel_partner": self.channel_partner, "posting_date": [">", end], "qty_reels": ["!=", 0]},
			):
				frappe.throw(
					"Record the declaration before subsequent stock movements, or cancel those movements first"
				)
			known = frappe.get_all(
				"Partner Serial",
				filters={"channel_partner": self.channel_partner, "status": "In stock"},
				fields=["name", "serial_no", "item_code"],
			)
			by_serial = {x.serial_no: x for x in known}
			if not counted.issubset(by_serial):
				frappe.throw("Count contains a serial not currently held in stock")
			totals = {}
			for sn in counted:
				totals[by_serial[sn].item_code] = totals.get(by_serial[sn].item_code, 0) + 1
		else:
			totals = {}
		for row in self.items:
			if row.item_code in seen:
				frappe.throw("Duplicate item in declaration")
			seen.add(row.item_code)
			row.expected = inv.get(row.item_code, {}).get("qty", 0)
			if self.method == "Scan":
				row.counted = totals.get(row.item_code, 0)
			if int(row.counted or 0) < 0 or int(row.counted or 0) > row.expected:
				frappe.throw(
					"Count must be between zero and expected stock; reconcile unexpected receipts first"
				)
			row.difference = int(row.counted or 0) - row.expected
		if any(v["qty"] and k not in seen for k, v in inv.items()):
			frappe.throw("Include every stocked item in the declaration")
		self.total_difference = sum(r.difference for r in self.items)

	def on_submit(self):
		counted = set((self.counted_serials or "").split())
		for row in self.items:
			movement = "Damage" if row.treatment == "Damage" else "Sale-Declared"
			missing = []
			if self.method == "Scan":
				missing = [
					frappe.get_doc("Partner Serial", x)
					for x in frappe.get_all(
						"Partner Serial",
						filters={
							"channel_partner": self.channel_partner,
							"item_code": row.item_code,
							"status": "In stock",
						},
						pluck="name",
					)
				]
				missing = [x for x in missing if x.serial_no not in counted]
				for s in missing:
					d.save_serial(
						s,
						status="Damaged" if movement == "Damage" else "Sold",
						sold_on=get_last_day(self.period) if movement != "Damage" else None,
						last_voucher=self.name,
					)
					d.write_ledger(
						self.channel_partner,
						s.item_code,
						0,
						movement,
						self,
						s,
						date=get_last_day(self.period),
						suffix="serial-reconciliation",
					)
			if row.difference:
				d.write_ledger(
					self.channel_partner,
					row.item_code,
					row.difference,
					movement,
					self,
					date=get_last_day(self.period),
				)

	def on_cancel(self):
		require_manager()
		d.lock_partner(self.channel_partner)
		if frappe.db.exists(
			"Stock Declaration",
			{
				"channel_partner": self.channel_partner,
				"docstatus": 1,
				"name": ["!=", self.name],
				"creation": [">", self.creation],
			},
		):
			frappe.throw("Cancel subsequent declarations first")
		if frappe.db.exists(
			"Partner Stock Ledger",
			{
				"channel_partner": self.channel_partner,
				"creation": [">", self.modified],
				"voucher_no": ["!=", self.name],
			},
		):
			frappe.throw("Reverse subsequent movements before cancelling this declaration")
		for name in frappe.get_all("Partner Serial", filters={"last_voucher": self.name}, pluck="name"):
			d.save_serial(
				frappe.get_doc("Partner Serial", name),
				status="In stock",
				sold_on=None,
				last_voucher="Cancelled " + self.name,
			)
		d.reverse_ledger(self)
		self.db_set("period_key", None)


class PartnerOrder(PartnerDocument):
	def validate(self):
		super().validate()
		if self.docstatus == 2:
			return
		if (
			self.docstatus == 1
			and not self.is_new()
			and self.get_doc_before_save()
			and self.get_doc_before_save().docstatus == 1
		):
			return
		partner = d.lock_partner(self.channel_partner)
		if getdate(self.required_by) < getdate(today()):
			frappe.throw("Required-by date cannot be in the past")
		if not self.items:
			frappe.throw("Add items to your order")
		if self.shipping_address and not frappe.db.exists(
			"Dynamic Link",
			{
				"parent": self.shipping_address,
				"parenttype": "Address",
				"link_doctype": "Customer",
				"link_name": partner.customer,
			},
		):
			frappe.throw("Shipping address does not belong to this customer")
		seen = set()
		total = 0
		for row in self.items:
			if row.item_code in seen:
				frappe.throw("Duplicate item in order")
			seen.add(row.item_code)
			if int(row.qty_reels or 0) <= 0:
				frappe.throw("Order quantities must be positive whole reels")
			price = d.item_rate(row.item_code, partner)
			row.rate = price["rate"]
			row.stock_qty = price["stock_qty"] * row.qty_reels
			row.stock_uom = price["stock_uom"]
			row.amount = row.rate * row.qty_reels
			total += row.amount
			self.currency = price["currency"]
		if sum(x.qty_reels for x in self.items) < d.settings().minimum_order_reels:
			frappe.throw("Order is below the configured minimum")
		self.total = total
		acct = d.account(partner)
		if self.currency != acct["currency"]:
			frappe.throw("Use a price list in the company currency for credit checks")
		self.credit_available = acct["available"]
		over = not acct["unlimited"] and total > acct["available"]
		if over and d.settings().credit_rule == "Block submit":
			frappe.throw("Order exceeds available credit")
		self.status = "Credit approval required" if over else "Pending HQ approval"
		if not self.docstatus:
			self.status = "Draft"
		self.sales_order = None
		self.resolution = None

	def on_submit(self):
		acct = d.account(require_partner(self.channel_partner))
		self.status = (
			"Credit approval required"
			if not acct["unlimited"] and self.total > acct["available"]
			else "Pending HQ approval"
		)
		self.db_set("status", self.status)

	@frappe.whitelist(methods=["POST"])
	def approve(self, credit_override: bool = False):
		require_manager()
		partner = d.lock_partner(self.channel_partner)
		self.reload()
		if self.docstatus != 1 or self.status not in ("Pending HQ approval", "Credit approval required"):
			frappe.throw("Only pending submitted orders can be approved")
		if (
			credit_override
			and frappe.session.user != "Administrator"
			and not {"Accounts Manager", "System Manager"}.intersection(frappe.get_roles())
		):
			frappe.throw("Accounts Manager must approve excess credit", frappe.PermissionError)
		acct = d.account(partner)
		if not acct["unlimited"] and self.total > acct["available"]:
			if not credit_override:
				frappe.throw("Credit approval is required")
			if frappe.session.user != "Administrator" and not {
				"Accounts Manager",
				"System Manager",
			}.intersection(frappe.get_roles()):
				frappe.throw("Accounts Manager must approve excess credit", frappe.PermissionError)
		warehouse = d.settings().default_warehouse
		if not warehouse or not frappe.db.exists(
			"Warehouse", {"name": warehouse, "company": partner.company, "is_group": 0, "disabled": 0}
		):
			frappe.throw("Configure an active dispatch warehouse for this company in Portal Settings")
		so = frappe.get_doc(
			dict(
				doctype="Sales Order",
				set_warehouse=warehouse,
				company=partner.company,
				customer=partner.customer,
				delivery_date=self.required_by,
				transaction_date=today(),
				currency=self.currency,
				selling_price_list=d.settings().price_list,
				po_no=self.po_number,
				shipping_address_name=self.shipping_address,
				distributor_partner_order=self.name,
				items=[
					dict(
						item_code=r.item_code,
						qty=r.stock_qty,
						uom=r.stock_uom,
						warehouse=warehouse,
						rate=r.amount / r.stock_qty,
						delivery_date=self.required_by,
					)
					for r in self.items
				],
			)
		)
		so.insert()
		if not acct["unlimited"] and flt(so.base_grand_total) > acct["available"] and not credit_override:
			frappe.throw("Order including ERPNext taxes exceeds credit; Accounts approval is required")
		self.sales_order = so.name
		self.status = "Approved"
		self.resolution = "Approved with credit override" if credit_override else "Approved by HQ"
		with d.internal():
			self.save()
		return so.name

	@frappe.whitelist(methods=["POST"])
	def reject(self, reason: str):
		require_manager()
		d.lock_partner(self.channel_partner)
		self.reload()
		if self.docstatus != 1 or self.status not in ("Pending HQ approval", "Credit approval required"):
			frappe.throw("Only pending orders can be rejected")
		if not reason.strip():
			frappe.throw("Enter a reason")
		self.status = "Rejected"
		self.resolution = reason
		with d.internal():
			self.save()
		return self.name

	def before_update_after_submit(self):
		if not d.is_internal():
			frappe.throw("Use the order approval actions", frappe.PermissionError)

	def on_cancel(self):
		require_manager()
		if self.sales_order and frappe.db.get_value("Sales Order", self.sales_order, "docstatus") != 2:
			frappe.throw("Cancel or delete the linked Sales Order first")


class PartnerReturn(PartnerDocument):
	def validate(self):
		super().validate()
		if self.docstatus == 2:
			return
		d.lock_partner(self.channel_partner)
		d.assert_open_date(self.channel_partner, self.posting_date)
		d.check_serial_items(self, allowed=None)
		for row in self.items:
			s = d.serial(row.serial_no, self.channel_partner, None)
			if s.status not in ("In stock", "Damaged"):
				frappe.throw("Only stock or damaged reels can be returned")
			row.decision = "Pending"
			if self.reason == "Damaged in transit" and (
				not s.received_on
				or date_diff(self.posting_date, s.received_on) > d.settings().damage_window_days
			):
				frappe.throw("Transit damage reporting window has expired")
		if (
			self.reason in ("Damaged in transit", "Damaged at godown")
			and d.settings().damage_photos_required
			and not self.photo
		):
			frappe.throw("Attach a damage photo")
		if self.photo:
			file = frappe.db.get_value(
				"File", {"file_url": self.photo}, ["owner", "is_private"], as_dict=True
			)
			if not file or not file.is_private or (not is_manager() and file.owner != frappe.session.user):
				frappe.throw("Use a private photo uploaded by you")
		self.status = "Draft"
		self.credit_note = None
		self.resolution = None

	def on_submit(self):
		for row in self.items:
			s = d.serial(row.serial_no, self.channel_partner, None)
			d.save_serial(s, return_previous_status=s.status, status="Return pending", last_voucher=self.name)
		self.db_set("status", "Submitted")

	def before_update_after_submit(self):
		if not d.is_internal():
			frappe.throw("Use the return workflow actions", frappe.PermissionError)

	@frappe.whitelist(methods=["POST"])
	def advance(self, status: str, note: str = "", decisions: dict | None = None):
		require_manager()
		d.lock_partner(self.channel_partner)
		self.reload()
		if self.docstatus != 1:
			frappe.throw("Submit the return first")
		transitions = {"Submitted": "Received", "Received": "Inspected"}
		if self.status in transitions:
			if status != transitions[self.status]:
				frappe.throw("Invalid return transition")
		elif self.status == "Inspected":
			if status != "Decide" or not decisions:
				frappe.throw("Provide an approval decision for every reel")
			accepted = 0
			for row in self.items:
				decision = decisions.get(row.serial_no)
				if decision not in ("Approved", "Rejected"):
					frappe.throw("Decide every reel")
				s = d.serial(row.serial_no, self.channel_partner, "Return pending")
				if s.last_voucher != self.name:
					frappe.throw("Reel is locked by a different transaction")
				row.decision = decision
				if decision == "Approved":
					accepted += 1
					if s.return_previous_status != "Damaged":
						d.write_ledger(self.channel_partner, s.item_code, -1, "Return", self, s, date=today())
					d.save_serial(s, status="Returned", last_voucher=self.name)
				else:
					d.save_serial(s, status=s.return_previous_status or "In stock", last_voucher=self.name)
			status = (
				"Approved"
				if accepted == len(self.items)
				else "Rejected"
				if accepted == 0
				else "Partly approved"
			)
		else:
			frappe.throw("This return has already been decided")
		self.status = status
		self.resolution = note
		with d.internal():
			# Decisions are audit metadata on submitted child rows, maintained only here.
			for row in self.items:
				row.db_set("decision", row.decision)
			self.save()
		return self.status

	@frappe.whitelist(methods=["POST"])
	def link_credit_note(self, invoice: str):
		require_manager()
		d.lock_partner(self.channel_partner)
		self.reload()
		inv = frappe.get_doc("Sales Invoice", invoice)
		partner = require_partner(self.channel_partner)
		if (
			self.status not in ("Approved", "Partly approved")
			or not inv.is_return
			or inv.docstatus != 1
			or inv.customer != partner.customer
			or inv.company != partner.company
		):
			frappe.throw("Choose a submitted credit note for this distributor and company")
		self.credit_note = invoice
		with d.internal():
			self.save()
		return invoice

	def on_cancel(self):
		require_manager()
		d.lock_partner(self.channel_partner)
		if self.status != "Submitted":
			frappe.throw("Only returns awaiting receipt can be cancelled")
		for row in self.items:
			s = d.serial(row.serial_no, self.channel_partner, "Return pending")
			d.save_serial(
				s, status=s.return_previous_status or "In stock", last_voucher="Cancelled " + self.name
			)


class TerritoryFlag(GeneratedDocument):
	@frappe.whitelist(methods=["POST"])
	def explain(self, explanation: str):
		d.lock_partner(self.channel_partner)
		self.reload()
		if self.status not in ("Open", "Explained"):
			frappe.throw("This flag is closed")
		if not explanation.strip():
			frappe.throw("Enter an explanation")
		self.explanation = explanation
		self.status = "Explained"
		with d.internal():
			self.save(ignore_permissions=True)
		return self.name

	@frappe.whitelist(methods=["POST"])
	def resolve(self, resolution: str, status: str = "Accepted"):
		require_manager()
		d.lock_partner(self.channel_partner)
		self.reload()
		if status not in ("Accepted", "Action taken") or not resolution.strip():
			frappe.throw("Select a resolution and enter a note")
		self.status = status
		self.resolution = resolution
		with d.internal():
			self.save()
		return self.name


class PartnerForecast(GeneratedDocument):
	pass
