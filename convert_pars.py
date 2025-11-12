import fastf1
import pandas as pd
import re

# 启用缓存
fastf1.Cache.enable_cache('f1_cache')

# 轮胎配方映射
TIRE_COMPOUND_MAPPING = {
    'C1': 'A2',
    'C2': 'A3',
    'C3': 'A4',
    'C4': 'A6',
    'C5': 'A7',
    'SOFT': 'A4',
    'MEDIUM': 'A3',
    'HARD': 'A2',
    'INTERMEDIATE': 'I',
    'WET': 'W'
}


def get_qualifying_results(year, race_name):
    """获取排位赛结果和最快圈速"""
    print(f"\n正在加载 {year} 年 {race_name} 排位赛数据...")

    try:
        session = fastf1.get_session(year, race_name, 'Q')
        session.load()

        results = session.results
        qualifying_positions = {}

        # 获取最快圈速
        fastest_lap_time = None
        laps = session.laps
        if len(laps) > 0:
            valid_laps = laps[laps['IsPersonalBest'] == True]
            if len(valid_laps) > 0:
                fastest_lap = valid_laps['LapTime'].min()
                if pd.notna(fastest_lap):
                    fastest_lap_time = fastest_lap.total_seconds()

        for idx, row in results.iterrows():
            driver_abbr = row['Abbreviation']
            if driver_abbr == 'HUL':
                driver_abbr = 'HÜL'

            if pd.notna(row['Position']):
                grid_pos = int(row['Position'])
            elif pd.notna(row['GridPosition']):
                grid_pos = int(row['GridPosition'])
            else:
                continue

            qualifying_positions[driver_abbr] = grid_pos

        print(f"✓ 成功获取 {len(qualifying_positions)} 位车手的排位赛结果")
        if fastest_lap_time:
            print(f"✓ 排位赛最快圈速: {fastest_lap_time:.3f}秒")
        for driver, pos in sorted(qualifying_positions.items(), key=lambda x: x[1])[:5]:
            print(f"  P{pos}: {driver}")

        return qualifying_positions, fastest_lap_time

    except Exception as e:
        print(f"✗ 获取排位赛数据失败: {e}")
        return {}, None


def get_tire_compounds_used(year, race_name):
    """获取比赛中使用的轮胎配方"""
    print(f"\n正在分析 {year} 年 {race_name} 轮胎使用情况...")

    try:
        session = fastf1.get_session(year, race_name, 'R')
        session.load()

        laps = session.laps
        compounds_used = set()

        for compound in laps['Compound'].unique():
            if pd.notna(compound) and compound in TIRE_COMPOUND_MAPPING:
                mapped = TIRE_COMPOUND_MAPPING[compound]
                compounds_used.add(mapped)

        dry_compounds = {c for c in compounds_used if c not in ['I', 'W']}

        print(f"✓ 检测到使用的轮胎配方: {sorted(list(compounds_used))}")
        print(f"  干胎配方: {sorted(list(dry_compounds))}")

        return compounds_used, dry_compounds

    except Exception as e:
        print(f"✗ 获取轮胎数据失败: {e}")
        return set(), set()


