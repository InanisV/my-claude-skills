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

## Dashboard 构成（按 v42 参考布局，从上到下）

### 1. Header（标题区）
标题用 `#ff44ff`（品红色）。副标题灰色，包含日期、数据源、关键发现摘要。

### 2. Highlight Block（冠军高亮区）— `.highlight`
渐变底色 `linear-gradient(135deg, #1a0a2e, #0a1a2e)` + 品红色半透明边框。
内部用 `.key-diff` 2x2 网格展示 winner vs baseline 的核心指标差异。
底部灰色小字说明核心改动。

### 3. Metric Cards（概要数字）— `.cards`
一行 3-5 个小卡片，每个卡片一个大数字 + 标签 + 副标签。
用于展示 REF 和 best 的关键指标对比、实验总数等概要信息。

### 4. Equity Curve（权益曲线）— 必须有
**每个 dashboard 都必须包含日粒度的权益曲线图。** 这是用户最需要的可视化。

要求：
- **数据必须是日线粒度**，完整嵌入 HTML（不要后端降采样，不要引用外部文件）
- Y 轴必须用**对数坐标**（`type: 'logarithmic'`）
- X 轴为日期，`maxRotation: 0`，`autoSkip: true`
- Winner 线粗 3px，baseline 2.5px，其他 1.5px（视觉区分主角）
- `pointRadius: 0`，`tension: 0.1`（轻微平滑）
- 前端 JS 中做渲染采样（>500天取每7天，>200天取每3天），原始数据保留
- 容器高度 `380px`，`max-height: 400px`

### 4.5. Drawdown Chart（回撤图）— 必须有
**紧跟在权益曲线下方，展示各配置的回撤走势。** 与权益曲线构成"增长+风险"双视图。

要求：
- Y 轴线性坐标（不是对数），显示百分比（`-60%`, `-40%`, ...）
- 填充区域（`fill: true`），半透明背景色（颜色 + `'30'` alpha）
- 容器高度 `300px`（比权益曲线矮一点，主次分明）
- 数据采样方式与权益曲线一致

### 5. Comparison Table（全指标对比表）
行 = configs，列 = metrics。最优值用 `.best`（品红色加粗）高亮。
正值用 `.good`（绿色），负值用 `.bad`（红色），N/A 用 `.neutral`（灰色）。
Winner 行加深背景 `#1a0a2e`，REF 行加深背景 `#0d1525`。

### 6. 其他图表（可选）
Bar chart（分时期收益对比等）。同样遵守高度约束。

### 7. Verdict（关键发现）— `.verdict`
左侧品红竖线，展示实验的核心结论和根因分析。适合放在 dashboard 最后。

### 8. Detail Tables（可选）
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

### 规则 6：X 轴禁止使用 `type: 'time'`，只用默认 category 类型

**这是 Chart.js 最常踩的坑，必须严格遵守。**

Chart.js 的 `type: 'time'` 轴依赖 date adapter（如 chartjs-adapter-date-fns），
如果没有正确安装 adapter，或者日期字符串格式有任何偏差，Chart.js 会静默地将日期
解析为错误的时间戳，导致 X 轴出现 2022→2116 这种荒谬的刻度。

**正确做法**：X 轴用默认的 category 类型（不写 `type`），labels 传字符串数组：

```js
// ✅ 正确：用字符串数组做 labels，X 轴不设 type
labels: ['2022-03-01', '2022-03-08', ...],  // 纯字符串
scales: {
  x: {
    // 不要写 type: 'time' ！
    ticks: {
      color: '#888',
      maxTicksLimit: 10,  // 控制最多显示几个刻度
      maxRotation: 0,     // 水平显示
      autoSkip: true,     // 自动跳过密集标签
    },
    grid: { color: '#1a1f30' }
  }
}
```

```js
// ❌ 错误：不要这样写
scales: {
  x: {
    type: 'time',  // ← 这行是万恶之源！
    time: { unit: 'month' },
    ...
  }
}
```

**为什么 category 类型就够了**：
- 我们的 labels 已经是排好序的日期字符串，Chart.js 按顺序显示即可
- `autoSkip: true` + `maxTicksLimit: 10` 会自动均匀选取 ~10 个标签显示
- 不需要 Chart.js 理解日期的语义，只需要按顺序展示字符串

**额外安全措施**：生成 labels 时自行做采样和格式化，不要依赖 Chart.js 做日期运算：
```js
// 如果原始日期太多，先采样再传给 Chart.js
const step = allDates.length > 500 ? 7 : allDates.length > 200 ? 3 : 1;
const labels = allDates.filter((_, i) => i % step === 0);
// 对应的 equity 数据也要同步采样
const data = allEquity.filter((_, i) => i % step === 0);
```

## 对数坐标权益曲线（标准 pattern）

**直接复制这段代码，只改 data 部分：**

