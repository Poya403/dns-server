async function loadRecords() {
    try {
        const res = await fetch("/admin/records");
        const data = await res.json();

        const tbody = document.getElementById("records-box");
        tbody.innerHTML = "";

        if (data.length === 0) {
            const tr = document.createElement("tr");
            const td = document.createElement("td");
            td.colSpan = 4;
            td.textContent = "رکوردی وجود ندارد";
            td.style.textAlign = "center";
            tr.appendChild(td);
            tbody.appendChild(tr);
            return;
        }

        data.forEach(r => {
            const tr = document.createElement("tr");

            const tdDomain = document.createElement("td");
            tdDomain.textContent = r.domain;
            tr.appendChild(tdDomain);

            const tdQtype = document.createElement("td");
            tdQtype.textContent = r.qtype;
            tr.appendChild(tdQtype);

            const tdValue = document.createElement("td");
            tdValue.textContent = r.value;
            tr.appendChild(tdValue);

            const tdTtl = document.createElement("td");
            tdTtl.textContent = r.ttl;
            tr.appendChild(tdTtl);

            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

async function loadLogs() {
    try {
        const res = await fetch("/admin/logs");
        const data = await res.json();

        const tbody = document.getElementById("logs-box");
        tbody.innerHTML = "";

        if (data.length === 0) {
            const tr = document.createElement("tr");
            const td = document.createElement("td");
            td.colSpan = 3;
            td.textContent = "درخواستی ثبت نشده";
            td.style.textAlign = "center";
            tr.appendChild(td);
            tbody.appendChild(tr);
            return;
        }

        data.forEach(log => {
            const tr = document.createElement("tr");

            const tdDomain = document.createElement("td");
            tdDomain.textContent = log.domain;
            tr.appendChild(tdDomain);

            const tdQtype = document.createElement("td");
            tdQtype.textContent = log.qtype;
            tr.appendChild(tdQtype);

            const tdIp = document.createElement("td");
            tdIp.textContent = log.user_ip;
            tr.appendChild(tdIp);

            const tdSrc = document.createElement("td");
            tdSrc.textContent = log.src;
            tr.appendChild(tdSrc);

            const tdCreatedAt = document.createElement("td");
            tdCreatedAt.textContent = log.created_at;
            tr.appendChild(tdCreatedAt);

            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

window.addEventListener("DOMContentLoaded", () => {
    loadRecords();
    loadLogs();
});
