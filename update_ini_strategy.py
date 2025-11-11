import fastf1
import pandas as pd
import configparser
from collections import OrderedDict

# 启用缓存
fastf1.Cache.enable_cache('f1_cache')

# 轮胎配方映射规则 (Pirelli官方配方 -> ini文件配方)
# 根据实际比赛来改
COMPOUND_MAPPING = {
    'SOFT': 'A4',      # C3 -> A4 (通常是软胎)
    'MEDIUM': 'A3',    # C2 -> A3 (通常是中性胎)
    'HARD': 'A2',      # C1 -> A2 (通常是硬胎)
    'INTERMEDIATE': 'I',
    'WET': 'W'
}

def get_driver_abbreviation_mapping(session):
    """创建车号到缩写的映射"""
    mapping = {}
    for driver_num in session.drivers:
        driver_info = session.get_driver(driver_num)
        mapping[driver_info['Abbreviation']] = {
            'initials': driver_info['Abbreviation'],
            'carno': int(driver_num)
        }
    return mapping

def extract_tire_strategy(session, driver_abbr):
    """提取单个车手的轮胎策略"""
    driver_laps = session.laps[session.laps['Driver'] == driver_abbr].copy()
    
    if len(driver_laps) == 0:
        return [[0, "A4", 0, 0.0]]  # 默认策略
    
    strategy = []
    current_compound = None
    current_tire_life = None
    stint_start_lap = 0
    
    for idx, lap in driver_laps.iterrows():
        lap_compound = lap['Compound']
        lap_number = int(lap['LapNumber']) if pd.notna(lap['LapNumber']) else 0
        tire_life = lap['TyreLife']
        
        # 映射轮胎配方
        if pd.notna(lap_compound):
            mapped_compound = COMPOUND_MAPPING.get(lap_compound, 'A4')
        else:
            mapped_compound = 'A4'
        
        # 检测轮胎更换
        is_new_stint = False
        
        if current_compound is None:
            # 第一个stint（起步）
            is_new_stint = True
            stint_start_lap = 0
        elif mapped_compound != current_compound:
            # 轮胎配方改变
            is_new_stint = True
            stint_start_lap = lap_number - 1  # 进站圈
        elif pd.notna(tire_life) and pd.notna(current_tire_life):
            if tire_life <= current_tire_life and tire_life <= 2:
                # TyreLife重置，说明换了新胎（即使配方相同）
                is_new_stint = True
                stint_start_lap = lap_number - 1
        
        if is_new_stint:
            if current_compound is None:
                # 起步轮胎
                strategy.append([0, mapped_compound, 0, 0.0])
            else:
                # 进站换胎
                strategy.append([stint_start_lap, mapped_compound, 0, 0.0])
            
            current_compound = mapped_compound
        
        current_tire_life = tire_life
    
    # 确保至少有一个策略条目
    if len(strategy) == 0:
        strategy.append([0, "A4", 0, 0.0])
    
    return strategy