```js
// 数据采样（日线数据超过 200 天时每 N 天取一个点，避免 canvas 渲染卡顿）
const step = dates.length > 500 ? 7 : dates.length > 200 ? 3 : 1;
const sampledDates = dates.filter((_, i) => i % step === 0);
const sampledIdx = dates.map((_, i) => i).filter(i => i % step === 0);

new Chart(document.getElementById('equityChart'), {
  type: 'line',
  data: {
    labels: sampledDates,
    datasets: configs.map((c, i) => ({
      label: c.name,
      data: sampledIdx.map(j => c.equity[j]),
      borderColor: c.color || COLORS[i],
      // winner 线粗 3px，baseline 2.5px，其他 1.5px
      borderWidth: c.isWinner ? 3 : c.isBaseline ? 2.5 : 1.5,
      pointRadius: 0,
      tension: 0.1,  // 轻微平滑，视觉更舒服
      fill: false,
    }))
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { intersect: false, mode: 'index' },
    scales: {
      y: {
        type: 'logarithmic',
        ticks: {
          color: '#888',
          callback: v => '$' + v.toLocaleString()
        },
        grid: { color: '#1a1f30' }
      },
      x: {
        ticks: { color: '#888', maxTicksAuto: 10, autoSkip: true, maxRotation: 0 },
        grid: { color: '#1a1f30' }
      }
    },
    plugins: {
      legend: {
        labels: { color: '#ccc', usePointStyle: true, padding: 16 }
      },
      tooltip: {
        callbacks: {
          label: ctx => `${ctx.dataset.label}: $${ctx.parsed.y?.toLocaleString(undefined, {maximumFractionDigits: 0})}`
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

## 完整 CSS（逐字复制，源自 v42_adaptive_plateau_dashboard.html）

```css
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0e1a;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px;max-width:1400px;margin:0 auto}

