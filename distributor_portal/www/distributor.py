import frappe

from distributor_portal.permissions import check_app_permission

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/distributor"
		raise frappe.Redirect
	if not check_app_permission():
		frappe.throw("Ask HQ to link your account to a Channel Partner", frappe.PermissionError)
	context.csrf_token = frappe.sessions.get_csrf_token()
	return context
