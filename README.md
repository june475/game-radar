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
