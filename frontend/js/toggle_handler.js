const modal = document.getElementById("recordModal");
const qtype = document.getElementById("qtype");
const priorityField = document.getElementById("priorityField");

document.getElementById("openFormBtn").onclick = () =>
    modal.classList.remove("hidden");

document.getElementById("closeModalBtn").onclick =
document.getElementById("cancelBtn").onclick = () =>
    modal.classList.add("hidden");

qtype.addEventListener("change", () => {
    priorityField.classList.toggle(
        "hidden",
        qtype.value !== "MX"
    );
});

document.getElementById("addRecordForm").addEventListener("submit", e => {
    e.preventDefault();

    let ok = true;
    document.querySelectorAll(".field").forEach(f => f.classList.remove("error"));
    document.querySelectorAll(".error").forEach(e => e.textContent = "");

    const domain = domainEl = document.getElementById("domain");
    const value = document.getElementById("value");

    if (!domain.value) {
        domain.parentElement.classList.add("error");
        domain.nextElementSibling.textContent = "دامنه الزامی است";
        ok = false;
    }

    if (!value.value) {
        value.parentElement.classList.add("error");
        value.nextElementSibling.textContent = "مقدار الزامی است";
        ok = false;
    }

    if (qtype.value === "MX") {
        const pr = document.getElementById("priority");
        if (!pr.value) {
            pr.parentElement.classList.add("error");
            pr.nextElementSibling.textContent = "Priority الزامی است";
            ok = false;
        }
    }

    if (!ok) return;

    modal.classList.add("hidden");
});
