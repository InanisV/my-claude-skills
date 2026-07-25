> **quant-code-review · 维度参考文件** — 由 SKILL.md 按维度 P.3 的适用性裁定按需加载，不要无差别全量读入。
> 文中交叉引用（如"见 2.8"、"参见 4.6"）按维度编号到 references/ 对应文件查找。

## 维度七：供应链与运行时安全

量化交易系统是高价值目标：它持有交易所 API Key（通常有交易权限），7x24 无人值守运行，
直接操控真金白银。供应链攻击一旦成功，攻击者可以：窃取 API Key 转移资产、
篡改策略逻辑制造亏损、植入后门长期潜伏。

**真实案例参考**（2026-03 axios 供应链攻击）：
攻击者通过盗取 npm 维护者凭证，发布了含恶意 postinstall 脚本的 axios 1.14.1。
该脚本通过 XOR+Base64 双层混淆，下载跨平台 RAT（远程访问木马），并在安装完成后
自动清除所有痕迹（用干净的 package.json 替换恶意版本）。从发布到下架仅 2-3 小时，
但足以感染大量 CI/CD 管道。

### 7.1 依赖链审计

```
核心原则：你的安全性等于你最弱的依赖的安全性。

检查项：

□ Lockfile 存在且被 commit
  → Python: requirements.txt 或 poetry.lock（带哈希 --hash）
  → Node: package-lock.json 或 yarn.lock
  → 没有 lockfile = 每次 install 可能拉到不同版本 = 不可复现 + 投毒窗口

□ 版本锁定（pinning）
  → 🔴 "ccxt>=4.0" — 开放范围，可能被投毒的新版本命中
  → ✅ "ccxt==4.2.31" — 精确锁定
  → 检查所有 requirements.txt / package.json 中的版本约束

□ 幽灵依赖检测（Phantom Dependencies）
  → 在 manifest（package.json / requirements.txt）中声明了，但代码中从未 import
  → 这是 axios 攻击的核心手法：加入 plain-crypto-js 作为依赖，
    代码不引用它，但 postinstall 脚本会自动执行
  → 扫描方法：列出所有声明的依赖 → grep 代码中的 import/require → 找出差集

□ 依赖数量合理性
  → 量化系统的核心依赖通常不多：ccxt/exchange SDK、numpy/pandas、TA 库
  → 如果 dependencies 列表异常庞大（>30），逐一审查每个依赖的必要性
  → 关注"你不认识的"依赖——你说不出它干什么的，就不应该在项目里

□ 新增依赖审查
  → 每次 code review 时，如果 requirements.txt / package.json 有改动：
    - 新加的依赖是什么？干什么的？谁维护的？
    - npm/PyPI 上发布多久了？下载量如何？
    - 有没有 typosquatting 嫌疑（如 ccxt-utils vs ccxt_utils）
```

### 7.2 安装脚本与构建钩子

```
核心原则：postinstall / setup.py 中的任意代码执行是供应链攻击的主要入口。

检查项：

□ postinstall 脚本审计（Node 项目）
  → 检查 node_modules 中所有 package.json 的 "scripts" 字段
  → 快速扫描：find node_modules -name package.json -exec grep -l "postinstall\|preinstall" {} \;
  → 任何触发外部下载（curl/wget/fetch）或执行（exec/spawn/eval）的 postinstall = 🔴

□ setup.py / pyproject.toml 审计（Python 项目）
  → setup.py 可以在 install 时执行任意 Python 代码
  → 检查 cmdclass 自定义命令、__builtins__ 操作、网络请求
  → 优选使用声明式 pyproject.toml 而非可执行的 setup.py

□ 混淆代码检测
  → 扫描依赖中的 eval()、exec()、compile()、__import__()
  → 检查 Base64 编码块、XOR 解码函数、charCodeAt 链
  → 量化项目的依赖不应该包含混淆代码——这不是前端 minification

□ CI/CD 安全
  → GitHub Actions / CI 中的 npm install / pip install 是否使用 --ignore-scripts？
  → 是否有 lockfile integrity check（如 npm ci 而非 npm install）？
  → CI 环境是否有出站网络白名单？
```

### 7.3 密钥与敏感信息管理

