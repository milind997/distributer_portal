import frappe
from frappe.utils import add_months, get_first_day, getdate, today

from distributor_portal.domain import settings


def daily():
	from distributor_portal.api import generate_forecast

	cfg = settings()
	day = getdate(today()).day
	previous = get_first_day(add_months(today(), -1))
	for partner in frappe.get_all("Channel Partner", filters={"active": 1}, pluck="name"):
		if day == cfg.forecast_day:
			generate_forecast(partner)
		if day not in (max(1, cfg.declaration_due_day - 3), cfg.declaration_due_day):
			continue
		if frappe.db.exists(
			"Stock Declaration", {"channel_partner": partner, "period": previous, "docstatus": 1}
		):
			continue
		for user in frappe.get_all(
			"Partner Portal User", filters={"parent": partner, "parenttype": "Channel Partner"}, pluck="user"
		):
			subject = f"Stock declaration due: {previous:%B %Y}"
			if not frappe.db.exists(
				"Notification Log", {"for_user": user, "subject": subject, "creation": [">=", today()]}
			):
				frappe.get_doc(
					dict(
						doctype="Notification Log",
						subject=subject,
						for_user=user,
						type="Alert",
						document_type="Channel Partner",
						document_name=partner,
						email_content="Submit your monthly stock declaration in Distributor Portal.",
					)
				).insert(ignore_permissions=True)
