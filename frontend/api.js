// Tiny fetch wrapper shared by the storefront and the admin dashboard.
class ApiError extends Error {
	constructor(status, code, message, fields) {
		super(message);
		Object.assign(this, { status, code, fields });
	}
}

async function api(path, { method = "GET", body, form } = {}) {
	const opts = { method, credentials: "same-origin", headers: { "X-Requested-With": "recircuit" } };
	if (form) opts.body = form; // multipart: browser sets the boundary header
	else if (body !== undefined) {
		opts.headers["Content-Type"] = "application/json";
		opts.body = JSON.stringify(body);
	}
	let res;
	try {
		res = await fetch(path, opts);
	} catch {
		throw new ApiError(0, "network", "Can't reach the server. Is it running?");
	}
	let data = null;
	try {
		data = await res.json();
	} catch {}
	if (!res.ok) {
		const e = (data && data.error) || {};
		throw new ApiError(res.status, e.code || "error", e.message || "Request failed.", e.fields);
	}
	return data;
}

// "Name is required. Email must be valid." -> single line for form error boxes
function errorText(err) {
	const f = err.fields ? Object.values(err.fields).join(" ") : "";
	return f || err.message;
}

function fmtDate(iso) {
	return iso ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—";
}