def convert_race_pars_to_pars(input_file, output_file, year, race_name):
    """转换race_pars文件为pars文件"""
    print("=" * 80)
    print(f"转换 {input_file} -> {output_file}")
    print(f"赛事: {year} {race_name}")
    print("=" * 80)

    # 读取原始文件
    print(f"\n正在读取 {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 获取排位赛数据
    qualifying_positions, fastest_lap_time = get_qualifying_results(year, race_name)

    # 获取轮胎配方数据
    compounds_used, dry_compounds = get_tire_compounds_used(year, race_name)

    print("\n" + "=" * 80)
    print("更新文件内容...")
    print("=" * 80)

    # 第一步：全局替换 supervised 为 realstrategy
    content = content.replace('"supervised"', '"realstrategy"')
    print("✓ 将vse_type全部替换为realstrategy")

    lines = content.split('\n')
    new_lines = []
    in_vse_pars = False
    in_track_pars = False
    updated_grid_count = 0
    updated_tq = False

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 检测TRACK_PARS section
        if '[TRACK_PARS]' in line:
            in_track_pars = True
            new_lines.append(line)
            i += 1
            continue

        # 检测VSE_PARS section
        if '[VSE_PARS]' in line:
            in_vse_pars = True
            in_track_pars = False
            new_lines.append(line)
            i += 1
            continue

        # 检测到新的section，退出当前section
        if stripped.startswith('[') and stripped.endswith(']'):
            in_vse_pars = False
            in_track_pars = False

        # 在TRACK_PARS中更新t_q
        if in_track_pars and '"t_q":' in line and fastest_lap_time:
            indent = ' ' * (len(line) - len(line.lstrip()))
            new_lines.append(f'{indent}"t_q": {fastest_lap_time:.3f},')
            updated_tq = True
            print(f"✓ 更新t_q: {fastest_lap_time:.3f}秒")
            i += 1
            continue

        # 在VSE_PARS中更新轮胎配方
        if in_vse_pars:
            # 更新available_compounds
            if '"available_compounds":' in line and compounds_used:
                indent = ' ' * (len(line) - len(line.lstrip()))
                compounds_list = sorted(list(compounds_used))
                if "I" not in compounds_list:
                    compounds_list.append("I")
                if "W" not in compounds_list:
                    compounds_list.append("W")
                compounds_str = ', '.join([f'"{c}"' for c in compounds_list])
                new_lines.append(f'{indent}"available_compounds": [{compounds_str}],')
                print(f"✓ 更新available_compounds: {compounds_list}")
                # 跳过原有数组的所有行
                bracket_count = line.count('[') - line.count(']')
                i += 1
                while bracket_count > 0 and i < len(lines):
                    bracket_count += lines[i].count('[') - lines[i].count(']')
                    i += 1
                continue

            # 更新param_dry_compounds
            if '"param_dry_compounds":' in line and dry_compounds:
                indent = ' ' * (len(line) - len(line.lstrip()))
                dry_list = sorted(list(dry_compounds))
                dry_str = ', '.join([f'"{c}"' for c in dry_list])
                new_lines.append(f'{indent}"param_dry_compounds": [{dry_str}],')
                print(f"✓ 更新param_dry_compounds: {dry_list}")
                # 跳过原有数组的所有行
                bracket_count = line.count('[') - line.count(']')
                i += 1
                while bracket_count > 0 and i < len(lines):
                    bracket_count += lines[i].count('[') - lines[i].count(']')
                    i += 1
                continue

        # 更新p_grid（在DRIVER_PARS section中）
        if '"p_grid":' in line and qualifying_positions:
            # 向上查找所属车手
            for j in range(len(new_lines) - 1, -1, -1):
                prev_line = new_lines[j]
                match = re.match(r'^\s*"([A-Z]{3}|HÜL)":\s*\{', prev_line)
                if match:
                    driver_abbr = match.group(1)
                    if driver_abbr in qualifying_positions:
                        indent = ' ' * (len(line) - len(line.lstrip()))
                        new_grid_pos = qualifying_positions[driver_abbr]
                        new_lines.append(f'{indent}"p_grid": {new_grid_pos},')
                        updated_grid_count += 1
                        i += 1
                        break
            else:
                new_lines.append(line)
                i += 1
        else:
            new_lines.append(line)
            i += 1

    # 写入新文件
    print(f"\n正在写入 {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

    print("\n" + "=" * 80)
    print("转换完成！")
    print("=" * 80)

    # 显示总结
    print("\n更新摘要:")
    if updated_tq:
        print(f"  ✓ 更新t_q为最快圈速: {fastest_lap_time:.3f}秒")

    if updated_grid_count > 0:
        print(f"  ✓ 更新了 {updated_grid_count} 位车手的排位数据")
        if qualifying_positions:
            sorted_quali = sorted(qualifying_positions.items(), key=lambda x: x[1])
            print("  前5名排位:")
            for driver, pos in sorted_quali[:5]:
                print(f"    P{pos}: {driver}")

    if compounds_used:
        print(f"  ✓ 更新轮胎配方: {sorted(list(compounds_used))}")

    print(f"  ✓ vse_type已全部设置为realstrategy")
    print(f"\n新文件已保存: {output_file}")


if __name__ == "__main__":
    # 配置参数
    INPUT_FILE = "race_pars_Suzuka_final.ini"
    OUTPUT_FILE = "pars_Suzuka_2025.ini"
    YEAR = 2025
    RACE_NAME = "Japan"

    # 执行转换
    convert_race_pars_to_pars(INPUT_FILE, OUTPUT_FILE, YEAR, RACE_NAME)