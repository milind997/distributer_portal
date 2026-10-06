export async function request(method, args = {}, verb = "GET", full = false) {
	const url = "/api/method/" + (full ? method : "distributor_portal.api." + method);
	const response = await fetch(url + (verb === "GET" ? "?" + new URLSearchParams(args) : ""), {
		method: verb,
		credentials: "same-origin",
		headers:
			verb === "GET"
				? {}
				: {
						"Content-Type": "application/json",
						"X-Frappe-CSRF-Token": window.distributor_csrf,
					},
		...(verb === "GET" ? {} : { body: JSON.stringify(args) }),
	});
	const data = await response.json();
	if (!response.ok || data.exc) {
		let message = data.message || data.exception || "Request failed";
		try {
			const messages = JSON.parse(data._server_messages || "[]");
			if (messages.length) message = JSON.parse(messages[0]).message;
		} catch {}
		throw new Error(String(message).replace(/<[^>]*>/g, ""));
	}
	return data.message;
}
export async function action(doctype, name, method, args = {}) {
	const response = await fetch(
		"/api/v2/document/" +
			encodeURIComponent(doctype) +
			"/" +
			encodeURIComponent(name) +
			"/method/" +
			method,
		{
			method: "POST",
			credentials: "same-origin",
			headers: {
				"Content-Type": "application/json",
				"X-Frappe-CSRF-Token": window.distributor_csrf,
			},
			body: JSON.stringify(args),
		},
	);
	const data = await response.json();
	if (!response.ok) {
		let message =
			data.message || data.exception || data.errors?.[0]?.message || "Action failed";
		try {
			if (data._server_messages)
				message = JSON.parse(JSON.parse(data._server_messages)[0]).message;
		} catch {}
		throw new Error(String(message).replace(/<[^>]*>/g, ""));
	}
	return data.data ?? data.message;
}
