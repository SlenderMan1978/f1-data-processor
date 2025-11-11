import re
import json

def clean_ini_file(file_path):
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # 1️⃣ 替换所有单引号为双引号
    content = content.replace("'", '"')

    # 2️⃣ 去掉 np.float64(...)，保留里面的数字
    content = re.sub(r'np\.float64\((.*?)\)', r'\1', content)

    # 写回文件（覆盖原文件）
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)

    print(f"已完成：替换引号并去除 np.float64() 包裹的数字 —— 文件已更新：{file_path}")

def scale_t_lap_var_sigma(file_path, divisor=13.18):
    """
    将 ini 文件中 t_lap_var_sigma = {...} 里的所有数字除以 divisor（默认13.18）
    并保留 3 位小数
    """
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # 匹配 t_lap_var_sigma 的字典部分
    match = re.search(r't_lap_var_sigma\s*=\s*(\{.*?\})', content, re.DOTALL)
    if not match:
        print("⚠️ 未找到 t_lap_var_sigma 部分！")
        return

    json_like = match.group(1)

    # 尝试解析为 JSON
    try:
        data = json.loads(json_like)
    except Exception as e:
        print("⚠️ 无法解析为 JSON，请确保文件中的引号是双引号：", e)
        return

    # 对每个值进行除法并保留 3 位小数
    for key in data:
        try:
            data[key] = round(float(data[key]) / divisor, 3)
        except ValueError:
            pass  # 忽略非数字项

    # 将更新后的字典转回字符串
    new_json = json.dumps(data, ensure_ascii=False, indent=None)

    # 替换原内容
    new_content = content[:match.start(1)] + new_json + content[match.end(1):]

    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(new_content)

    print(f"✅ 已将 t_lap_var_sigma 中的所有数值除以 {divisor} 并保留 3 位小数 —— 文件已更新：{file_path}")

if __name__ == "__main__":
    # clean_ini_file("f1_2020_2025_pars_mcs.ini")
    scale_t_lap_var_sigma("f1_2020_2025_pars_mcs.ini")
