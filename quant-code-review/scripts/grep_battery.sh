#!/usr/bin/env bash
# grep_battery.sh — quant-code-review 多维度 grep 预扫描（只读，不修改任何文件）
#
# 把 SKILL.md 各维度散落的自动化 grep 探测集中为一次运行，作为人工审计前的
# 前置扫描。命中 != 一定有 bug，但每个命中都应在对应维度的 checklist 中过一遍。
#
# Usage: bash grep_battery.sh [project_root]
set -uo pipefail
ROOT="${1:-.}"
cd "$ROOT" || { echo "path not found: $ROOT" >&2; exit 2; }

EXCL='--exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=venv --exclude-dir=data --exclude-dir=results'
LIM=15

sec() { printf '\n============ %s ============\n' "$1"; }
g() {  # g <label> <pattern> [extra grep args...]
  local label="$1"; shift
  local pat="$1"; shift
  local hits
  hits=$(grep -rnE $EXCL --include='*.py' "$@" "$pat" . 2>/dev/null | grep -vE '(^|/)(tests?|test_)' | head -$LIM)
  if [ -n "$hits" ]; then
    printf -- '--- %s ---\n%s\n' "$label" "$hits"
  else
    printf -- '--- %s --- (no hits)\n' "$label"
  fi
}

sec "0.1 功能模块 feature flags（回测有/实盘无 比对起点）"
g "enable 开关" "_ENABLE|_enable\b|use_[a-z_]+ *[:=]"

sec "1.4 部署缺口（research champion 是否真的接入实盘）"
g "未完成部署 TODO" "TODO.*(wire|deploy|switch|port|integrate)"
g "production_status 标记" "_production_status|NOT_DEPLOYED|DEPLOYED"
g "信号引擎 import" "import.*[Ss]ignal[Ee]ngine|from.*signal_engine"

sec "1.5 Bar 时间约定"
g "索引列设置" "set_index.*(open_time|close_time)"
g "resample 边界" "resample\("
g "partial-bar guard" "subbars|n_subbars"

sec "2.3.1 前视偏差"
g "负向 shift" "shift\(-"
g "居中窗口" "center=True"
g "全样本拟合" "fit_transform|scaler\.fit"
g "选币用全期统计（人工确认时点）" "sort_values.*volume"

sec "2.4 回报率与 turnover 口径"
g "对数回报参与组合 PnL（人工确认）" "np\.log|log_return"
g "turnover 除以 2（费用低估嫌疑）" "turnover.*/ *2|/ *2.*turnover"
g "年化因子 252（crypto 应 365）" "\b252\b"

sec "2.5 杠杆 PnL 公式"
g "杠杆参与 PnL" "sqrt.*lev|leverage.*pnl|pnl.*leverage"

sec "2.8 保证金/爆仓/资金费"
g "保证金核心" "margin_ratio|maintenance_margin|liquidat"
g "可用余额检查" "available.*balance|free.*margin|can_open"
g "funding 结算" "funding.*(rate|fee)|settlement"

sec "2.13 真实性 flag（详见 audit_cascade_simulation.py）"
g "realism flags" "use_(liquidation|wick|funding|slippage|partial_fill|realistic_spread)[a-z_]*|next_bar_entry"

sec "3.12 .env 加载与 NTP"
g ".env loader" "def load_env|os\.environ\.setdefault|dotenv"
hits=$(grep -rnE --include='*.md' --include='*.txt' "NTP|timedatectl|chrony" docs README.md DEPLOY* 2>/dev/null | head -$LIM)
printf -- '--- NTP 文档要求 ---\n%s\n' "${hits:-(no hits — runbook 缺 NTP 要求?)}"

sec "4.6 Unknown-state 硬闩锁"
g "unknown-state 路径" "OrderStateUnknown|unknown_state|ack.*lost|reconcile"

sec "6.1 防御性 fallback（关键路径应 fail-fast）"
g "静默兜底 0" "\?\? 0|\|\| 0|\bor 0\b|\.get\([^,)]+, *0\)"

sec "6.2 宽泛异常捕获"
g "except Exception / 裸 except" "except Exception|except *:"

sec "7.3 密钥硬编码（排除 .example 后人工复核）"
g "key/secret 字面量" "api_key|api_secret|apiKey|apiSecret|private_key"

sec "完成"
echo "提示：每个命中都不是结论，是入口 — 回到 SKILL.md 对应维度的 checklist 逐项判定。"
echo "三个专项脚本：audit_risk_flags.py (P.4) / audit_cascade_simulation.py (2.13) / audit_identity_hardcode.py (4.5.2)"
