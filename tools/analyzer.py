# -*- coding: utf-8 -*-
"""
数据分析核心引擎
提供数据加载、指标计算、查询等功能
"""

import pandas as pd
import yaml
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from .config_manager import ConfigManager
    from .project_matcher import ProjectMatcher
except ImportError:
    from config_manager import ConfigManager
    from project_matcher import ProjectMatcher


class DataAnalyzer:
    """数据分析核心类"""

    def __init__(self, config_manager: ConfigManager = None):
        """
        初始化

        Args:
            config_manager: 配置管理器（可选，用于多项目支持）
        """
        self.df = None
        self.file_path = None
        self.metrics_config = None
        self.config_manager = config_manager or ConfigManager()
        self.current_project = None
        self.current_schema = None

    def load_data(self, file_path: str, project_name: str = None) -> 'DataAnalyzer':
        """
        加载Excel数据

        Args:
            file_path: Excel文件路径
            project_name: 项目名称（可选，不提供则自动检测）

        Returns:
            self

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式错误
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        try:
            # 使用pandas读取Excel
            self.df = pd.read_excel(file_path)
            self.file_path = file_path

            # 自动检测或指定项目
            if project_name:
                self.current_project = project_name
            else:
                matcher = ProjectMatcher(self.config_manager)
                match_result = matcher.detect_project(file_path, self.df)
                if match_result:
                    self.current_project = match_result.project_name
                else:
                    # 未检测到项目，使用默认路径加载metrics配置
                    self.current_project = None

            # 加载metrics配置
            if self.current_project:
                self.metrics_config = self.config_manager.load_metrics(self.current_project)
            else:
                # 使用默认路径
                self.metrics_config = load_metrics_config()

            return self
        except Exception as e:
            raise ValueError(f"读取Excel文件失败: {str(e)}")

    def get_summary(self) -> Dict[str, Any]:
        """
        获取数据概览

        Returns:
            包含行数、列数、列名、数据类型的字典
        """
        if self.df is None:
            raise ValueError("未加载数据，请先调用 load_data()")

        return {
            "rows": len(self.df),
            "columns": len(self.df.columns),
            "column_names": list(self.df.columns),
            "dtypes": {col: str(dtype) for col, dtype in self.df.dtypes.items()},
            "file_path": self.file_path
        }

    def get_columns(self) -> List[str]:
        """获取所有列名"""
        if self.df is None:
            raise ValueError("未加载数据，请先调用 load_data()")
        return list(self.df.columns)

    def validate_data_schema(self) -> bool:
        """
        验证数据是否符合项目 schema 定义

        Returns:
            是否通过验证
        """
        if not self.current_project:
            # 没有项目配置，跳过验证
            return True

        try:
            mapping = self.config_manager.load_mapping(self.current_project)
            default_schema = mapping.get('default_schema')

            if not default_schema:
                # 没有schema定义，跳过验证
                return True

            schema = self.config_manager.load_schema(self.current_project, default_schema)
            columns_def = schema.get('columns', {})

            # 验证必需列是否存在
            missing_columns = []
            for col_name, col_def in columns_def.items():
                if col_def.get('required', False) and col_name not in self.df.columns:
                    missing_columns.append(col_name)

            if missing_columns:
                print(f"验证失败: 缺少必需列: {', '.join(missing_columns)}")
                return False

            return True

        except Exception as e:
            print(f"验证schema时出错: {str(e)}")
            return False

    def get_current_project(self) -> Optional[str]:
        """获取当前项目名称"""
        return self.current_project

    def set_current_project(self, project_name: str) -> None:
        """
        设置当前项目

        Args:
            project_name: 项目名称
        """
        if not self.config_manager.project_exists(project_name):
            raise ValueError(f"项目不存在: {project_name}")

        self.current_project = project_name
        self.metrics_config = self.config_manager.load_metrics(project_name)

    def group_by_user(self, user_column: str = "user_id") -> pd.DataFrame:
        """
        按用户分组聚合

        Args:
            user_column: 用户ID列名，默认为'user_id'

        Returns:
            分组后的DataFrame
        """
        if self.df is None:
            raise ValueError("未加载数据，请先调用 load_data()")

        if user_column not in self.df.columns:
            raise ValueError(f"列不存在: {user_column}")

        # 统计每个用户的事件数
        grouped = self.df.groupby(user_column).size().reset_index(name='event_count')

        # 计算每个用户的平均停留时长
        if 'duration_ms' in self.df.columns:
            avg_duration = self.df.groupby(user_column)['duration_ms'].mean().reset_index(name='avg_duration_ms')
            grouped = grouped.merge(avg_duration, on=user_column)

        return grouped

    def get_user_timeline(self, user_id: str, user_column: str = "user_id", timestamp_column: str = "timestamp") -> pd.DataFrame:
        """
        获取特定用户的行为时序

        Args:
            user_id: 用户ID
            user_column: 用户ID列名，默认为'user_id'
            timestamp_column: 时间戳列名，默认为'timestamp'

        Returns:
            按时间排序的用户行为数据
        """
        if self.df is None:
            raise ValueError("未加载数据，请先调用 load_data()")

        if user_column not in self.df.columns:
            raise ValueError(f"列不存在: {user_column}")

        if timestamp_column not in self.df.columns:
            raise ValueError(f"列不存在: {timestamp_column}")

        # 筛选用户数据
        user_data = self.df[self.df[user_column] == user_id].copy()

        if user_data.empty:
            return pd.DataFrame()

        # 转换时间戳并排序
        try:
            user_data[timestamp_column] = pd.to_datetime(user_data[timestamp_column])
            user_data = user_data.sort_values(timestamp_column)
        except Exception as e:
            # 如果时间戳转换失败，使用原始排序
            user_data = user_data.copy()

        return user_data

    def query(self, filters: Dict[str, Any]) -> pd.DataFrame:
        """
        条件查询数据

        Args:
            filters: 过滤条件字典，如 {"event_type": "page_view", "page_name": "home"}

        Returns:
            筛选后的DataFrame
        """
        if self.df is None:
            raise ValueError("未加载数据，请先调用 load_data()")

        result = self.df.copy()

        for column, value in filters.items():
            if column not in result.columns:
                raise ValueError(f"列不存在: {column}")

            # 支持列表匹配（in操作）
            if isinstance(value, list):
                result = result[result[column].isin(value)]
            else:
                result = result[result[column] == value]

        return result

    def calculate_metric(self, name: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        计算指定指标

        Args:
            name: 指标名称
            config: 指标配置（可选，如果不提供则使用预定义配置）

        Returns:
            包含指标名称、值和描述的字典
        """
        if self.df is None:
            raise ValueError("未加载数据，请先调用 load_data()")

        # 使用提供的配置或预定义配置
        if config is None:
            if self.metrics_config is None:
                self.metrics_config = load_metrics_config()

            if name not in self.metrics_config['metrics']:
                raise ValueError(f"未定义的指标: {name}")

            config = self.metrics_config['metrics'][name]

        metric_type = config.get('type', 'count')

        # 根据指标类型调用相应的计算函数
        if metric_type == 'count':
            column = config.get('column')
            result = calculate_count(self.df, column)
        elif metric_type == 'unique_count':
            column = config.get('column')
            result = calculate_unique_count(self.df, column)
        elif metric_type == 'average':
            column = config.get('column')
            result = calculate_average(self.df, column)
        elif metric_type == 'custom':
            result = calculate_custom_metric(self.df, name, config)
        elif metric_type == 'derived':
            result = calculate_derived_metric(self.df, name, config)
        else:
            raise ValueError(f"不支持的指标类型: {metric_type}")

        return {
            "name": config.get('name', name),
            "value": result,
            "description": config.get('description', ''),
            "type": metric_type
        }

    def export_to_json(self, path: str, data: Optional[pd.DataFrame] = None) -> str:
        """
        导出数据到JSON

        Args:
            path: 输出路径
            data: 要导出的数据（可选，默认为当前DataFrame）

        Returns:
            输出文件路径
        """
        if data is None:
            data = self.df

        if data is None:
            raise ValueError("没有数据可导出")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        data.to_json(path, orient='records', force_ascii=False, indent=2)

        return path


