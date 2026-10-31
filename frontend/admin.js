// ReCircuit admin dashboard (talks to /api/admin/*).
const $ = (id) => document.getElementById(id);
let admin = null, tab = "subs", statusFilter = "pending", timer = null;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const can = (p) => admin && admin.permissions.includes(p);
const cap = (s) => s[0].toUpperCase() + s.slice(1);

function toast(msg) {
	const t = $("toast");
	t.textContent = msg;
	t.classList.add("show");
	clearTimeout(window.toastTimer);
	window.toastTimer = setTimeout(() => t.classList.remove("show"), 2600);
}

async function boot() {
	try {
		admin = (await api("/api/admin/auth/me")).admin;
	} catch {}
	admin ? enterDashboard() : ($("loginView").classList.remove("hide"), $("dashView").classList.add("hide"));
}

$("loginForm").addEventListener("submit", async (e) => {
	e.preventDefault();
	const btn = $("aBtn");
	btn.disabled = true;
	$("aError").textContent = "";
	try {
		admin = (await api("/api/admin/auth/login", { method: "POST", body: { email: $("aEmail").value.trim(), password: $("aPassword").value } })).admin;
		e.target.reset();
		enterDashboard();
	} catch (err) {
		$("aError").textContent = errorText(err);
	} finally {
		btn.disabled = false;
	}
});

async function adminLogout() {
	try { await api("/api/admin/auth/logout", { method: "POST" }); } catch {}
	admin = null;
	$("dashView").classList.add("hide");
	$("loginView").classList.remove("hide");
}

function enterDashboard() {
	$("loginView").classList.add("hide");
	$("dashView").classList.remove("hide");
	$("adminName").textContent = admin.name;
	$("adminRole").textContent = admin.role.replace("_", " ");
	$("tabUsers").classList.toggle("hide", !can("view_users"));
	showTab("subs");
	loadStats();
}

async function loadStats() {
	try {
		const s = await api("/api/admin/stats");
		$("stPending").textContent = s.pending;
		$("stApproved").textContent = s.approved;
		$("stRejected").textContent = s.rejected;
		$("stUsers").textContent = s.users;
	} catch {}
}

function showTab(t) {
	tab = t;
	for (const [k, id] of [["subs", "tabSubs"], ["listings", "tabListings"], ["users", "tabUsers"]])
		$(id).classList.toggle("active", k === t);
	$("aSearch").value = "";
	$("chipsRow").classList.toggle("hide", t !== "subs");
	if (t === "subs") renderChips();
	load();
}

function renderChips() {
	$("chipsRow").innerHTML = ["pending", "approved", "rejected", "all"]
		.map((s) => `<button class="${s === statusFilter ? "active" : ""}" onclick="setStatus('${s}')">${cap(s)}</button>`)
		.join("");
}
function setStatus(s) { statusFilter = s; renderChips(); load(); }
function debounceLoad() { clearTimeout(timer); timer = setTimeout(load, 250); }

async function load() {
	const box = $("tableBox"), q = encodeURIComponent($("aSearch").value.trim());
	box.innerHTML = '<div class="loading"><div class="spinner"></div>Loading…</div>';
	try {
		if (tab === "users") {
			const { users } = await api("/api/admin/users?q=" + q);
			box.innerHTML = users.length
				? `<table><tr><th>Name</th><th>Email</th><th>Phone</th><th>Organization</th><th>Joined</th><th>Submissions</th><th>Approved</th></tr>${users.map((u) => `<tr><td><b>${esc(u.name)}</b></td><td>${esc(u.email)}</td><td>${esc(u.phone || "—")}</td><td>${esc(u.organization || "—")}</td><td>${fmtDate(u.created_at)}</td><td>${u.submissions}</td><td>${u.approved}</td></tr>`).join("")}</table>`
				: '<div class="empty">No users found.</div>';
			return;
		}
		const status = tab === "listings" ? "approved" : statusFilter === "all" ? "" : statusFilter;
		const { components } = await api(`/api/admin/components?status=${status}&q=${q}`);
		if (!components.length) {
			box.innerHTML = `<div class="empty">${tab === "listings" ? "No live listings." : "No submissions here."}</div>`;
			return;
		}
		box.innerHTML = `<table><tr><th>Component</th><th>Submitted by</th><th>Category</th><th>Qty</th><th>Price</th><th>Status</th><th>Submitted</th><th></th></tr>${components.map(row).join("")}</table>`;
	} catch (err) {
		if (err.status === 401) return adminLogout();
		box.innerHTML = `<div class="empty">⚠️ ${esc(err.message)}<br><br><button class="btn btn-light" onclick="load()">Try again</button></div>`;
	}
}

