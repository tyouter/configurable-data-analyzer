# -*- coding: utf-8 -*-
"""
项目自动匹配器 - 智能识别数据文件属于哪个项目
"""

import os
import re
import pandas as pd
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass

try:
    from .config_manager import ConfigManager
except ImportError:
    from config_manager import ConfigManager


@dataclass
class MatchResult:
    """匹配结果"""
    project_name: str
    confidence: float  # 置信度 0-1
    match_method: str  # 匹配方法
    schema_name: str
    details: Dict[str, Any]


class ProjectMatcher:
    """项目自动匹配器"""

    def __init__(self, config_manager: ConfigManager = None):
        """
        初始化

        Args:
            config_manager: 配置管理器（可选）
        """
        self.config_manager = config_manager or ConfigManager()

    def detect_project(self, file_path: str, df: pd.DataFrame = None) -> Optional[MatchResult]:
        """
        自动检测数据文件属于哪个项目

        匹配策略（优先级从高到低）：
        1. 文件名模式匹配（正则表达式）
        2. 数据特征匹配（检查列名）
        3. 列名相似度匹配（Jaccard 相似度）
        4. 返回置信度最高的匹配结果

        Args:
            file_path: 数据文件路径
            df: 数据框（可选，如果不提供则尝试读取）

        Returns:
            匹配结果，如果未匹配则返回 None
        """
        filename = os.path.basename(file_path)

        # 如果没有提供 df，尝试读取
        if df is None:
            try:
                # 判断文件类型
                if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
                    df = pd.read_excel(file_path)
                elif file_path.endswith('.csv'):
                    df = pd.read_csv(file_path)
                else:
                    return None
            except Exception:
                return None

        columns = list(df.columns)

        # 1. 文件名匹配
        filename = os.path.basename(file_path)
        filename_matches = self.match_by_filename(filename)

        # 2. 列名特征匹配
        column_matches = self.dmatch_by_columns(columns)

        # 3. 合并所有匹配结果
        all_matches = []

        # 添加文件名匹配结果
        for project_name, confidence, schema_name in filename_matches:
            all_matches.append(MatchResult(
                project_name=project_name,
                confidence=confidence,
                match_method="filename",
                schema_name=schema_name,
                details={"filename": filename}
            ))

        # 添加列名匹配结果
        for project_name, confidence, schema_name in column_matches:
            all_matches.append(MatchResult(
                project_name=project_name,
                confidence=confidence,
                match_method="columns",
                schema_name=schema_name,
                details={"matched_columns": columns}
            ))

        # 如果有多个匹配，选择置信度最高的
        if all_matches:
            ranked = self.rank_matches(all_matches)
            return ranked[0]

        return None

    def match_by_filename(self, filename: str) -> List[Tuple[str, float, str]]:
        """
        根据文件名模式匹配项目

        Args:
            filename: 文件名

        Returns:
            [(project_name, confidence, schema_name), ...]
        """
        matches = []
        projects = self.config_manager.list_projects()

        for project in projects:
            try:
                mapping = self.config_manager.load_mapping(project.name)
                patterns = mapping.get('file_patterns', [])
                default_schema = mapping.get('default_schema')
                priority = mapping.get('priority', 10)

                for pattern in patterns:
                    # 使用正则匹配
                    try:
                        if re.search(pattern, filename, re.IGNORECASE):
                            # 根据优先级计算置信度
                            confidence = min(0.9, priority / 10.0)
                            matches.append((project.name, confidence, default_schema))
                    except re.error:
                        pass
            except Exception:
                continue

        # 按置信度排序
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def dmatch_by_columns(self, columns: List[str]) -> List[Tuple[str, float, str]]:
        """
        根据列名特征匹配项目

        Args:
            columns: 列名列表

        Returns:
            [(project_name, confidence, schema_name), ...]
        """
        matches = []
        projects = self.config_manager.list_projects()

        for project in projects:
            try:
                mapping = self.config_manager.load_mapping(project.name)
                signatures = mapping.get('data_signatures', [])
                default_schema = mapping.get('default_schema')

                for signature in signatures:
                    required_columns = signature.get('required_columns', [])
                    base_confidence = signature.get('confidence', 0.7)

                    # 检查是否包含所有必需列
                    matched = all(col in columns for col in required_columns)

                    if matched:
                        matches.append((project.name, base_confidence, default_schema))

            except Exception:
                continue

        # 如果没有特征匹配，使用相似度匹配
        if not matches:
            return self.match_by_similarity(columns)

        # 按置信度排序
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def match_by_similarity(self, columns: List[str]) -> List[Tuple[str, float, str]]:
        """
        使用列名相似度匹配项目

        Args:
            columns: 列名列表

        Returns:
            [(project_name, confidence, schema_name), ...]
        """
        matches = []
        projects = self.config_manager.list_projects()

        # 将列名转换为小写集合
        cols_set = set(col.lower() for col in columns)

        for project in projects:
            schemas = self.config_manager.list_schemas(project.name)

            for schema_name in schemas:
                try:
                    schema = self.config_manager.load_schema(project.name, schema_name)
                    schema_columns = schema.get('columns', {})

                    # 获取 schema 中的列名
                    schema_cols_set = set(col.lower() for col in schema_columns.keys())

                    # 计算 Jaccard 相似度
                    similarity = self.calculate_similarity(cols_set, schema_cols_set)

                    if similarity > 0.1:  # 至少有一些相似度
                        matches.append((project.name, similarity, schema_name))

                except Exception:
                    continue

        # 按置信度排序
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def calculate_similarity(self, cols1: set, cols2: set) -> float:
        """
        计算列名集合的 Jaccard 相似度

        Args:
            cols1: 列名集合1
            cols2: 列名集合2

        Returns:
            相似度 0-1
        """
        if not cols1 or not cols2:
            return 0.0

        intersection = len(cols1.intersection(cols2))
        union = len(cols1.union(cols2))

        if union == 0:
            return 0.0

        return intersection / union

    def rank_matches(self, matches: List[MatchResult]) -> List[MatchResult]:
        """
        根据优先级和置信度排序匹配结果

        Args:
            matches: 匹配结果列表

        Returns:
            排序后的匹配结果列表
        """
        # 根据项目优先级调整置信度
        for match in matches:
            try:
                mapping = self.config_manager.load_mapping(match.project_name)
                priority = mapping.get('priority', 10)

                # 优先级越高（数字越大），置信度加成越多
                match.confidence = match.confidence * (1 + priority / 50.0)
            except Exception:
                pass

        # 按调整后的置信度排序
        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches


