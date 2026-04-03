# -*- coding: utf-8 -*-
"""
数据结构配置生成器 - 从表头说明文档和数据样本生成 schema 配置
"""

import os
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime


class SchemaGenerator:
    """数据结构配置生成器"""

    def __init__(self, xlsx_skill=None):
        """
        初始化

        Args:
            xlsx_skill: xlsx SKILL 实例（可选，用于读取表头说明文档）
        """
        self.xlsx_skill = xlsx_skill

    def generate_from_template(self, template_file: str, data_file: str) -> dict:
        """
        从表头说明模板生成 schema 配置

        Args:
            template_file: 表头说明文档（Excel/MD 格式）
            data_file: 数据样本文件（用于推断数据类型）

        Returns:
            schema 配置字典
        """
        # 解析模板文档
        template_data = self.parse_template_document(template_file)

        # 从数据样本推断类型
        if data_file and os.path.exists(data_file):
            df = pd.read_excel(data_file) if data_file.endswith('.xlsx') else pd.read_csv(data_file)
            inferred_types = self.infer_column_types(df)
        else:
            inferred_types = {}

        # 创建 schema 配置
        schema_dict = self.create_schema_dict(template_data, inferred_types)

        return schema_dict

    def infer_column_types(self, df: pd.DataFrame, sample_size: int = 1000) -> Dict[str, Any]:
        """
        从数据样本推断列类型

        Args:
            df: 数据框
            sample_size: 样本大小（用于推断枚举值）

        Returns:
            {column_name: inferred_type}
        """
        inferred = {}

        for column in df.columns:
            # 获取样本数据
            sample_data = df[column].dropna().head(sample_size)

            if len(sample_data) == 0:
                inferred[column] = {
                    "type": "unknown",
                    "description": "无数据"
                }
                continue

            # 推断类型
            dtype = str(df[column].dtype)

            if 'int' in dtype:
                inferred[column] = {
                    "type": "integer",
                    "description": "整数类型"
                }
            elif 'float' in dtype:
                inferred[column] = {
                    "type": "float",
                    "description": "浮点数类型"
                }
            elif 'bool' in dtype:
                inferred[column] = {
                    "type": "boolean",
                    "description": "布尔类型"
                }
            elif 'datetime' in dtype or 'time' in dtype:
                inferred[column] = {
                    "type": "datetime",
                    "description": "日期时间类型",
                    "format": "%Y-%m-%d %H:%M:%S"
                }
            else:
                # 字符串类型，进一步推断
                unique_values = sample_data.unique()
                unique_count = len(unique_values)

                # 如果唯一值较少，可能是分类变量
                if unique_count <= 50 and unique_count <= len(sample_data) * 0.1:
                    inferred[column] = {
                        "type": "categorical",
                        "description": "分类变量",
                        "enum": [str(v) for v in unique_values[:20]]  # 最多保存20个枚举值
                    }
                else:
                    inferred[column] = {
                        "type": "string",
                        "description": "字符串类型"
                    }

        return inferred

    def parse_template_document(self, template_file: str) -> Dict[str, Any]:
        """
        解析表头说明文档

        支持 Excel 和 MD 格式

        Args:
            template_file: 模板文件路径

        Returns:
            解析后的模板数据
        """
        if not os.path.exists(template_file):
            return {
                "schema": {
                    "name": "自动生成",
                    "version": "1.0",
                    "description": "自动生成的schema配置"
                },
                "columns": {}
            }

        if template_file.endswith('.xlsx') or template_file.endswith('.xls'):
            return self._parse_excel_template(template_file)
        elif template_file.endswith('.md') or template_file.endswith('.markdown'):
            return self._parse_markdown_template(template_file)
        else:
            return {
                "schema": {
                    "name": "自动生成",
                    "version": "1.0",
                    "description": "不支持的模板格式"
                },
                "columns": {}
            }

    def _parse_excel_template(self, template_file: str) -> Dict[str, Any]:
        """
        解析 Excel 模板文件

        预期格式：
        - 第一行：列名
        - 第二行：描述
        - 第三行：类型（可选）

        Args:
            template_file: Excel 文件路径

        Returns:
            解析后的模板数据
        """
        try:
            df = pd.read_excel(template_file)

            columns = {}

            for idx, row in df.iterrows():
                if idx == 0:
                    # 第一行是表头
                    continue

                # 尝试从不同格式中提取信息
                col_name = row.get('列名') or row.get('Column') or row.get('field_name')
                if pd.isna(col_name):
                    continue

                col_name = str(col_name).strip()

                description = row.get('描述') or row.get('Description') or row.get('description')
                if pd.isna(description):
                    description = "自动生成的描述"
                else:
                    description = str(description).strip()

                col_type = row.get('类型') or row.get('Type') or row.get('type')
                if pd.isna(col_type):
                    col_type = "string"
                else:
                    col_type = str(col_type).strip()

                required = row.get('必需') or row.get('Required') or row.get('required')
                if pd.isna(required):
                    required = False
                else:
                    required = str(required).strip().lower() in ['true', 'yes', 'y', '1']

                columns[col_name] = {
                    "type": col_type,
                    "required": required,
                    "description": description
                }

            return {
                "schema": {
                    "name": "从 Excel 生成",
                    "version": "1.0",
                    "description": f"从 {os.path.basename(template_file)} 生成"
                },
                "columns": columns
            }

        except Exception as e:
            return {
                "schema": {
                    "name": "解析失败",
                    "version": "1.0",
                    "description": f"解析 Excel 模板失败: {str(e)}"
                },
                "columns": {}
            }

    def _parse_markdown_template(self, template_file: str) -> Dict[str, Any]:
        """
        解析 Markdown 模板文件

        预期格式：
        ```markdown
        # Schema 名称

        描述文本...

        ## 列定义

        | 列名 | 类型 | 必需 | 描述 |
        | ```` | ```` | ```` | ```` |
        | user_id | string | Yes | 用户ID |
        ````

        Args:
            template_file: Markdown 文件路径

        Returns:
            解析后的模板数据
        """
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 简单的解析逻辑
            lines = content.split('\n')

            schema_name = "从 Markdown 生成"
            description = "从 Markdown 生成的 schema"
            columns = {}

            in_table = False
            for i, line in enumerate(lines):
                line = line.strip()

                # 提取 schema 名称
                if line.startswith('#') and not in_table:
                    schema_name = line.lstrip('#').strip()
                    continue

                # 检测表格开始
                if '| 列名' in line or '| Column' in line or '| Field' in line:
                    in_table = True
                    continue

                # 跳过表格分隔符
                if in_table and '|' in line and all(c in '-| ' for c in line):
                    continue

                # 解析表格行
                if in_table and '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 4 and all(p for p in parts[:4]):
                        col_name = parts[0]
                        col_type = parts[1]
                        required_str = parts[2].lower()
                        desc = parts[3]

                        required = required_str in ['yes', 'true', 'y', '1']

                        columns[col_name] = {
                            "type": col_type,
                            "required": required,
                            "description": desc
                        }

            return {
                "schema": {
                    "name": schema_name,
                    "version": "1.0",
                    "description": description
                },
                "columns": columns
            }

        except Exception as e:
            return {
                "schema": {
                    "name": "解析失败",
                    "version": "1.0",
                    "description": f"解析 Markdown 模板失败: {str(e)}"
                },
                "columns": {}
            }

    def create_schema_dict(self, template_data: dict, inferred_types: dict) -> dict:
        """
        合并模板信息和推断类型，创建完整的 schema 配置

        Args:
            template_data: 模板解析数据
            inferred_types: 推断的类型信息

        Returns:
            完整的 schema 配置
        """
        schema_info = template_data.get('schema', {})
        template_columns = template_data.get('columns', {})

        # 创建结果字典
        result = {
            "schema": {
                "name": schema_info.get('name', '自动生成'),
                "version": schema_info.get('version', '1.0'),
                "description": schema_info.get('description', '自动生成的schema配置'),
                "created_at": datetime.now().isoformat()
            },
            "columns": {}
        }

        # 合并列定义
        # 首先使用模板中的定义
        for col_name, col_def in template_columns.items():
            result['columns'][col_name] = col_def.copy()

        # 然后补充推断的类型（如果模板中没有）
        for col_name, type_info in inferred_types.items():
            if col_name not in result['columns']:
                # 模板中没有这个列，直接使用推断的信息
                result['columns'][col_name] = {
                    "type": type_info.get('type', 'string'),
                    "required": False,
                    "description": type_info.get('description', '自动生成的描述')
                }

                # 如果有枚举值，添加进去
                if 'enum' in type_info:
                    result['columns'][col_name]['enum'] = type_info['enum']

            else:
                # 模板中有这个列，只补充缺失的类型信息
                if 'type' not in result['columns'][col_name] or result['columns'][col_name]['type'] == 'unknown':
                    result['columns'][col_name]['type'] = type_info.get('type', 'string')

                # 如果推断出是枚举类型且模板中没有定义枚举，补充枚举值
                if 'enum' in type_info and 'enum' not in result['columns'][col_name]:
                    result['columns'][col_name]['enum'] = type_info['enum']

        return result

    def generate_schema_from_dataframe(self, df: pd.DataFrame, schema_name: str = "自动生成",
                                     schema_description: str = "从数据生成的schema") -> dict:
        """
        直接从数据框生成 schema 配置

        Args:
            df: 数据框
           从: schema 名称
            schema_description: schema 描述

        Returns:
            schema 配置字典
        """
        inferred_types = self.infer_column_types(df)

        result = {
            "schema": {
                "name": schema_name,
                "version": "1.0",
                "description": schema_description,
                "created_at": datetime.now().isoformat(),
                "columns_count": len(df.columns),
                "rows_sampled": len(df)
            },
            "columns": {}
        }

        for col_name, type_info in inferred_types.items():
            result['columns'][col_name] = {
                "type": type_info.get('type', 'string'),
                "required": False,
                "description": type_info.get('description', '自动生成的描述')
            }

            if 'enum' in type_info:
                result['columns'][col_name]['enum'] = type_info['enum']

        return result


