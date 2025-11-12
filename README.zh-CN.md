# FastF1 赛事实参流水线

> 🇬🇧 Prefer English? See [`README.md`](README.md).

## 项目简介

本仓库基于 [FastF1](https://theoehrly.github.io/Fast-F1/) 提供的实况遥测数据，自动化生成 F1 Manager 生态所需的 `pars` 参数文件。  
流水线从初始的 `race_pars_*.ini` 模板出发，依次刷新实战轮胎策略、拟合缺失的轮胎退化参数，并补全排位赛与轮胎信息，最终产出可直接用于模拟的 `pars_*.ini`。

```
FastF1 数据 ──▶ race_pars 模板 ──▶ 策略更新 ──▶ 轮胎拟合 ──▶ 最终 pars 文件
```

### 核心能力

- 从 FastF1 抓取比赛与排位数据，自动启用本地缓存。
- 重写车手 `strategy_info` / `real_strategy` 策略段，匹配真实的进站与轮胎使用。
- 通过 SciPy 对缺失的轮胎配方进行线性（默认）或二次退化拟合。
- 估算并回写赛道的进站时间损失以及排位赛基准圈速。
- 輸出合规的 `pars_*.ini` 文件，便于 Monte Carlo 或其他仿真工具继续使用。

## 仓库结构

- `f1_pipeline_main.py`：三阶段流水线调度脚本。
- `update_ini_strategy.py`：依据比赛实际数据更新车手轮胎策略。
- `fit_tire_degradation.py`：拟合轮胎退化系数并补全进站损失。
- `convert_pars.py`：规范化 INI 结构，补充排位/轮胎元数据。
- `data/`：示例 `race_pars` 模板与 Monte Carlo 参数文件。
- `f1_cache/`：FastF1 首次请求后产生的缓存目录。

## 环境要求

- Python 3.9 及以上版本（建议使用最新的 CPython）。
- 首次运行需联网以下载 FastF1 数据。
- Windows 环境若安装 SciPy 失败，可能需要额外的 Microsoft Visual C++ 运行库。

安装依赖：

```bash
python -m venv .venv
.venv\Scripts\activate          # 在 Windows PowerShell 中
pip install -r requirements.txt
```

> 建议整个开发周期内都激活虚拟环境，避免与系统包冲突。

## FastF1 缓存说明

首次请求某个赛季/分站时，FastF1 会把相关 JSON/Parquet 文件写入 `f1_cache/`。  
后续重复运行会直接复用缓存，只在缺失时重新下载。若磁盘空间吃紧，可按赛季清理，但请保留仍需处理的场次。

## 运行流水线

1. 准备好基础的 `race_pars_*.ini` 文件，可放在仓库根目录或自定义路径。
2. 打开 `f1_pipeline_main.py`，修改 `main()` 中的配置：

```python
YEAR = 2025
RACE_NAME = "Japan"
BASE_INI_FILE = "race_pars_Suzuka.ini"
```

3. 执行：

```bash
python f1_pipeline_main.py
```

4. 终端会展示每个阶段的详情，默认保留中间结果：
   - `<base>_updated.ini`：策略更新后的版本
   - `<base>_final.ini`：补全轮胎退化后的版本
   - `pars_<track>_<year>.ini`：最终产物

5. 程序结束后可按提示选择是否删除中间文件。

### 单独调用各环节

三个脚本都暴露了函数接口，便于在 Notebook 或定制流程中复用：

- `update_ini_strategy.update_ini_file(input_file, output_file, year, race_name)`
- `fit_tire_degradation.update_tire_parameters(input_file, output_file, year, race_name, model="lin")`
- `convert_pars.convert_race_pars_to_pars(input_file, output_file, year, race_name)`

## 配置与自定义

- **轮胎映射**：`update_ini_strategy.py` 与 `fit_tire_degradation.py` 中的映射表可根据赛事需求调整，例如特别比赛或冲刺赛的配方命名。
- **退化模型**：如需更精细的拟合，可在调用 `update_tire_parameters` 时指定 `model="quad"`，但要确保每个配方拥有更多有效圈数。
- **车手缩写**：程序对 Nico Hülkenberg (`HÜL`) 做了特殊处理，以满足 INI 文件的编码约定。
- **燃油补偿**：`fit_tire_degradation.py` 默认每圈减少 `0.063s`，可根据策略模型调整 `FUEL_EFFECT_PER_LAP`。

## 常见问题

- **会话名称不匹配**：`RACE_NAME` 需使用 FastF1 的英文赛站名称（如 `"Singapore"`），否则无法加载数据。
- **网络或证书错误**：请确认 FastF1 版本 ≥ 3.2，并确保系统证书链正常。
- **数据点不足**：若某位车手/配方的有效圈数不足 3 圈，曲线拟合会跳过并保留原参数。

## 贡献指南

欢迎提交 Pull Request。新增赛道或更改模型假设时，请同步更新中英文 README，确保流水线依旧可以从头到尾顺利运行。

## 许可说明

本项目仅供个人数据分析学习之用。请在使用时遵守 FastF1 与 F1 赛事计时数据相关的服务条款。


