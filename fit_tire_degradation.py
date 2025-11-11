import fastf1
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
import configparser
import re

# 启用缓存
fastf1.Cache.enable_cache('f1_cache')

# 配置参数
FUEL_EFFECT_PER_LAP = 0.063  # 秒/圈，燃料消耗带来的时间减少

# 轮胎配方映射
# 根据比赛更改
COMPOUND_MAPPING = {
    'SOFT': 'A4',
    'MEDIUM': 'A3',
    'HARD': 'A2',
    'INTERMEDIATE': 'I',
    'WET': 'W'
}


def linear_tire_model(tire_age, k_0, k_1_lin):
    """线性轮胎退化模型"""
    return k_0 + k_1_lin * tire_age


def quadratic_tire_model(tire_age, k_0, k_1_quad, k_2_quad):
    """二次轮胎退化模型"""
    return k_0 + k_1_quad * tire_age + k_2_quad * tire_age ** 2


def fit_tire_degradation(driver_abbr, compound, laps_data, model='lin'):
    """
    拟合轮胎退化参数

    参数:
        driver_abbr: 车手缩写
        compound: 轮胎配方（已映射，如'A3'）
        laps_data: DataFrame，包含圈速数据
        model: 'lin' 或 'quad'

    返回:
        dict: 拟合参数 {k_0, k_1_lin/k_1_quad, k_2_quad}
    """
    if len(laps_data) < 3:
        print(f"  ⚠️  {driver_abbr} 的 {compound} 数据点不足（{len(laps_data)}圈），跳过")
        return None

    # 准备数据
    tire_ages = []
    corrected_lap_times = []

    for idx, lap in laps_data.iterrows():
        tire_age = lap['TyreLife']
        lap_time_seconds = lap['LapTime'].total_seconds()
        lap_number = lap['LapNumber']

        # 修正燃料效应（假设从第1圈开始计算）
        fuel_correction = (lap_number - 1) * FUEL_EFFECT_PER_LAP
        corrected_time = lap_time_seconds + fuel_correction

        tire_ages.append(tire_age)
        corrected_lap_times.append(corrected_time)

    tire_ages = np.array(tire_ages)
    corrected_lap_times = np.array(corrected_lap_times)

    # 归一化到最快圈速
    base_time = np.min(corrected_lap_times)
    delta_times = corrected_lap_times - base_time

    try:
        if model == 'lin':
            # 线性拟合
            popt, _ = curve_fit(linear_tire_model, tire_ages, delta_times,
                                p0=[0.0, 0.05], maxfev=10000)
            k_0, k_1_lin = popt

            # 计算R²
            predictions = linear_tire_model(tire_ages, k_0, k_1_lin)
            ss_res = np.sum((delta_times - predictions) ** 2)
            ss_tot = np.sum((delta_times - np.mean(delta_times)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            print(f"  ✓ {driver_abbr} - {compound}: k_0={k_0:.4f}, k_1_lin={k_1_lin:.4f}, R²={r_squared:.3f}")

            return {
                'k_0': round(k_0, 4),
                'k_1_lin': round(k_1_lin, 4),
                'k_1_quad': 0.0,
                'k_2_quad': 0.0
            }
        else:
            # 二次拟合
            popt, _ = curve_fit(quadratic_tire_model, tire_ages, delta_times,
                                p0=[0.0, 0.05, 0.001], maxfev=10000)
            k_0, k_1_quad, k_2_quad = popt

            # 计算R²
            predictions = quadratic_tire_model(tire_ages, k_0, k_1_quad, k_2_quad)
            ss_res = np.sum((delta_times - predictions) ** 2)
            ss_tot = np.sum((delta_times - np.mean(delta_times)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            print(
                f"  ✓ {driver_abbr} - {compound}: k_0={k_0:.4f}, k_1_quad={k_1_quad:.4f}, k_2_quad={k_2_quad:.6f}, R²={r_squared:.3f}")

            return {
                'k_0': round(k_0, 4),
                'k_1_lin': 0.0,
                'k_1_quad': round(k_1_quad, 4),
                'k_2_quad': round(k_2_quad, 6)
            }
    except Exception as e:
        print(f"  ✗ {driver_abbr} - {compound}: 拟合失败 - {e}")
        return None


def calculate_pit_times(session):
    """计算进站圈和出站圈的平均时间损失"""
    laps = session.laps

    inlap_deltas = []
    outlap_deltas = []

    for driver_abbr in session.drivers:
        driver_info = session.get_driver(driver_abbr)
        driver_laps = laps[laps['Driver'] == driver_info['Abbreviation']].copy()

        if len(driver_laps) == 0:
            continue

        # 找出进站圈和出站圈
        for idx, lap in driver_laps.iterrows():
            # 进站圈（PitInTime不为空）
            if pd.notna(lap['PitInTime']) and lap['PitInTime'] is not pd.NaT:
                if pd.notna(lap['LapTime']):
                    lap_time = lap['LapTime'].total_seconds()
                    # 找到该车手的有效圈速作为基准
                    valid_laps = driver_laps[
                        (driver_laps['IsAccurate'] == True) &
                        (pd.isna(driver_laps['PitInTime'])) &
                        (pd.isna(driver_laps['PitOutTime']))
                        ]
                    if len(valid_laps) > 0:
                        avg_time = valid_laps['LapTime'].apply(lambda x: x.total_seconds()).median()
                        delta = lap_time - avg_time
                        if 0 < delta < 20:  # 合理范围
                            inlap_deltas.append(delta)

            # 出站圈（PitOutTime不为空）
            if pd.notna(lap['PitOutTime']) and lap['PitOutTime'] is not pd.NaT:
                if pd.notna(lap['LapTime']):
                    lap_time = lap['LapTime'].total_seconds()
                    valid_laps = driver_laps[
                        (driver_laps['IsAccurate'] == True) &
                        (pd.isna(driver_laps['PitInTime'])) &
                        (pd.isna(driver_laps['PitOutTime']))
                        ]
                    if len(valid_laps) > 0:
                        avg_time = valid_laps['LapTime'].apply(lambda x: x.total_seconds()).median()
                        delta = lap_time - avg_time
                        if 0 < delta < 20:  # 合理范围
                            outlap_deltas.append(delta)

    t_pitdrive_inlap = np.median(inlap_deltas) if len(inlap_deltas) > 0 else 1.5
    t_pitdrive_outlap = np.median(outlap_deltas) if len(outlap_deltas) > 0 else 2.5

    print(f"\n进站圈时间损失: {t_pitdrive_inlap:.3f}秒 (基于{len(inlap_deltas)}个样本)")
    print(f"出站圈时间损失: {t_pitdrive_outlap:.3f}秒 (基于{len(outlap_deltas)}个样本)")

    return round(t_pitdrive_inlap, 3), round(t_pitdrive_outlap, 3)


def parse_existing_tire_params(content):
    """解析现有的轮胎参数"""
    tireset_pars = {}
    lines = content.split('\n')

    in_tireset = False
    current_driver = None
    bracket_depth = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 检测 TIRESET_PARS 开始
        if 'tireset_pars = {' in stripped:
            in_tireset = True
            bracket_depth = 1
            continue

        if not in_tireset:
            continue

        # 跟踪括号深度
        bracket_depth += stripped.count('{') - stripped.count('}')

        # TIRESET_PARS 结束
        if bracket_depth == 0:
            break

        # 检测车手（3字符缩写）
        match = re.match(r'^"([A-Z]{3}|HÜL)":\s*\{', stripped)
        if match and bracket_depth == 2:
            current_driver = match.group(1)
            if current_driver == "HÜL":
                current_driver = "HUL"  # 统一处理HUL
            tireset_pars[current_driver] = set()
            continue

        # 检测轮胎配方
        if current_driver and bracket_depth == 3:
            match = re.match(r'^"(A[2-7]|I|W)":\s*\{', stripped)
            if match:
                compound = match.group(1)
                tireset_pars[current_driver].add(compound)

    return tireset_pars


def update_tire_parameters(input_file, output_file, year, race_name, model='lin'):
    """更新轮胎退化参数"""

    print(f"正在加载 {year} 年 {race_name} 大奖赛数据...")
    session = fastf1.get_session(year, race_name, 'R')
    session.load()

    print(f"\n赛事: {session.event['EventName']}")
    print(f"赛道: {session.event['Location']}")

    # 计算进站时间
    print("\n" + "=" * 80)
    print("计算进站时间损失...")
    print("=" * 80)
    t_pitdrive_inlap, t_pitdrive_outlap = calculate_pit_times(session)

    # 读取原始ini文件
    print(f"\n正在读取 {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析现有的轮胎参数
    tireset_pars = parse_existing_tire_params(content)

    print("\n当前文件中的轮胎配方:")
    for driver, compounds in tireset_pars.items():
        if compounds:
            print(f"  {driver}: {sorted(list(compounds))}")

    print("\n" + "=" * 80)
    print("拟合轮胎退化参数...")
    print("=" * 80)

    laps = session.laps
    all_tire_params = {}

    for driver_num in sorted(session.drivers):
        driver_info = session.get_driver(driver_num)
        driver_abbr = driver_info['Abbreviation']

        print(f"\n处理车手: {driver_abbr}")

        driver_laps = laps[laps['Driver'] == driver_abbr].copy()

        if len(driver_laps) == 0:
            continue

        # 获取该车手现有的轮胎配方参数
        existing_compounds = tireset_pars.get(driver_abbr, set())

        # 获取该车手在比赛中使用的轮胎配方
        used_compounds = set()
        for compound in driver_laps['Compound'].unique():
            if pd.notna(compound):
                mapped = COMPOUND_MAPPING.get(compound, None)
                if mapped:
                    used_compounds.add(mapped)

        # 找出需要拟合的配方（在比赛中使用但原文件中缺失的）
        missing_compounds = used_compounds - existing_compounds

        if not missing_compounds:
            print(f"  所有使用的轮胎配方都已存在，跳过")
            continue

        print(f"  现有配方: {sorted(list(existing_compounds))}")
        print(f"  比赛使用: {sorted(list(used_compounds))}")
        print(f"  需要添加: {sorted(list(missing_compounds))}")

        driver_tire_params = {}

        for compound in sorted(missing_compounds):
            # 反向映射找到原始配方名称
            original_compound = None
            for k, v in COMPOUND_MAPPING.items():
                if v == compound:
                    original_compound = k
                    break

            if not original_compound:
                continue

            # 筛选该配方的圈速数据
            compound_laps = driver_laps[driver_laps['Compound'] == original_compound].copy()

            # 移除进站圈和出站圈
            compound_laps = compound_laps[
                (pd.isna(compound_laps['PitInTime']) | (compound_laps['PitInTime'] == pd.NaT)) &
                (pd.isna(compound_laps['PitOutTime']) | (compound_laps['PitOutTime'] == pd.NaT))
                ]

            # 只保留有效圈速
            compound_laps = compound_laps[
                (compound_laps['IsAccurate'] == True) &
                (pd.notna(compound_laps['LapTime'])) &
                (pd.notna(compound_laps['TyreLife']))
                ]

            if len(compound_laps) < 3:
                print(f"  ⚠️  {compound} 有效数据不足，跳过")
                continue

            # 拟合参数
            params = fit_tire_degradation(driver_abbr, compound, compound_laps, model=model)

            if params:
                driver_tire_params[compound] = params

        if driver_tire_params:
            if (driver_abbr == "HUL"):
                driver_abbr = "HÜL"
            all_tire_params[driver_abbr] = driver_tire_params

    # 更新ini文件
    print("\n" + "=" * 80)
    print("更新INI文件...")
    print("=" * 80)

    lines = content.split('\n')
    new_lines = []
    current_section = None
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 检测section
        if stripped.startswith('[') and stripped.endswith(']'):
            current_section = stripped[1:-1]
            new_lines.append(line)
            i += 1
            continue

        # 更新TRACK_PARS中的进站时间
        if current_section == 'TRACK_PARS':
            if '"t_pitdrive_inlap":' in line:
                indent = ' ' * (len(line) - len(line.lstrip()))
                new_lines.append(f'{indent}"t_pitdrive_inlap": {t_pitdrive_inlap},')
                i += 1
                continue
            elif '"t_pitdrive_outlap":' in line:
                indent = ' ' * (len(line) - len(line.lstrip()))
                new_lines.append(f'{indent}"t_pitdrive_outlap": {t_pitdrive_outlap},')
                i += 1
                continue

        # 更新TIRESET_PARS中的轮胎参数
        if current_section == 'TIRESET_PARS':
            # 检测车手定义行
            match = re.match(r'^(\s*)"([A-Z]{3}|HÜL)":\s*\{', line)
            if match:
                indent_str = match.group(1)
                current_driver = match.group(2)

                # 如果这个车手需要添加新的轮胎配方参数
                if current_driver in all_tire_params:
                    # 添加车手定义行
                    new_lines.append(line)
                    i += 1

                    # 收集该车手的所有行，直到遇到闭合括号
                    driver_lines = []
                    bracket_count = 1

                    while i < len(lines):
                        current_line = lines[i]
                        bracket_count += current_line.count('{') - current_line.count('}')

                        # 如果到达车手块的闭合括号
                        if bracket_count == 0:
                            # 在闭合括号前插入新配方
                            compound_indent = indent_str + ' ' * 4

                            # 检查是否需要在最后一行添加逗号
                            if driver_lines and not driver_lines[-1].strip().endswith(','):
                                driver_lines[-1] = driver_lines[-1].rstrip() + ','

                            # 添加新的配方参数
                            new_compounds = sorted(all_tire_params[current_driver].items())
                            for compound_idx, (compound, params) in enumerate(new_compounds):
                                is_last = compound_idx == len(new_compounds) - 1
                                comma = '' if is_last else ','

                                driver_lines.append(f'{compound_indent}"{compound}": {{')
                                driver_lines.append(f'{compound_indent}    "k_0": {params["k_0"]},')
                                driver_lines.append(f'{compound_indent}    "k_1_lin": {params["k_1_lin"]},')
                                driver_lines.append(f'{compound_indent}    "k_1_quad": {params["k_1_quad"]},')
                                driver_lines.append(f'{compound_indent}    "k_2_quad": {params["k_2_quad"]}')
                                driver_lines.append(f'{compound_indent}}}{comma}')

                            # 添加车手块的闭合括号
                            driver_lines.append(current_line)
                            new_lines.extend(driver_lines)
                            i += 1
                            break
                        else:
                            driver_lines.append(current_line)
                            i += 1

                    continue
                else:
                    # 不需要修改的车手，直接添加
                    new_lines.append(line)
                    i += 1
                    continue

        new_lines.append(line)
        i += 1

    # 写入新文件
    print(f"\n正在写入 {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

    print("\n" + "=" * 80)
    print("完成！")
    print("=" * 80)
    print(f"\n已为 {len(all_tire_params)} 位车手添加新的轮胎退化参数:")
    for driver, compounds in all_tire_params.items():
        print(f"  {driver}: {sorted(list(compounds.keys()))}")
    print(f"\n进站时间已更新:")
    print(f"  t_pitdrive_inlap: {t_pitdrive_inlap}s")
    print(f"  t_pitdrive_outlap: {t_pitdrive_outlap}s")


if __name__ == "__main__":
    INPUT_INI = "race_pars_Suzuka_updated.ini"
    OUTPUT_INI = "race_pars_Suzuka_final.ini"
    YEAR = 2025
    RACE_NAME = "Japan"
    MODEL = 'lin'  # 'lin' 或 'quad'

    update_tire_parameters(INPUT_INI, OUTPUT_INI, YEAR, RACE_NAME, MODEL)