```
核心原则：API Key 是交易系统的"最高权限凭证"，泄露 = 资产被转移。

检查项：

□ 硬编码密钥扫描
  → grep -rn "api_key\|api_secret\|apiKey\|apiSecret\|private_key" --include="*.py" --include="*.js" --include="*.ts"
  → 排除 .env.example / config.example 中的占位符
  → 🔴 任何真实密钥出现在代码文件中 = Critical（即使在 .gitignore 的文件里也不行，
    因为可能有其他工具/agent 读取代码时泄露）

□ .env / 配置文件安全
  → .env 是否在 .gitignore 中？
  → .env 的权限是否 600（仅所有者可读写）？
  → 是否有 .env.example 模板（不含真实值）？
  → 配置中是否有 withdrawal 相关权限？量化 bot 通常只需 trade 权限，不需要 withdraw

□ Git 历史中的密钥泄露
  → 即使当前代码没有密钥，历史 commit 中可能曾经有
  → git log -p --all -S "api_key" --since="1 year ago" 快速扫描
  → 如发现历史泄露 → 🔴 必须立即轮换该密钥

□ AI Agent 上下文中的密钥暴露
  → 量化项目经常使用 AI（包括本 skill 所在的 Claude）辅助开发
  → 确保 .env 文件不会被 AI agent 读取或出现在对话上下文中
  → 确保 config 加载逻辑不会在日志/错误信息中打印密钥值
  → logger.error(f"Config: {config}") → 🔴 如果 config 包含密钥
```

### 7.4 网络出站控制

```
核心原则：交易 bot 的合法出站连接非常有限——只有交易所 API。
任何其他出站请求都是异常信号。

检查项：

□ 合法出站清单
  → 列出代码中所有硬编码的 URL/域名/IP
  → 交易所 API（api.binance.com, api.hyperliquid.xyz 等）→ ✅ 合法
  → Telegram Bot API（用于通知）→ ✅ 合法
  → 其他任何域名 → 🟡 需要解释为什么需要

□ 动态 URL 检测
  → 搜索从环境变量/配置/远程读取 URL 后发起请求的代码
  → requests.get(config["webhook_url"]) → 🟡 URL 来源可控吗？
  → eval(response.text) / exec(downloaded_code) → 🔴 远程代码执行

□ DNS 与出站防火墙（生产环境）
  → 实盘 bot 运行的服务器是否配置了出站白名单？
  → 建议：iptables / ufw 只允许交易所 IP + Telegram IP 的出站连接
  → 所有非白名单出站请求 = 告警

□ WebSocket 连接审计
  → 量化系统常用 WS 接收实时数据
  → 检查 WS 连接的目标地址是否全部指向合法交易所
  → 检查 WS 消息处理是否有反序列化漏洞（如 pickle.loads / JSON.parse + eval）
```

### 7.5 运行时隔离与权限最小化

```
核心原则：即使代码被攻破，限制攻击者能做的事。

检查项：

□ 运行用户权限
  → bot 是否以 root 运行？→ 🔴 不要用 root
  → 应创建专用用户，只对必要目录有读写权限

□ API Key 权限最小化
  → 交易所 API Key 是否只开启了必要权限？
  → ✅ spot trading / futures trading
  → 🔴 withdrawal（提现）— 量化 bot 绝不需要提现权限
  → 🟡 universal transfer — 除非策略需要跨账户调拨
  → 如果交易所支持 IP 白名单 → 必须绑定 bot 服务器 IP

□ 文件系统隔离
  → bot 是否只能访问自己的工作目录？
  → 是否能读取其他用户的 home 目录、~/.ssh/、~/.aws/ 等敏感路径？
  → Docker 化部署可以天然实现文件系统隔离

□ 进程监控
  → 是否有机制检测 bot 进程产生的异常子进程？
  → 正常的量化 bot 不应 fork/spawn 未知子进程
  → 如果使用 systemd：配置 ProtectHome=true, ProtectSystem=strict
```

### 7.6 代码完整性与变更审计

