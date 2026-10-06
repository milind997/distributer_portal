"""Local verification helpers; not exposed as HTTP endpoints."""

import json
from pathlib import Path

import frappe


def seed(path):
	if frappe.local.site != "distributor-portal-test.localhost":
		raise RuntimeError("Test fixture site only")
	from frappe.utils import today
	from frappe.utils.password import update_password

	from distributor_portal import domain as d
	from distributor_portal.tests.test_workflows import TestDistributorWorkflows

	case = TestDistributorWorkflows(methodName="test_partner_sale_api")
	case.setUp()
	reels = case.reels(6)
	user = case.user()
	password = frappe.generate_hash(length=35)
	update_password(user, password)
	sn = frappe.get_doc(
		dict(
			doctype="Serial No",
			serial_no="DP-TRANSIT-" + case.tag,
			item_code=case.item.name,
			company=case.company,
		)
	).insert()
	with d.internal():
		transit = frappe.get_doc(
			dict(
				doctype="Partner Serial",
				serial_no=sn.name,
				channel_partner=case.partner.name,
				item_code=case.item.name,
				length_m=305,
				status="In transit",
			)
		).insert()
	# The browser receipt uses the per-serial action for this standalone fixture.
	payload = dict(
		partner=case.partner.name,
		partner_name=case.partner.partner_name,
		outlet=case.outlet.name,
		outlet_name=case.outlet.outlet_name,
		item=case.item.name,
		serials=[x.serial_no for x in reels],
		serial_ids=[x.name for x in reels],
		transit=transit.name,
		territory=case.territory,
		user=user,
		password=password,
	)
	file = Path(path)
	file.write_text(json.dumps(payload))
	file.chmod(0o600)
	frappe.db.set_single_value("System Settings", "setup_complete", 1)
	frappe.db.commit()
	return "Browser fixtures prepared on isolated test site"


def session_file(path):
	from datetime import UTC, datetime, timedelta

	from frappe.sessions import Session
	from werkzeug.wrappers import Request

	frappe.local.request = Request.from_values(base_url="http://test-com.localhost:8001")
	frappe.local.request_ip = "127.0.0.1"
	session = Session(
		user="Administrator",
		resume=False,
		full_name="Administrator",
		user_type="System User",
		session_end=(datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
		audit_user="Distributor portal verification",
	)
	file = Path(path)
	file.write_text(session.sid)
	file.chmod(0o600)
	frappe.db.commit()
	return "Temporary verification session created"


def revoke_session_file(path):
	from frappe.sessions import delete_session

	file = Path(path)
	if file.exists():
		delete_session(file.read_text(), reason="Distributor portal verification completed")
		frappe.db.commit()
		file.unlink()
	return "Verification session revoked"
