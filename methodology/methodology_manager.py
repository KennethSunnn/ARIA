import os
import sys
import json
from datetime import datetime
import hashlib

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class MethodologyManager:
    """方法论库模块"""
    def __init__(self):
        self.methodology_dir = os.path.join("data", "methodology")
        os.makedirs(self.methodology_dir, exist_ok=True)
        self.methodology_file = os.path.join(self.methodology_dir, "methodologies.json")
        self.methodologies = self.load_methodologies()
    
    def load_methodologies(self):
        """加载方法论库"""
        if os.path.exists(self.methodology_file):
            try:
                with open(self.methodology_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载方法论库失败: {e}")
                return []
        else:
            return []
    
    def save_methodologies(self):
        """保存方法论库"""
        try:
            with open(self.methodology_file, 'w', encoding='utf-8') as f:
                json.dump(self.methodologies, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存方法论库失败: {e}")
            return False
    
    def generate_methodology_id(self, methodology_info):
        """生成方法论ID（使用雪花算法思想）"""
        # 简单的ID生成方法，实际应用中可以使用更复杂的雪花算法
        timestamp = str(int(datetime.now().timestamp() * 1000))
        content_hash = hashlib.md5(str(methodology_info).encode()).hexdigest()[:8]
        return f"methodology_{timestamp}_{content_hash}"
    
    def add_methodology(self, methodology_info: dict) -> str:
        """新增方法论：外网学习后自动存入，包含相似度检测和去重"""
        # 检查是否存在相似方法论
        similar_method = self.find_similar_methodology(methodology_info)
        if similar_method:
            # 相似度≥70%，更新已有方法论
            self.update_methodology(similar_method["methodology_id"], methodology_info)
            return similar_method["methodology_id"]
        
        # 不存在相似方法论，创建新的
        # 生成方法论ID
        methodology_id = self.generate_methodology_id(methodology_info)
        
        # 构建方法论数据结构
        methodology = {
            "methodology_id": methodology_id,
            "name": methodology_info.get("name", ""),
            "scenario": methodology_info.get("scenario", ""),
            "category": methodology_info.get("category", ""),
            "tags": methodology_info.get("tags", []),
            "description": methodology_info.get("description", ""),
            "cover_image": methodology_info.get("cover_image", ""),
            "core_keywords": methodology_info.get("core_keywords", []),
            "solve_steps": methodology_info.get("solve_steps", []),
            "applicable_range": methodology_info.get("applicable_range", ""),
            "content_template": methodology_info.get("content_template", ""),
            "status": methodology_info.get("status", "published"),  # draft/published
            "success_count": 0,
            "usage_count": 0,
            "is_favorite": False,
            "last_optimize_time": datetime.now().isoformat(),
            "last_update_time": datetime.now().isoformat(),
            "create_time": datetime.now().isoformat(),
            "version": "1.0"
        }
        
        # 添加到方法论库
        self.methodologies.append(methodology)
        
        # 保存到文件
        self.save_methodologies()
        
        return methodology_id
    
    def find_similar_methodology(self, new_methodology_info):
        """查找相似方法论，相似度≥70%返回对应方法论"""
        new_keywords = set(new_methodology_info.get("core_keywords", []))
        new_scenario = new_methodology_info.get("scenario", "")
        
        for method in self.methodologies:
            # 计算场景相似度
            scenario_score = 1.0 if method.get("scenario") == new_scenario else 0.5
            
            # 计算关键词相似度
            method_keywords = set(method.get("core_keywords", []))
            intersection = len(new_keywords & method_keywords)
            union = len(new_keywords | method_keywords)
            keyword_score = intersection / union if union > 0 else 0.0
            
            # 综合相似度
            similarity = scenario_score * 0.6 + keyword_score * 0.4
            
            if similarity >= 0.7:
                return method
        return None
    
    def create_methodology(self, methodology_data: dict) -> str:
        """创建方法论：支持自定义填写所有字段，支持保存为草稿或直接发布，包含相似度检测和去重"""
        # 检查是否存在相似方法论
        similar_method = self.find_similar_methodology(methodology_data)
        if similar_method:
            # 相似度≥70%，更新已有方法论
            self.update_methodology(similar_method["methodology_id"], methodology_data)
            return similar_method["methodology_id"]
        
        # 不存在相似方法论，创建新的
        # 生成方法论ID
        methodology_id = self.generate_methodology_id(methodology_data)
        
        # 构建方法论数据结构
        methodology = {
            "methodology_id": methodology_id,
            "name": methodology_data.get("name", ""),
            "category": methodology_data.get("category", ""),
            "tags": methodology_data.get("tags", []),
            "description": methodology_data.get("description", ""),
            "cover_image": methodology_data.get("cover_image", ""),
            "content_template": methodology_data.get("content_template", ""),
            "core_keywords": methodology_data.get("core_keywords", []),
            "solve_steps": methodology_data.get("solve_steps", []),
            "applicable_range": methodology_data.get("applicable_range", ""),
            "status": methodology_data.get("status", "draft"),  # draft/published
            "success_count": 0,
            "usage_count": 0,
            "is_favorite": False,
            "last_optimize_time": datetime.now().isoformat(),
            "last_update_time": datetime.now().isoformat(),
            "create_time": datetime.now().isoformat(),
            "version": "1.0"
        }
        
        # 添加到方法论库
        self.methodologies.append(methodology)
        
        # 保存到文件
        self.save_methodologies()
        
        return methodology_id
    
    def match_methodology(self, requirement_info: dict) -> tuple[float, dict]:
        """相似度匹配：基于需求场景和关键词，匹配最相关的方法论"""
        # 轻量化实现：采用TF-IDF+余弦相似度
        import math
        
        if not self.methodologies:
            return 0.0, {}
        
        # 提取需求的关键词
        requirement_keywords = set(requirement_info.get("core_keywords", []))
        requirement_scenario = requirement_info.get("scenario", "")
        
        best_match_score = 0.0
        best_match_methodology = {}
        
        # 优化：提前计算需求关键词的长度，避免重复计算
        req_keywords_len = len(requirement_keywords)
        
        for methodology in self.methodologies:
            # 计算场景匹配得分
            scenario_score = 1.0 if methodology.get("scenario") == requirement_scenario else 0.5
            
            # 计算关键词匹配得分
            methodology_keywords = set(methodology.get("core_keywords", []))
            # 优化：使用集合的内置方法，比手动计算更高效
            intersection = len(requirement_keywords & methodology_keywords)
            union = req_keywords_len + len(methodology_keywords) - intersection
            keyword_score = intersection / union if union > 0 else 0.0
            
            # 计算综合得分
            match_score = scenario_score * 0.6 + keyword_score * 0.4
            match_score = match_score * 100  # 转换为百分比
            
            # 考虑成功次数的权重
            success_count = methodology.get("success_count", 0)
            success_bonus = min(success_count * 0.5, 20)  # 最多20分的奖励
            final_score = match_score + success_bonus
            
            # 更新最佳匹配
            if final_score > best_match_score:
                best_match_score = final_score
                best_match_methodology = methodology
        
        return best_match_score, best_match_methodology
    
    def optimize_methodology(self, methodology_id: str, execution_result: dict) -> bool:
        """方法论优化：任务执行完成后，基于执行结果优化步骤"""
        # 查找方法论
        for methodology in self.methodologies:
            if methodology.get("methodology_id") == methodology_id:
                # 更新成功次数
                methodology["success_count"] += 1
                
                # 更新最后优化时间
                methodology["last_optimize_time"] = datetime.now().isoformat()
                
                # 简单的优化逻辑，实际应用中可以根据执行结果进行更复杂的优化
                # 例如，根据执行结果调整解决步骤的顺序或内容
                
                # 保存到文件
                self.save_methodologies()
                return True
        
        return False
    
    def get_methodology_list(self, page: int = 1, page_size: int = 10) -> list:
        """方法论管理：查询/删除/列表展示"""
        # 按成功次数倒序排序
        sorted_methodologies = sorted(
            self.methodologies, 
            key=lambda x: x.get("success_count", 0), 
            reverse=True
        )
        
        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        return sorted_methodologies[start:end]
    
    def delete_methodology(self, methodology_id: str, confirm: bool = False) -> bool:
        """删除方法论（支持二次确认）"""
        # 二次确认检查
        if not confirm:
            # 实际应用中这里应该返回需要确认的信息
            return False
        
        # 查找并删除方法论
        for i, methodology in enumerate(self.methodologies):
            if methodology.get("methodology_id") == methodology_id:
                del self.methodologies[i]
                # 保存到文件
                self.save_methodologies()
                return True
        
        return False
    
    def update_methodology(self, methodology_id: str, update_data: dict) -> bool:
        """编辑已有方法论"""
        for methodology in self.methodologies:
            if methodology.get("methodology_id") == methodology_id:
                # 更新字段
                for key, value in update_data.items():
                    methodology[key] = value
                
                # 更新最后更新时间
                methodology["last_update_time"] = datetime.now().isoformat()
                
                # 保存到文件
                self.save_methodologies()
                return True
        
        return False
    
    def batch_delete_methodologies(self, methodology_ids: list, confirm: bool = False) -> int:
        """批量删除方法论"""
        if not confirm:
            return 0
        
        deleted_count = 0
        # 反向遍历，避免索引问题
        for i in range(len(self.methodologies) - 1, -1, -1):
            if self.methodologies[i].get("methodology_id") in methodology_ids:
                del self.methodologies[i]
                deleted_count += 1
        
        if deleted_count > 0:
            # 保存到文件
            self.save_methodologies()
        
        return deleted_count
    
    def batch_operate_methodologies(self, methodology_ids: list, operation: str, value: any = None) -> int:
        """批量操作方法论"""
        operated_count = 0
        
        for methodology in self.methodologies:
            if methodology.get("methodology_id") in methodology_ids:
                if operation == "publish":
                    methodology["status"] = "published"
                elif operation == "draft":
                    methodology["status"] = "draft"
                elif operation == "favorite":
                    methodology["is_favorite"] = True
                elif operation == "unfavorite":
                    methodology["is_favorite"] = False
                elif operation == "update_category" and value:
                    methodology["category"] = value
                
                methodology["last_update_time"] = datetime.now().isoformat()
                operated_count += 1
        
        if operated_count > 0:
            # 保存到文件
            self.save_methodologies()
        
        return operated_count
    
    def get_methodology_by_id(self, methodology_id: str) -> dict:
        """根据ID获取方法论"""
        for methodology in self.methodologies:
            if methodology.get("methodology_id") == methodology_id:
                return methodology
        return {}
    
    def search_methodology(self, keyword: str) -> list:
        """根据关键词搜索方法论"""
        results = []
        for methodology in self.methodologies:
            if keyword in methodology.get("scenario", "") or \
               any(keyword in kw for kw in methodology.get("core_keywords", [])) or \
               keyword in methodology.get("applicable_range", ""):
                results.append(methodology)
        return results
    
    def search_and_filter_methodologies(self, keyword: str = "", category: str = "", tags: list = None, sort_by: str = "usage_count", page: int = 1, page_size: int = 20) -> tuple[list, int]:
        """搜索和筛选方法论：支持关键词全文搜索、多维度组合筛选和自定义排序"""
        if tags is None:
            tags = []
        
        # 筛选方法论
        filtered_methodologies = []
        for methodology in self.methodologies:
            # 关键词搜索
            if keyword:
                keyword_match = False
                search_fields = ["name", "description", "scenario", "category", "applicable_range"]
                for field in search_fields:
                    if keyword in str(methodology.get(field, "")):
                        keyword_match = True
                        break
                # 搜索标签
                for tag in methodology.get("tags", []):
                    if keyword in tag:
                        keyword_match = True
                        break
                # 搜索核心关键词
                for kw in methodology.get("core_keywords", []):
                    if keyword in kw:
                        keyword_match = True
                        break
                if not keyword_match:
                    continue
            
            # 分类筛选
            if category and methodology.get("category") != category:
                continue
            
            # 标签筛选
            if tags:
                methodology_tags = set(methodology.get("tags", []))
                if not methodology_tags.intersection(set(tags)):
                    continue
            
            filtered_methodologies.append(methodology)
        
        # 排序
        sort_key = None
        if sort_by == "usage_count":
            sort_key = lambda x: x.get("usage_count", 0)
        elif sort_by == "update_time":
            sort_key = lambda x: x.get("last_update_time", "")
        elif sort_by == "name":
            sort_key = lambda x: x.get("name", "")
        elif sort_by == "create_time":
            sort_key = lambda x: x.get("create_time", "")
        
        if sort_key:
            filtered_methodologies.sort(key=sort_key, reverse=(sort_by != "name"))
        
        # 分页
        total = len(filtered_methodologies)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_result = filtered_methodologies[start:end]
        
        return paginated_result, total
    
    def reference_methodology(self, methodology_id: str, project_id: str = "") -> dict:
        """引用方法论到当前项目"""
        for methodology in self.methodologies:
            if methodology.get("methodology_id") == methodology_id:
                # 增加使用次数
                methodology["usage_count"] = methodology.get("usage_count", 0) + 1
                methodology["last_update_time"] = datetime.now().isoformat()
                
                # 保存到文件
                self.save_methodologies()
                
                # 返回方法论内容，供项目使用
                return {
                    "methodology_id": methodology_id,
                    "name": methodology.get("name"),
                    "content_template": methodology.get("content_template"),
                    "solve_steps": methodology.get("solve_steps"),
                    "core_keywords": methodology.get("core_keywords")
                }
        return {}
    
    def export_methodology(self, methodology_id: str, export_format: str = "markdown") -> str:
        """导出方法论为PDF/Markdown格式"""
        for methodology in self.methodologies:
            if methodology.get("methodology_id") == methodology_id:
                if export_format == "markdown":
                    # 生成Markdown格式
                    markdown_content = f"# {methodology.get('name', '方法论')}\n\n"
                    markdown_content += f"## 分类\n{methodology.get('category', '未分类')}\n\n"
                    markdown_content += f"## 标签\n{', '.join(methodology.get('tags', []))}\n\n"
                    markdown_content += f"## 描述\n{methodology.get('description', '无描述')}\n\n"
                    markdown_content += f"## 适用范围\n{methodology.get('applicable_range', '无')}\n\n"
                    markdown_content += "## 解决步骤\n"
                    for i, step in enumerate(methodology.get('solve_steps', []), 1):
                        markdown_content += f"{i}. {step}\n"
                    markdown_content += "\n"
                    markdown_content += f"## 核心关键词\n{', '.join(methodology.get('core_keywords', []))}\n\n"
                    markdown_content += f"## 使用次数\n{methodology.get('usage_count', 0)}次\n\n"
                    markdown_content += f"## 创建时间\n{methodology.get('create_time', '')}\n"
                    
                    # 保存到文件
                    export_dir = os.path.join(self.methodology_dir, "exports")
                    os.makedirs(export_dir, exist_ok=True)
                    export_file = os.path.join(export_dir, f"{methodology.get('name', 'methodology')}.md")
                    
                    with open(export_file, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    
                    return export_file
                # 后续可以添加PDF格式导出
                return ""
        return ""
    
    def toggle_favorite(self, methodology_id: str) -> bool:
        """切换方法论收藏状态"""
        for methodology in self.methodologies:
            if methodology.get("methodology_id") == methodology_id:
                methodology["is_favorite"] = not methodology.get("is_favorite", False)
                methodology["last_update_time"] = datetime.now().isoformat()
                
                # 保存到文件
                self.save_methodologies()
                return True
        return False
    
    def get_favorite_methodologies(self) -> list:
        """获取收藏的方法论"""
        return [m for m in self.methodologies if m.get("is_favorite", False)]
    
    def import_methodologies(self, file_path: str) -> int:
        """导入方法论模板（支持JSON/CSV格式）"""
        imported_count = 0
        
        try:
            if file_path.endswith('.json'):
                # 导入JSON格式
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported_data = json.load(f)
                
                if isinstance(imported_data, list):
                    for item in imported_data:
                        # 生成新的ID，避免冲突
                        item.pop('methodology_id', None)
                        item.pop('create_time', None)
                        item.pop('last_update_time', None)
                        item.pop('last_optimize_time', None)
                        item.pop('success_count', None)
                        item.pop('usage_count', None)
                        item.pop('is_favorite', None)
                        item.pop('version', None)
                        
                        # 创建新的方法论
                        self.create_methodology(item)
                        imported_count += 1
            elif file_path.endswith('.csv'):
                # 导入CSV格式
                import csv
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # 处理CSV数据
                        methodology_data = {
                            "name": row.get('name', ''),
                            "category": row.get('category', ''),
                            "tags": [tag.strip() for tag in row.get('tags', '').split(',') if tag.strip()],
                            "description": row.get('description', ''),
                            "content_template": row.get('content_template', ''),
                            "core_keywords": [kw.strip() for kw in row.get('core_keywords', '').split(',') if kw.strip()],
                            "solve_steps": [step.strip() for step in row.get('solve_steps', '').split('|') if step.strip()],
                            "applicable_range": row.get('applicable_range', ''),
                            "status": row.get('status', 'draft')
                        }
                        
                        self.create_methodology(methodology_data)
                        imported_count += 1
        except Exception as e:
            print(f"导入方法论失败: {e}")
        
        return imported_count
    
    def export_methodologies(self, export_format: str = "json", filters: dict = None) -> str:
        """批量导出方法论"""
        if filters is None:
            filters = {}
        
        # 筛选要导出的方法论
        export_methodologies = []
        for methodology in self.methodologies:
            # 应用筛选条件
            if filters.get('category') and methodology.get('category') != filters['category']:
                continue
            if filters.get('status') and methodology.get('status') != filters['status']:
                continue
            if filters.get('is_favorite') and not methodology.get('is_favorite', False):
                continue
            
            export_methodologies.append(methodology)
        
        # 生成导出文件
        export_dir = os.path.join(self.methodology_dir, "exports")
        os.makedirs(export_dir, exist_ok=True)
        
        if export_format == "json":
            export_file = os.path.join(export_dir, f"methodologies_export_{int(datetime.now().timestamp())}.json")
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_methodologies, f, ensure_ascii=False, indent=2)
        elif export_format == "csv":
            export_file = os.path.join(export_dir, f"methodologies_export_{int(datetime.now().timestamp())}.csv")
            import csv
            if export_methodologies:
                # 获取所有字段
                fieldnames = list(export_methodologies[0].keys())
                with open(export_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for methodology in export_methodologies:
                        writer.writerow(methodology)
        else:
            return ""
        
        return export_file

if __name__ == "__main__":
    # 测试MethodologyManager
    manager = MethodologyManager()
    
    # 添加测试方法论
    test_methodology = {
        "scenario": "代码开发",
        "core_keywords": ["Python", "爬虫", "requests", "BeautifulSoup"],
        "solve_steps": [
            "安装必要的库：pip install requests beautifulsoup4",
            "导入库：import requests, from bs4 import BeautifulSoup",
            "发送HTTP请求获取页面内容",
            "使用BeautifulSoup解析页面",
            "提取所需数据",
            "保存数据到文件或数据库"
        ],
        "applicable_range": "适用于简单的静态网页数据抓取"
    }
    
    methodology_id = manager.add_methodology(test_methodology)
    print(f"添加方法论成功，ID: {methodology_id}")
    
    # 测试匹配
    test_requirement = {
        "scenario": "代码开发",
        "core_keywords": ["Python", "爬虫", "数据抓取"]
    }
    
    match_score, matched_methodology = manager.match_methodology(test_requirement)
    print(f"匹配结果：匹配度={match_score}%，方法论ID={matched_methodology.get('methodology_id', 'N/A')}")
    
    # 测试优化
    test_execution_result = {
        "success": True,
        "execution_time": "10s",
        "output": "成功抓取数据"
    }
    
    optimize_success = manager.optimize_methodology(methodology_id, test_execution_result)
    print(f"优化方法论：{optimize_success}")
    
    # 测试列表
    methodologies = manager.get_methodology_list()
    print(f"方法论列表：{len(methodologies)}个")
    for methodology in methodologies:
        print(f"- {methodology['scenario']} (成功次数: {methodology['success_count']})")
