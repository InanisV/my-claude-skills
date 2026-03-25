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

## 铁律：UI 样式不允许自由发挥

**每次生成 dashboard 时，必须从 `references/template.html` 复制 CSS 和 Chart.js 配置。**
不要凭记忆写 CSS，不要"参考风格后自由发挥"，不要微调颜色/间距/字号。
直接复制 template 中的 `<style>` 块和 Chart.js options，只修改数据部分。

为什么这么严格：AI 每次"参考风格"都会产生微妙的偏移——字号差 0.1em、
间距差 4px、颜色差一个色阶——累积起来用户每次看到的 dashboard 都长得不一样。
唯一的解法是 **逐字复制**，不是"参考"。

## Dashboard 构成

### 1. Header（标题区）
标题 + 副标题（日期、数据源、关键参数变化摘要）。

### 2. Winner Card（冠军卡片）
用绿色边框高亮最优配置，展示 3-6 个核心指标 + vs baseline 的变化百分比。
只有一个 winner card，不要给每个 config 都做一张大卡片。

### 3. Comparison Table（对比表）
行 = configs，列 = metrics。每列最优值加粗绿色高亮。
这是 dashboard 的核心，必须有。

### 4. Equity Curve（权益曲线）— 必须有
**每个 dashboard 都必须包含日粒度的权益曲线图。** 这是用户最需要的可视化。

要求：
- Y 轴必须用**对数坐标**（`type: 'logarithmic'`），方便比较不同量级的增长
- X 轴为日期，格式 `YYYY-MM-DD` 或 `MMM DD`
- 每条曲线一个 config，用不同颜色区分
- `pointRadius: 0`，`borderWidth: 1.5`（线不能太粗）
- 固定高度 `400px`，不允许超出

### 5. 其他图表（可选）
Bar chart 对比、drawdown 曲线等。同样遵守高度约束。

### 6. Detail Tables（可选）
Per-seed、per-asset 的明细数据。

## Chart.js 防溢出铁律

**Chart.js 图表高度溢出是最常见的 bug，以下规则必须严格遵守：**

### 规则 1：canvas 必须包在固定高度容器中
```html
<div class="chart-container">
  <canvas id="myChart"></canvas>
</div>
```

### 规则 2：CSS 必须同时设置 height + max-height + overflow
```css
.chart-container {
  position: relative;
  height: 400px;
  max-height: 400px;
  overflow: hidden;      /* 兜底：即使 Chart.js 渲染出错也不溢出 */
  margin-top: 16px;
}
```

### 规则 3：Chart.js options 中必须同时设置这两项
```js
options: {
  responsive: true,
  maintainAspectRatio: false,  // ← 没有这行 Chart.js 会忽略容器高度！
  ...
}
```

### 规则 4：不允许用 aspectRatio 替代固定高度
不要写 `aspectRatio: 2` 之类的配置。在不同屏幕宽度下 aspectRatio 会导致
高度不可预测。永远用固定高度容器 + `maintainAspectRatio: false`。

### 规则 5：多个图表各自独立容器
每个 `<canvas>` 单独一个 `.chart-container`，不要把多个 canvas 放在同一个
容器里。

## 对数坐标权益曲线（标准 pattern）

**直接复制这段代码，只改 data 部分：**

```js
new Chart(document.getElementById('equityChart'), {
  type: 'line',
  data: {
    labels: dates,  // ['2024-01-01', '2024-01-02', ...]
    datasets: configs.map((c, i) => ({
      label: c.name,
      data: c.equity,  // [1000000, 1002500, ...]
      borderColor: COLORS[i],
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0,
      fill: false,
    }))
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    scales: {
      y: {
        type: 'logarithmic',
        ticks: {
          color: '#888',
          callback: function(v) {
            if (v >= 1000000) return '$' + (v/1000000).toFixed(1) + 'M';
            if (v >= 1000) return '$' + (v/1000).toFixed(0) + 'K';
            return '$' + v;
          }
        },
        grid: { color: '#1a1f30' }
      },
      x: {
        ticks: {
          color: '#888',
          maxRotation: 0,
          autoSkip: true,
          maxTicksLimit: 10
        },
        grid: { color: '#1a1f30' }
      }
    },
    plugins: {
      legend: {
        labels: { color: '#ccc', usePointStyle: true, pointStyle: 'line' }
      },
      tooltip: {
        callbacks: {
          label: function(ctx) {
            return ctx.dataset.label + ': $' + ctx.parsed.y.toLocaleString();
          }
        }
      }
    }
  }
});
```