function badge(c) {
	const rec = c.route === "recycle" ? ' <span class="badge recycle">Recycling</span>' : "";
	return `<span class="badge ${c.status}">${cap(c.status)}</span>${rec}`;
}

function row(c) {
	return `<tr><td><b>${esc(c.name)}</b><br><small class="muted">${esc(c.condition)} · ${esc(c.route)}</small></td>
    <td>${c.submitter ? esc(c.submitter.name) + `<br><small class="muted">${esc(c.submitter.email)}</small>` : '<span class="muted">ReCircuit (seed)</span>'}</td>
    <td>${esc(c.category)}</td><td>${c.quantity}</td><td>${c.price ? "₹" + c.price : "Free"}</td><td>${badge(c)}</td><td>${fmtDate(c.submitted_at)}</td>
    <td><button class="btn btn-outline" style="padding:8px 14px" onclick="openDetail(${c.id})">${c.status === "pending" ? "Review" : "View"}</button></td></tr>`;
}

async function openDetail(id) {
	$("detailModal").classList.add("show");
	$("detailBox").innerHTML = '<div class="loading"><div class="spinner"></div></div>';
	try {
		const c = (await api("/api/admin/components/" + id)).component;
		const pending = c.status === "pending", privileged = can("manage_listings");
		const s = c.submitter;
		const approveBtn = c.status !== "approved" && (pending || privileged) ? `<button class="btn btn-primary" onclick="decide(${c.id},'approve')">✓ Approve</button>` : "";
		const rejectBtn = c.status !== "rejected" && (pending || privileged) ? `<button class="btn btn-danger" onclick="decide(${c.id},'reject')">${c.status === "approved" ? "Take down" : "✕ Reject"}</button>` : "";
		const delBtn = privileged ? `<button class="btn btn-outline" onclick="removeListing(${c.id})">🗑 Delete</button>` : "";
		$("detailBox").innerHTML = `
      <div class="modal-head"><h2>${esc(c.name)}</h2><button class="close" onclick="closeDetail()">×</button></div>
      ${badge(c)}
      ${c.images.length ? `<div class="imgs">${c.images.map((u) => `<a href="${esc(u)}" target="_blank" rel="noopener"><img src="${esc(u)}" alt=""></a>`).join("")}</div>` : ""}
      <dl>
        <dt>Category</dt><dd>${esc(c.category)}</dd>
        <dt>Condition</dt><dd>${esc(c.condition)}</dd>
        <dt>Quantity</dt><dd>${c.quantity}</dd>
        <dt>Price per item</dt><dd>${c.price ? "₹" + c.price : "Free"}</dd>
        <dt>Option chosen</dt><dd>${esc(c.route)}</dd>
        <dt>Notes</dt><dd>${esc(c.description) || "—"}</dd>
        <dt>Submitted by</dt><dd>${s ? `${esc(s.name)} (${esc(s.email)})<br><small class="muted">${esc(s.phone || "no phone")} · ${esc(s.organization || "no organization")}</small>` : "ReCircuit (seed data)"}</dd>
        <dt>Submitted</dt><dd>${fmtDate(c.submitted_at)}</dd>
        <dt>Reviewed</dt><dd>${fmtDate(c.reviewed_at)}${c.review_note ? `<br><small class="muted">“${esc(c.review_note)}”</small>` : ""}</dd>
      </dl>
      ${approveBtn || rejectBtn ? `<div class="field"><label>Feedback / rejection reason (optional, shown to the user)</label><textarea id="reviewNote" maxlength="500"></textarea></div>` : ""}
      <div class="form-error" id="detailError"></div>
      <div class="actions">${approveBtn}${rejectBtn}${delBtn}</div>
      ${!approveBtn && !rejectBtn && !pending && !privileged ? '<p class="muted">Only a super admin can change an already-reviewed listing.</p>' : ""}`;
	} catch (err) {
		$("detailBox").innerHTML = `<div class="empty">⚠️ ${esc(err.message)}</div>`;
	}
}
function closeDetail() { $("detailModal").classList.remove("show"); }

async function decide(id, action) {
	const note = ($("reviewNote") || {}).value || "";
	try {
		await api(`/api/admin/components/${id}/${action}`, { method: "POST", body: action === "approve" ? { note } : { reason: note } });
		closeDetail();
		toast(action === "approve" ? "Approved — now live in the marketplace." : "Rejected.");
		load(); loadStats();
	} catch (err) {
		$("detailError").textContent = errorText(err);
	}
}

async function removeListing(id) {
	if (!confirm("Permanently delete this component? This cannot be undone.")) return;
	try {
		await api("/api/admin/components/" + id, { method: "DELETE" });
		closeDetail(); toast("Deleted."); load(); loadStats();
	} catch (err) {
		$("detailError").textContent = errorText(err);
	}
}

boot();
