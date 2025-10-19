import fastf1
import pandas as pd
import numpy as np
from scipy import stats
from collections import defaultdict
import configparser
import warnings
import os

warnings.filterwarnings('ignore')

# 创建并启用FastF1缓存以加快数据加载
cache_dir = 'f1_cache'
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)
    print(f"创建缓存目录: {cache_dir}")
fastf1.Cache.enable_cache(cache_dir)


class F1DataProcessor:
    def __init__(self, start_year, end_year):
        self.start_year = start_year
        self.end_year = end_year
        self.all_data = []

    def load_season_data(self):
        """加载指定年份范围的所有赛季数据"""
        print("开始加载数据...")
        for year in range(self.start_year, self.end_year + 1):
            print(f"\n处理 {year} 赛季...")
            try:
                # 尝试不同的方式获取赛程
                try:
                    schedule = fastf1.get_event_schedule(year)
                except Exception as e:
                    print(f"  无法加载{year}赛季赛程: {e}")
                    print(f"  跳过{year}赛季")
                    continue

                race_rounds = schedule[schedule['EventFormat'] != 'testing']

                for idx, event in race_rounds.iterrows():
                    try:
                        print(f"  加载: {event['EventName']}")
                        session = fastf1.get_session(year, event['RoundNumber'], 'R')
                        session.load()

                        # 验证数据是否成功加载
                        if not hasattr(session, '_laps') or session._laps is None:
                            print(f"    警告: {event['EventName']} 圈速数据未加载，跳过")
                            continue
                        if not hasattr(session, '_results') or session._results is None:
                            print(f"    警告: {event['EventName']} 结果数据未加载，跳过")
                            continue

                        race_data = {
                            'year': year,
                            'round': event['RoundNumber'],
                            'event': event['EventName'],
                            'session': session
                        }
                        self.all_data.append(race_data)
                    except Exception as e:
                        print(f"    跳过 {event['EventName']}: {e}")

            except Exception as e:
                print(f"  {year}赛季加载失败: {e}")

        print(f"\n总共加载了 {len(self.all_data)} 场比赛数据")

        if len(self.all_data) == 0:
            raise ValueError("未能加载任何比赛数据！请检查网络连接或年份范围。")

    def calculate_accident_probabilities(self):
        """计算车手事故概率"""
        print("\n计算事故概率...")
        driver_stats = defaultdict(lambda: {'races': 0, 'accidents': 0})

        for race_data in self.all_data:
            session = race_data['session']
            results = session.results

            for _, driver in results.iterrows():
                driver_name = driver['FullName']
                driver_stats[driver_name]['races'] += 1

                # 判断是否为事故退赛
                status = str(driver['Status']).lower()
                if any(keyword in status for keyword in ['collision', 'accident', 'damage', 'crash', 'spun']):
                    driver_stats[driver_name]['accidents'] += 1

        # 计算概率，最小值设为0.045
        accident_probs = {}
        for driver, stats in driver_stats.items():
            if stats['races'] > 0:
                prob = max(0.045, stats['accidents'] / stats['races'])
                accident_probs[driver] = round(prob, 3)

        return accident_probs

    def calculate_failure_probabilities(self):
        """计算车队故障概率"""
        print("计算故障概率...")
        team_stats = defaultdict(lambda: {'races': 0, 'failures': 0})

        for race_data in self.all_data:
            session = race_data['session']
            results = session.results

            for _, driver in results.iterrows():
                team_name = driver['TeamName']
                team_stats[team_name]['races'] += 1

                # 判断是否为技术故障
                status = str(driver['Status']).lower()
                if any(keyword in status for keyword in ['engine', 'gearbox', 'hydraulics',
                                                         'electrical', 'mechanical', 'power unit', 'transmission',
                                                         'suspension']):
                    team_stats[team_name]['failures'] += 1

        # 计算概率，最小值设为0.041
        failure_probs = {}
        for team, stats in team_stats.items():
            if stats['races'] > 0:
                prob = max(0.041, stats['failures'] / stats['races'])
                failure_probs[team] = round(prob, 3)

        return failure_probs

    def calculate_lap_time_variability(self):
        """计算车手圈速变化标准差"""
        print("计算圈速变化...")
        driver_laps = defaultdict(list)
        driver_mapping = {}  # 存储车手代号到全名的映射

        for race_data in self.all_data:
            session = race_data['session']

            try:
                results = session.results
                laps = session.laps
            except Exception as e:
                print(f"  跳过 {race_data['event']}: 无法访问数据 - {e}")
                continue

            # 创建车手代号到全名的映射
            try:
                for _, driver_result in results.iterrows():
                    driver_abbr = driver_result['Abbreviation']
                    driver_full = driver_result['FullName']
                    driver_mapping[driver_abbr] = driver_full
            except Exception as e:
                print(f"  警告: {race_data['event']} 无法创建车手映射")
                continue

            # 只考虑正常圈速（排除进站圈、安全车等）
            try:
                valid_laps = laps[
                    (laps['LapTime'].notna()) &
                    (laps['PitOutTime'].isna()) &
                    (laps['PitInTime'].isna())
                    ]
            except Exception as e:
                print(f"  警告: {race_data['event']} 无法过滤圈速数据")
                continue

            for driver in valid_laps['Driver'].unique():
                driver_name = driver_mapping.get(driver, driver)
                try:
                    lap_times = valid_laps[valid_laps['Driver'] == driver]['LapTime'].dt.total_seconds()

                    if len(lap_times) > 5:  # 至少5圈数据
                        # 计算相对于中位数的标准差
                        median_time = lap_times.median()
                        normalized_times = (lap_times - median_time).abs()
                        driver_laps[driver_name].extend(normalized_times.tolist())
                except Exception:
                    continue

        # 计算每个车手的标准差
        lap_var_sigma = {}
        for driver, times in driver_laps.items():
            if len(times) > 10:
                sigma = np.std(times)
                lap_var_sigma[driver] = round(sigma, 3)

        print(f"  成功计算 {len(lap_var_sigma)} 位车手的圈速变化")
        return lap_var_sigma

    def calculate_start_performance(self):
        """计算车手起步表现"""
        print("计算起步表现...")
        driver_starts = defaultdict(list)

        for race_data in self.all_data:
            session = race_data['session']
            results = session.results

            for _, driver in results.iterrows():
                driver_name = driver['FullName']
                grid_pos = driver['GridPosition']
                final_pos = driver['Position']

                if pd.notna(grid_pos) and pd.notna(final_pos):
                    # 简化的起步表现计算（位置变化）
                    # 正值表示失去位置，负值表示获得位置
                    position_change = float(final_pos - grid_pos)
                    driver_starts[driver_name].append(position_change)

        # 计算均值和标准差
        start_perf = {}
        for driver, changes in driver_starts.items():
            if len(changes) > 3:
                mean_change = np.mean(changes) * -0.05  # 转换为时间（估算）
                sigma_change = np.std(changes) * 0.05
                start_perf[driver] = {
                    'mean': round(mean_change, 3),
                    'sigma': round(sigma_change, 3)
                }

        return start_perf

    def estimate_pit_stop_parameters(self):
        """估算进站时间分布参数"""
        print("计算进站时间参数...")
        team_pit_times = defaultdict(list)

        for race_data in self.all_data:
            session = race_data['session']

            try:
                results = session.results
                laps = session.laps
            except Exception as e:
                print(f"  跳过 {race_data['event']}: 无法访问数据")
                continue

            # 创建车手代号到车队的映射
            driver_to_team = {}
            try:
                for _, driver_result in results.iterrows():
                    driver_abbr = driver_result['Abbreviation']
                    team_name = driver_result['TeamName']
                    driver_to_team[driver_abbr] = team_name
            except Exception:
                continue

            # 找到进站圈
            try:
                pit_laps = laps[laps['PitInTime'].notna()]

                for _, lap in pit_laps.iterrows():
                    if pd.notna(lap['PitOutTime']) and pd.notna(lap['PitInTime']):
                        pit_duration = (lap['PitOutTime'] - lap['PitInTime']).total_seconds()
                        if 15 < pit_duration < 60:  # 合理的进站时间范围
                            driver_abbr = lap['Driver']
                            team_name = driver_to_team.get(driver_abbr, 'Unknown')
                            if team_name != 'Unknown':
                                team_pit_times[team_name].append(pit_duration)
            except Exception:
                continue

        # 使用简化的参数估计（基于均值和标准差）
        pit_var_pars = {}
        for team, times in team_pit_times.items():
            if len(times) > 10:
                mean_time = np.mean(times)
                std_time = np.std(times)
                # 简化的Fisk参数估算
                alpha = max(1.5, mean_time / 10)
                beta = -std_time / mean_time
                gamma = std_time
                pit_var_pars[team] = [round(alpha, 3), round(beta, 3), round(gamma, 3)]

        print(f"  成功计算 {len(pit_var_pars)} 支车队的进站参数")
        return pit_var_pars

    def generate_ini_file(self, output_file='f1_2020_2025_pars_mcs.ini'):
        """生成INI配置文件"""
        print(f"\n生成INI文件: {output_file}")

        # 计算所有统计数据
        accident_probs = self.calculate_accident_probabilities()
        failure_probs = self.calculate_failure_probabilities()
        lap_var_sigma = self.calculate_lap_time_variability()
        start_perf = self.calculate_start_performance()
        pit_var_pars = self.estimate_pit_stop_parameters()

        # 创建INI文件
        config = configparser.ConfigParser()
        config.optionxform = str  # 保持键名大小写

        # 按年份分组数据
        years = range(self.start_year, self.end_year + 1)
        for year in years:
            section_name = f"SEASON_{year}"
            config[section_name] = {}

            # 过滤该年份的车手和车队
            year_drivers = set()
            year_teams = set()

            for race_data in self.all_data:
                if race_data['year'] == year:
                    results = race_data['session'].results
                    year_drivers.update(results['FullName'].tolist())
                    year_teams.update(results['TeamName'].tolist())

            # 添加事故概率
            year_accident_probs = {d: accident_probs.get(d, 0.058)
                                   for d in sorted(year_drivers) if d in accident_probs}
            config[section_name]['p_accident'] = str(year_accident_probs)

            # 添加故障概率
            year_failure_probs = {t: failure_probs.get(t, 0.071)
                                  for t in sorted(year_teams) if t in failure_probs}
            config[section_name]['p_failure'] = str(year_failure_probs)

        # 添加通用参数
        config['ALL_SEASONS'] = {}
        config['ALL_SEASONS']['p_fcy_phases'] = str({
            "p_sc_quant": [0.455, 0.413, 0.099, 0.033],
            "p_sc_start": [0.364, 0.136, 0.136, 0.08, 0.193, 0.091],
            "p_sc_duration": [0.0, 0.182, 0.25, 0.227, 0.193, 0.057, 0.068, 0.023, 0.0, 0.0],
            "p_vsc_aft_failure": 0.227,
            "p_vsc_duration": [0.479, 0.396, 0.021, 0.104]
        })

        config['ALL_SEASONS']['t_pit_var_fisk_pars'] = str(pit_var_pars)
        config['ALL_SEASONS']['t_lap_var_sigma'] = str(lap_var_sigma)

        # 添加未知车手的默认值
        if start_perf:
            avg_sigma = np.mean([v['sigma'] for v in start_perf.values()])
            start_perf['unknown'] = {'mean': 0.0, 'sigma': round(avg_sigma, 3)}
        config['ALL_SEASONS']['t_startperf'] = str(start_perf)

        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# F1 Monte Carlo Simulation Parameters (2020-2025)\n")
            f.write("# Generated from FastF1 data\n\n")
            config.write(f)

        print(f"✓ INI文件已生成: {output_file}")

        # 打印统计摘要
        print(f"\n统计摘要:")
        print(f"  车手数量: {len(accident_probs)}")
        print(f"  车队数量: {len(failure_probs)}")
        print(f"  圈速数据: {len(lap_var_sigma)} 位车手")
        print(f"  起步数据: {len(start_perf)} 位车手")
        print(f"  进站数据: {len(pit_var_pars)} 支车队")


# 使用示例
if __name__ == "__main__":
    # 创建处理器实例
    # 注意: FastF1 API对2022年及之后的数据可能不稳定
    # 程序会自动跳过无法加载的赛季和比赛
    processor = F1DataProcessor(start_year=2020, end_year=2025)

    # 加载数据
    processor.load_season_data()

    # 生成INI文件
    processor.generate_ini_file('f1_2020_2025_pars_mcs.ini')

    print("\n✓ 处理完成！")