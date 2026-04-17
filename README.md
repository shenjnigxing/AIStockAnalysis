# A 股数据系统

基于 FastAPI + SQLite 的 A 股数据存储和分析系统，支持历史 K 线、基本面数据、K 线图表、选股器等功能。

## 功能特性

### 📊 数据中心
- **实时行情**: 从腾讯财经获取实时股票行情
- **历史 K 线**: 支持 5 年历史 K 线数据存储（不复权/前复权/后复权）
- **基本面数据**: 股票基本信息、财务指标、股东数据
- **数据导出**: 支持 CSV/Excel 格式导出

### 📈 前端功能
- **首页**: 市场概览、实时行情、快速选股
- **K 线图**: 交互式 K 线图表（基于 Lightweight Charts）
- **选股器**: 多条件组合选股、预设策略、自定义策略保存
- **数据中心**: 基本面数据查询、财务指标查询

### 🔌 API 接口
- `GET /api/market/stats` - 市场统计信息
- `GET /api/market/stocks` - 股票列表（支持筛选分页）
- `GET /api/market/kline/{code}` - K 线历史数据
- `GET /api/market/kline/{code}/chart` - K 线图表数据
- `GET /api/market/basic/{code}` - 股票基本信息
- `GET /api/market/financial/{code}` - 财务指标数据
- `GET /api/market/screen` - 选股器接口
- `GET /api/market/export/{code}` - 导出股票数据
- `POST /api/market/history/init` - 初始化历史数据

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python run_api.py
```

服务启动后访问：
- **管理页面**: http://localhost:8080/
- **K 线图**: http://localhost:8080/chart
- **选股器**: http://localhost:8080/screener
- **API 文档**: http://localhost:8080/docs

### 3. 初始化数据

#### 获取实时行情
在首页点击"🔄 刷新行情"按钮，或访问：
```bash
curl -X POST http://localhost:8080/api/market/refresh
```

#### 获取历史 K 线（可选）
在首页点击"📚 初始化历史数据"按钮，或访问：
```bash
curl -X POST "http://localhost:8080/api/market/history/init?years=5"
```

⚠️ 注意：初始化 5 年历史数据可能需要 10-30 分钟

## 数据说明

### 数据来源
- **实时行情**: 腾讯财经 (`qt.gtimg.cn`)
- **历史 K 线**: Baostock (需要联网)
- **基本面数据**: Baostock

### 数据库结构
系统使用 SQLite 数据库 (`stock_data.db`)，包含以下表：

| 表名 | 说明 |
|------|------|
| `daily_market` | 每日市场快照（实时行情） |
| `kline_data` | K 线历史数据（支持复权） |
| `stock_basic` | 股票基本信息 |
| `financial_data` | 财务指标（季度） |
| `stock_holder` | 股东数据 |

### 数据字段
#### K 线数据
- 日期、开盘价、最高价、最低价、收盘价
- 成交量、成交额
- 涨跌幅、振幅、换手率
- 市盈率 (PE TTM)、市净率 (PB MRQ)
- 复权类型标记

#### 基本面数据
- 股票名称、上市日期
- 总股本、流通股本
- 所属行业、地区、板块

#### 财务指标
- ROE、净利率、毛利率
- 净利润、每股收益
- 资产负债率、流动比率、速动比率

## 选股器使用

### 预设策略
1. **低估值策略**: PE 0-20, PB 0-5, 换手率 1%-10%
2. **高换手策略**: 换手率>10%, 涨跌幅>-3%
3. **突破策略**: 涨跌幅>5%, 换手率>5%
4. **小盘成长**: 股价<20 元，PE 10-50

### 自定义条件
- 估值条件：PE、PB 范围
- 换手率范围
- 涨跌幅范围
- 价格范围
- 排除 ST 股

## 项目结构

```
AIStockAnalysis/
├── core/
│   ├── main.py           # FastAPI 应用入口
│   ├── api_routes.py     # API 路由定义
│   └── data_manager.py   # 数据管理模块
├── static/
│   ├── index.html        # 首页
│   ├── chart.html        # K 线图页面
│   └── screener.html     # 选股器页面
├── run_api.py            # 启动脚本
├── requirements.txt      # 依赖包列表
└── stock_data.db         # SQLite 数据库
```

## 常见问题

### Q: 如何获取历史 K 线数据？
A: 在首页点击"初始化历史数据"按钮，系统会使用 Baostock 获取 5 年历史数据。

### Q: 数据多久更新一次？
A: 实时行情需要手动刷新（点击"刷新行情"按钮），建议每个交易日收盘后刷新。

### Q: 导出的数据保存在哪里？
A: 浏览器会自动下载到下载文件夹。

### Q: 支持科创板/创业板吗？
A: 支持，选股器可以设置是否排除科创板。

## 技术栈

- **后端**: FastAPI, SQLite, Pandas, Baostock
- **前端**: HTML5, CSS3, JavaScript (原生)
- **图表**: Lightweight Charts (TradingView)

## License

MIT
