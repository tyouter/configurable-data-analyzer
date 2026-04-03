# -*- coding: utf-8 -*-
"""
多项目配置系统端到端测试
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import pandas as pd
from config_manager import ConfigManager
from project_matcher import ProjectMatcher
from schema_generator import SchemaGenerator
from analyzer import DataAnalyzer

print("=" * 60)
print("多项目配置系统端到端测试")
print("=" * 60)

# 清理之前的测试数据
print("\n清理测试数据...")
cm = ConfigManager()

# 删除测试项目（如果存在）
for project in cm.list_projects():
    if project.name == "test_multi_project":
        try:
            cm.delete_project(project.name)
            print(f"  删除测试项目: {project.name}")
        except Exception as e:
            print(f"  删除失败: {e}")

# 测试 1：创建新项目
print("\n" + "=" * 60)
print("测试 1: 创建新项目")
print("=" * 60)

try:
    project_path = cm.create_project("test_multi_project", "测试多项目")
    print(f"项目创建成功: {project_path}")
except Exception as e:
    print(f"项目创建失败: {e}")

# 测试 2：生成 Schema
print("\n" + "=" * 60)
print("测试 2: 从数据样本生成 Schema")
print("=" * 60)

# 读取测试数据
test_data = {
    "order_id": ["ord_001", "ord_002", "ord_003"],
    "customer_id": ["cust_001", "cust_002", "cust_003"],
    "order_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
    "amount": [100.5, 200.75, 150.25],
    "status": ["pending", "completed", "shipped"]
}

df = pd.DataFrame(test_data)

generator = SchemaGenerator()
schema = generator.generate_schema_from_dataframe(
    df,
    schema_name="订单数据",
    schema_description="订单业务数据结构"
)

print(f"Schema 名称: {schema['schema']['name']}")
print(f"Schema 描述: {schema['schema']['description']}")
print(f"列数: {len(schema['columns'])}")

# 保存 Schema
try:
    schema_path = cm.save_schema("test_multi_project", "order_data", schema)
    print(f"Schema 保存成功: {schema_path}")
except Exception as e:
    print(f"Schema 保存失败: {e}")

# 测试 3：创建 Metrics 配置
print("\n" + "=" * 60)
print("测试 3: 创建 Metrics 配置")
print("=" * 60)

metrics_data = {
    "metrics": {
        "total_orders": {
            "name": "总订单数",
            "type": "count",
            "column": "order_id",
            "description": "订单总数",
            "keywords": ["订单数", "总订单"]
        },
        "total_customers": {
            "name": "总客户数",
            "type": "unique_count",
            "column": "customer_id",
            "description": "客户总数",
            "keywords": ["客户数", "总客户"]
        },
        "avg_amount": {
            "name": "平均订单金额",
            "type": "average",
            "column": "amount",
            "description": "平均订单金额",
            "keywords": ["平均金额", "订单金额"]
        }
    }
}

try:
    metrics_path = cm.save_metrics("test_multi_project", metrics_data)
    print(f"Metrics 保存成功: {metrics_path}")
except Exception as e:
    print(f"Metrics 保存失败: {e}")

# 测试 4：创建 Mapping 配置
print("\n" + "=" * 60)
print("测试 4: 创建 Mapping 配置")
print("=" * 60)

mapping_data = {
    "project": {
        "name": "test_multi_project",
        "display_name": "测试多项目",
        "version": "1.0"
    },
    "file_patterns": [
        r"order_.*\.xlsx",
        r"test_.*\.xlsx"
    ],
    "data_signatures": [
        {
            "required_columns": ["order_id", "customer_id", "order_date"],
            "confidence": 0.9
        }
    ],
    "default_schema": "order_data",
    "priority": 20
}

try:
    mapping_path = cm.save_mapping("test_multi_project", mapping_data)
    print(f"Mapping 保存成功: {mapping_path}")
except Exception as e:
    print(f"Mapping 保存失败: {e}")

# 测试 5：列出所有项目
print("\n" + "=" * 60)
print("测试 5: 列出所有项目")
print("=" * 60)

projects = cm.list_projects()
for project in projects:
    print(f"  - {project.name} ({project.display_name}) v{project.version}")

# 测试 6：项目匹配
print("\n" + "=" * 60)
print("测试 6: 项目匹配")
print("=" * 60)

matcher = ProjectMatcher(cm)

# 测试文件名匹配
test_filenames = [
    "order_data_202404.xlsx",
    "test_sample.xlsx",
    "unknown_data.xlsx"
]

for filename in test_filenames:
    matches = matcher.match_by_filename(filename)
    if matches:
        print(f"  {filename} -> {matches[0][0]} (置信度: {matches[0][1]:.2f})")
    else:
        print(f"  {filename} -> 未匹配")

# 测试列名匹配
test_columns = [
    ["order_id", "customer_id", "order_date", "amount"],
    ["user_id", "event_type", "timestamp"]
]

for columns in test_columns:
    matches = matcher.dmatch_by_columns(columns)
    if matches:
        print(f"  {columns[:3]} -> {matches[0][0]} (置信度: {matches[0][1]:.2f})")
    else:
        print(f"  {columns[:3]} -> 未匹配")

# 测试 7：加载项目配置
print("\n" + "=" * 60)
print("测试 7: 加载完整项目配置")
print("=" * 60)

try:
    project_config = cm.load_project_config("test_multi_project")
    print(f"  项目名称: {project_config['project_name']}")
    print(f"  Mapping 包含: {list(project_config['mapping'].keys())}")
    print(f"  Metrics 包含: {len(project_config['metrics']['metrics'])} 个指标")
    if project_config['schema']:
        print(f"  Schema 名称: {project_config['schema']['schema']['name']}")
except Exception as e:
    print(f"  加载失败: {e}")

# 测试 8：使用 DataAnalyzer 进行数据分析
print("\n" + "=" * 60)
print("测试 8: 使用 DataAnalyzer 进行数据分析")
print("=" * 60)

# 保存测试数据到 Excel
test_file = "test_order_data.xlsx"
df.to_excel(test_file, index=False)
print(f"  创建测试数据文件: {test_file}")

try:
    analyzer = DataAnalyzer(cm)
    analyzer.load_data(test_file)

    print(f"  当前项目: {analyzer.get_current_project()}")

    # 数据概览
    summary = analyzer.get_summary()
    print(f"  数据行数: {summary['rows']}")
    print(f"  数据列数: {summary['columns']}")
    print(f"  数据列名: {summary['column_names']}")

    # 验证 Schema
    is_valid = analyzer.validate_data_schema()
    print(f"  Schema 验证: {'通过' if is_valid else '失败'}")

    # 计算指标
    print("\n  计算指标:")
    for metric_name in ["total_orders", "total_customers", "avg_amount"]:
        try:
            result = analyzer.calculate_metric(metric_name)
            print(f"    {result['name']}: {result['value']}")
        except Exception as e:
            print(f"    {metric_name}: 计算失败 - {str(e)}")

except Exception as e:
    print(f"  分析失败: {e}")
    import traceback
    traceback.print_exc()

# 清理测试文件
if os.path.exists(test_file):
    os.remove(test_file)
    print(f"\n  清理测试文件: {test_file}")

# 测试 9：测试 rednote_project
print("\n" + "=" * 60)
print("测试 9: 测试 rednote_project 自动匹配")
print("=" * 60)

# 检查 rednote_project 是否存在
if cm.project_exists("rednote_project"):
    print("  rednote_project 存在")

    # 列出 schemas
    schemas = cm.list_schemas("rednote_project")
    print(f"  Schemas: {schemas}")

    # 加载 metrics
    metrics = cm.load_metrics("rednote_project")
    print(f"  Metrics 包含: {len(metrics['metrics'])} 个指标")

    # 测试样本数据匹配
    sample_file = "../data/sample_data.xlsx"
    if os.path.exists(sample_file):
        try:
            df_sample = pd.read_excel(sample_file)
            match_result = matcher.detect_project(sample_file, df_sample)
            if match_result:
                print(f"  sample_data.xlsx 匹配到: {match_result.project_name}")
                print(f"    置信度: {match_result.confidence:.2f}")
                print(f"    匹配方法: {match_result.match_method}")
                print(f"    Schema: {match_result.schema_name}")
            else:
                print(f"  sample_data.xlsx 未匹配到项目")
        except Exception as e:
            print(f"  测试匹配失败: {e}")
else:
    print("  rednote_project 不存在")

# 清理测试项目
print("\n" + "=" * 60)
print("清理测试数据")
print("=" * 60)

try:
    cm.delete_project("test_multi_project")
    print("测试项目已删除")
except Exception as e:
    print(f"删除失败: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
