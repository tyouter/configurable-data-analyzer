# -*- coding: utf-8 -*-
"""
配置文件管理器 - 支持多项目配置
"""

import os
import yaml
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ProjectInfo:
    """项目信息"""
    name: str
    display_name: str
    version: str
    path: str
    exists: bool


class ConfigManager:
    """配置文件管理器，支持多项目"""

    def __init__(self, config_root: str = "config"):
        """
        初始化配置管理器

        Args:
            config_root: 配置根目录路径
        """
        self.config_root = config_root
        self._ensure_config_root()

    def _ensure_config_root(self):
        """确保配置根目录存在"""
        if not os.path.exists(self.config_root):
            os.makedirs(self.config_root, exist_ok=True)

    def create_project(self, project_name: str, display_name: str = None) -> str:
        """
        创建新项目配置目录

        Args:
            project_name: 项目名称（用于目录名）
            display_name: 项目显示名称（可选）

        Returns:
            项目路径

        Raises:
            ValueError: 项目已存在
        """
        project_path = self.get_project_path(project_name)

        if os.path.exists(project_path):
            raise ValueError(f"项目已存在: {project_name}")

        # 创建项目目录结构
        os.makedirs(os.path.join(project_path, "schemas"), exist_ok=True)

        # 创建 mapping.yaml
        mapping_data = {
            "project": {
                "name": project_name,
                "display_name": display_name or project_name,
                "version": "1.0",
                "created_at": datetime.now().isoformat()
            },
            "file_patterns": [],
            "data_signatures": [],
            "default_schema": None,
            "priority": 10
        }
        self.save_mapping(project_name, mapping_data)

        # 创建空的 metrics.yaml
        metrics_data = {"metrics": {}}
        self.save_metrics(project_name, metrics_data)

        return project_path

    def list_projects(self) -> List[ProjectInfo]:
        """
        列出所有已配置的项目

        Returns:
            项目信息列表
        """
        projects = []

        if not os.path.exists(self.config_root):
            return projects

        for item in os.listdir(self.config_root):
            project_path = os.path.join(self.config_root, item)

            # 只处理目录
            if not os.path.isdir(project_path):
                continue

            # 跳过非项目目录（如 __pycache__）
            if item.startswith('_') or item.startswith('.'):
                continue

            # 尝试加载 mapping.yaml 获取项目信息
            mapping_path = os.path.join(project_path, "mapping.yaml")
            if os.path.exists(mapping_path):
                try:
                    with open(mapping_path, 'r', encoding='utf-8') as f:
                        mapping_data = yaml.safe_load(f)
                    project_info = mapping_data.get('project', {})
                    projects.append(ProjectInfo(
                        name=item,
                        display_name=project_info.get('display_name', item),
                        version=project_info.get('version', '1.0'),
                        path=project_path,
                        exists=True
                    ))
                except Exception:
                    # 如果读取失败，使用基本目录信息
                    projects.append(ProjectInfo(
                        name=item,
                        display_name=item,
                        version="unknown",
                        path=project_path,
                        exists=True
                    ))

        return projects

    def load_project_config(self, project_name: str) -> Dict[str, Any]:
        """
        加载指定项目的完整配置

        Args:
            project_name: 项目名称

        Returns:
            包含 schema, metrics, mapping 的字典

        Raises:
            FileNotFoundError: 项目不存在
        """
        if not self.project_exists(project_name):
            raise FileNotFoundError(f"项目不存在: {project_name}")

        mapping = self.load_mapping(project_name)
        metrics = self.load_metrics(project_name)

        default_schema = mapping.get('default_schema')
        schema = None
        if default_schema:
            try:
                schema = self.load_schema(project_name, default_schema)
            except FileNotFoundError:
                schema = None

        return {
            "project_name": project_name,
            "mapping": mapping,
            "metrics": metrics,
            "schema": schema
        }

    def get_project_path(self, project_name: str) -> str:
        """
        获取项目配置路径

        Args:
            project_name: 项目名称

        Returns:
            项目配置目录路径
        """
        return os.path.join(self.config_root, project_name)

    def project_exists(self, project_name: str) -> bool:
        """
        检查项目是否存在

        Args:
            project_name: 项目名称

        Returns:
            项目是否存在
        """
        project_path = self.get_project_path(project_name)
        return os.path.isdir(project_path)

    def save_schema(self, project_name: str, schema_name: str, schema_data: dict) -> str:
        """
        保存 schema 配置文件

        Args:
            project_name: 项目名称
            schema_name: schema 名称（不含.yaml扩展名）
            schema_data: schema 配置数据

        Returns:
            保存的文件路径

        Raises:
            FileNotFoundError: 项目不存在
        """
        if not self.project_exists(project_name):
            raise FileNotFoundError(f"项目不存在: {project_name}")

        schemas_dir = os.path.join(self.get_project_path(project_name), "schemas")
        os.makedirs(schemas_dir, exist_ok=True)

        file_path = os.path.join(schemas_dir, f"{schema_name}.yaml")

        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(schema_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return file_path

    def load_schema(self, project_name: str, schema_name: str) -> dict:
        """
        加载 schema 配置文件

        Args:
            project_name: 项目名称
            schema_name: schema 名称（不含.yaml扩展名）

        Returns:
            schema 配置字典

        Raises:
            FileNotFoundError: 项目或schema不存在
        """
        schemas_dir = os.path.join(self.get_project_path(project_name), "schemas")
        file_path = os.path.join(schemas_dir, f"{schema_name}.yaml")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Schema不存在: {schema_name}")

        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def list_schemas(self, project_name: str) -> List[str]:
        """
        列出项目的所有schema

        Args:
            project_name: 项目名称

        Returns:
            schema名称列表
        """
        if not self.project_exists(project_name):
            return []

        schemas_dir = os.path.join(self.get_project_path(project_name), "schemas")

        if not os.path.exists(schemas_dir):
            return []

        schemas = []
        for item in os.listdir(schemas_dir):
            if item.endswith('.yaml'):
                schemas.append(item[:-5])  # 去掉 .yaml

        return schemas

    def save_metrics(self, project_name: str, metrics_data: dict) -> str:
        """
        保存 metrics 配置文件

        Args:
            project_name: 项目名称
            metrics_data: metrics 配置数据

        Returns:
            保存的文件路径

        Raises:
            FileNotFoundError: 项目不存在
        """
        if not self.project_exists(project_name):
            raise FileNotFoundError(f"项目不存在: {project_name}")

        file_path = os.path.join(self.get_project_path(project_name), "metrics.yaml")

        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(metrics_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return file_path

    def load_metrics(self, project_name: str) -> dict:
        """
        加载 metrics 配置文件

        Args:
            project_name: 项目名称

        Returns:
            metrics 配置字典

        Raises:
            FileNotFoundError: 项目不存在
        """
        file_path = os.path.join(self.get_project_path(project_name), "metrics.yaml")

        if not os.path.exists(file_path):
            return {"metrics": {}}

        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def save_mapping(self, project_name: str, mapping_data: dict) -> str:
        """
        保存 mapping 配置文件

        Args:
            project_name: 项目名称
            mapping_data: mapping 配置数据

        Returns:
            保存的文件路径

        Raises:
            FileNotFoundError: 项目不存在
        """
        if not self.project_exists(project_name):
            raise FileNotFoundError(f"项目不存在: {project_name}")

        file_path = os.path.join(self.get_project_path(project_name), "mapping.yaml")

        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(mapping_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return file_path

    def load_mapping(self, project_name: str) -> dict:
        """
        加载 mapping 配置文件

        Args:
            project_name: 项目名称

        Returns:
            mapping 配置字典

        Raises:
            FileNotFoundError: 项目不存在
        """
        file_path = os.path.join(self.get_project_path(project_name), "mapping.yaml")

        if not os.path.exists(file_path):
            return {
                "project": {
                    "name": project_name,
                    "display_name": project_name,
                    "version": "1.0"
                },
                "file_patterns": [],
                "data_signatures": [],
                "default_schema": None,
                "priority": 10
            }

        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def delete_project(self, project_name: str) -> bool:
        """
        删除项目配置

        Args:
            project_name: 项目名称

        Returns:
            是否删除成功

        Raises:
            ValueError: 项目不存在
        """
        if not self.project_exists(project_name):
            raise ValueError(f"项目不存在: {project_name}")

        import shutil
        project_path = self.get_project_path(project_name)
        shutil.rmtree(project_path)

        return True


if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    # 测试代码
    print("ConfigManager 测试")

    cm = ConfigManager()

    # 测试创建项目
    print("\n测试创建项目...")
    try:
        path = cm.create_project("test_project", "测试项目")
        print(f"创建成功: {path}")
    except ValueError as e:
        print(f"创建失败: {e}")

    # 测试列出项目
    print("\n列出所有项目:")
    projects = cm.list_projects()
    for p in projects:
        print(f"  - {p.name} ({p.display_name}) v{p.version}")

    # 测试加载配置
    print("\n测试加载项目配置:")
    if projects:
        first_project = projects[0].name
        config = cm.load_project_config(first_project)
        print(f"  项目: {config['project_name']}")
        print(f"  mapping 包含: {list(config['mapping'].keys())}")
        print(f"  metrics 包含: {len(config['metrics'].get('metrics', {}))} 个指标")

    # 测试 schema 操作
    print("\n测试 schema 操作:")
    test_schema = {
        "schema": {
            "name": "测试schema",
            "version": "1.0",
            "description": "测试用数据结构"
        },
        "columns": {
            "test_col": {
                "type": "string",
                "required": True,
                "description": "测试列"
            }
        }
    }

    try:
        schema_path = cm.save_schema("test_project", "test_schema", test_schema)
        print(f"保存 schema 成功: {schema_path}")

        loaded_schema = cm.load_schema("test_project", "test_schema")
        print(f"加载 schema 成功: {loaded_schema['schema']['name']}")

        schemas = cm.list_schemas("test_project")
        print(f"列出 schemas: {schemas}")
    except Exception as e:
        print(f"schema 操作失败: {e}")

    # 测试删除项目
    print("\n测试删除项目...")
    try:
        cm.delete_project("test_project")
        print("删除成功")
    except Exception as e:
        print(f"删除失败: {e}")
