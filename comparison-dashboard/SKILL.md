---
name: comparison-dashboard
description: >
  Generate standalone HTML dashboards for comparing experiment results across
  multiple configurations. Use this skill when the user has results from
  parameter sweeps, A/B tests, backtest comparisons, model evaluations, or
  any scenario with "N configs × M metrics" data. Trigger on: "generate a
  dashboard", "visualize the results", "compare these configs", "make a
  comparison chart", "show me a report/看板/可视化", or when the user has
  JSON/CSV results and wants a visual overview. Also trigger when you've just
  finished running experiments with multiple configurations and need to
  present the results clearly.
---

# Comparison Dashboard Generator

Generate clean, interactive, standalone HTML dashboards for comparing
experiment results across multiple configurations.

## When to use

- After running parameter sweeps or grid searches
- Comparing A/B test results or strategy variants
- Presenting backtest results across different settings
- Any "N configurations × M metrics" comparison
- User asks for "dashboard", "可视化", "看板", "comparison chart"

## Dashboard anatomy

Every comparison dashboard has these building blocks. Pick the ones
that fit the data:

### 1. Header section
Title, subtitle with context (date, data source, key parameters).

### 2. Metric cards (the "headline numbers")
3-5 top-level KPIs as large colored cards. Use these to show the
most important metric for each configuration at a glance.

Color scheme:
- Green (#00cc66) for best/positive values
- Red (#ff4444) for worst/negative values
- Blue (#4488ff) for neutral/informational
- Yellow (#ffaa00) for warnings/caution

### 3. Comparison table
The core of any comparison dashboard. Rows = configs, columns = metrics.
Highlight the best value in each column with bold + color.

### 4. Charts (optional, when time-series or distributions exist)
- Line charts for equity curves / time-series
- Bar charts for metric comparisons
- Use Chart.js 4 (CDN: `https://cdn.jsdelivr.net/npm/chart.js@4`)

### 5. Detail tables (optional)
Per-config breakdowns (e.g., per-seed results, per-asset results).

## How to build it

### Step 1: Structure the data

Before writing HTML, organize the comparison data into this mental model:

```
configs = [
  { name: "Config A", metrics: { pnl: 1000, sharpe: 1.5, wr: 0.57, ... } },
  { name: "Config B", metrics: { pnl: 800, sharpe: 2.1, wr: 0.55, ... } },
]
```

If there are sub-results (per-seed, per-asset), structure them as nested data:

```
configs[0].details = [
  { seed: 42, pnl: 1200, sharpe: 1.6 },
  { seed: 123, pnl: 800, sharpe: 1.4 },
]
```

### Step 2: Choose what to show

Not every metric deserves a card or chart. Prioritize:

1. **Cards**: The single most important metric (usually the primary objective)
   plus 1-2 secondary metrics. One card per config.
2. **Table**: All metrics, all configs. This is the reference.
3. **Charts**: Only if there's meaningful time-series data or distributions.
   Don't force charts on tabular-only data.

### Step 3: Write the HTML

Use the template in `references/template.html` as a starting point.
Key principles:

- **Single file**: Everything (HTML + CSS + JS) in one `.html` file.
  No external dependencies except Chart.js CDN.
- **Dark theme**: `background: #0a0e1a`, text `#e0e0e0`. This is the
  standard for data dashboards and looks professional.
- **Responsive grid**: Use CSS Grid with `repeat(auto-fit, minmax(250px, 1fr))`
  for cards, and standard table for comparisons.
- **No frameworks**: Plain HTML/CSS/JS. No React, no Tailwind, no build step.
- **Embed data as JS**: Put the comparison data as a JS object directly in
  a `<script>` tag. Don't fetch from external files.

### Step 4: Format numbers well

This matters more than people think:

- Large numbers: use `toLocaleString()` → `$1,234,567`
- Percentages: one decimal → `57.3%`
- Small decimals: two decimals → `1.66`
- Negative numbers: red color + minus sign → <span style="color:red">-$45</span>
- Highlight best-in-class values with bold + green

### Step 5: Save and present

Save the dashboard HTML to the project directory (not a temp location).
Tell the user where it is and provide a direct link.

## CSS patterns to use

```css
/* Base */
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0a0e1a; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; padding: 24px; }

/* Title */
h1 { text-align: center; color: #00cc66; font-size: 1.8em; margin-bottom: 8px; }
.subtitle { text-align: center; color: #888; margin-bottom: 32px; font-size: 0.95em; }

/* Cards grid */
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 32px; }
.card { background: #141824; border: 1px solid #1e2438; border-radius: 12px; padding: 20px; text-align: center; }
.card .label { color: #888; font-size: 0.8em; text-transform: uppercase; margin-bottom: 6px; }
.card .value { font-size: 1.8em; font-weight: bold; }
.card .sub { color: #666; font-size: 0.78em; margin-top: 4px; }

/* Section containers */
.section { background: #0f1320; border: 1px solid #1a1f30; border-radius: 12px; padding: 24px; margin-bottom: 24px; }
.section h2 { color: #ccc; font-size: 1.15em; margin-bottom: 16px; }

/* Tables */
table { width: 100%; border-collapse: collapse; }
th { background: #1a1f30; color: #aaa; padding: 10px 14px; text-align: left; font-weight: 600; font-size: 0.85em; }
td { padding: 10px 14px; border-bottom: 1px solid #1a1f30; font-size: 0.9em; }
tr:hover { background: #161b2e; }

/* Colors */
.green { color: #00cc66; }
.red { color: #ff4444; }
.blue { color: #4488ff; }
.yellow { color: #ffaa00; }
.bold { font-weight: bold; }
```

## Chart.js patterns

For time-series (equity curves, cumulative metrics):

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script>
new Chart(document.getElementById('myChart'), {
  type: 'line',
  data: {
    labels: timestamps,  // array of date strings or numbers
    datasets: configs.map((c, i) => ({
      label: c.name,
      data: c.equityCurve,
      borderColor: ['#00cc66','#4488ff','#ffaa00','#ff4444'][i],
      borderWidth: 2,
      pointRadius: 0,
      fill: false,
    }))
  },
  options: {
    responsive: true,
    scales: {
      y: {
        ticks: { color: '#888', callback: v => '$' + v.toLocaleString() },
        grid: { color: '#1a1f30' }
      },
      x: {
        ticks: { color: '#888', maxTicksAuto: 8 },
        grid: { color: '#1a1f30' }
      }
    },
    plugins: {
      legend: { labels: { color: '#ccc' } }
    }
  }
});
</script>
```

For bar comparisons:

```js
new Chart(ctx, {
  type: 'bar',
  data: {
    labels: configs.map(c => c.name),
    datasets: [{
      label: metricName,
      data: configs.map(c => c.metrics[metricKey]),
      backgroundColor: configs.map((c, i) =>
        ['#00cc6680','#4488ff80','#ffaa0080','#ff444480'][i]
      ),
      borderColor: ['#00cc66','#4488ff','#ffaa00','#ff4444'],
      borderWidth: 1
    }]
  }
});
```

## Common mistakes to avoid

- Don't generate charts for data that's better as a table (small config counts)
- Don't use `localhost` URLs or external data files — everything must be embedded
- Don't use white/light backgrounds — dark theme is standard for data dashboards
- Don't forget to `toLocaleString()` large numbers
- Don't put 20 metrics in cards — pick 3-5 that matter most
- Don't skip the "best value" highlighting in comparison tables

## Reference

See `references/template.html` for a complete working example dashboard.
Use it as a starting point and modify to fit the specific data.
