# 00 · 主流程（唯一权威）

目录
1. 项目骨架与唯一真源
2. 五个阶段、产物与停点
3. 两步法：先 animatic 后完整版
4. 按镜修改
5. 收尾与复盘

## 1. 项目骨架与唯一真源

开工第一件事建目录（`$PROJECT_ROOT` 由进件决定，不要沿用历史项目的路径）：

```
$PROJECT_ROOT/
  brief/        brief.md、decisions.md、delivery-contract.md、numbers.json（可选，成片里的数字只能来自这里）
  footage/      raw/（只读）、work/、index/、clips/、stills/、retake/、reports/
  design/       screen-inventory.md、feature-list.md、frames/
  look/         风格静帧与评分
  components/   复刻界面 HTML 组件
  renderer/     确定性渲染器
  gen/          生成镜头候选、manifest、评分接触表
  audio/        voice/、music/、sfx/、voice_test.md、music_test.md、pronunciation_check.md
  storyboard.json   唯一真源
  script.md         从 storyboard 导出，不手改
  out/          成片与母版
  reports/      接触表、qa_report.md、instruments.md
  run-log.md    每个决定、失败、改法，一行一条（复盘和回写 kit 的来源）
```

唯一真源是 `storyboard.json`：每拍的类型、来源、时间码、文案、旁白、配音时长、图层参数、版式、色温、版本分支。其他一切从它导出。

## 2. 五个阶段、产物与停点

| 阶段 | 做什么 | 读哪份 | 产物 | 停点 |
|---|---|---|---|---|
| 0 进件 | 访谈 ≤ 6 问；交付合同；授权与决策文件；定档位 | 01 | brief.md、delivery-contract.md、decisions.md | 合同有空项时问人 |
| 1 分镜 | 前期研究三件事；三个候选主线；beat sheet 与能量曲线；每镜一行的分镜表（运动用名字）；关键帧板与动态预演；十项评审 | 11、02、12 | 研究文件、三个 logline、shot-list、关键帧板、motion board、storyboard.json v1 | 候选主线交人选；分镜板与评审表交人；不过不进生产 |
| 2 素材与界面 | 录屏理解与选段；补录清单；设计稿清单；复刻界面（标准档） | 03、05 | footage 索引与候选、retake-list、components | 补录清单交人；候选拼图交人按镜号复核 |
| 3 生成与声音 | 平台侦察（首次）；风格静帧；生成镜头候选与评分；逐句配音与仪表；选曲与试混 | 04、06 | gen/、audio/、look/ | 静帧板与试音样本交人定方向和音色 |
| 4 渲染与交付 | animatic → 完整版；仪表全套；最终编码验收；版本分支；按合同导出 | 05、07 | out/、reports/ | animatic 交人看一分钟；成片交人验收 |

阶段 1 的精力不低于阶段 2 到 4 之和；生产中出现的"结构不对"回阶段 1 改。

每个阶段结束写 10 行以内汇报：做了什么、哪些门禁过、哪些缺口、三个坑。缺口照实写，交付完成不等于全过。

## 3. 两步法：先 animatic 后完整版

形式级的改动必须先看粗样，这一条省下的返工最多：

1. 关键帧板：每拍 2 到 3 张静帧（复刻界面或真机截图放进舞台摆位、带色温），拼一张图。
2. animatic：关键帧加简单位移，配真实配音和配乐，出一条粗样。
3. 停下来，人用一分钟定"方向对不对"，顺手听两三个音色样本。
4. 方向对了再做完整版：所有运动做实、生成镜头替换占位、仪表全套。

完整版出来后只允许按拍号增量修改，不再开新形式。两到三轮后定稿，剩余精力转去复盘和参数化。

## 4. 按镜修改

先判断改动类型，再决定重做范围：

| 改动 | 重做范围 |
|---|---|
| 文案 / 字幕 / 布局（单拍） | 只重渲该拍，必要时补渲相邻衔接帧 |
| 时长 / 事件位置（单拍） | 重渲该拍，重检一镜到底与事件锚 |
| 换音色 / 换配乐 / 音效 | 画面包保持，重混音轨，视频 stream copy，核对画面 payload 一致 |
| 导出格式（GIF / 小文件） | 从原生清晰源导出，不重渲、不重配音 |
| 形式 / 结构 | 新建项目目录，旧 storyboard 不沿用 |

改前把当前 story、freeze、proof、manifest 归档；原始录屏和已交付文件永不覆盖。修改冻结范围内的渲染器或组件源码会使全部缓存失效，先想能不能只改数据层。

## 5. 收尾与复盘

- 交付包：成片（按合同格式）、4K 母版（标准档）、storyboard.json、script、qa_report.md（含未过项）、run-log.md。
- 交付后的"上传失败"：先问介质、大小、报错原文，不要无限压小 MP4；见 07 第 5 节。
- 复盘：从 run-log 抽三类内容回写本 kit：通用规则进 references，项目参数进 10-overfit-guard 的参数表，一次性实验进 08-lessons 的可选项。
