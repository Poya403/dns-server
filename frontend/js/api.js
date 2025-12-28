async function loadRecords() {
    const res = await fetch("/admin/records");
    const data = await res.json();

    const tbody = document.getElementById("records-box");
    tbody.innerHTML = "";

    if (data.length === 0) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 5;
        td.textContent = "رکوردی وجود ندارد";
        td.style.textAlign = "center";
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    data.forEach(r => {
        const tr = document.createElement("tr");

        tr.innerHTML = `
            <td>${r.domain}</td>
            <td>${r.qtype}</td>
            <td>${r.value}</td>
            <td>${r.ttl}</td>
            <td>
                <button class="del_btn" onclick="deleteRecord('${r.domain}','${r.qtype}')">
                    حذف
                </button>
            </td>
        `;

        tbody.appendChild(tr);
    });
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

async function deleteRecord(domain, qtype) {
    if (!confirm("آیا از حذف این رکورد مطمئن هستید؟")) return;

    await fetch(`/admin/record/${domain}?qtype=${qtype}`, {
        method: "DELETE"
    });

    loadRecords();
}

window.addEventListener("DOMContentLoaded", () => {
    loadRecords();
    loadLogs();
});

document.getElementById("addRecordForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const record = {
        domain: document.getElementById("domain").value,
        qtype: document.getElementById("qtype").value,
        value: document.getElementById("value").value,
        ttl: Number(document.getElementById("ttl").value)
    };

    await fetch("/admin/record", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(record)
    });

    e.target.reset();
    loadRecords();
});
