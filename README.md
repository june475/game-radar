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
