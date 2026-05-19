# 豆瓣 Top250 电影评分分析项目

这是一个基于 Python 的数据采集与分析练习项目，当前聚焦于豆瓣电影 Top250 榜单数据。

项目第一阶段的目标是：

- 抓取豆瓣 Top250 列表页电影信息
- 清洗并保存为结构化表格数据
- 为后续写入 MySQL 和数据分析做准备

当前已经提供一个可运行的 Jupyter Notebook：

- [douban_top250_scraper.ipynb](/D:/AI/App01/notebooks/douban_top250_scraper.ipynb)
- [douban_top250_analysis.ipynb](/D:/AI/App01/notebooks/douban_top250_analysis.ipynb)

## 项目状态

当前版本优先保证采集流程稳定，采用“两阶段采集”思路：

1. 先抓取 Top250 列表页数据
2. 详情页字段作为可选增强，少量分批补抓

这样设计的原因是：

- 列表页字段已经足够支撑第一版分析
- 详情页更容易触发站点限流与风控
- 先跑通采集、存储、分析闭环更重要

## 当前可采集字段

第一版默认抓取列表页字段：

- `rank`：榜单排名
- `title_cn`：中文标题
- `title_other`：外文标题或别名
- `rating`：豆瓣评分
- `rating_count`：评价人数
- `quote`：短评摘录
- `detail_url`：详情页链接
- `poster_url`：海报链接
- `crawl_time`：采集时间

这些字段已经足够支持以下分析：

- 评分分布分析
- 评分人数分布分析
- 排名与评分关系分析
- 排名与热度关系分析
- 高分高热度电影识别
- 经典短评文本展示

## 项目结构

当前目录结构如下：

```text
App01/
├─ .env.example
├─ .gitignore
├─ flask_app.py
├─ notebooks/
│  ├─ douban_top250_analysis.ipynb
│  ├─ douban_top250_scraper.ipynb
│  └─ douban_top250_to_mysql.ipynb
├─ output/
├─ requirements.txt
├─ sql/
│  └─ create_douban_top250_movies.sql
├─ static/
│  └─ dashboard.css
├─ src/
│  ├─ load_douban_top250_to_mysql.py
│  ├─ run_dashboard.ps1
│  └─ run_flask_dashboard.ps1
├─ templates/
│  └─ dashboard.html
├─ streamlit_app.py
└─ README.md
```

当前结构已经按职责拆分为：

```text
App01/
├─ flask_app.py
├─ notebooks/
│  ├─ douban_top250_analysis.ipynb
│  ├─ douban_top250_scraper.ipynb
│  └─ douban_top250_to_mysql.ipynb
├─ output/
├─ sql/
│  └─ create_douban_top250_movies.sql
├─ static/
│  └─ dashboard.css
├─ src/
│  ├─ load_douban_top250_to_mysql.py
│  ├─ run_dashboard.ps1
│  └─ run_flask_dashboard.ps1
├─ templates/
│  └─ dashboard.html
├─ streamlit_app.py
├─ requirements.txt
├─ README.md
└─ .gitignore
```

推荐的职责划分：

- `notebooks/`：采集、清洗、分析实验
- `data/`：原始数据或中间数据
- `output/`：导出结果、图表、报表
- `sql/`：建表脚本
- `src/`：后续可复用的 Python 模块

## 环境要求

建议环境：

- Python 3.10 及以上
- Jupyter Notebook 或 JupyterLab

Notebook 中当前使用到的主要依赖：

- `requests`
- `beautifulsoup4`
- `pandas`
- `openpyxl`
- `lxml`
- `pymysql`
- `plotly`
- `streamlit`
- `flask`

如果本地没有安装依赖，可以先安装：

```bash
pip install -r requirements.txt
```

## 快速开始

### 1. 打开 Notebook

打开：

- [douban_top250_scraper.ipynb](/D:/AI/App01/notebooks/douban_top250_scraper.ipynb)

按顺序运行各个单元。

### 2. 默认采集方式

当前推荐先运行列表页采集函数：

```python
df_movies = crawl_douban_top250_list_only()
```

这会抓取 Top250 列表页中的全部 250 条记录。

### 3. 导出结果

采集完成后，结果会保存到 `output/` 目录：

- `douban_top250_movies_list.csv`
- `douban_top250_movies_list.xlsx`

## MySQL 入库

项目已经提供 MySQL 建表脚本和 Python 入库脚本：

- [create_douban_top250_movies.sql](/D:/AI/App01/sql/create_douban_top250_movies.sql)
- [load_douban_top250_to_mysql.py](/D:/AI/App01/src/load_douban_top250_to_mysql.py)
- [douban_top250_to_mysql.ipynb](/D:/AI/App01/notebooks/douban_top250_to_mysql.ipynb)

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置数据库连接

可以直接传命令行参数，也可以先参考 [.env.example](/D:/AI/App01/.env.example) 设置这些环境变量：

- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`
- `MYSQL_TABLE`

### 3. 建表并导入 CSV

默认导入文件是：

- `output/douban_top250_movies_list.csv`

运行方式：

```bash
python src/load_douban_top250_to_mysql.py --password 你的MySQL密码
```

如果希望导入前清空表：

```bash
python src/load_douban_top250_to_mysql.py --password 你的MySQL密码 --truncate
```

如果表已经建好，不想重复执行建表 SQL：

```bash
python src/load_douban_top250_to_mysql.py --password 你的MySQL密码 --skip-init-schema
```

这个脚本会自动完成：

- 读取列表页 CSV
- 校验字段是否齐全
- 清洗字段类型
- 自动创建数据库
- 执行建表 SQL
- 将数据 upsert 到 MySQL

### 4. 当前表结构说明

当前表 `douban_top250_movies` 包含这些核心列：

- `movie_rank`
- `title_cn`
- `title_other`
- `rating`
- `rating_count`
- `quote_text`
- `detail_url`
- `poster_url`
- `crawl_time`

并设置了：

- `detail_url` 唯一键
- `movie_rank` 唯一键
- `rating`、`rating_count`、`crawl_time` 索引

## 关于详情页抓取

Notebook 中保留了详情页增强函数：

```python
df_movie_details = enrich_movie_details(df_movies, max_movies=5, detail_delay_range=(10, 18))
```

但需要注意：

- 豆瓣详情页更容易触发限流
- 可能出现 `429 Too Many Requests`
- 可能被跳转到 `sec.douban.com` 风控页

因此当前建议：

- 详情页只做少量测试
- 不把详情页抓取作为第一阶段主流程

## 数据输出说明

当前 Notebook 会导出结构化表格数据，便于后续：

- 导入 MySQL
- 使用 pandas 做统计分析
- 使用 matplotlib / seaborn 做可视化

后续计划中的输出包括：

- 清洗后的分析数据表
- 评分分析图表
- 热门电影排行图
- 简单数据分析报告

## Web 可视化看板

项目已经提供一个可交互的 Web 看板：

- [streamlit_app.py](/D:/AI/App01/streamlit_app.py)
- [run_dashboard.ps1](/D:/AI/App01/src/run_dashboard.ps1)

### 启动方式速查

#### Streamlit 版本

直接命令：

```bash
streamlit run streamlit_app.py
```

如果你使用 Anaconda，也可以这样启动：

```powershell
D:/Anaconda/python.exe -m streamlit run D:/AI/App01/streamlit_app.py
```

项目脚本：

```powershell
.\src\run_dashboard.ps1
```

默认地址：

- [http://localhost:8501](http://localhost:8501)

这套看板优先从 MySQL 读取数据，如果数据库连接失败，会自动回退到本地 CSV 文件：

- `output/analysis/douban_top250_analysis.csv`
- `output/douban_top250_movies_list.csv`

### Flask + ECharts 版本

除了 Streamlit 版，这个项目现在还额外提供了一个 `Flask + ECharts` 网页版本：

- [flask_app.py](/D:/AI/App01/flask_app.py)
- [dashboard.html](/D:/AI/App01/templates/dashboard.html)
- [dashboard.css](/D:/AI/App01/static/dashboard.css)
- [run_flask_dashboard.ps1](/D:/AI/App01/src/run_flask_dashboard.ps1)

这套版本更接近传统 Web 项目，特点是：

- Flask 提供页面和数据接口
- ECharts 负责图表渲染
- 前端通过接口实时筛选与刷新
- 保留榜单、明细表、评分分布、热度关系等交互能力

主要交互包括：

- 排名范围筛选
- 评分范围筛选
- 最低评价人数筛选
- 标题关键词搜索
- 排序字段和排序方向切换
- 评分 Top10 / 热度 Top10 / 综合指数 Top10 标签页切换

启动方式：

```bash
python flask_app.py
```

如果你使用 Anaconda，也可以这样启动：

```powershell
D:/Anaconda/python.exe D:/AI/App01/flask_app.py
```

或者使用 PowerShell 启动脚本：

```powershell
.\src\run_flask_dashboard.ps1
```

启动后默认访问：

- [http://localhost:5000](http://localhost:5000)

### 功能特性

- 侧边栏交互筛选
- 排名范围筛选
- 评分范围筛选
- 最低评价人数筛选
- 标题关键词搜索
- 评分、热度、综合指数排序
- Plotly 交互图表展示
- 评分 Top10、热度 Top10、综合指数 Top10
- 电影明细表格展示

### 启动方式

安装依赖：

```bash
pip install -r requirements.txt
```

直接运行：

```bash
streamlit run streamlit_app.py
```

或者使用项目自带 PowerShell 启动脚本：

```powershell
.\src\run_dashboard.ps1
```

这个脚本会自动选择可用的 Python 解释器，并使用 `python -m streamlit run` 的正确方式启动看板。

启动后默认访问：

- [http://localhost:8501](http://localhost:8501)

## 后续开发路线

这个项目可以按下面顺序继续推进：

1. 完成列表页数据稳定采集
2. 将采集结果写入 MySQL
3. 视需要补充详情页字段
4. 使用 pandas 做数据清洗
5. 输出评分分析与可视化图表
6. 将 Notebook 逻辑模块化为脚本或包

## 推荐的 MySQL 表设计方向

第一版已经落地一个简单表：

表名建议：`douban_top250_movies`

核心字段建议：

- `id`
- `rank`
- `title_cn`
- `title_other`
- `rating`
- `rating_count`
- `quote`
- `detail_url`
- `poster_url`
- `crawl_time`

如果后续需要补详情页信息，再扩展：

- `director`
- `screenwriter`
- `actors`
- `genres`
- `country_region`
- `language`
- `release_dates`
- `runtime_minutes`
- `imdb`

## 合规与说明

本项目仅作为学习与练习用途。

使用采集脚本时应注意：

- 遵守目标网站的服务条款与 robots 约束
- 控制请求频率，避免对目标站点造成不必要压力
- 不将抓取数据用于违规或未授权用途

## 当前已完成内容

- 完成 Top250 列表页采集 Notebook
- 将采集与入库 Notebook 统一整理到 `notebooks/` 目录
- 支持导出 CSV / Excel
- 支持详情页字段增强函数
- 增加了限流场景下的等待与重试逻辑
- 调整为更稳妥的“两阶段采集”策略
