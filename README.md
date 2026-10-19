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