# ====== 指标计算函数 ======

def calculate_count(df: pd.DataFrame, column: str) -> int:
    """
    计算某列的计数

    Args:
        df: 数据框
        column: 列名

    Returns:
        计数结果
    """
    if column not in df.columns:
        raise ValueError(f"列不存在: {column}")

    return len(df[column].dropna())


def calculate_unique_count(df: pd.DataFrame.dtypes, column: str) -> int:
    """
    计算某列的唯一值计数

    Args:
        df: 数据框
        column: 列名

    Returns:
        唯一值计数
    """
    if column not in df.columns:
        raise ValueError(f"列不存在: {column}")

    return len(df[column].unique())


def calculate_average(df: pd.DataFrame, column: str) -> float:
    """
    计算某列的平均值

    Args:
        df: 数据框
        column: 列名

    Returns:
        平均值
    """
    if column not in df.columns:
        raise ValueError(f"列不存在: {column}")

    return float(df[column].mean())


def calculate_custom_metric(df: pd.DataFrame, metric_name: str, config: Dict[str, Any]) -> Any:
    """
    计算自定义指标

    Args:
        df: 数据框
        metric_name: 指标名称
        config: 指标配置

    Returns:
        计算结果
    """
    # 根据指标名称执行不同的计算逻辑
    if metric_name == "daily_active_users":
        # 计算日活跃用户数
        if 'timestamp' not in df.columns:
            raise ValueError("缺少timestamp列")

        # 解析时间戳
        df_temp = df.copy()
        df_temp['timestamp'] = pd.to_datetime(df_temp['timestamp'])

        # 获取今天
        today = datetime.now().date()

        # 筛选今天的数据
        today_data = df_temp[df[df_temp['timestamp'].dt.date == today]]

        return len(today_data['user_id'].unique())

    elif metric_name == "high_value_users":
        # 识别高价值用户（事件数>平均值+标准差的用户）
        if 'user_id' not in df.columns:
            raise ValueError("缺少user_id列")

        user_events = df.groupby('user_id').size()
        mean_events = user_events.mean()
        std_events = user_events.std()
        threshold = mean_events + std_events

        high_value = user_events[user_events > threshold]
        return list(high_value.index)

    else:
        raise ValueError(f"未实现的自定义指标: {metric_name}")