def update_ini_file(input_file, output_file, year, race_name):
    """读取ini文件并更新轮胎策略数据"""
    
    print(f"正在加载 {year} 年 {race_name} 大奖赛数据...")
    session = fastf1.get_session(year, race_name, 'R')
    session.load()
    
    print(f"\n赛事: {session.event['EventName']}")
    print(f"赛道: {session.event['Location']}")
    print(f"日期: {session.event['EventDate']}")
    
    # 读取原始ini文件
    print(f"\n正在读取 {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 使用configparser解析
    config = configparser.ConfigParser()
    config.read(input_file, encoding='utf-8')
    
    # 获取车手映射
    driver_mapping = get_driver_abbreviation_mapping(session)
    
    print("\n" + "="*80)
    print("提取车手轮胎策略...")
    print("="*80)
    
    # 存储所有车手的策略
    all_strategies = {}
    
    for driver_abbr in sorted(driver_mapping.keys()):
        print(f"\n处理车手: {driver_abbr}")
        strategy = extract_tire_strategy(session, driver_abbr)
        if driver_abbr == "HUL":
            driver_abbr = "HÜL"  # 特例处理HUL
        all_strategies[driver_abbr] = strategy
        
        # 打印策略
        print(f"  策略: {strategy}")
    
    # 手动构建新的ini内容
    print("\n" + "="*80)
    print("更新INI文件...")
    print("="*80)
    
    # 读取并修改内容
    lines = content.split('\n')
    new_lines = []
    current_section = None
    current_driver = None
    skip_until_next_key = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # 检测section
        if stripped.startswith('[') and stripped.endswith(']'):
            current_section = stripped[1:-1]
            new_lines.append(line)
            skip_until_next_key = False
            i += 1
            continue
        
        # 在DRIVER_PARS section中处理strategy_info
        if current_section == 'DRIVER_PARS':
            # 检测车手定义开始
            if stripped.startswith('"') and stripped.endswith('": {'):
                current_driver = stripped[1:stripped.index('"', 1)]
                new_lines.append(line)
                skip_until_next_key = False
                i += 1
                continue
            
            # 检测strategy_info
            if '"strategy_info":' in stripped and current_driver in all_strategies:
                # 添加新的strategy_info
                indent = ' ' * 8
                new_lines.append(f'{indent}"strategy_info": [')
                for j, stint in enumerate(all_strategies[current_driver]):
                    comma = ',' if j < len(all_strategies[current_driver]) - 1 else ''
                    new_lines.append(f'{indent}    {stint}{comma}')
                new_lines.append(f'{indent}],')
                
                # 跳过原有的strategy_info内容
                i += 1
                bracket_count = 1
                while i < len(lines) and bracket_count > 0:
                    if '[' in lines[i]:
                        bracket_count += 1
                    if ']' in lines[i]:
                        bracket_count -= 1
                    i += 1
                continue
        
        # 在VSE_PARS section中处理real_strategy
        if current_section == 'VSE_PARS':
            # 检测real_strategy开始
            if '"real_strategy": {' in stripped:
                new_lines.append(line)
                i += 1
                
                # 重写所有real_strategy
                indent = ' ' * 8
                driver_count = 0
                for driver_abbr in sorted(all_strategies.keys()):
                    driver_count += 1
                    comma = ',' if driver_count < len(all_strategies) else ''
                    new_lines.append(f'{indent}"{driver_abbr}": [')
                    
                    for j, stint in enumerate(all_strategies[driver_abbr]):
                        stint_comma = ',' if j < len(all_strategies[driver_abbr]) - 1 else ''
                        new_lines.append(f'{indent}    {stint}{stint_comma}')
                    
                    new_lines.append(f'{indent}]{comma}')
                
                # 跳过原有的real_strategy内容，直到找到闭合的}
                bracket_count = 1
                while i < len(lines):
                    if '{' in lines[i]:
                        bracket_count += 1
                    if '}' in lines[i]:
                        bracket_count -= 1
                        if bracket_count == 0:
                            new_lines.append(lines[i])
                            i += 1
                            break
                    i += 1
                continue
        
        new_lines.append(line)
        i += 1
    
    # 写入新文件
    print(f"\n正在写入 {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    
    print("\n" + "="*80)
    print("完成！轮胎策略已更新")
    print("="*80)
    
    # 打印统计信息
    print(f"\n已更新 {len(all_strategies)} 位车手的轮胎策略")
    print("\n策略概览:")
    for driver_abbr in sorted(all_strategies.keys()):
        strategy = all_strategies[driver_abbr]
        print(f"  {driver_abbr}: {len(strategy)} 个stint")

if __name__ == "__main__":
    # 配置参数
    INPUT_INI = "race_pars_Suzuka.ini"  # 输入的ini文件
    OUTPUT_INI = "race_pars_Suzuka_updated.ini"  # 输出的ini文件
    YEAR = 2025
    RACE_NAME = "Japan"  # 可以是 "Japanese" 或 "Japan"
    
    # 执行更新
    update_ini_file(INPUT_INI, OUTPUT_INI, YEAR, RACE_NAME)