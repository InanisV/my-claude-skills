# 证据怎么拿：上币领先天数（公开接口，可复核）

"交易所里最早"这类词必须有数。广场那次用公开接口拉了近三个月热点币的上币时间，口径写进附录，每月可复核。

## 数据源（2026-09 实测可用）

| 交易所 | 接口 | 字段 | 备注 |
|---|---|---|---|
| MEXC 合约 | `GET https://contract.mexc.com/api/v1/contract/detail` | `data[].symbol`、`data[].openingTime`（毫秒，UTC） | 一次返回全部合约，1179 个；按 baseCoin 过滤 |
| 币安 | `GET https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo=N&pageSize=20&catalogId=48` | `articles[].title`、`releaseDate` | catalogId=48 是「新币上线」；标题里写明合约/现货和上线日 |
| OKX | `GET https://www.okx.com/api/v5/support/announcements?annType=announcements-new-listings&page=N` | `details[].title`、`pTime` | 现货上新少，合约可能在别的 annType |
| Bybit | `api.bybit.com/v5/announcements/index` | | 沙箱里被地理限制，拉不到 |

## 口径

- MEXC 合约上线时间：openingTime，UTC
- 币安上线：公告标题所示上线日；合约与现货分别记录，领先天数取币安最早的那个
- OKX 上线：公告发布日
- 领先天数 = 币安最早上线日 − MEXC 合约上线日
- 同日写同日，反例也写；不画入的（领先 11 个月之类）在注里说明

## 结果（2026 Q3，8 枚热点币）

| 币 | MEXC 合约 | 币安 | 领先 |
|---|---|---|---|
| PONS | 07-15 | 合约 09-06 | 53 天 |
| MarsCoin | 07-30 | 合约 09-01，现货 09-04 | 33 天 |
| UNITREE | 07-31 | 合约 08-19 | 19 天 |
| GRAM | 06-15 | 现货 07-02（OKX 06-17） | 17 天 |
| 牛来 | 08-16 | 合约 08-30，现货 09-09 | 14 天 |
| GRVT | 07-30 | 合约 07-31（OKX 现货同日） | 1 天 |
| DOS | 08-11 | 合约 08-11 | 同日 |
| 哈基米 | 2025-10-11 | 合约 2026-09-06 | 11 个月 |

CSV 见 examples/evidence_上币领先天数.csv。

## 写进方案的方式

- 一图流：柱状图四到五根加一个大数「平均早 2 周+」，注一行来源
- 文档：全表 + 🟩 条形（每格 5 天）+ 来源 + 一句解读（"热点在 MEXC 先上是常态不是个案；两周够一个热点从候选走到置顶"）
- 不写"用户什么时候看到"，这个没数据；只写"领先期里站内没有讨论阵地"，这个是事实
