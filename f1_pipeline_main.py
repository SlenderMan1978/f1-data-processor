"""
F1比赛数据处理流水线主程序
按顺序执行：更新策略 -> 拟合轮胎退化 -> 转换参数文件
"""

import os
import sys
from datetime import datetime

# 导入三个处理模块
from update_ini_strategy import update_ini_file
from fit_tire_degradation import update_tire_parameters
from convert_pars import convert_race_pars_to_pars


class F1DataPipeline:
    """F1数据处理流水线"""
    
    def __init__(self, year, race_name, base_ini_file, output_filename=None):
        """
        初始化流水线

        参数:
            year: 赛季年份（如2025）
            race_name: 比赛名称（如"Japan"）
            base_ini_file: 基础ini文件路径
            output_filename: 最终输出文件名（可选，如"pars_Suzuka_2025.ini"）
        """
        self.year = year
        self.race_name = race_name
        self.base_ini_file = base_ini_file

        # 生成中间文件名
        base_name = os.path.splitext(base_ini_file)[0]
        self.updated_ini = f"{base_name}_updated.ini"
        self.final_ini = f"{base_name}_final.ini"

        # 设置最终输出文件名
        if output_filename:
            self.output_pars = output_filename
        else:
            # 默认命名规则
            self.output_pars = f"pars_{base_name.replace('race_pars_', '')}_{year}.ini"

        # 配置参数
        self.tire_model = 'lin'  # 轮胎模型：'lin' 或 'quad'

    def print_header(self, text):
        """打印格式化的标题"""
        print("\n" + "=" * 80)
        print(f"  {text}")
        print("=" * 80 + "\n")

    def check_file_exists(self, filepath):
        """检查文件是否存在"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"找不到文件: {filepath}")
        return True

    def replace_single_quotes_with_double(self, filepath):
        """将文件中的所有单引号替换为双引号"""
        print(f"\n正在处理引号替换: {filepath}")

        try:
            # 读取文件内容
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # 统计单引号数量
            single_quote_count = content.count("'")

            if single_quote_count > 0:
                # 替换所有单引号为双引号
                content = content.replace("'", '"')

                # 写回文件
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)

                print(f"✓ 已替换 {single_quote_count} 个单引号为双引号")
            else:
                print("✓ 文件中没有单引号，无需替换")

            return True

        except Exception as e:
            print(f"✗ 引号替换失败: {e}")
            return False

    def run(self):
        """执行完整的数据处理流水线"""
        start_time = datetime.now()

        try:
            # 检查基础文件是否存在
            self.print_header("开始F1数据处理流水线")
            print(f"赛季: {self.year}")
            print(f"比赛: {self.race_name}")
            print(f"基础文件: {self.base_ini_file}")
            print(f"最终输出: {self.output_pars}")

            self.check_file_exists(self.base_ini_file)

            # ========== 步骤1: 更新轮胎策略 ==========
            self.print_header("步骤 1/3: 更新轮胎策略数据")
            print(f"输入文件: {self.base_ini_file}")
            print(f"输出文件: {self.updated_ini}\n")

            update_ini_file(
                input_file=self.base_ini_file,
                output_file=self.updated_ini,
                year=self.year,
                race_name=self.race_name
            )

            # 检查生成的文件
            self.check_file_exists(self.updated_ini)
            print(f"\n✓ 策略更新完成: {self.updated_ini}")

            # ========== 步骤2: 拟合轮胎退化参数 ==========
            self.print_header("步骤 2/3: 拟合轮胎退化参数")
            print(f"输入文件: {self.updated_ini}")
            print(f"输出文件: {self.final_ini}")
            print(f"轮胎模型: {self.tire_model}\n")

            update_tire_parameters(
                input_file=self.updated_ini,
                output_file=self.final_ini,
                year=self.year,
                race_name=self.race_name,
                model=self.tire_model
            )

            # 检查生成的文件
            self.check_file_exists(self.final_ini)
            print(f"\n✓ 轮胎参数拟合完成: {self.final_ini}")

            # ========== 步骤3: 转换为最终参数文件 ==========
            self.print_header("步骤 3/3: 转换为最终参数文件")
            print(f"输入文件: {self.final_ini}")
            print(f"输出文件: {self.output_pars}\n")

            convert_race_pars_to_pars(
                input_file=self.final_ini,
                output_file=self.output_pars,
                year=self.year,
                race_name=self.race_name
            )

            # 检查生成的文件
            self.check_file_exists(self.output_pars)
            print(f"\n✓ 参数转换完成: {self.output_pars}")

            # ========== 步骤4: 替换单引号为双引号 ==========
            self.print_header("步骤 4/4: 处理引号格式")
            self.replace_single_quotes_with_double(self.output_pars)

            # ========== 完成 ==========
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            self.print_header("流水线执行完成！")
            print("生成的文件:")
            print(f"  1. {self.updated_ini} (策略更新)")
            print(f"  2. {self.final_ini} (轮胎参数)")
            print(f"  3. {self.output_pars} (最终参数 - 已处理引号)")
            print(f"\n总耗时: {duration:.1f} 秒")
            print("\n✓ 所有处理步骤已完成！")

            return True

        except FileNotFoundError as e:
            print(f"\n✗ 错误: {e}")
            print("请确保输入文件存在且路径正确")
            return False

        except Exception as e:
            print(f"\n✗ 流水线执行失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def cleanup_intermediate_files(self):
        """清理中间文件（可选）"""
        print("\n是否删除中间文件？(y/n): ", end='')
        response = input().strip().lower()

        if response == 'y':
            files_to_remove = [self.updated_ini, self.final_ini]
            for file in files_to_remove:
                try:
                    if os.path.exists(file):
                        os.remove(file)
                        print(f"  已删除: {file}")
                except Exception as e:
                    print(f"  无法删除 {file}: {e}")


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("  F1比赛数据处理流水线")
    print("  自动执行: 策略更新 -> 轮胎拟合 -> 参数转换 -> 引号处理")
    print("=" * 80)

    # ========== 配置参数 ==========
    # 在这里修改你的配置
    YEAR = 2025
    RACE_NAME = "Japan"  # 比赛名称（如"Japan", "Monaco", "Silverstone"等）
    BASE_INI_FILE = "race_pars_Suzuka.ini"  # 基础ini文件路径
    OUTPUT_FILENAME = "pars_Suzuka_2025.ini"  # 最终输出文件名（可选，留空则自动生成）

    # ========== 执行流水线 ==========
    pipeline = F1DataPipeline(
        year=YEAR,
        race_name=RACE_NAME,
        base_ini_file=BASE_INI_FILE,
        output_filename=OUTPUT_FILENAME  # 如果不想指定，可以传入None或删除此参数
    )

    success = pipeline.run()

    if success:
        # 询问是否清理中间文件
        pipeline.cleanup_intermediate_files()
    else:
        print("\n流水线执行失败，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()