if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("ProjectMatcher 测试")

    # 首先创建一个测试项目
    cm = ConfigManager()

    print("\n创建测试项目...")
    try:
        path = cm.create_project("rednote_project", "Rednote 数据分析")
        print(f"创建成功: {path}")
    except ValueError as e:
        print(f"项目已存在: {e}")

    # 创建测试 schema
    print("\n创建测试 schema...")
    test_schema = {
        "schema": {
            "name": "用户行为数据",
            "version": "1.0",
            "description": "用户行为埋点数据结构"
        },
        "columns": {
            "user_id": {
                "type": "string",
                "required": True,
                "description": "用户唯一标识"
            },
            "event_type": {
                "type": "categorical",
                "required": True,
                "description": "事件类型"
            },
            "timestamp": {
                "type": "datetime",
                "required": True,
                "description": "事件发生时间"
            }
        }
    }

    try:
        cm.save_schema("rednote_project", "user_behavior", test_schema)
        print("保存 schema 成功")
    except Exception as e:
        print(f"保存 schema 失败: {e}")

    # 更新 mapping 配置
    print("\n更新 mapping 配置...")
    mapping_data = {
        "project": {
            "name": "rednote_project",
            "display_name": "Rednote 数据分析",
            "version": "1.0"
        },
        "file_patterns": [
            r"rednote_.*\.xlsx",
            r"sample_data\.xlsx",
            r"user_.*\.xlsx"
        ],
        "data_signatures": [
            {
                "required_columns": ["user_id", "event_type", "timestamp"],
                "confidence": 0.9
            }
        ],
        "default_schema": "user_behavior",
        "priority": 10
    }

    try:
        cm.save_mapping("rednote_project", mapping_data)
        print("更新 mapping 成功")
    except Exception as e:
        print(f"更新 mapping 失败: {e}")

    # 测试匹配
    print("\n测试项目匹配...")
    matcher = ProjectMatcher(cm)

    # 测试文件名匹配
    test_filenames = [
        "rednote_data_202403.xlsx",
        "sample_data.xlsx",
        "other_data.xlsx"
    ]

    for filename in test_filenames:
        matches = matcher.match_by_filename(filename)
        print(f"\n文件名: {filename}")
        if matches:
            for project_name, confidence, schema_name in matches:
                print(f"  匹配: {project_name} (置信度: {confidence:.2f}, schema: {schema_name})")
        else:
            print("  未匹配到项目")

    # 测试列名匹配
    print("\n测试列名匹配...")
    test_columns_sets = [
        ["user_id", "event_type", "timestamp", "page_name"],
        ["user_id", "event_type", "timestamp"],
        ["id", "name", "value"]
    ]

    for columns in test_columns_sets:
        matches = matcher.dmatch_by_columns(columns)
        print(f"\n列名: {columns}")
        if matches:
            for project_name, confidence, schema_name in matches:
                print(f"  匹配: {project_name} (置信度: {confidence:.2f}, schema: {schema_name})")
        else:
            print("  未匹配到项目")

    # 测试相似度计算
    print("\n测试相似度计算...")
    cols1 = {"user_id", "event_type", "timestamp", "page_name"}
    cols2 = {"user_id", "event_type", "timestamp", "action"}
    cols3 = {"id", "name", "value"}

    print(f"set1 vs set2: {matcher.calculate_similarity(cols1, cols2):.2f}")
    print(f"set1 vs set3: {matcher.calculate_similarity(cols1, cols3):.2f}")

    # 测试完整检测
    print("\n测试完整检测...")
    test_file_path = "data/sample_data.xlsx"

    if os.path.exists(test_file_path):
        result = matcher.detect_project(test_file_path)
        if result:
            print(f"检测文件: {test_file_path}")
            print(f"  项目: {result.project_name}")
            print(f"  置信度: {result.confidence:.2f}")
            print(f"  匹配方法: {result.match_method}")
            print(f"  Schema: {result.schema_name}")
        else:
            print(f"未检测到项目: {test_file_path}")
    else:
        print(f"测试文件不存在: {test_file_path}")
