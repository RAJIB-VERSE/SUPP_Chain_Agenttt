const API_BASE_URL = 'https://tag0qv2isi.execute-api.us-east-1.amazonaws.com/Prod/api';

// DOM Elements
const inventoryTableBody = document.getElementById('inventory-table-body');
const kpiHealthy = document.getElementById('kpi-healthy');
const kpiWarning = document.getElementById('kpi-warning');
const kpiCritical = document.getElementById('kpi-critical');
const kpiLatency = document.getElementById('kpi-latency');
const mlModal = document.getElementById('ml-modal');
const mlModalBody = document.getElementById('ml-modal-body');

// State
let currentSkuForPromo = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    fetchDashboard();
    fetchInventory();
    setupTabs();
});

function setupTabs() {
    const navDashboard = document.getElementById('nav-dashboard');
    const navInventory = document.getElementById('nav-inventory');
    const navForecast = document.getElementById('nav-ml-forecast');
    const navPo = document.getElementById('nav-po');
    
    const allTabs = [navDashboard, navInventory, navForecast, navPo];
    
    const viewDashboard = document.getElementById('dashboard-view');
    const viewInventory = document.getElementById('inventory-view');
    const viewForecast = document.getElementById('forecast-view');
    const viewPo = document.getElementById('po-view');
    const allViews = [viewDashboard, viewInventory, viewForecast, viewPo];
    
    function switchView(tab, viewElement) {
        allTabs.forEach(t => t.parentElement.classList.remove('active'));
        tab.parentElement.classList.add('active');
        allViews.forEach(v => v.style.display = 'none');
        viewElement.style.display = 'block';
    }
    
    navDashboard.addEventListener('click', (e) => {
        e.preventDefault(); switchView(navDashboard, viewDashboard);
        fetchDashboard(); fetchInventory();
    });
    
    navInventory.addEventListener('click', (e) => {
        e.preventDefault(); switchView(navInventory, viewInventory);
        // Reuse fetchInventory for simplicity, but copy table HTML to full-inventory-table
        fetchInventory().then(() => {
            const sourceTable = document.getElementById('dashboard-inventory-table');
            if (sourceTable) {
                document.getElementById('full-inventory-table').innerHTML = sourceTable.innerHTML;
            }
        });
    });
    
    navForecast.addEventListener('click', (e) => {
        e.preventDefault(); switchView(navForecast, viewForecast);
    });
    
    navPo.addEventListener('click', (e) => {
        e.preventDefault(); switchView(navPo, viewPo);
    });

    // Topbar Actions
    const notifBell = document.querySelector('.notification-bell');
    const profileAvatar = document.querySelector('.avatar');
    
    if (notifBell) {
        notifBell.addEventListener('click', () => {
            const criticalCount = document.getElementById('kpi-critical').textContent;
            alert(`You have ${criticalCount} critical stockout alerts pending review in the table below.`);
        });
    }
    
    if (profileAvatar) {
        profileAvatar.addEventListener('click', () => {
            alert("Supply Manager Profile\nRole: Regional Admin\nStatus: Online");
        });
    }
}

// Fetch Dashboard KPIs
async function fetchDashboard() {
    const startTime = performance.now();
    try {
        const res = await fetch(`${API_BASE_URL}/dashboard`);
        const data = await res.json();
        
        const latency = Math.round(performance.now() - startTime);
        
        if (res.ok) {
            kpiHealthy.textContent = data.summary.healthy_sku_records;
            kpiWarning.textContent = data.summary.warning_alerts;
            kpiCritical.textContent = data.summary.critical_stockout_alerts;
            kpiLatency.textContent = latency;
        }
    } catch (err) {
        console.error("Dashboard fetch error:", err);
    }
}

