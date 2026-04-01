# MEXC Design Tokens — 产品信息图专用

> 基于 MEXC 2025-2026 设计规范（Ocean Blue + 暗色金融主题）
> 最后更新: 2026-04

## CSS 变量定义

将以下变量放在 HTML 的 `<style>` 标签开头。所有组件样式引用这些变量。

```css
:root {
  /* ========== 背景层级 ========== */
  --bg-base:        #0B0E11;     /* 最深底色 — body */
  --bg-surface:     #12151A;     /* 主内容区背景 */
  --bg-card:        #181B22;     /* 卡片/模块背景 */
  --bg-card-hover:  #1E222B;     /* 卡片悬浮态 */
  --bg-elevated:    #242830;     /* 弹出层/高亮区块 */

  /* ========== 品牌色 (Ocean Blue) ========== */
  --brand-primary:    #2B6AFF;   /* 主品牌蓝 — 按钮、链接、选中态 */
  --brand-light:      #5B8FFF;   /* 浅品牌蓝 — 次要强调 */
  --brand-bg:         rgba(43, 106, 255, 0.12);  /* 品牌色弱背景 */
  --brand-gradient:   linear-gradient(135deg, #2B6AFF, #1B4FD8);  /* 品牌渐变 */

  /* ========== 语义色 ========== */
  --color-up:         #00B87A;   /* 涨/盈利/正面/成功 */
  --color-up-bg:      rgba(0, 184, 122, 0.12);
  --color-down:       #F6465D;   /* 跌/亏损/负面/错误 */
  --color-down-bg:    rgba(246, 70, 93, 0.12);
  --color-warning:    #F0B90B;   /* 警告/关注 — MEXC 经典金色 */
  --color-warning-bg: rgba(240, 185, 11, 0.12);
  --color-info:       #1E9FF2;   /* 信息/提示 */
  --color-info-bg:    rgba(30, 159, 242, 0.12);

  /* ========== 文本 ========== */
  --text-primary:     #EAECEF;   /* 主要文本 */
  --text-secondary:   #848E9C;   /* 次要文本/描述 */
  --text-tertiary:    #5E6673;   /* 禁用/最弱文本 */
  --text-inverse:     #0B0E11;   /* 反色文本（用于亮色按钮上） */

  /* ========== 边框 & 分割 ========== */
  --border-default:   rgba(234, 236, 239, 0.06);  /* 默认边框 */
  --border-card:      rgba(234, 236, 239, 0.08);  /* 卡片边框 */
  --border-emphasis:  rgba(234, 236, 239, 0.15);  /* 强调边框 */
  --divider:          rgba(234, 236, 239, 0.06);  /* 分割线 */

  /* ========== 特殊渐变 ========== */
  --gradient-hero:    linear-gradient(135deg, #12151A 0%, #0B0E11 100%);
  --gradient-gold:    linear-gradient(90deg, #F0B90B, #F8D33A);
  --gradient-blue:    linear-gradient(90deg, #2B6AFF, #5B8FFF);
  --gradient-green:   linear-gradient(90deg, #00B87A, #20D59C);
  --gradient-red:     linear-gradient(90deg, #F6465D, #FF6B7D);
  --gradient-footer:  linear-gradient(90deg, #12151A, #1A2038);

  /* ========== 阴影 ========== */
  --shadow-card:      0 2px 8px rgba(0, 0, 0, 0.3);
  --shadow-elevated:  0 4px 16px rgba(0, 0, 0, 0.4);
  --shadow-glow-blue: 0 0 20px rgba(43, 106, 255, 0.15);

  /* ========== 圆角 ========== */
  --radius-sm:   6px;
  --radius-md:   10px;
  --radius-lg:   14px;
  --radius-xl:   20px;
  --radius-full: 9999px;

  /* ========== 间距 ========== */
  --space-xs:  6px;
  --space-sm:  10px;
  --space-md:  16px;
  --space-lg:  24px;
  --space-xl:  36px;
  --space-2xl: 48px;

  /* ========== 字体 ========== */
  --font-sans: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: "SF Mono", "JetBrains Mono", "Fira Code", monospace;
  --font-display: "DIN Alternate", "DIN", "Barlow", var(--font-sans);
}
```

## 全局基础样式

```css
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  background: var(--bg-base);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 14px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

.page {
  width: 820px;
  margin: 0 auto;
  padding: var(--space-xl) var(--space-lg);
}
```

## 组件样式参考

### Hero 区域

