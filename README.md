# Game Radar

个人游戏折扣与新游雷达。

- 每天北京时间 **14:00**（UTC 06:00）由 GitHub Actions 自动更新。
- 当前自动数据源：Steam 国区公开接口。
- 自动排除 config.json 中已拥有的游戏。
- “站内新低”是本项目开始追踪后的最低价，不等于 SteamDB 全历史史低。
- Epic 免费史、SteamPY / SteamCiCi、DLC、中文差评、官方手机移植需要额外可靠数据源；没有核实时不会伪造。

## GitHub Pages

仓库 Settings → Pages → Build and deployment → Source 选择 **GitHub Actions**。
之后运行一次 Daily Game Radar 工作流即可发布。


## SQLite 持久化

定时任务运行时会在 GitHub Actions 容器中写入 `data/game_radar.db`（SQLite），并通过 `git add data/` 把数据库提交回仓库。下次运行会从上次的数据库继续累计；它**不是 ChatGPT 服务器上的持久磁盘**，也不会自动同步到你的 Mac。

已有的 `data/games.json` 继续提供 GitHub Pages 网站展示，`data/history.json` 继续保存旧版站内最低价。新库从启用之日起按天积累实际观测，不把历史 JSON 中没有日期的低价伪造成某日价格。

表结构：`game_info`、`steam_price_history`、`key_price_history`、`epic_free_history`、`mobile_platform`、`steam_deck_info`、`game_dlc`、`user_owned_games`。

目前 `steam_price_history` 存储 Steam 国区接口每日候选价格，`key_price_history` 严格区分散 Key 接口参考价与 SteamCiCi 历史挂售；Steam Deck、DLC 仅为未来已核实数据保留结构，不代表现在已自动抓取。

本仓库是公开仓库，因此 SQLite 文件也是公开的，不应向数据库或配置文件写入任何账号、令牌或隐私资料。请定期下载备份数据库。


## 独立推荐池（V2）

每天分别挑选**最多30款老游戏折扣**与**最多30款最近120天内发售的新游戏**，互不占用名额。Steam 商店搜索候选不足、网络请求失败或未达到筛选要求时，各栏展示真实数量，不为了凑满30款而收录不合格游戏。同一 AppID 不重复展示。每款卡片显示 Steam 官方游戏类型和发行日期，无法获取时标明未知。网页仍通过 `data/games.json` 展示，SQLite 数据库继续持久化采集数据。

## 尝鲜发现（V3）

新增独立 Tab **尝鲜发现**（最多20款），不按个人口味筛选或排序。简中好评率至少85%、简中评论至少100条、Steam国区价格不高于¥40；按口碑、评论数量与低价评分。独立于老游戏和新游名额，且仍排除已拥有和已确认 Epic 赠送的游戏。候选范围新增模拟、竞速、恐怖、视觉小说、平台跳跃、城市建造等分类。候选不足时显示实际数量。

## 尝鲜发现差评原因分析（V4）

尝鲜榜现在不设价格上限或好评率最低门槛。使用评论数量、Steam 国区价格和评论好评程度进行初排，再从 Steam 简中近期差评中最多抽取 30 条/游戏，以关键词归纳运营/商业争议、性能/技术、玩法、内容完成度和本地化。关键词是话题提及而非确定原因；样本不足时明确标示。运营类争议不能直接当成无效差评，严重性能/玩法问题会降低排序。每天最多分析约 45 个尝鲜候选，避免过量接口请求。分析结果保存到 `games.json` 与 SQLite `game_info.review_analysis_json`。关注名单 `config.json.explore_watchlist` 目前有《恶意不息》AppID 1371980。对已拥有或已确认 Epic 赠送的游戏仍按原规则排除。

## 发布、采集、自动补偿（V5）

GitHub Actions 分离为两个工作流，均以北京时间计时：

- `Publish Game Radar`：每天 14:00（UTC 06:00），直接发布仓库现有 `data/games.json`，不会联网抓游戏数据，因此不会被 Steam 429 阻塞。
- `Collect and Repair Game Radar Data`：每天 14:20 执行新数据发现与增量采集；17:15、21:15 自动运行补偿。每次生成更新后的 JSON 和 SQLite、提交到 GitHub 并重新部署 Pages。

`data/pending.json` 保存尚未处理的游戏候选（按类型 + AppID 去重）。采集到达时间预算时，尚未处理的游戏仍留在队列；下次补偿优先继续处理。补偿也会重查网站上缺少评价或差评分析的游戏。Steam 评论请求出现 HTTP 429 时停用当轮评论请求，优先使用已有缓存，并在后续执行时再试。抓取失败不能用伪造价格、好评率或差评结论填充。