// Fetch Inventory Table
async function fetchInventory() {
    try {
        const res = await fetch(`${API_BASE_URL}/inventory`);
        const data = await res.json();
        
        if (res.ok) {
            renderInventoryTable(data.inventory);
        } else {
            inventoryTableBody.innerHTML = `<tr><td colspan="6" style="color:var(--critical)">Error loading inventory. Is the backend running?</td></tr>`;
        }
    } catch (err) {
        inventoryTableBody.innerHTML = `<tr><td colspan="6" style="color:var(--critical)">Connection refused. Ensure backend is running on port 8000.</td></tr>`;
        console.error(err);
    }
}

// Render Table
function renderInventoryTable(items) {
    inventoryTableBody.innerHTML = '';
    
    // Sort so critical is at top
    items.sort((a, b) => {
        const riskVal = { "CRITICAL": 3, "WARNING": 2, "HEALTHY": 1 };
        return riskVal[b.risk_level] - riskVal[a.risk_level];
    });

    items.forEach(item => {
        const tr = document.createElement('tr');
        
        let riskBadge = '';
        if (item.risk_level === 'CRITICAL') {
            riskBadge = `<span class="status-badge critical"><i class="fa-solid fa-skull-crossbones"></i> CRITICAL</span>`;
        } else if (item.risk_level === 'WARNING') {
            riskBadge = `<span class="status-badge warning"><i class="fa-solid fa-triangle-exclamation"></i> WARNING</span>`;
        } else {
            riskBadge = `<span class="status-badge healthy"><i class="fa-solid fa-check"></i> HEALTHY</span>`;
        }

        tr.innerHTML = `
            <td>
                <strong>${item.store_id}</strong><br>
                <small style="color:var(--text-secondary)">${item.store_name}</small>
            </td>
            <td>
                <strong>${item.sku_name}</strong><br>
                <small style="color:var(--text-secondary)">${item.sku_id} &bull; ${item.category}</small>
            </td>
            <td><strong>${item.current_stock_units}</strong> units</td>
            <td>${item.days_of_inventory.toFixed(1)} days</td>
            <td>${riskBadge}</td>
            <td>
                <button class="btn btn-outline btn-small" onclick="viewForecast('${item.store_id}', '${item.sku_id}')">
                    <i class="fa-solid fa-brain" style="color:var(--accent-primary)"></i> Forecast
                </button>
            </td>
        `;
        inventoryTableBody.appendChild(tr);
    });
}