```css
.hero {
  background: var(--gradient-hero);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-xl);
  padding: var(--space-xl) var(--space-lg);
  margin-bottom: var(--space-lg);
  position: relative;
  overflow: hidden;
}

/* 装饰性光晕 */
.hero::before {
  content: '';
  position: absolute;
  top: -60px; right: -60px;
  width: 200px; height: 200px;
  background: radial-gradient(circle, rgba(43, 106, 255, 0.08), transparent 70%);
  border-radius: 50%;
}

.hero-tag {
  display: inline-block;
  padding: 4px 14px;
  background: var(--brand-bg);
  border: 1px solid rgba(43, 106, 255, 0.3);
  border-radius: var(--radius-full);
  color: var(--brand-light);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: var(--space-md);
}

.hero-title {
  font-size: 38px;
  font-weight: 800;
  line-height: 1.2;
  margin-bottom: var(--space-sm);
}

.hero-title em {
  font-style: normal;
  background: var(--gradient-gold);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-subtitle {
  color: var(--text-secondary);
  font-size: 15px;
  margin-bottom: var(--space-lg);
}

/* Hero 右侧统计数字 */
.hero-stats {
  display: flex;
  gap: var(--space-md);
  position: absolute;
  top: var(--space-xl);
  right: var(--space-lg);
}

.hero-stat {
  text-align: center;
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-md);
  min-width: 100px;
}

.hero-stat-value {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  color: var(--brand-primary);
}

.hero-stat-label {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
```

### 信息条（Info Bar）

```css
.info-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-2xl);
  font-size: 13px;
}

.info-bar-text {
  color: var(--text-secondary);
}

.info-bar-tags {
  display: flex;
  gap: var(--space-xs);
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
}

.tag-blue    { background: var(--brand-bg);         color: var(--brand-light); }
.tag-green   { background: var(--color-up-bg);       color: var(--color-up); }
.tag-red     { background: var(--color-down-bg);     color: var(--color-down); }
.tag-gold    { background: var(--color-warning-bg);  color: var(--color-warning); }
.tag-neutral { background: var(--bg-elevated);       color: var(--text-secondary); }
```

### Section 容器

```css
.section {
  margin-bottom: var(--space-2xl);
}

.section-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-lg);
}

.section-num {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px; height: 28px;
  background: var(--brand-primary);
  color: white;
  font-weight: 700;
  font-size: 14px;
  border-radius: 50%;
  flex-shrink: 0;
}

.section-header h2 {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.3;
}

.section-header h2 em {
  font-style: normal;
  color: var(--color-warning);
}

.section-header h2 .text-blue   { color: var(--brand-primary); }
.section-header h2 .text-green  { color: var(--color-up); }
.section-header h2 .text-red    { color: var(--color-down); }
.section-header h2 .text-gold   { color: var(--color-warning); }
```

### 布局: Comparison（对比）

```css
.comparison {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-md);
  align-items: stretch;
}

.comparison-card {
  padding: var(--space-lg);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  position: relative;
}

.comparison-card.negative {
  border-left: 3px solid var(--color-down);
}

.comparison-card.positive {
  border-left: 3px solid var(--color-up);
}

.comparison-label {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 600;
  margin-bottom: var(--space-sm);
}

.comparison-label.negative {
  background: var(--color-down-bg);
  color: var(--color-down);
}

.comparison-label.positive {
  background: var(--color-up-bg);
  color: var(--color-up);
}

.comparison-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: var(--space-sm);
}

.comparison-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  position: absolute;
  top: 50%;
  right: -22px;
  transform: translateY(-50%);
  width: 32px; height: 32px;
  background: var(--brand-primary);
  border-radius: 50%;
  z-index: 1;
  color: white;
  font-size: 16px;
}
```

### 布局: Cards Row（并列卡片）

```css
.cards-row {
  display: grid;
  gap: var(--space-md);
}

.cards-row.cols-2 { grid-template-columns: 1fr 1fr; }
.cards-row.cols-3 { grid-template-columns: 1fr 1fr 1fr; }
.cards-row.cols-4 { grid-template-columns: 1fr 1fr 1fr 1fr; }

.card {
  padding: var(--space-lg);
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  text-align: center;
}

.card-icon {
  width: 48px; height: 48px;
  margin: 0 auto var(--space-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 22px;
}

.card-icon.green  { background: var(--color-up-bg);       color: var(--color-up); }
.card-icon.red    { background: var(--color-down-bg);     color: var(--color-down); }
.card-icon.blue   { background: var(--brand-bg);          color: var(--brand-primary); }
.card-icon.gold   { background: var(--color-warning-bg);  color: var(--color-warning); }

.card-label {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
  margin-bottom: var(--space-xs);
}

.card-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 4px;
}

.card-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}
```

### 布局: Flow Steps（流程步骤）

```css
.flow-steps {
  display: flex;
  gap: 0;
  align-items: stretch;
}

.flow-step {
  flex: 1;
  padding: var(--space-md);
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  text-align: center;
  position: relative;
}

.flow-step + .flow-step {
  margin-left: var(--space-md);
}

/* 步骤之间的箭头 */
.flow-step + .flow-step::before {
  content: '›';
  position: absolute;
  left: calc(var(--space-md) * -1 + 2px);
  top: 50%;
  transform: translate(-50%, -50%);
  color: var(--text-tertiary);
  font-size: 20px;
  z-index: 1;
}

.step-num {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 700;
  margin-bottom: var(--space-xs);
  color: white;
}

.step-num.blue  { background: var(--brand-primary); }
.step-num.green { background: var(--color-up); }
.step-num.gold  { background: var(--color-warning); }
.step-num.red   { background: var(--color-down); }

.step-icon {
  font-size: 28px;
  margin: var(--space-xs) 0;
}

.step-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 4px;
}

.step-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: var(--space-xs);
}

.step-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
}
```