## Bar Chart（标准 pattern）

```js
new Chart(document.getElementById('barChart'), {
  type: 'bar',
  data: {
    labels: configs.map(c => c.name),
    datasets: [{
      label: metricName,
      data: configs.map(c => c.metrics[key]),
      backgroundColor: configs.map((_, i) => COLORS[i] + '80'),
      borderColor: configs.map((_, i) => COLORS[i]),
      borderWidth: 1
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: {
        ticks: { color: '#888' },
        grid: { color: '#1a1f30' }
      },
      x: {
        ticks: { color: '#888' },
        grid: { display: false }
      }
    },
    plugins: { legend: { display: false } }
  }
});
```

## 标准颜色表

```js
const COLORS = [
  '#00cc66',  // green  - 通常给 winner / baseline
  '#4488ff',  // blue
  '#ffaa00',  // yellow/orange
  '#ff4444',  // red
  '#aa66ff',  // purple
  '#00cccc',  // cyan
  '#ff66aa',  // pink
  '#88cc00',  // lime
];
```

固定顺序，不要随意换。用户看多了会形成颜色→配置的直觉。

## 完整 CSS（逐字复制）

```css
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0e1a;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px;max-width:1400px;margin:0 auto}

/* Header */
h1{text-align:center;color:#00cc66;font-size:1.8em;margin-bottom:8px}
.subtitle{text-align:center;color:#888;margin-bottom:32px;font-size:0.95em}

/* Winner card */
.winner{background:#141824;border:2px solid #00cc66;border-radius:12px;padding:24px;margin-bottom:32px}
.winner .title{color:#00cc66;font-size:1.1em;font-weight:bold;margin-bottom:12px}
.winner .title::before{content:'🏆 '}
.winner .desc{color:#aaa;font-size:0.9em;margin-bottom:16px}
.winner .metrics{display:flex;flex-wrap:wrap;gap:24px}
.winner .metric{text-align:center}
.winner .metric .val{font-size:1.6em;font-weight:bold;color:#fff}
.winner .metric .label{color:#888;font-size:0.75em;margin-top:2px}
.winner .params{color:#888;font-size:0.82em;margin-top:16px;border-top:1px solid #1e2438;padding-top:12px}

/* Section containers */
.section{background:#0f1320;border:1px solid #1a1f30;border-radius:12px;padding:24px;margin-bottom:24px}
.section h2{color:#ccc;font-size:1.15em;margin-bottom:16px}

/* Tables */
table{width:100%;border-collapse:collapse}
th{background:#1a1f30;color:#aaa;padding:10px 14px;text-align:left;font-weight:600;font-size:0.85em;text-transform:uppercase;letter-spacing:0.3px}
td{padding:10px 14px;border-bottom:1px solid #1a1f30;font-size:0.9em}
tr:hover{background:#161b2e}
.best{color:#00cc66;font-weight:bold}

/* Chart — 防溢出核心规则 */
.chart-container{position:relative;height:400px;max-height:400px;overflow:hidden;margin-top:16px}

/* Colors */
.green{color:#00cc66}.red{color:#ff4444}.blue{color:#4488ff}.yellow{color:#ffaa00}.purple{color:#aa66ff}
.bold{font-weight:bold}
```

## 格式化数字

- 大数字：`toLocaleString()` → `$1,234,567`
- 百分比：一位小数 → `57.3%`
- 小数：两位 → `1.66`
- 负值：红色 + 负号
- 最优值：绿色加粗（`.best` class）

## 常见错误提醒

1. ❌ 忘记 `maintainAspectRatio: false` → 图表无视容器高度，撑满屏幕
2. ❌ 用 `aspectRatio` 代替固定高度 → 不同屏幕宽度下高度不可预测
3. ❌ 没有 `.chart-container` 包裹 → canvas 直接撑满父元素
4. ❌ 多个 canvas 共享一个容器 → 高度叠加
5. ❌ 权益曲线用线性 Y 轴 → 早期平坦、后期陡峭，看不出中间的波动
6. ❌ 自由发挥 CSS → 每次生成的 dashboard 长得不一样
7. ❌ 给每个 config 都做一张大卡片 → 卡片太多太占空间，应该只高亮 winner
8. ❌ 缺少权益曲线图 → 用户每次都要问"曲线呢"

## Reference

See `references/template.html` for a complete working example.
**生成 dashboard 时直接复制 template 的结构和 CSS，只替换数据。**
