import os
import time
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class VolcengineLLM:
    """火山引擎LLM基座"""
    def __init__(self, api_key=None):
        try:
            from volcenginesdkarkruntime import Ark
            # 优先使用传入的 key；与 web_app 一致：VOLCANO_API_KEY，兼容 ARK_API_KEY
            api_key = api_key or os.getenv('VOLCANO_API_KEY') or os.getenv('ARK_API_KEY')
            
            if api_key:
                self.ark = Ark(
                    base_url='https://ark.cn-beijing.volces.com/api/v3',
                    api_key=api_key,
                )
                self.model_name = os.getenv('MODEL_NAME', 'doubao-seed-2-0-mini-260215')
                self.max_retries = 3
                print("API Key配置成功")
            else:
                # 初始化但不创建Ark实例，等待后续设置API key
                self.ark = None
                self.model_name = os.getenv('MODEL_NAME', 'doubao-seed-2-0-mini-260215')
                self.max_retries = 3
                print("等待设置API Key")
        except ImportError:
            print("未安装 volcenginesdkarkruntime，请运行: pip install 'volcengine-python-sdk[ark]'")
            self.ark = None
        except Exception as e:
            print(f"初始化LLM失败: {str(e)}")
            self.ark = None
    
    def set_api_key(self, api_key):
        """设置API Key"""
        try:
            from volcenginesdkarkruntime import Ark
            self.ark = Ark(
                base_url='https://ark.cn-beijing.volces.com/api/v3',
                api_key=api_key,
            )
            print("API Key设置成功")
            return True
        except Exception as e:
            print(f"设置API Key失败: {str(e)}")
            return False
    
    def handle_api_error(self, error, attempt):
        """智能API错误处理"""
        print(f"API错误处理 (尝试 {attempt}/3): {str(error)}")
        
        # 错误分类处理
        if "429" in str(error):
            # 速率限制，增加等待时间
            wait_time = attempt * 10
            print(f"速率限制，等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)
        elif "404" in str(error):
            # 资源不存在，可能是模型名称错误
            print("检查模型配置...")
        elif "500" in str(error):
            # 服务器错误，等待后重试
            wait_time = attempt * 5
            print(f"服务器错误，等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)
        else:
            # 其他错误，默认等待
            wait_time = attempt * 3
            print(f"未知错误，等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)
    
    def generate(self, messages):
        """调用火山引擎API生成内容"""
        if not self.ark:
            return """请先设置API Key"""
        
        for attempt in range(self.max_retries):
            try:
                print("火山引擎API调用:")
                print(f"  Model: {self.model_name}")
                
                # 转换消息格式，适应官方SDK
                input_messages = []
                for msg in messages:
                    if msg['role'] == 'system':
                        input_messages.append({
                            "role": "system",
                            "content": msg['content']
                        })
                    elif msg['role'] == 'user':
                        input_messages.append({
                            "role": "user",
                            "content": msg['content']
                        })
                
                # 使用官方SDK调用API
                response = self.ark.responses.create(
                    model=self.model_name,
                    input=input_messages
                )
                
                print("API调用成功")
                
                # 处理响应
                if hasattr(response, 'output') and len(response.output) > 0:
                    for item in response.output:
                        if hasattr(item, 'type') and item.type == 'message':
                            if hasattr(item, 'content') and len(item.content) > 0:
                                for content_item in item.content:
                                    if hasattr(content_item, 'type') and content_item.type == 'output_text':
                                        if hasattr(content_item, 'text'):
                                            return content_item.text
                
                # 尝试多种响应格式
                if hasattr(response, 'choices') and len(response.choices) > 0:
                    choice = response.choices[0]
                    if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                        return choice.message.content
                    elif hasattr(choice, 'content'):
                        return choice.content
                
                # 尝试直接从响应对象获取内容
                if hasattr(response, 'content'):
                    return response.content
                
                # 尝试获取完整响应
                import json
                try:
                    return json.dumps(response.__dict__, ensure_ascii=False)
                except:
                    pass
                
                return """未收到有效响应"""
            except Exception as e:
                print(f"API调用失败 ({attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    # 使用智能错误处理
                    self.handle_api_error(e, attempt + 1)
                else:
                    print("多次失败，返回默认响应")
                    return """API调用失败，请检查配置"""