### 布局: KPI Highlight（指标展示）

```css
.kpi-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-md);
}

.kpi-card {
  padding: var(--space-lg);
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
}

.kpi-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
}

.kpi-icon {
  width: 36px; height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  font-size: 18px;
}

.kpi-label {
  font-size: 15px;
  font-weight: 700;
}

.kpi-sublabel {
  font-size: 12px;
  color: var(--text-secondary);
}

.kpi-value {
  font-family: var(--font-display);
  font-size: 42px;
  font-weight: 800;
  line-height: 1.1;
  margin-bottom: 4px;
}

.kpi-value .unit {
  font-size: 20px;
  font-weight: 600;
}

.kpi-note {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: var(--space-xs);
}

.kpi-footnote {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: var(--space-xs);
}
```

### 布局: Feature Grid（特性网格）

```css
.feature-grid {
  display: grid;
  gap: var(--space-md);
}

.feature-grid.cols-2 { grid-template-columns: 1fr 1fr; }

.feature-highlight {
  padding: var(--space-md) var(--space-lg);
  background: var(--brand-bg);
  border: 1px solid rgba(43, 106, 255, 0.2);
  border-radius: var(--radius-lg);
  grid-column: 1 / -1;  /* 横跨整行 */
}

.feature-item {
  padding: var(--space-md) var(--space-lg);
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
}

.feature-icon {
  font-size: 20px;
  flex-shrink: 0;
  margin-top: 2px;
}

.feature-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 2px;
}

.feature-desc {
  font-size: 12px;
  color: var(--text-secondary);
}
```

### 布局: Hierarchy / 1-3-9 架构

```css
.hierarchy {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.h-level-1 {
  padding: var(--space-md) var(--space-lg);
  background: var(--brand-gradient);
  border-radius: var(--radius-lg);
  text-align: center;
  color: white;
  font-size: 18px;
  font-weight: 700;
}

.h-level-2-group {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-md);
}

.h-level-2 {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.h-level-2-header {
  padding: var(--space-sm) var(--space-md);
  font-weight: 700;
  font-size: 14px;
  text-align: center;
  border-bottom: 1px solid var(--border-card);
}

.h-level-3-list {
  padding: var(--space-sm) var(--space-md);
}

.h-level-3-item {
  padding: var(--space-xs) 0;
  font-size: 12px;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-default);
}

.h-level-3-item:last-child {
  border-bottom: none;
}
```

### 底栏

```css
.footer-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-md) var(--space-lg);
  background: var(--gradient-footer);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-lg);
  margin-top: var(--space-xl);
}

.footer-title {
  font-size: 16px;
  font-weight: 700;
}

.footer-title em {
  font-style: normal;
  color: var(--color-warning);
}

.footer-subtitle {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

.footer-tags {
  display: flex;
  gap: var(--space-xs);
}
```

### 通用列表样式

```css
.bullet-list {
  list-style: none;
  padding: 0;
}

.bullet-list li {
  padding: var(--space-xs) 0;
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: flex-start;
  gap: var(--space-xs);
}

.bullet-list li::before {
  content: '•';
  color: var(--text-tertiary);
  flex-shrink: 0;
  margin-top: 1px;
}

.bullet-list li.positive::before { content: '✓'; color: var(--color-up); }
.bullet-list li.negative::before { content: '✗'; color: var(--color-down); }
.bullet-list li.highlight::before { content: '★'; color: var(--color-warning); }
```

## 配色使用规则

| 元素 | 推荐色 |
|------|-------|
| Section 编号圆圈 | `--brand-primary` |
| 标题强调词 | `--color-warning`（金色）或 `--color-up`（绿色） |
| 正面/我方方案 | `--color-up` 系列 |
| 负面/行业问题 | `--color-down` 系列 |
| 核心卖点/亮点 | `--color-warning` 系列 |
| 信息性/中性 | `--brand-primary` 系列 |
| 次要/辅助说明 | `--text-secondary` |

## 备注

- 颜色值基于 MEXC 2025-2026 Ocean Blue 暗色主题。如果 MEXC 更新了设计规范，只需修改此文件中的 CSS 变量值即可全局生效。
- 如需亮色版本，可覆盖 `--bg-*` 变量为白色系，`--text-*` 变量为深色系。
- 820px 固定宽度适合 2x 渲染为 1640px 宽的高清 PNG，兼顾微信/钉钉/飞书发送和 PPT 嵌入。