手动执行时：`Publish Game Radar` 立即发布现有数据；`Collect and Repair Game Radar Data` 的 `mode=daily` 重新发现候选，`mode=compensate` 只处理待补偿队列和已有卡片缺失数据。GitHub cron 是尽力调度，可能延迟，并不保证整点执行。

## 每小时按分类补偿（V6）

`Collect and Repair Game Radar Data` 在 UTC 每小时 **35 分**检查一次仓库已发布的 `data/games.json`（北京时间每小时 :35）。先检查 `deal`、`new`、`explore` 各分类是否已经至少有一款推荐：

- 三类均有推荐：跳过采集、数据库写入及 Pages 重新部署。
- 仅部分分类为空：只处理该分类在 `data/pending.json` 中尚未完成的候选；没有待办则为这个分类发现候选；保留另外两个分类的现有推荐。
- 另保留每天北京时间 14:20 的新一轮完整采集，用于更新价格、发现新游戏；每日 14:00 的独立发布不抓取。

此处的“已存在”是**该分类至少一条游戏推荐**，不是数量达到 20/30，也不代表所有价格或评论均已补全。如需自动补齐缺少评价/散 Key 的卡片，可进一步使用字段级补偿规则。GitHub Actions 的 cron 可能延迟。

## 分字段的小批量补全（V7）

新增第三条 GitHub Actions 工作流 `Enrich Missing Game Fields`，**只检查已推荐的游戏**，不再为缺少散 Key、评论等字段重新跑完整游戏发现。各任务定时错峰，每轮最多处理 5 款（避免 Steam 429）。UTC 时区定时：

| 字段 | 频率 | 可补充内容 |
|---|---|---|
| 散 Key | 每小时 :12 | SteamPY 接口参考价、SteamCiCi 历史挂售参考价；不冒充现货 |
| 差评 | 每 3 小时 :22 | Steam 近期简中差评的关键词主题及样本量 |
| Steam Deck | 每 6 小时 :28 | Steam 兼容等级（仅当接口明确返回可识别值） |
| 地区历史低价 | 每 8 小时 :34 | SteamRaw 覆盖期内最低，不冒充完整 SteamDB 史低 |
| Epic 赠送记录 | 每天 00:40 UTC | 从不完整的第三方赠送档案匹配已赠送游戏，确认后从购买推荐移出 |
| 手机版 | 每天 01:46 UTC | 按已核实 AppID 清单补充 Android / iOS 状态，未收录不推断没有手机版 |
| DLC | 每天 02:52 UTC | Steam 商店的关联 DLC 数量及部分 AppID，不代表已评价 DLC 价值 |

每个字段按 `appid + task` 在 SQLite 的 `enrichment_state` 表中记录上次检查、结果状态、下次重试时间。同一字段成功后进入较长冷却期；查询失败通常 6 小时重试，无可靠报价通常 24 小时重试。无有效数据时写入“待核实/暂无可靠报价”状态，不编造价格、库存、史低或差评原因。结果增量合并到 `games.json`，并写入 SQLite 的相关表；有数据更新才重新部署网站。历史数据更新仍由每日完整采集负责。

手动执行：Actions → **Enrich Missing Game Fields** → **Run workflow** → 选择 `keys` / `reviews` / `deck` / `history` / `epic` / `mobile` / `dlc`。

## 手动一次运行全部字段

`Enrich Missing Game Fields` → `Run workflow` → `task=all`（默认选项）将按 `keys → reviews → deck → history → epic → mobile → dlc` 顺序运行，每类最多检查 2 款，且尊重 SQLite `enrichment_state` 中的到期时间；不是一次把全站所有游戏的数据全部补齐。单独选择字段时仍是每类最多 5 款。完成后如有数据变化自动提交并重新部署。

`all` 仅控制**此次手动运行**；每天及每小时自动执行由工作流既有的 `schedule` 单独驱动，无需先执行一次 `all` 才会启动。以后新增多个互不依赖的补全类型时，应同步更新这个 `all` 顺序执行列表和选项。

## 当前热门 · 特惠（独立 Tab）

- **完全不读取个人偏好评分、用户兴趣标签、口味权重**，候选从 Steam 国区「热销 + 特惠」搜索发现，按来源顺序排列（是热度代理，并非实时销量或在线玩家排名）。
- 优先展示 Steam 国区热门折扣游戏，最多 30 款；如果 SteamRaw 有明确的 CNY 覆盖期低价、且现价达到该低点，额外标记“已核实覆盖期低价”。否则明确显示“史低待核实”，绝不冒充 Steam 全历史史低。
- 单独运行 `Refresh Popular Low-Price Games`，每天北京时间 15:05 更新，也支持手动 `Run workflow → all`。它不拖慢老游戏、新游、尝鲜三类个性化发现。
- 数据独立保存在 `data/hot_low.json`，页面仅从中读取热门榜，不会影响前三个 Tab 的推荐排名。
