import frappe
from frappe.utils import today

from distributor_portal import domain as d


def delivery_serials(doc):
	for row in doc.items:
		if row.get("serial_and_batch_bundle"):
			entries = frappe.get_all(
				"Serial and Batch Entry",
				filters={"parent": row.serial_and_batch_bundle},
				fields=["serial_no", "batch_no"],
			)
		else:
			entries = [
				frappe._dict(serial_no=s, batch_no=row.get("batch_no"))
				for s in (row.get("serial_no") or "").split()
			]
		for entry in entries:
			if entry.serial_no:
				yield row, entry


def delivery_submit(doc, method=None):
	name = frappe.db.get_value(
		"Channel Partner", {"customer": doc.customer, "company": doc.company, "active": 1}, "name"
	)
	if not name:
		return
	# ERPNext dispatch is an HQ operation; portal access is not required for warehouse users.
	frappe.db.sql("select name from `tabChannel Partner` where name=%s for update", name)
	for row, entry in delivery_serials(doc):
		existing = frappe.db.get_value("Partner Serial", {"serial_no": entry.serial_no}, "name")
		if doc.is_return:
			if not existing:
				continue
			s = frappe.get_doc("Partner Serial", existing)
			if s.channel_partner != name:
				frappe.throw("Returned reel belongs to a different distributor")
			if s.status == "Returned":
				continue  # Already processed by the approved partner return.
			if s.status not in ("In stock", "In transit"):
				frappe.throw("Cannot return a reel already sold onward")
			if s.status != "In transit":
				d.write_ledger(name, s.item_code, -1, "Return", doc, s)
			d.save_serial(s, status="Returned", return_previous_status=s.status, last_voucher=doc.name)
		else:
			if existing:
				s = frappe.get_doc("Partner Serial", existing)
				if s.delivery_note == doc.name:
					continue
				if s.status != "Returned":
					frappe.throw(f"Serial {entry.serial_no} is already assigned in the channel")
				d.save_serial(
					s,
					channel_partner=name,
					delivery_note=doc.name,
					status="In transit",
					received_on=None,
					sold_on=None,
					sold_to=None,
					last_voucher=doc.name,
				)
			else:
				with d.internal():
					s = frappe.get_doc(
						dict(
							doctype="Partner Serial",
							serial_no=entry.serial_no,
							channel_partner=name,
							item_code=row.item_code,
							batch_no=entry.batch_no,
							length_m=d.reel_length(row.item_code),
							delivery_note=doc.name,
							status="In transit",
							last_voucher=doc.name,
						)
					).insert(ignore_permissions=True)
			d.write_ledger(name, s.item_code, 0, "Dispatch", doc, s)


def delivery_cancel(doc, method=None):
	for _row, entry in delivery_serials(doc):
		name = frappe.db.get_value("Partner Serial", {"serial_no": entry.serial_no}, "name")
		if not name:
			continue
		s = frappe.get_doc("Partner Serial", name)
		if doc.is_return:
			if s.last_voucher != doc.name:
				continue
			if s.status != "Returned":
				frappe.throw("The returned reel has moved again")
			d.save_serial(
				s,
				status=s.return_previous_status or "In stock",
				last_voucher=s.name if s.received_on else s.delivery_note,
			)
			continue
		if s.delivery_note != doc.name:
			continue
		if s.last_voucher != doc.name or s.status != "In transit":
			frappe.throw(
				"A reel has moved in the distributor portal. Reverse its movements before cancelling dispatch"
			)
		d.save_serial(s, status="Returned", last_voucher="Cancelled " + doc.name)
	d.reverse_ledger(doc)
