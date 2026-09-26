# 年代约束审计 API

供地质记录整理使用的审计服务：提交编号唯一的地层、各自允许的整数年代区间
（单位：百万年，**数值越大越古老**），以及“甲比乙古老”的观测关系；服务把每条
关系转为约束 `age(甲) >= age(乙) + 1`，检测关系环、沿关系图传播收紧各地层的
最早/最晚可行年代，并在可行时给出按古老到年轻、编号字典序最小的合法顺序。

## 运行

```bash
docker compose up --build
```

一条命令即可启动（镜像构建时安装依赖，无需任何外部服务）。

- API 地址：**http://localhost:8000**
- 交互式文档（Swagger UI）：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 配置项

均为环境变量，可在 `docker-compose.yml` 的 `environment` 中调整：

| 变量   | 默认值    | 说明                                   |
| ------ | --------- | -------------------------------------- |
| `HOST` | `0.0.0.0` | 服务监听地址                           |
| `PORT` | `8000`    | 服务监听端口（改后需同步调整 ports 映射） |

Compose 默认把宿主机 `8000` 映射到容器 `8000`。

## API

### `POST /audit`

请求体：

```json
{
  "strata": [
    {"id": "A", "min_age": 5,  "max_age": 25},
    {"id": "B", "min_age": 8,  "max_age": 20},
    {"id": "C", "min_age": 9,  "max_age": 15}
  ],
  "relations": [
    {"older": "B", "younger": "A"},
    {"older": "A", "younger": "C"}
  ]
}
```

字段说明：

- `strata[].id`：地层编号，必须唯一。
- `strata[].min_age` / `max_age`：允许的整数年代区间下界/上界（下界=最年轻，
  上界=最古老），要求 `0 <= min_age <= max_age`。
- `relations[].older` / `younger`：观测关系“older 比 younger 古老”，即
  `age(older) >= age(younger) + 1`；两端必须引用已登记的地层编号，且不允许
  同一地层比自身古老（`older == younger` 会被拒绝，HTTP 422）。

响应（`status` 三选一）：

1. `ok` —— 可行。`intervals` 为各地层收紧后的区间；`order` 为按古老到年轻
   排列、编号字典序最小的合法顺序（满足全部关系约束的拓扑序，按编号字符串
   比较字典序）。

   ```json
   {
     "status": "ok",
     "cycle": null,
     "conflicts": null,
     "intervals": {
       "A": {"min_age": 10, "max_age": 19},
       "B": {"min_age": 11, "max_age": 20},
       "C": {"min_age": 9,  "max_age": 15}
     },
     "order": ["B", "A", "C"]
   }
   ```

2. `cycle` —— 关系成环。`cycle` 给出一条成环的地层编号路径，首尾相同，
   例如 `["A", "B", "C", "A"]`。

3. `conflict` —— 无环但传播后某些地层区间被压空（下界 > 上界）。
   `conflicts` 列出每个冲突地层及其被压空后的区间，例如
   `[{"id": "B", "min_age": 10, "max_age": 7}]`。

输入不合法（编号重复、区间为空、关系引用未知地层、自反关系等）时返回
HTTP 422 及具体错误信息。

### `GET /health`

返回 `{"status": "ok"}`，用于存活检查。

## 本地开发与测试

不依赖 Docker 也可以运行：

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                 # 运行测试
python -m app.main     # 本机启动服务，默认 http://localhost:8000
```