def calculate_derived_metric(df: pd.DataFrame, metric_name: str, config: Dict[str, Any]) -> float:
    """
    计算派生指标（基于其他指标）

    Args:
        df: 数据框
        metric_name: 指标名称
        config: 指标配置

    Returns:
        计算结果
    """
    formula = config.get('formula', '')

    if metric_name == "user_activity_rate":
        # 用户活跃度 = 日活用户数 / 总用户数
        dau = calculate_custom_metric(df, "daily_active_users", config)
        total_users = calculate_unique_count(df, "user_id")

        if total_users == 0:
            return 0.0

        return round(dau / total_users, 4)

    else:
        raise ValueError(f"未实现的派生指标: {metric_name}")


# ====== 辅助函数 ======

def load_metrics_config(config_path: str = "config/metrics.yaml") -> Dict[str, Any]:
    """
    加载指标配置

    Args:
        config_path: 配置文件路径

    Returns:
        指标配置字典
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def match_metric_by_keywords(keywords: List[str], config_path: str = "config/metrics.yaml") -> List[Dict[str, Any]]:
    """
    通过关键词匹配指标

    Args:
        keywords: 关键词列表
        config_path: 配置文件路径

    Returns:
        匹配的指标列表（按匹配度排序）
    """
    try:
        config = load_metrics_config(config_path)
    except FileNotFoundError:
        return []

    metrics = config.get('metrics', {})
    matched = []

    # 转换关键词为小写用于模糊匹配
    keyword_set = {kw.lower() for kw in keywords}

    for metric_id, metric_config in metrics.items():
        metric_keywords = metric_config.get('keywords', [])
        metric_name = metric_config.get('name', metric_id)

        # 计算匹配分数
        match_score = 0
        matched_keywords = []

        for kw in keyword_set:
            for mk in metric_keywords:
                if kw in mk.lower() or mk.lower() in kw:
                    match_score += 1
                    matched_keywords.append(mk)

        # 判断指标名称是否也匹配
        for kw in keyword_set:
            if kw in metric_name.lower() or metric_name.lower() in kw:
                match_score += 1

        if match_score > 0:
            matched.append({
                "id": metric_id,
                "name": metric_name,
                "description": metric_config.get('description', ''),
                "type": metric_config.get('type', ''),
                "match_score": match_score,
                "matched_keywords": matched_keywords
            })

    # 按匹配分数降序排序
    matched.sort(key=lambda x: x['match_score'], reverse=True)

    return matched


# ====== 独立函数 ======

def load_excel(path: str) -> DataAnalyzer:
    """
    快速加载Excel并返回分析器

    Args:
        path: Excel文件路径

    Returns:
        DataAnalyzer实例
    """
    analyzer = DataAnalyzer()
    analyzer.load_data(path)
    return analyzer


def query_data(analyzer: DataAnalyzer, filters: Dict[str, Any]) -> pd.DataFrame:
    """
    查询数据

    Args:
        analyzer: DataAnalyzer实例
        filters: 过滤条件

    Returns:
        筛选后的DataFrame
    """
    return analyzer.query(filters)


def aggregate_by_user(analyzer: DataAnalyzer, column: str = "user_id") -> pd.DataFrame:
    """
    按用户聚合

    Args:
        analyzer: DataAnalyzer实例
        column: 用户ID列名

    Returns:
        分组后的DataFrame
    """
    return analyzer.group_by_user(column)


def calculate_metrics(analyzer: DataAnalyzer, names: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    批量计算指标

    Args:
        analyzer: DataAnalyzer实例
        names: 指标名称列表

    Returns:
        指标计算结果字典
    """
    results = {}

    for name in names:
        try:
            results[name] = analyzer.calculate_metric(name)
        except Exception as e:
            results[name] = {
                "error": str(e),
                "name": name
            }

    return results


if __name__ == "__main__":
    # 测试代码
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("数据分析引擎测试")

    # 测试加载配置
    try:
        config = load_metrics_config()
        print(f"成功加载配置，包含 {len(config['metrics'])} 个指标")
    except FileNotFoundError:
        print("配置文件未找到")

    # 测试关键词匹配
    print("\n测试关键词匹配:")
    results = match_metric_by_keywords(["用户数", "日活"])
    for r in results:
        print(f"  - {r['name']} (匹配分数: {r['match_score']})")