/* Header */
h1{text-align:center;color:#ff44ff;font-size:1.8em;margin-bottom:8px}
.subtitle{text-align:center;color:#888;margin-bottom:32px;font-size:0.95em}

/* Highlight block (冠军高亮区，渐变底色) */
.highlight{background:linear-gradient(135deg,#1a0a2e,#0a1a2e);border:1px solid #ff44ff40;border-radius:12px;padding:20px;margin-bottom:24px}
.highlight h2{color:#ff44ff}
.key-diff{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:12px}
.key-diff .item{background:#0a0e1a;padding:12px;border-radius:8px}
.key-diff .item .metric{font-size:1.2em;font-weight:bold}

/* Metric cards (概要数字一行排列) */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:32px}
.card{background:#141824;border:1px solid #1e2438;border-radius:12px;padding:20px;text-align:center}
.card .label{color:#888;font-size:0.75em;text-transform:uppercase;margin-bottom:6px}
.card .value{font-size:1.8em;font-weight:bold}
.card .sub{color:#666;font-size:0.78em;margin-top:4px}

/* Section containers */
.section{background:#0f1320;border:1px solid #1a1f30;border-radius:12px;padding:24px;margin-bottom:24px}
.section h2{color:#ccc;font-size:1.15em;margin-bottom:16px}

/* Tables */
table{width:100%;border-collapse:collapse}
th{background:#1a1f30;color:#aaa;padding:10px 14px;text-align:left;font-weight:600;font-size:0.85em;white-space:nowrap}
td{padding:10px 14px;border-bottom:1px solid #1a1f30;font-size:0.9em}
tr:hover{background:#161b2e}
.best{color:#ff44ff;font-weight:bold}

/* Verdict block (关键发现区) */
.verdict{background:#141824;border-left:4px solid #ff44ff;padding:16px 20px;margin-top:16px;border-radius:0 8px 8px 0}
.verdict h3{color:#ff44ff;margin-bottom:8px}
.verdict p{color:#bbb;line-height:1.6}

/* Chart — 防溢出核心规则（双保险：容器 + canvas 本身） */
canvas{max-height:400px}
.chart-container{position:relative;height:380px;max-height:400px;overflow:hidden;margin-bottom:16px}
.chart-container-short{position:relative;height:300px;max-height:320px;overflow:hidden;margin-bottom:16px}

/* Colors */
.good{color:#00cc66}.bad{color:#ff4444}.neutral{color:#888}
.green{color:#00cc66}.red{color:#ff4444}.blue{color:#4488ff}.yellow{color:#ffaa00}.purple{color:#aa66ff}
.config-desc{color:#666;font-size:0.8em}
```

## 格式化数字

- 大数字：`toLocaleString()` → `$1,234,567`
- 百分比：一位小数 → `57.3%`
- 小数：两位 → `1.66`
- 负值：红色 + 负号
- 最优值：绿色加粗（`.best` class）

## 🔴 Chart.js CDN 路径铁律

**CDN 路径写错是最致命的 bug——所有图表静默空白，页面上没有任何可视的错误提示。**

```html
<!-- ✅ 正确：使用 UMD bundle 的完整路径 -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>

<!-- ❌ 错误：这些路径在 v4 中都不存在 -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js/dist/chart.min.js"></script>
```

为什么会踩坑：Chart.js v2/v3 时代 `chart.min.js` 是正确的，但 v4 重构了构建产物，
UMD 包改名为 `chart.umd.min.js`。写 `chart.min.js` CDN 返回 404，
浏览器只在 DevTools Console 报错，页面上所有图表区域都是空白。

简写 `chart.js@4`（不带 `/dist/...`）也可以（jsDelivr 会自动解析），
但显式写 `chart.umd.min.js` 更安全，不依赖 CDN 的 auto-resolve 行为。

## 🔴 数据必须嵌入 HTML，禁止引用外部文件

Dashboard 必须是 **100% 自包含的单个 HTML 文件**。所有数据直接嵌入 JS 变量中。

```js
// ✅ 正确：数据直接嵌入
const chartData = {
  dates: ["2022-03-01", "2022-03-02", ...],
  baseline: { equity: [100000, 100234, ...], drawdown: [0, -0.002, ...] },
};

// ❌ 错误：外部文件加载
fetch('./equity_curves.json').then(r => r.json()).then(data => { ... })
```

Dashboard 经常被移动、分享、在不同设备上打开。外部引用会断链，用户看到空白图表。
1487 天 × 4 配置 ≈ 200KB 额外体积，换来的是零依赖、永不失效。

## 🔴 权益曲线数据粒度：日线是底线

**禁止在后端做 weekly/monthly 采样。** 用户需要看到每天的波动来评估策略质量——
周线会平滑掉短期回撤，月线完全看不出日内剧烈波动。

性能优化在**前端 JS 做渲染采样**，原始数据完整保留：

```js
const RAW_DATES = [...];   // 完整日线，嵌入 HTML
const step = RAW_DATES.length > 500 ? 7 : RAW_DATES.length > 200 ? 3 : 1;
const sampledDates = RAW_DATES.filter((_, i) => i % step === 0);
// equity/drawdown 数据同步采样
```

## 🔴 回撤图是标配，不是可选

**每个 dashboard 必须包含回撤（Drawdown）图，紧跟在权益曲线下方。**

回撤图和权益曲线是量化分析的"双视图"——权益曲线看增长，回撤图看风险。
缺少回撤图用户无法判断 MaxDD 的时间分布和恢复速度，每次都要追加要求。

回撤图标准 pattern（直接复制，只改 data）：

```js
new Chart(document.getElementById('drawdownChart'), {
  type: 'line',
  data: {
    labels: sampledDates,
    datasets: configs.map((c, i) => ({
      label: c.name,
      data: sampledIdx.map(j => c.drawdown[j]),
      borderColor: c.color || COLORS[i],
      backgroundColor: (c.color || COLORS[i]) + '30',  // 半透明填充
      borderWidth: c.isWinner ? 2.5 : 1.5,
      fill: true,       // 填充区域，视觉强调回撤深度
      pointRadius: 0,
      tension: 0.1,
    }))
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { intersect: false, mode: 'index' },
    scales: {
      y: {
        ticks: {
          color: '#888',
          callback: v => (v * 100).toFixed(0) + '%'
        },
        grid: { color: '#1a1f30' }
      },
      x: {
        ticks: { color: '#888', maxTicksLimit: 12, autoSkip: true, maxRotation: 0 },
        grid: { color: '#1a1f30' }
      }
    },
    plugins: {
      legend: { labels: { color: '#ccc', usePointStyle: true, padding: 16 } },
      tooltip: {
        callbacks: {
          label: ctx => `${ctx.dataset.label}: ${(ctx.parsed.y * 100).toFixed(1)}%`
        }
      }
    }
  }
});
```

## 常见错误提醒

1. ❌ 忘记 `maintainAspectRatio: false` → 图表无视容器高度，撑满屏幕
2. ❌ 用 `aspectRatio` 代替固定高度 → 不同屏幕宽度下高度不可预测
3. ❌ 没有 `.chart-container` 包裹 → canvas 直接撑满父元素
4. ❌ 多个 canvas 共享一个容器 → 高度叠加
5. ❌ 权益曲线用线性 Y 轴 → 早期平坦、后期陡峭，看不出中间的波动
6. ❌ 自由发挥 CSS → 每次生成的 dashboard 长得不一样
7. ❌ 给每个 config 都做一张大卡片 → 卡片太多太占空间，应该只高亮 winner
8. ❌ 缺少权益曲线图 → 用户每次都要问"曲线呢"
9. ❌ X 轴用 `type: 'time'` → 没有 date adapter 时日期解析错乱，出现 2022→2116 的荒谬刻度
10. ❌ labels 和 data 长度不匹配 → 采样时只采了 labels 没采 data（或反过来），导致曲线错位
11. ❌ **CDN 路径用 `chart.min.js`** → v4 不存在此文件，所有图表静默空白（最阴险的 bug）
12. ❌ **数据放在外部 JSON 文件** → 文件移动后图表断链，看到空白
13. ❌ **后端做 weekly/monthly 采样** → 丢失日内波动，用户要求重新生成
14. ❌ **缺少回撤图** → 无法评估风险分布，每次追加要求

## Reference

See `references/template.html` for a complete working example.
**生成 dashboard 时直接复制 template 的结构和 CSS，只替换数据。**
