import os
import json
from datetime import datetime

class AgentMemory:
    """智能体记忆存储"""
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.save_path = os.path.join("memory", agent_id)
        os.makedirs(self.save_path, exist_ok=True)
        
        # 初始化存储文件
        self.files = {
            "task_history": os.path.join(self.save_path, "task_history.json"),
            "reflections": os.path.join(self.save_path, "reflections.json"),
            "learning_history": os.path.join(self.save_path, "learning_history.json"),
            "communication_history": os.path.join(self.save_path, "communication_history.json"),
            "skill_tree": os.path.join(self.save_path, "skill_tree.json")
        }
        
        # 加载或初始化数据
        self.task_history = self._load_json(self.files["task_history"], [])
        self.reflections = self._load_json(self.files["reflections"], [])
        self.learning_history = self._load_json(self.files["learning_history"], [])
        self.communication_history = self._load_json(self.files["communication_history"], [])
        self.skill_tree = self._load_json(self.files["skill_tree"], {})
    
    def _load_json(self, file_path, default):
        """加载JSON文件"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ 加载文件失败 {file_path}: {str(e)}")
        return default
    
    def _save_json(self, file_path, data):
        """保存JSON文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"⚠️ 保存文件失败 {file_path}: {str(e)}")
            return False
    
    def add_task_history(self, task, result, timestamp=None):
        """添加任务执行历史"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        entry = {
            "task": task,
            "result": result,
            "timestamp": timestamp
        }
        self.task_history.append(entry)
        # 只保留最近100条记录
        if len(self.task_history) > 100:
            self.task_history = self.task_history[-100:]
        self._save_json(self.files["task_history"], self.task_history)
    
    def add_reflection(self, task, reflection, timestamp=None):
        """添加反思结果"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        entry = {
            "task": task,
            "reflection": reflection,
            "timestamp": timestamp
        }
        self.reflections.append(entry)
        # 只保留最近100条记录
        if len(self.reflections) > 100:
            self.reflections = self.reflections[-100:]
        self._save_json(self.files["reflections"], self.reflections)
    
    def add_learning_history(self, topic, task, result, timestamp=None):
        """添加学习历史记录"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        entry = {
            "topic": topic,
            "task": task,
            "result": result,
            "timestamp": timestamp
        }
        self.learning_history.append(entry)
        # 只保留最近100条记录
        if len(self.learning_history) > 100:
            self.learning_history = self.learning_history[-100:]
        self._save_json(self.files["learning_history"], self.learning_history)
    
    def save_learning_progress(self, learning_plan, progress, status):
        """保存学习进度（断点续存）"""
        progress_data = {
            "learning_plan": learning_plan,
            "progress": progress,
            "status": status,
            "last_updated": datetime.now().isoformat()
        }
        progress_file = os.path.join(self.save_path, "learning_progress.json")
        return self._save_json(progress_file, progress_data)
    
    def get_learning_progress(self):
        """获取学习进度"""
        progress_file = os.path.join(self.save_path, "learning_progress.json")
        return self._load_json(progress_file, {})
    
    def add_experience(self, experience, type="task", timestamp=None):
        """存储经验"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        entry = {
            "experience": experience,
            "type": type,  # task, learning, communication
            "timestamp": timestamp
        }
        # 经验存储在reflections文件中
        self.reflections.append(entry)
        # 只保留最近100条记录
        if len(self.reflections) > 100:
            self.reflections = self.reflections[-100:]
        self._save_json(self.files["reflections"], self.reflections)
    
    def review_task_history(self):
        """历史任务复盘"""
        if not self.task_history:
            return "暂无任务历史"
        
        review = f"任务历史复盘报告：\n\n"
        review += f"总任务数：{len(self.task_history)}\n"
        review += f"最近任务：{self.task_history[-1]['task'][:50]}...\n\n"
        
        # 分析任务类型
        task_types = {}
        for task in self.task_history:
            task_lower = task['task'].lower()
            if '代码' in task_lower or '编程' in task_lower:
                task_types['编程'] = task_types.get('编程', 0) + 1
            elif '文案' in task_lower or '写作' in task_lower:
                task_types['文案'] = task_types.get('文案', 0) + 1
            elif '设计' in task_lower or 'UI' in task_lower:
                task_types['设计'] = task_types.get('设计', 0) + 1
            else:
                task_types['其他'] = task_types.get('其他', 0) + 1
        
        review += "任务类型分布：\n"
        for task_type, count in task_types.items():
            review += f"- {task_type}: {count}个\n"
        
        return review
    
    def manage_skill_tree(self, action, skill=None, level=None):
        """技能树管理"""
        if action == "get":
            return self.skill_tree
        elif action == "update":
            if skill and level:
                # 找到并更新技能等级
                for category, skills in self.skill_tree.items():
                    for s in skills:
                        if s['name'] == skill:
                            s['level'] = level
                            self._save_json(self.files["skill_tree"], self.skill_tree)
                            return f"技能 {skill} 等级已更新为 {level}"
                return f"技能 {skill} 不存在"
            else:
                return "请提供技能名称和等级"
        elif action == "unlock":
            if skill:
                # 解锁技能
                for category, skills in self.skill_tree.items():
                    for s in skills:
                        if s['name'] == skill:
                            s['unlocked'] = True
                            self._save_json(self.files["skill_tree"], self.skill_tree)
                            return f"技能 {skill} 已解锁"
                return f"技能 {skill} 不存在"
            else:
                return "请提供技能名称"
        else:
            return "不支持的操作"
    
    def add_communication(self, sender_id, recipient_id, message, type="message", timestamp=None):
        """添加通信记录"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        entry = {
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "message": message,
            "type": type,  # message, help_request, result_report
            "timestamp": timestamp
        }
        self.communication_history.append(entry)
        # 只保留最近100条记录
        if len(self.communication_history) > 100:
            self.communication_history = self.communication_history[-100:]
        self._save_json(self.files["communication_history"], self.communication_history)
    
    def update_skill_tree(self, skill_tree):
        """更新技能树"""
        self.skill_tree = skill_tree
        self._save_json(self.files["skill_tree"], self.skill_tree)
    
    def get_task_history(self):
        """获取任务历史"""
        return self.task_history
    
    def get_reflections(self):
        """获取反思记录"""
        return self.reflections
    
    def get_learning_history(self):
        """获取学习历史"""
        return self.learning_history
    
    def get_communication_history(self):
        """获取通信历史"""
        return self.communication_history
    
    def get_skill_tree(self):
        """获取技能树"""
        return self.skill_tree
    
    def search_memory(self, query, category=None):
        """智能搜索记忆"""
        results = []
        
        # 搜索任务历史
        if category is None or category == 'task':
            for entry in self.task_history:
                if self._matches_search(entry, query):
                    results.append({'type': 'task', 'entry': entry})
        
        # 搜索反思记录
        if category is None or category == 'reflection':
            for entry in self.reflections:
                if self._matches_search(entry, query):
                    results.append({'type': 'reflection', 'entry': entry})
        
        # 搜索学习历史
        if category is None or category == 'learning':
            for entry in self.learning_history:
                if self._matches_search(entry, query):
                    results.append({'type': 'learning', 'entry': entry})
        
        # 按相关性排序
        results.sort(key=lambda x: self._calculate_relevance(x, query), reverse=True)
        
        return results
    
    def _matches_search(self, entry, query):
        """检查条目是否匹配搜索条件"""
        if query:
            query_lower = query.lower()
            for key, value in entry.items():
                if isinstance(value, str) and query_lower in value.lower():
                    return True
                elif isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, str) and query_lower in sub_value.lower():
                            return True
        return False
    
    def _calculate_relevance(self, result, query):
        """计算结果与查询的相关性"""
        relevance = 0
        entry = result['entry']
        query_lower = query.lower() if query else ''
        
        for key, value in entry.items():
            if isinstance(value, str):
                relevance += value.lower().count(query_lower)
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, str):
                        relevance += sub_value.lower().count(query_lower)
        
        return relevance
    
    def clean_memory(self):
        """清理和去重记忆"""
        # 去重任务历史
        seen_tasks = set()
        unique_tasks = []
        for task in self.task_history:
            task_key = task['task'] + task['result'][:100]
            if task_key not in seen_tasks:
                seen_tasks.add(task_key)
                unique_tasks.append(task)
        self.task_history = unique_tasks[-100:]
        
        # 去重反思记录
        seen_reflections = set()
        unique_reflections = []
        for reflection in self.reflections:
            reflection_key = reflection['task'] + reflection['reflection'][:100]
            if reflection_key not in seen_reflections:
                seen_reflections.add(reflection_key)
                unique_reflections.append(reflection)
        self.reflections = unique_reflections[-100:]
        
        # 去重学习历史
        seen_learning = set()
        unique_learning = []
        for learning in self.learning_history:
            learning_key = learning['topic'] + str(learning['task'])[:100]
            if learning_key not in seen_learning:
                seen_learning.add(learning_key)
                unique_learning.append(learning)
        self.learning_history = unique_learning[-100:]
        
        # 去重通信历史
        seen_communication = set()
        unique_communication = []
        for communication in self.communication_history:
            comm_key = communication['sender_id'] + communication['recipient_id'] + communication['message'][:100]
            if comm_key not in seen_communication:
                seen_communication.add(comm_key)
                unique_communication.append(communication)
        self.communication_history = unique_communication[-100:]
        
        # 保存清理后的记忆
        self._save_json(self.files["task_history"], self.task_history)
        self._save_json(self.files["reflections"], self.reflections)
        self._save_json(self.files["learning_history"], self.learning_history)
        self._save_json(self.files["communication_history"], self.communication_history)
        
        return f"记忆清理完成，清理后任务历史: {len(self.task_history)}，反思记录: {len(self.reflections)}，学习历史: {len(self.learning_history)}，通信历史: {len(self.communication_history)}"