```
核心原则：确保运行的代码就是你审计过的代码。

检查项：

□ 部署完整性
  → 生产环境的代码是否从 git tag/release 部署？
  → 是否有机制验证部署的代码和 git 中的一致（如 git diff --stat）？
  → 手动改了生产服务器上的文件但没 commit → 🔴 不可追溯

□ AI Agent 代码变更审计（与 alpha-lab 配合）
  → 当 AI agent（如 alpha-lab 研究循环）自主修改策略代码时：
  → 每次修改都有 git commit → ✅（已在 alpha-lab 中要求）
  → 里程碑版本经过 quant-code-review → ✅（已在 alpha-lab 中要求）
  → 但需额外检查：AI 是否引入了不在修改范围内的变更？
    git diff --stat 是否只改了预期的文件？
  → 🔴 AI 修改了 .env / config 中的 API endpoint / 加了新依赖但没说明

□ 依赖更新时的差异审查
  → pip install --upgrade / npm update 后：
  → 检查 lockfile diff，确认只有预期的包被更新
  → 对更新的包检查 changelog，是否有异常（如 maintainer 变更、
    突然增加新依赖、postinstall 脚本变更）

□ 定期安全扫描
  → pip audit / npm audit 定期运行
  → 关注 Critical 和 High 级别的 CVE
  → 尤其关注涉及 RCE（远程代码执行）和 SSRF 的漏洞
```

### 7.7 量化系统特有的攻击面

```
这些攻击面是量化交易系统独有的，通用安全指南通常不会覆盖：

□ 数据源投毒
  → 如果策略依赖第三方数据源（非交易所直接 API），
    数据被篡改 → 策略做出错误决策 → 亏损
  → 检查：数据源是否有 HTTPS + 证书验证？
  → 检查：是否有数据合理性校验（价格在合理范围内、无突变等）？

□ 策略逻辑外泄
  → 策略代码是核心知识产权
  → 是否有日志/错误信息泄露策略细节？
  → 是否有遥测/分析工具在收集代码行为数据？
  → AI agent 对话记录中是否包含完整策略逻辑？

□ Telegram / 通知渠道安全
  → Telegram Bot Token 泄露 = 攻击者可以伪造通知
  → 更严重：如果 bot 支持通过 Telegram 命令控制（如 /stop /close_all），
    Token 泄露 = 攻击者可以远程操控你的交易
  → 检查：Telegram 命令是否有鉴权（如白名单 chat_id）？

□ 时间同步攻击
  → 量化系统依赖准确的时间戳（K线对齐、funding settlement 时间等）
  → NTP 被劫持或服务器时间漂移 → 策略在错误的时间做决策
  → 检查：服务器是否配置了多个 NTP 源？是否有时间偏差告警？
```

### 7.8 API 版本与认证方案兼容性（API Version & Auth Scheme Compatibility）

**为什么这是"安全+运维"交叉的必查项**：交易所会同时维护多套 API（V1/V2/V3、
REST/WS、HMAC-SHA256/Web3-ECDSA/Ed25519 等），并在升级过程中废弃旧版本。
常见踩坑：
- 用户从文档 copy 了 V3 的 Web3 签名示例，但 bot 代码用的是 V1 HMAC-SHA256
- 用户的 API key 是 V1 key，但 bot 代码发的是 V3 请求 → 所有请求返回
  `401 Unauthorized`，用户以为 key 没激活，跑去重新申请，被告知"V1 停止新建"
- 交易所悄悄废弃 V1，给一个 cutoff 日期，用户的老 bot 在那天之后直接失联
- bot 在多交易所/多市场并存时，每个交易所的 auth 方案不同，代码混用

**这种 bug 的特点是"登录层就挂"，根本走不到策略逻辑**——所以必须在审计的"入场"
环节就卡住，不要让它混进生产。

**审查清单**：