// ML Forecast Action
async function viewForecast(store_id, sku_id) {
    // Show loading inside modal
    mlModalBody.innerHTML = `<div class="loading-state"><i class="fa-solid fa-circle-notch fa-spin"></i> Running ML Engine...</div>`;
    mlModal.classList.add('active');

    try {
        const payload = {
            store_id: store_id,
            sku_id: sku_id,
            festival_key: "DIWALI",
            forecast_days: 7,
            sales_history: [10,12,15,18,22,25,28,30,35,40,42,45,48,50] // Mock history for UI
        };

        const res = await fetch(`${API_BASE_URL}/forecast`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        
        if (res.ok) {
            currentSkuForPromo = data;
            
            // Render ML insights
            const risk = data.stockout_risk;
            const forecast = data.forecast;
            const hasML = forecast.ml_model_prediction_cartons !== undefined;
            
            let html = `
                <div style="margin-bottom: 20px;">
                    <h3>${data.sku_name} <span style="color:var(--text-secondary)">(${data.store_id})</span></h3>
                    <p style="color:var(--text-secondary); font-size: 0.9rem; margin-top: 5px;">
                        <i class="fa-solid fa-microchip"></i> Engine: ${forecast.engine_used}
                    </p>
                </div>
                
                <div style="display: flex; gap: 20px; margin-bottom: 20px;">
                    <div class="glass" style="padding: 15px; flex: 1; text-align: center;">
                        <div style="color:var(--text-secondary); font-size:0.8rem; margin-bottom:5px;">Realtime Avg Demand</div>
                        <div style="font-size: 1.5rem; font-weight: bold;">${forecast.base_daily_demand.toFixed(1)} <small>units/day</small></div>
                    </div>
                    <div class="glass" style="padding: 15px; flex: 1; text-align: center; border: 1px solid var(--accent-primary);">
                        <div style="color:var(--accent-primary); font-size:0.8rem; margin-bottom:5px;">
                            <i class="fa-solid fa-wand-magic-sparkles"></i> ML Festive Prediction (Diwali)
                        </div>
                        <div style="font-size: 1.5rem; font-weight: bold; color:white;">
                            ${hasML ? forecast.ml_model_prediction_cartons : (forecast.adjusted_daily_demand/24).toFixed(1)} <small>cartons</small>
                        </div>
                    </div>
                </div>

                <div class="glass" style="padding: 15px; background: rgba(255,118,117,0.1); border-color: rgba(255,118,117,0.3);">
                    <h4 style="color: var(--critical); margin-bottom: 10px;"><i class="fa-solid fa-triangle-exclamation"></i> Risk Assessment</h4>
                    <ul style="list-style: none; font-size: 0.9rem; display:flex; flex-direction:column; gap:8px;">
                        <li><strong>Current Stock:</strong> ${risk.current_stock_units} units</li>
                        <li><strong>Runway:</strong> ${risk.days_of_inventory.toFixed(1)} days</li>
                        <li><strong>Shortage:</strong> <span style="color:var(--critical)">${risk.units_short.toFixed(0)} units short</span></li>
                        <li><strong>Lost Revenue Risk:</strong> <span style="color:var(--critical)">₹${risk.projected_revenue_loss_inr.toFixed(2)}</span></li>
                    </ul>
                </div>
            `;
            mlModalBody.innerHTML = html;
        } else {
            mlModalBody.innerHTML = `<div style="color:var(--critical)">Error: ${data.error}</div>`;
        }
    } catch (err) {
        mlModalBody.innerHTML = `<div style="color:var(--critical)">Network Error</div>`;
    }
}

// Close Modal
function closeModal() {
    mlModal.classList.remove('active');
    currentSkuForPromo = null;
}

// Generate Auto-PO
async function generateAutoPO(isStandaloneView = false) {
    if (!isStandaloneView) {
        alert("Generating consolidated Auto-PO for critical SKUs...");
    }
    const payload = {
        store_id: "STR-001",
        festival_key: "DIWALI",
        sku_ids: ["SKU-001", "SKU-005", "SKU-008"] 
    };
    
    try {
        const res = await fetch(`${API_BASE_URL}/auto-po`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if (res.ok) {
            console.log("Generated PO response:", data);
            if (isStandaloneView) {
                const poArea = document.getElementById('po-results-area');
                if (data.purchase_order) {
                    poArea.innerHTML = `
                        <div style="background: var(--bg-primary); padding: 1.5rem; border-radius: 8px; border: 1px solid var(--border-color);">
                            <h4 style="color: var(--accent-primary); margin-bottom: 1rem;">PO #${data.purchase_order.po_number}</h4>
                            <p><strong>Store:</strong> ${data.purchase_order.store_id}</p>
                            <p><strong>Total Amount:</strong> ₹${data.purchase_order.total_amount_inr}</p>
                            <hr style="border-color: var(--border-color); margin: 1rem 0;">
                            <button class="btn btn-primary" onclick="alert('PO Approved & Sent to Supplier!')">Approve & Send to Supplier</button>
                        </div>
                    `;
                } else {
                    poArea.innerHTML = `<p style="color: var(--status-success);"><i class="fa-solid fa-circle-check"></i> ${data.message}</p>`;
                }
            } else {
                if (data.purchase_order) {
                    alert(`Purchase Order #${data.purchase_order.po_number} Generated!\nTotal Amount: ₹${data.purchase_order.total_amount_inr}`);
                } else {
                    alert(`Auto-PO Status:\n${data.message}`);
                }
            }
        } else {
            alert(`Error: ${data.error}`);
        }
    } catch(e) {
        console.error(e);
        alert("Failed to process Auto-PO request. See console for details.");
    }
}

// Standalone ML Forecast
async function runStandaloneForecast() {
    const selected = document.getElementById('forecast-sku-select').value.split('|');
    const store_id = selected[0];
    const sku_id = selected[1];
    
    const resultArea = document.getElementById('standalone-forecast-result');
    resultArea.innerHTML = '<p><i class="fa-solid fa-spinner fa-spin"></i> Running ML pipeline...</p>';

    try {
        const payload = {
            store_id: store_id,
            sku_id: sku_id,
            festival_key: "DIWALI",
            forecast_days: 30,
            sales_history: [120, 130, 115, 140, 135, 125, 130]
        };
        const res = await fetch(`${API_BASE_URL}/forecast`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if (res.ok) {
            const hasML = data.forecast.ml_model_prediction_cartons !== undefined;
            const mlDisplay = hasML ? `${data.forecast.ml_model_prediction_cartons} cartons` : "Not available";
            
            resultArea.innerHTML = `
                <div style="display: flex; gap: 2rem; background: var(--bg-primary); padding: 1.5rem; border-radius: 8px; border: 1px solid var(--border-color);">
                    <div style="flex: 1;">
                        <h4 style="color: var(--text-secondary); margin-bottom: 0.5rem;">S3 Cached ML Forecast</h4>
                        <div style="font-size: 2rem; color: var(--accent-primary); font-weight: 700;">
                            ${mlDisplay}
                        </div>
                        <p style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.5rem;"><i class="fa-solid fa-microchip"></i> Engine: ${data.forecast.engine_used}</p>
                    </div>
                    <div style="flex: 1;">
                        <h4 style="color: var(--text-secondary); margin-bottom: 0.5rem;">Real-time Baseline</h4>
                        <div style="font-size: 2rem; font-weight: 700;">
                            ${data.forecast.base_daily_demand.toFixed(1)} units/day
                        </div>
                    </div>
                </div>
            `;
        } else {
            resultArea.innerHTML = `<p style="color: var(--status-critical);">Error: ${data.error}</p>`;
        }
    } catch (e) {
        console.error("Forecast Error:", e);
        resultArea.innerHTML = `<p style="color: var(--status-critical);">Connection failed or processing error.</p>`;
    }
}

// Trigger WhatsApp Promo
async function triggerPromo() {
    if (!currentSkuForPromo) return;
    
    const hasML = currentSkuForPromo.forecast.ml_model_prediction_cartons !== undefined;
    const cartons = hasML ? currentSkuForPromo.forecast.ml_model_prediction_cartons : 5;

    const payload = {
        sku_name: currentSkuForPromo.sku_name,
        recommended_cartons: cartons,
        festival_key: "DIWALI"
    };

    try {
        const res = await fetch(`${API_BASE_URL}/promotions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if (res.ok) {
            alert("Promo message generated:\n\n" + data.messages.english);
        }
    } catch(e) {
        alert("Failed to connect to backend for Promo.");
    }
}

// Send Telegram Alert
async function triggerTelegramAlert() {
    if (!currentSkuForPromo) return;
    
    // Change button state
    const btn = document.querySelector('.modal-actions .btn-primary');
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Sending...';
    btn.disabled = true;

    try {
        const payload = {
            sku_name: currentSkuForPromo.sku_name,
            recommended_cartons: currentSkuForPromo.forecast.ml_model_prediction_cartons || Math.round(currentSkuForPromo.forecast.adjusted_daily_demand / 24),
            festival_key: "DIWALI",
            send_to_telegram: true
        };

        const res = await fetch(`${API_BASE_URL}/promotions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        
        if (res.ok) {
            btn.innerHTML = '<i class="fa-solid fa-check"></i> Sent via Telegram!';
            btn.style.background = '#2ecc71';
            btn.style.borderColor = '#2ecc71';
        } else {
            alert("Telegram Failed: " + data.error);
            btn.innerHTML = '<i class="fa-brands fa-telegram"></i> Send Telegram Alert';
            btn.disabled = false;
        }
    } catch (e) {
        alert("Network error sending Telegram alert.");
        btn.innerHTML = '<i class="fa-brands fa-telegram"></i> Send Telegram Alert';
        btn.disabled = false;
    }
}

