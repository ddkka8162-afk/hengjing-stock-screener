# 衡镜：A股量化筛选器 MVP

一个不依赖第三方 Python 包即可运行的首版网站，包含：

- 多条件组合筛选、排序与分页
- 上证、深证、创业板指数点数与分时走势（每 5 秒刷新）
- 按20日、120日动量及当日表现动态排序的热门板块
- 结合换手率、量比、20日动量与当日涨跌的股票热度排行
- 左侧条件即时自动筛选（文本输入采用防抖请求）
- 行情终端式三栏布局：左侧策略筛选、中间行情列表、右侧指数走势
- 概念板块与行业板块双榜单，按板块平均涨跌幅降序展示
- 深色行情终端主题，统一面板、表格、表单和涨跌色彩
- 股票星标收藏与本地持久化，自选榜单按涨跌幅降序排列
- 独立虚拟币行情页面，展示12种主流币价格、涨跌、市值、成交额和7日走势
- 虚拟币三栏市场终端、分类/涨跌榜/收藏操作及可点击的单币详情页
- 单币详情支持24H/7D走势切换、价格区间、收藏、价格提醒和复制链接
- 单币详情支持5分钟、15分钟、1小时、4小时、日线和周线实时K线
- 质量价值、质量成长、趋势动量和多因子模板
- 浏览器本地保存策略
- CSV 导出
- SQLite 数据快照
- 数据源适配器与 SQL 字段白名单
- 响应式中文界面

> 当前内置的是 40 只股票的确定性演示快照，并非真实行情，不得用于投资决策。

## 本地启动

需要 Python 3.10 或更高版本：

```powershell
python app.py
```

浏览器访问 <http://127.0.0.1:8000>。

运行测试：

```powershell
python -m unittest discover -s tests -v
```

## API

- `GET /api/health`：健康检查
- `GET /api/meta`：行业、股票池和更新时间
- `GET /api/market-overview`：主要指数点数及最近 60 分钟序列
- `GET /api/sector-rankings`：概念与行业板块涨跌幅排行
- `GET /api/watchlist?codes=600519,000858`：获取自选股票最新快照
- `GET /api/crypto-markets`：虚拟币实时行情；上游不可用时明确返回演示模式
- `GET /api/crypto-history?id=bitcoin&interval=5m`：单币分钟/小时/日/周历史行情
- `GET /api/screen`：筛选、排序和分页
- `GET /api/export.csv`：导出当前结果
- `POST /api/admin/refresh-demo`：重建演示快照

示例：

```text
/api/screen?min_roe=15&max_pe=30&sort=score&order=desc&page=1&page_size=20
```

## 接入真实数据

在 `stock_screener/providers.py` 中实现 `MarketDataProvider`：

1. 将供应商字段转换为 `Stock` 模型；
2. 保留原始数据时间与供应商状态；
3. 定时调用 `repository.replace_all()` 生成一致性快照；
4. 经数据源书面许可后，才在公开网站展示或再分发行情。

建议上线顺序：

1. 首先接入授权的每日行情和财务快照；
2. 增加披露日期、复权因子及历史日线表；
3. 盘中行情进入 Redis，页面通过 WebSocket 接收增量；
4. SQLite 换为 PostgreSQL，后台任务换为 Celery；
5. 管理接口增加鉴权、限流、审计和监控。

## 生产部署底线

- 不要直接公开 `POST /api/admin/*`；
- HTTPS、反向代理、请求限流和数据库备份必须启用；
- 页面展示数据源、延迟时间、复权方法和免责声明；
- 严格核对数据供应商关于缓存、公开展示及再分发的授权条款。