if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("SchemaGenerator 测试")

    generator = SchemaGenerator()

    # 测试从数据框生成 schema
    print("\n测试从数据框生成 schema...")
    test_data = {
        "user_id": ["user_001", "user_002", "user_003"],
        "event_type": ["page_view", "click", "page_view"],
        "timestamp": ["2024-01-01 10:00:00", "2024-01-01 10:01:00", "2024-01-01 10:02:00"],
        "duration_ms": [1000, 500, 2000],
        "page_name": ["home", "product", "home"]
    }

    df = pd.DataFrame(test_data)
    schema = generator.generate_schema_from_dataframe(
        df,
        schema_name="测试数据Schema",
        schema_description="用于测试的schema配置"
    )

    print(f"Schema 名称: {schema['schema']['name']}")
    print(f"Schema 描述: {schema['schema']['description']}")
    print(f"列数: {len(schema['columns'])}")
    print("\n列定义:")
    for col_name, col_def in schema['columns'].items():
        print(f"  {col_name}:")
        print(f"    类型: {col_def.get('type')}")
        print(f"    描述: {col_def.get('description')}")
        if 'enum' in col_def:
            print(f"    枚举值: {col_def['enum']}")

    # 测试从实际文件生成
    print("\n测试从实际文件生成 schema...")
    test_file = "data/sample_data.xlsx"

    if os.path.exists(test_file):
        try:
            df = pd.read_excel(test_file)
            schema = generator.generate_schema_from_dataframe(
                df,
                schema_name="Sample Data Schema",
                schema_description="从 sample_data.xlsx 生成"
            )

            print(f"Schema 名称: {schema['schema']['name']}")
            print(f"数据行数: {schema['schema']['rows_sampled']}")
            print(f"列数: {len(schema['columns'])}")
            print("\n列定义:")
            for col_name, col_def in list(schema['columns'].items())[:5]:  # 只显示前5列
                print(f"  {col_name}: {col_def.get('type')} - {col_def.get('description')}")
        except Exception as e:
            print(f"处理文件失败: {e}")
    else:
        print(f"测试文件不存在: {test_file}")

    # 测试类型推断
    print("\n测试类型推断...")
    test_types = {
        "int_col": [1, 2, 3, 4, 5],
        "float_col": [1.1, 2.2, 3.3, 4.4, 5.5],
        "str_col": ["a", "b", "c", "d", "e"],
        "cat_col": ["A", "B", "A", "B", "A"],
        "bool_col": [True, False, True, False, True]
    }

    df_types = pd.DataFrame(test_types)
    inferred = generator.infer_column_types(df_types)

    for col_name, type_info in inferred.items():
        print(f"  {col_name}: {type_info.get('type')}")
