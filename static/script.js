let allTransactions = [];
let anomalyDates = [];
let pieChartInstance = null;
let barChartInstance = null;

async function uploadFile() {
    const fileInput = document.getElementById("csvFile");
    const status = document.getElementById("uploadStatus");

    if (!fileInput.files[0]) {
        status.textContent = "Please select a CSV file first.";
        return;
    }

    status.textContent = "Analysing...";

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (data.error) {
            status.textContent = "Error: " + data.error;
            return;
        }

        status.textContent = "Analysis complete.";
        status.style.color = "#ffffff";
        renderDashboard(data);

    } catch (error) {
        status.textContent = "Failed to connect to server.";
        console.error(error);
    }
}

function renderDashboard(data) {
    // Show dashboard
    document.getElementById("dashboard").classList.remove("hidden");

    allTransactions = data.all_transactions;
    anomalyDates = data.anomalies.map(a => a.description + a.date);

    // Stats bar
    const total = Object.values(data.category_totals).reduce((a, b) => a + b, 0);
    document.getElementById("totalSpent").textContent = "₹" + total.toLocaleString("en-IN", {minimumFractionDigits: 2});
    document.getElementById("avgTransaction").textContent = "₹" + data.mean.toLocaleString("en-IN");
    document.getElementById("anomalyThreshold").textContent = "₹" + data.threshold.toLocaleString("en-IN");
    document.getElementById("anomalyCount").textContent = data.anomalies.length;

    // Pie chart
    const categories = Object.keys(data.category_totals);
    const categoryAmounts = Object.values(data.category_totals);
    const pieColors = ["#003f5c", "#006770", "#008c54", "#7aa609", "#ffa600"];

    if (pieChartInstance) pieChartInstance.destroy();
    pieChartInstance = new Chart(document.getElementById("pieChart"), {
        type: "pie",
        data: {
            labels: categories,
            datasets: [{
                data: categoryAmounts,
                backgroundColor: pieColors
            }]
        },
        options: {
            plugins: {
                legend: {
                    position: "bottom",
                    labels: { color: "#ffffff" }
                }
            }
        }
    });

    // Bar chart
    const months = Object.keys(data.monthly_totals);
    const monthlyAmounts = Object.values(data.monthly_totals);

    if (barChartInstance) barChartInstance.destroy();
    barChartInstance = new Chart(document.getElementById("barChart"), {
        type: "bar",
        data: {
            labels: months,
            datasets: [{
                label: "Total Spending (₹)",
                data: monthlyAmounts,
                backgroundColor: "#008c54",
                borderRadius: 6
            }]
        },
        options: {
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { color: "#ffffff" },
                    grid: { color: "rgba(255,255,255,0.1)" }
                },
                x: {
                    ticks: { color: "#ffffff" },
                    grid: { color: "rgba(255,255,255,0.1)" }
                }
            }
        }
    });

    // Populate filters
    const categoryFilter = document.getElementById("categoryFilter");
    const monthFilter = document.getElementById("monthFilter");

    categoryFilter.innerHTML = '<option value="all">All</option>';
    monthFilter.innerHTML = '<option value="all">All</option>';

    categories.forEach(cat => {
        const opt = document.createElement("option");
        opt.value = cat;
        opt.textContent = cat;
        categoryFilter.appendChild(opt);
    });

    months.forEach(month => {
        const opt = document.createElement("option");
        opt.value = month;
        opt.textContent = month;
        monthFilter.appendChild(opt);
    });

    // Render table
    renderTable(allTransactions);
}

function renderTable(transactions) {
    const tbody = document.getElementById("tableBody");
    tbody.innerHTML = "";

    transactions.forEach(row => {
        const isAnomaly = anomalyDates.includes(row.description + row.date);
        const tr = document.createElement("tr");
        if (isAnomaly) tr.classList.add("anomaly-row");

        tr.innerHTML = `
            <td>${row.date}</td>
            <td>${row.description}</td>
            <td>₹${parseFloat(row.amount).toLocaleString("en-IN", {minimumFractionDigits: 2})}</td>
            <td>${row.category}</td>
            <td>
                ${isAnomaly
                    ? '<span class="badge-anomaly">Anomaly</span>'
                    : '<span class="badge-normal">Normal</span>'
                }
            </td>
        `;

        tbody.appendChild(tr);
    });
}

function filterTable() {
    const selectedCategory = document.getElementById("categoryFilter").value;
    const selectedMonth = document.getElementById("monthFilter").value;

    let filtered = allTransactions;

    if (selectedCategory !== "all") {
        filtered = filtered.filter(t => t.category === selectedCategory);
    }

    if (selectedMonth !== "all") {
        filtered = filtered.filter(t => t.date.startsWith(selectedMonth));
    }

    renderTable(filtered);
}