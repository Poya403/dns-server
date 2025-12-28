document.querySelectorAll(".actions").forEach((actionDiv) => {
    const toggleBtn = document.createElement("button");
    toggleBtn.textContent = "🔽";
    toggleBtn.style.marginLeft = "10px";
    toggleBtn.classList.add("btn-secondary");
    actionDiv.prepend(toggleBtn);

    toggleBtn.addEventListener("click", () => {
        actionDiv.classList.toggle("collapsed");
        toggleBtn.textContent = actionDiv.classList.contains("collapsed") ? "🔼" : "🔽";
    });
});

function filterRecords() {
    const domain = document.getElementById("searchDomain").value.toLowerCase();
    const qtype = document.getElementById("searchQtype").value.toLowerCase();
    const value = document.getElementById("searchValue").value.toLowerCase();
    const ttl = document.getElementById("searchTTL").value;

    const rows = document.querySelectorAll("#records-box tr");
    rows.forEach(row => {
        const cells = row.querySelectorAll("td");
        const match =
            cells[0].textContent.toLowerCase().includes(domain) &&
            cells[1].textContent.toLowerCase().includes(qtype) &&
            cells[2].textContent.toLowerCase().includes(value) &&
            cells[3].textContent.includes(ttl);
        row.style.display = match ? "" : "none";
    });
}

function filterLogs() {
    const domain = document.getElementById("searchDomainLogs").value.toLowerCase();
    const qtype = document.getElementById("searchQtypeLogs").value.toLowerCase();
    const ip = document.getElementById("searchIpLogs").value.toLowerCase();
    const source = document.getElementById("searchSourceLogs").value.toLowerCase();
    const time = document.getElementById("searchTimeLogs").value.toLowerCase();

    const rows = document.querySelectorAll("#logs-box tr");
    rows.forEach(row => {
        const cells = row.querySelectorAll("td");
        const match =
            cells[0].textContent.toLowerCase().includes(domain) &&
            cells[1].textContent.toLowerCase().includes(qtype) &&
            cells[2].textContent.toLowerCase().includes(ip) &&
            cells[3].textContent.toLowerCase().includes(source) &&
            cells[4].textContent.toLowerCase().includes(time);
        row.style.display = match ? "" : "none";
    });
}


document.getElementById("searchBtnRecords")?.addEventListener("click", filterRecords);
document.getElementById("searchBtnLogs")?.addEventListener("click", filterLogs);

document.querySelectorAll("#records-box input, #logs-box input").forEach(input => {
    input.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            filterRecords();
            filterLogs();
        }
    });
});
