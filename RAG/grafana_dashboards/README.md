# Grafana Dashboards for AI Officer

## 📊 **Available Dashboards**

### **1. LLM Performance** (`1_llm_performance.json`)
Monitors LLM costs, tokens, and latency.

**Panels:**
- Total LLM Requests
- Cost Rate ($/hour)
- Cost per Query
- Average LLM Latency
- LLM Request Rate (by path)
- LLM Cost Rate
- Requests by Path (pie chart)
- Token Usage (stacked)
- LLM Latency Percentiles (P50/P90/P95/P99)

### **2. Retrieval Performance** (`2_retrieval_performance.json`)
Monitors retrieval components and performance.

**Panels:**
- Average Results
- Vector Search Latency
- Graph Query Latency
- Memory Search Latency
- Component Latency Breakdown
- Results by Source
- Results Distribution
- P95 Latencies

### **3. System Health** (`3_system_health.json`)
Overall system health and performance.

**Panels:**
- Requests/sec
- Error Rate
- P95 Latency
- Active Requests
- Request Rate Over Time
- Request Latency Percentiles
- Error Rate Trend
- Requests by Endpoint

### **4. Cost Tracking** (`4_cost_tracking.json`)
Detailed cost analysis and projections.

**Panels:**
- Total Cost
- Daily Projection
- Monthly Projection
- Cost per Query
- Cost Trend
- Cost by Path
- Cost by Model
- Cost per Query by Path
- Token Efficiency

---

## 🚀 **Import Instructions**

### **Method 1: Import via Grafana UI**

1. **Open Grafana**: http://localhost:3000
2. **Login**: admin / admin (default)
3. **Import Dashboard**:
   - Click **+** (Create) → **Import**
   - Click **Upload JSON file**
   - Select one of the JSON files
   - Click **Import**
4. **Configure Data Source**:
   - If prompted, select **Prometheus** as data source
   - Click **Import**
5. **Repeat** for all 4 dashboards

### **Method 2: Import via API** (Advanced)

```powershell
# Set Grafana URL and credentials
$grafanaUrl = "http://localhost:3000"
$grafanaUser = "admin"
$grafanaPass = "admin"

# Import each dashboard
Get-ChildItem "d:\ai officer\RAG\grafana_dashboards\*.json" | ForEach-Object {
    $dashboard = Get-Content $_.FullName -Raw | ConvertFrom-Json
    $body = @{
        dashboard = $dashboard
        overwrite = $true
    } | ConvertTo-Json -Depth 100
    
    $headers = @{
        "Content-Type" = "application/json"
    }
    
    $base64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${grafanaUser}:${grafanaPass}"))
    $headers["Authorization"] = "Basic $base64"
    
    Invoke-RestMethod -Uri "$grafanaUrl/api/dashboards/db" -Method Post -Body $body -Headers $headers
    Write-Host "✅ Imported $($_.Name)"
}
```

---

## ⚠️ **Important: Data Source Configuration**

### **After Import, Configure Prometheus Data Source:**

1. **Go to**: Configuration → Data Sources
2. **Add Prometheus**:
   - Name: `prometheus`
   - URL: `http://localhost:9090`
   - Access: **Server** (default)
3. **Save & Test**
4. **If dashboards show "No data"**:
   - Click on any panel
   - Edit → Query options
   - Make sure Data source is set to **Prometheus**

---

## 📈 **Understanding "No Data"**

### **Why you might see "No Data":**

1. **API Not Running** ⚠️
   - Dashboards show historical data from Prometheus
   - If API was never run, there's no data to show
   - **Solution**: Start your API, send test requests

2. **No Recent Data** 
   - Time range is "Last 6 hours" by default
   - If API ran yesterday, change time range to "Last 24 hours"
   - **Solution**: Adjust time picker (top right)

3. **Prometheus Not Scraping**
   - Check: http://localhost:9090/targets
   - Should show `ai-officer-api` target as **UP**
   - **Solution**: Configure Prometheus scraping

### **Generate Test Data:**

```powershell
# Start your API (if not running)
cd "d:\ai officer\RAG"
python -m uvicorn api.main:app --reload

# Send test requests (in another terminal)
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chat" -Method Post `
  -Body (@{
    message = "Test query"
    executive_id = "exec_001_test"
  } | ConvertTo-Json) `
  -ContentType "application/json"
```

---

## 🔍 **Verifying Data Flow**

### **Step 1: Check if metrics exist**
```powershell
# Query Prometheus directly
Invoke-RestMethod -Uri "http://localhost:9090/api/v1/label/__name__/values" | 
  ConvertFrom-Json | Select-Object -ExpandProperty data | 
  Where-Object { $_ -like "ai_officer*" }
```

### **Step 2: Query specific metric**
```powershell
# Check if there's data for LLM requests
Invoke-RestMethod -Uri "http://localhost:9090/api/v1/query?query=ai_officer_llm_requests_total" |
  ConvertFrom-Json | Select-Object -ExpandProperty data
```

### **Step 3: Check Grafana can see Prometheus**
- Open: http://localhost:3000/datasources
- Click on **Prometheus**
- Click **Save & Test**
- Should see: ✅ "Data source is working"

---

## 🎯 **Quick Start Checklist**

- [ ] Grafana running on http://localhost:3000
- [ ] Prometheus running on http://localhost:9090
- [ ] Prometheus data source configured in Grafana
- [ ] 4 dashboard JSON files imported
- [ ] API has been running and received requests
- [ ] Dashboards showing data (or understand why not)

---

## 📚 **Resources**

- **Grafana Docs**: https://grafana.com/docs/
- **Prometheus Query Examples**: https://prometheus.io/docs/prometheus/latest/querying/basics/
- **Dashboard Design Guide**: `../GRAFANA_DASHBOARD_DETAILED_DESIGN.md`
- **Quick Start Guide**: `../GRAFANA_QUICK_START.md`

---

## 🆘 **Troubleshooting**

### **Dashboard shows "No data"**
1. Check time range (top right corner)
2. Check if Prometheus has data: http://localhost:9090/graph
3. Run test queries to generate data
4. Verify Prometheus target is UP: http://localhost:9090/targets

### **"Failed to load datasource"**
1. Go to Configuration → Data Sources
2. Add Prometheus with URL: http://localhost:9090
3. Re-import dashboards

### **Panels show errors**
1. Click on panel → Edit
2. Check Query is valid
3. Run query manually in Prometheus UI
4. Verify metric names match your instrumentation

---

**Created**: 2025-11-02  
**Version**: 1.0  
**Status**: Ready for Import