```
1. API 版本显式声明：
   □ 代码中实例化 exchange client 时是否显式指定 API 版本
     反例：client = ExchangeClient(key, secret)  # 不知道调的是哪版
     正例：client = ExchangeClientV1(key, secret)  # 或 api_version="v1"
   □ .env.example 的 API key 字段旁边是否注明版本
     示例：
     # ASTER_API_KEY - V1 HMAC-SHA256 key（非 V3 Web3 key）
     #   注意：官方已于 2026-03-25 停止新建 V1 key，老 key 仍可用
     #   新建步骤：https://docs.asterdex.com/api/v1/rest-api#authentication
     ASTER_API_KEY=
     ASTER_API_SECRET=
   □ DEPLOY_RUNBOOK / README 里有"本 bot 使用的 API 版本"章节
   □ requirements.txt 里 pin 的 SDK 版本和 bot 代码调用的 API 版本匹配
     （SDK 升大版本可能默认切换到新 API）

2. 认证方案一致性：
   □ bot 的签名逻辑和 API key 类型匹配：
     - V1 HMAC 类：key + secret 对，用 HMAC-SHA256 签 query string，
       header 是 `X-MBX-APIKEY` / `API-KEY` 等
     - V3 Web3 类：EOA 私钥，用 ECDSA 签 typed data，header 是
       `X-Signature-Address` 等
     - Ed25519 类（部分新交易所）：独立公私钥对
   □ 用错方案的典型症状：401 Unauthorized / "Invalid signature"
     而不是 403 Forbidden
   □ 签名和请求 body 的对齐：body 里的 timestamp 必须和签名里的 timestamp
     一致（用不同 time.time() 调用会差几毫秒，某些 window 严格的交易所会拒签）

3. 官方文档链接与 cutoff 日期：
   □ .env.example / README 里带上"API key 怎么申请"的官方链接
     （用户很容易点进一个看起来像官网的钓鱼站）
   □ 如果交易所公告了"V1 废弃日期"，在 DEPLOY_RUNBOOK 的"已知限制"
     章节明确记录：
     - 老 key 何时会停用
     - 到期前需要完成的迁移步骤
     - 迁移后 bot 代码的变动点
   □ 如果交易所没公告废弃日期，至少记录"本 bot 使用 V1 API，未来升级
     到 V3 需要重写 live/exchange_client.py 的 _sign() 方法"

4. 权限最小化（和 7.3 联动）：
   □ 申请 API key 时是否启用了最小必要权限：
     - READ（必需）
     - FUTURES_TRADE 或对应的 "trade" 权限（必需）
     - WITHDRAW（默认关闭！除非 bot 真的要提币）
     - TRANSFER / SUB_ACCOUNT / MARGIN_BORROW 等高风险权限（默认关闭）
   □ 是否配置了 IP 白名单（绑定部署服务器的 IP）
     - 配置后，即使 key 泄露，攻击者在非白名单 IP 上也无法使用
     - 代价：服务器 IP 变更时要同步更新白名单
   □ 审查时用 bot 账号登录交易所后台对着核对，不是看 .env 猜
   □ 不要使用"主账号"的 API key，应该用子账号 / 独立账号隔离资金

5. 多交易所共存时的隔离：
   □ 如果 bot 同时连接多个交易所（套利 / 多品种 / 主备）：
     - 每个交易所的 API key/secret 用不同的 env 变量名
       反例：API_KEY / API_SECRET（不知道是哪家的）
       正例：ASTER_API_KEY / BINANCE_API_KEY / HYPERLIQUID_PRIVATE_KEY
     - 每个交易所用独立的 client class，不共享签名逻辑
     - 密钥泄露影响范围被限制在单一交易所

6. 升级流程：
   □ 从旧 API 版本迁移到新 API 版本的流程是否写在 DEPLOY_RUNBOOK 里：
     1. 在 testnet / 沙盒环境上用新 key 跑新代码一段时间
     2. 对比新旧 API 返回的关键字段（持仓、余额、订单状态）是否一致
     3. 逐步切换（先读后写、先小金额后全量）
     4. 保留回滚点（旧代码 + 旧 key 配置）
   □ 迁移期间老代码不能被删——保留至少一个 release cycle
```

**参考模式（.env.example 片段）**：

```bash
# ============================================================
# AsterDEX Futures (perpetual contracts)
# ============================================================
# API version:  V1 (HMAC-SHA256)   ← 本 bot 使用
# Auth scheme:  api_key + api_secret (header: X-MBX-APIKEY)
# Docs:         https://docs.asterdex.com/api/v1/rest-api
#
# ⚠️  重要：AsterDEX 已于 2026-03-25 停止创建新的 V1 API key。
#     如果你没有 V1 key，必须迁移到 V3（Web3 签名方案），届时
#     需要重写 live/exchange_client.py 的 _sign() 方法。
#     老 V1 key 仍可继续使用，具体停用时间看官方公告。
# ============================================================
ASTER_API_KEY=
ASTER_API_SECRET=

# API key 权限最小化检查：
# - [x] READ
# - [x] FUTURES_TRADE
# - [ ] WITHDRAW   ← 必须关闭
# - [ ] TRANSFER   ← 必须关闭
# IP 白名单：已绑定部署服务器 IP（可选但强烈推荐）
```

