import fastf1
import pandas as pd
from datetime import timedelta

# 启用缓存
fastf1.Cache.enable_cache('f1_cache')

# 加载2025年日本大奖赛正赛
print("正在加载2025年日本大奖赛数据...")
session = fastf1.get_session(2025, 'Japan', 'R')
session.load()

print("\n" + "=" * 80)
print(f"赛事: {session.event['EventName']}")
print(f"赛道: {session.event['Location']}")
print(f"日期: {session.event['EventDate']}")
print("=" * 80)

# 获取所有圈速数据
laps = session.laps

# 获取所有车手列表
drivers = session.drivers
driver_info = [session.get_driver(d) for d in drivers]

print(f"\n参赛车手数量: {len(drivers)}")

# 分析每位车手的轮胎策略和每圈数据
print("\n" + "=" * 80)
print("所有车手详细圈速和轮胎策略")
print("=" * 80)

for driver_number in sorted(drivers):
    driver = session.get_driver(driver_number)
    driver_name = driver['BroadcastName']
    team_name = driver['TeamName']

    # 获取该车手的所有圈速
    driver_laps = laps[laps['Driver'] == driver['Abbreviation']].copy()

    if len(driver_laps) == 0:
        continue

    print(f"\n{'═' * 80}")
    print(f"车手: {driver_name} ({driver['Abbreviation']}) | 车队: {team_name}")
    print(f"{'═' * 80}")

    # 打印每圈详细数据
    print(f"\n{'圈数':>4} | {'轮胎类型':^8} | {'圈速时间':>12} | {'胎龄':>4} | {'进站':^4}")
    print("─" * 80)

    previous_compound = None
    stint_number = 0

    for idx, lap in driver_laps.iterrows():
        lap_number = int(lap['LapNumber']) if pd.notna(lap['LapNumber']) else 0
        compound = lap['Compound'] if pd.notna(lap['Compound']) else 'N/A'
        lap_time = lap['LapTime']
        tire_life = int(lap['TyreLife']) if pd.notna(lap['TyreLife']) else 0
        pit_out = '是' if lap['PitOutTime'] is not pd.NaT else ''
        pit_in = '是' if lap['PitInTime'] is not pd.NaT else ''

        # 检测轮胎更换
        tire_change = ''
        if previous_compound is not None and compound != previous_compound:
            tire_change = f' ← 换胎: {previous_compound}→{compound}'
        elif tire_life == 1 and previous_compound == compound and lap_number > 1:
            tire_change = f' ← 换胎: {compound}(新)'

        previous_compound = compound

        # 格式化圈速时间
        if pd.notna(lap_time):
            total_seconds = lap_time.total_seconds()
            minutes = int(total_seconds // 60)
            seconds = total_seconds % 60
            time_str = f"{minutes}:{seconds:06.3f}"
        else:
            time_str = "N/A"

        # 进站标记
        pit_marker = ''
        if pit_out:
            pit_marker = '出站'
        elif pit_in:
            pit_marker = '进站'

        print(f"{lap_number:4d} | {compound:^8s} | {time_str:>12s} | {tire_life:4d} | {pit_marker:^4s}{tire_change}")

    # 统计轮胎策略
    print("\n" + "─" * 80)
    print("轮胎策略总结:")
    print("─" * 80)

    tire_stints = []
    current_compound = None
    current_tire_life = None
    stint_start = None
    stint_number = 0

    for idx, lap in driver_laps.iterrows():
        lap_compound = lap['Compound']
        lap_number = lap['LapNumber']
        tire_life = lap['TyreLife']

        is_new_stint = False

        if current_compound is None:
            is_new_stint = True
        elif lap_compound != current_compound:
            is_new_stint = True
        elif pd.notna(tire_life) and pd.notna(current_tire_life):
            if tire_life <= current_tire_life and tire_life <= 2:
                is_new_stint = True

        if is_new_stint:
            if current_compound is not None:
                stint_number += 1
                tire_stints.append({
                    'stint': stint_number,
                    'compound': current_compound,
                    'start_lap': stint_start,
                    'end_lap': lap_number - 1,
                    'laps': lap_number - stint_start
                })

            current_compound = lap_compound
            stint_start = lap_number

        current_tire_life = tire_life

    if current_compound is not None:
        stint_number += 1
        last_lap = driver_laps['LapNumber'].max()
        tire_stints.append({
            'stint': stint_number,
            'compound': current_compound,
            'start_lap': stint_start,
            'end_lap': last_lap,
            'laps': last_lap - stint_start + 1
        })

    if tire_stints:
        print(f"进站次数: {len(tire_stints) - 1}")
        print(f"Stint总数: {len(tire_stints)}\n")

        for stint in tire_stints:
            compound_name = stint['compound'] if pd.notna(stint['compound']) else 'UNKNOWN'
            print(f"  Stint {stint['stint']}: "
                  f"{compound_name:8s} | "
                  f"第 {int(stint['start_lap']):2d}-{int(stint['end_lap']):2d} 圈 | "
                  f"使用 {int(stint['laps']):2d} 圈")

        print(f"\n轮胎使用统计:")
        compound_summary = {}
        for stint in tire_stints:
            compound = stint['compound'] if pd.notna(stint['compound']) else 'UNKNOWN'
            if compound not in compound_summary:
                compound_summary[compound] = {'count': 0, 'laps': 0}
            compound_summary[compound]['count'] += 1
            compound_summary[compound]['laps'] += int(stint['laps'])

        for compound, stats in compound_summary.items():
            print(f"  {compound:8s}: 使用 {stats['count']} 次, 共 {stats['laps']} 圈")

print("\n" + "=" * 80)
print("分析完成！")
print("=" * 80)