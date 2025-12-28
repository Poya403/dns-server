async function loadRecords() {
    try {
        const res = await fetch("/admin/records");
        const data = await res.json();

        const box = document.getElementById("records-box");
        box.innerHTML = "";

        if (data.length === 0) {
            box.innerHTML = "<p>رکوردی وجود ندارد</p>";
            return;
        }

        const table = document.createElement("table");
        table.style.width = "100%";
        table.style.borderCollapse = "collapse";

        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");
        ["Domain", "QType", "Value", "TTL"].forEach(text => {
            const th = document.createElement("th");
            th.textContent = text;
            th.style.border = "1px solid #ccc";
            th.style.padding = "8px";
            th.style.textAlign = "left";
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");
        data.forEach(r => {
            const row = document.createElement("tr");
            [r.domain, r.qtype, r.value, r.ttl].forEach(val => {
                const td = document.createElement("td");
                td.textContent = val;
                td.style.border = "1px solid #ccc";
                td.style.padding = "8px";
                row.appendChild(td);
            });
            tbody.appendChild(row);
        });
        table.appendChild(tbody);

        box.appendChild(table);
    } catch (err) {
        console.error(err);
    }
}


async function loadLogs() {
    try {
        const res = await fetch("/admin/logs");
        const data = await res.json();

        const box = document.getElementById("logs-box");
        box.innerHTML = "";

        if (!data || data.length === 0) {
            box.innerHTML = "<p>درخواستی ثبت نشده</p>";
            return;
        }

        data.forEach(log => {
            const div = document.createElement("div");
            div.textContent = `${log.domain} | ${log.qtype} | ${log.client_ip}`;
            box.appendChild(div);
        });
    } catch (err) {
        console.error(err);
        const box = document.getElementById("logs-box");
        box.innerHTML = "<p>خطا در بارگذاری لاگ‌ها</p>";
    }
}

window.addEventListener("DOMContentLoaded", () => {
    loadRecords();
    loadLogs();
});