**参考模式（DEPLOY_RUNBOOK 章节片段）**：

```markdown
## 3. API Keys

本 bot 连接 AsterDEX Futures，使用 **V1 API + HMAC-SHA256** 签名方案。

### 3.1 申请步骤
1. 访问 https://asterdex.com/account/api-management
2. 选择 "Create V1 Key"（如果找不到此选项见 §3.2）
3. 勾选权限：READ + FUTURES_TRADE，不要勾 WITHDRAW 和 TRANSFER
4. 绑定服务器 IP 到白名单
5. 保存 key 和 secret 到部署机的 .env 文件

### 3.2 V1 key 创建受限的情况
AsterDEX 于 2026-03-25 默认隐藏 "Create V1 Key" 按钮。
如果你的账户是 2026-03-25 之后注册的，需要：
- 选项 A（推荐）：联系客服申请开放 V1 权限，明确告知是用于做市/量化
- 选项 B：使用 V3（Web3 签名）key，但本 bot 代码不支持，需要额外开发
  （预估工作量：重写 exchange_client.py 约 300 行，1-2 天）

### 3.3 API 版本停用时间表（已知）
- V1 新建：2026-03-25 停止
- V1 使用：目前无公告停用日期，我们会持续监控官方公告
- 建议：至少每季度检查一次 https://asterdex.com/announcements
```

**常见反模式**：

| 反模式 | 后果 | 正确做法 |
|--------|------|----------|
| .env.example 里只写 `API_KEY=` 没说版本 | 用户申请错版本 key，签名 401 | 注明版本 + 签名方案 + 文档链接 |
| SDK 版本未 pin（`pip install exchange-sdk`） | SDK 升级默认换 API 版本 → 某天 bot 静默切到新 API | pin 到 `==x.y.z`，升级前审 changelog |
| bot 的签名逻辑混用多套方案（if exchange == "A" elif ...） | 新增交易所要改核心 auth 路径，容易回归 bug | 每个交易所独立 client class |
| 所有交易所共用一套 `API_KEY` / `API_SECRET` env | 泄露时影响面大 | 每家独立 env 变量名 |
| 申请 key 时"一键开启所有权限" | 泄露后攻击者可以提币、转账 | READ + 对应 trade 权限即可 |
| 没配 IP 白名单 | key 泄露后立刻能用 | 绑定服务器 IP |
| 用主账号 key | 主账号资金全暴露 | 独立子账号 |
| DEPLOY_RUNBOOK 不记录 cutoff 日期 | 某天醒来 bot 失联，查了 2 小时才发现是 API 废弃 | "已知限制" 章节明写 |
| V1 与 V3 混搭（V1 key 配 V3 签名代码） | 所有请求 401，用户以为是 key 坏了 | 启动时先调一个无害 endpoint 校验 auth |

**启动时的自检**：

bot 在 `prepare()` 阶段应该调用一个"无副作用"的 endpoint（如 `GET /fapi/v1/account`
或 `GET /v3/user/positions`）来验证签名正确。**不要等第一次下单时才发现签名错**——
下单失败的原因有十种，很难第一时间归因到"auth 方案选错了"；但启动自检一旦失败，
报错信息可以非常明确：

```python
def verify_auth(self):
    """启动时调用一次，确保签名方案和 key 匹配。"""
    try:
        account = self.client.get_account()
    except AuthError as e:
        # 尽量给出排障提示
        raise SystemExit(
            f"❌ Auth self-check failed: {e}\n"
            f"   Used API version: {self.client.api_version}\n"
            f"   Used auth scheme: {self.client.auth_scheme}\n"
            f"   请核对 .env 中的 ASTER_API_KEY 是否是 {self.client.api_version} "
            f"版本的 key。V1 key 和 V3 key 的签名方案不同。\n"
            f"   文档：{self.client.DOCS_URL}"
        )
    log.info("auth self-check OK: api=%s, account_id=%s",
             self.client.api_version, account["accountId"])
```

**与维度 7.3 "密钥与敏感信息管理" 的关系**：
- 7.3 关注的是 "密钥不要泄露"（存储、传输、日志脱敏）
- 7.8 关注的是 "密钥和代码匹配"（版本、签名方案、权限范围）
- 两个维度都是 API key 生命周期管理的一部分，可以在同一次审计中一起过
