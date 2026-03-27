from flask import Flask, render_template, request, jsonify, Response
import os
import sys
import time
import json
import queue
import threading
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aria_manager import ARIAManager, TaskCancelledError
from conversation_lib import ConversationLibrary
from method_lib import MethodologyLibrary

app = Flask(__name__)

# 初始化管理器
manager = ARIAManager()
methodology_manager = MethodologyLibrary()
conversation_manager = ConversationLibrary()
sse_subscribers: dict[str, list[queue.Queue]] = {}
sse_lock = threading.Lock()


def publish_workflow_event(event: dict):
    conversation_id = event.get("conversation_id", "")
    if not conversation_id:
        return
    with sse_lock:
        subscribers = list(sse_subscribers.get(conversation_id, []))
    for q in subscribers:
        try:
            q.put_nowait(event)
        except Exception:
            pass


manager.set_event_sink(publish_workflow_event)

# 大模型 API：仅从环境变量 / .env 读取（不在 Web 中保存密钥，便于开源部署）
API_KEY = os.getenv('VOLCANO_API_KEY', '') or os.getenv('ARK_API_KEY', '')


@app.route('/api/check_api_key')
def check_api_key():
    # 仅返回是否已配置，不返回任何密钥片段
    return jsonify({'has_api_key': bool(API_KEY)})

# 首页
@app.route('/')
def index():
    # 首页展示落地页；进入应用后才进入主交互界面
    return render_template('landing.html')

# 主交互页面
@app.route('/app')
def app_ui():
    return render_template('simple_index.html')

# 处理用户输入
@app.route('/api/process_input', methods=['POST'])
def process_input():
    data = request.json
    user_input = data.get('user_input')
    conversation_id = data.get('conversation_id')
    request_id = data.get('request_id', '')
    if not conversation_id:
        conversation = conversation_manager.create_conversation("新会话")
        conversation_id = conversation.get("conversation_id")
    elif not conversation_manager.get_conversation(conversation_id):
        conversation = conversation_manager.create_conversation("新会话")
        conversation_id = conversation.get("conversation_id")
    manager.set_conversation_context(conversation_id)
    manager.current_request_id = request_id or ""
    
    # 检查是否已配置 VOLCANO_API_KEY（或 ARK_API_KEY）
    if not API_KEY:
        # 生成模拟日志
        logs = [
            {
                "agent": "系统",
                "content": "未检测到 VOLCANO_API_KEY，使用模拟模式",
                "status": "warning",
                "timestamp": time.time()
            },
            {
                "agent": "TaskParser",
                "content": "正在分析你的问题",
                "status": "running",
                "timestamp": time.time() + 0.5
            },
            {
                "agent": "TaskParser",
                "content": "问题分析完成",
                "status": "completed",
                "timestamp": time.time() + 1
            },
            {
                "agent": "系统",
                "content": "请在项目根目录配置环境变量 VOLCANO_API_KEY（可复制 .env.example 为 .env）后重启服务",
                "status": "warning",
                "timestamp": time.time() + 1.5
            }
        ]
        conversation_manager.append_message(conversation_id, "user", user_input or "")
        mock_reply = '未配置 VOLCANO_API_KEY（或 ARK_API_KEY）。请复制 .env.example 为 .env 并填写密钥，或设置系统环境变量后重启 python web_app.py。'
        conversation_manager.append_message(
            conversation_id,
            "assistant",
            mock_reply,
            {"logs": logs, "workflow_events": []},
        )
        manager.set_conversation_context("")
        return jsonify({
            'result': mock_reply,
            'logs': logs,
            'workflow_events': [],
            'conversation_id': conversation_id,
            'api_key_configured': False,
            'task_id': "",
            'request_id': request_id or "",
        })
    
    agents = {}
    try:
        # 同步当前 API Key，避免应用启动后配置变更未生效
        manager.set_api_key(API_KEY)
        manager.set_conversation_context(conversation_id)
        # 清空上一次执行的日志，避免 UI 一直累积
        manager.clear_execution_log()
        manager.clear_workflow_events()
        conversation_manager.append_message(conversation_id, "user", user_input or "")

        # 轻量问候直达：寒暄类输入跳过多Agent重流程，避免响应慢且冗长
        route = manager.classify_interaction_mode(user_input or "")
        if route.get("mode") == "small_talk":
            manager.current_task_id = f"smalltalk-{int(time.time() * 1000)}"
            manager.push_event(
                "small_talk_detect",
                "success",
                "TaskParser",
                "识别为日常问候，切换轻量回复",
                {"reason": route.get("reason", ""), "source": route.get("source", "heuristic")},
            )
            manager.push_log("TaskParser", "识别为问候/闲聊，已跳过复杂流程", "completed")
            final_result = manager.generate_small_talk_reply(user_input or "")
            manager.push_event("small_talk_reply", "success", "TextExecAgent", "已生成简洁回复")
            manager.push_log("TextExecAgent", "简洁回复已发送", "completed")
            logs = manager.get_execution_log()
            workflow_events = manager.get_workflow_events()
            conversation_manager.append_message(
                conversation_id,
                "assistant",
                final_result,
                {"logs": logs, "workflow_events": workflow_events},
            )
            conversation_manager.replace_workflow_events(conversation_id, workflow_events)
            return jsonify({
                'result': final_result,
                'logs': logs,
                'workflow_events': workflow_events,
                'conversation_id': conversation_id,
                'api_key_configured': True,
                'task_id': manager.current_task_id,
                'request_id': request_id or "",
            })

        # 解析任务
        task_info = manager.parse_task(user_input)
        current_task_id = task_info.get("task_id", "")
        
        # 匹配方法论
        score, method = manager.match_methodology(task_info)
        
        # 如果匹配度低于70%，学习新方案（与 README 的相似度阈值一致）
        if score < 0.7:
            method = manager.learn_from_external(task_info)
        
        # 拆分子任务
        sub_tasks = manager.split_sub_tasks(task_info, method)
        
        # 生成Agent
        agents = manager.create_agents(sub_tasks)
        
        # 执行Agent
        results = manager.run_agents(agents)
        
        # 校验结果
        check_payload = manager.check_result(results)
        final_result = check_payload.get("final_result") if isinstance(check_payload, dict) else check_payload
        
        # 保存方法论
        manager.save_methodology(task_info, method, check_payload)
        
        # 销毁Agent
        manager.destroy_agents(agents)
        
        # 获取执行日志
        logs = manager.get_execution_log()
        workflow_events = manager.get_workflow_events()
        conversation_manager.append_message(
            conversation_id,
            "assistant",
            final_result,
            {"logs": logs, "workflow_events": workflow_events},
        )
        conversation_manager.replace_workflow_events(conversation_id, workflow_events)
        
        return jsonify({
            'result': final_result,
            'logs': logs,
            'workflow_events': workflow_events,
            'conversation_id': conversation_id,
            'api_key_configured': True,
            'task_id': current_task_id,
            'request_id': request_id or "",
        })
    except TaskCancelledError:
        cancelled_text = "任务已中止。你可以调整问题后重新发起。"
        logs = manager.get_execution_log()
        workflow_events = manager.get_workflow_events()
        conversation_manager.append_message(
            conversation_id,
            "assistant",
            cancelled_text,
            {"logs": logs, "workflow_events": workflow_events},
        )
        conversation_manager.replace_workflow_events(conversation_id, workflow_events)
        return jsonify({
            'result': cancelled_text,
            'logs': logs,
            'workflow_events': workflow_events,
            'conversation_id': conversation_id,
            'api_key_configured': True,
            'task_id': getattr(manager, "current_task_id", ""),
            'request_id': request_id or "",
            'cancelled': True,
        })
    except Exception as e:
        err = f'执行错误: {str(e)}'
        conversation_manager.append_message(conversation_id, "assistant", err, {"logs": [], "workflow_events": []})
        return jsonify({
            'result': err,
            'logs': [],
            'workflow_events': [],
            'conversation_id': conversation_id,
            'api_key_configured': True,
            'task_id': getattr(manager, "current_task_id", ""),
            'request_id': request_id or "",
        })
    finally:
        if agents:
            try:
                manager.destroy_agents(agents)
            except TaskCancelledError:
                pass
            except Exception:
                pass
        manager.set_conversation_context("")
        manager.current_task_id = ""
        manager.current_request_id = ""
        manager.clear_cancel(request_id)


@app.route('/api/cancel_task', methods=['POST'])
def cancel_task():
    data = request.json or {}
    request_id = (data.get('request_id') or '').strip()
    conversation_id = (data.get('conversation_id') or '').strip()
    if not request_id:
        return jsonify({'success': False, 'message': '缺少 request_id'}), 400

    manager.request_cancel(request_id)
    if conversation_id:
        old_conv = manager.current_conversation_id
        old_req = manager.current_request_id
        manager.set_conversation_context(conversation_id)
        manager.current_request_id = request_id
        manager.push_event(
            "task_cancelled",
            "success",
            "TaskParser",
            "用户主动中止当前任务",
            {"request_id": request_id},
        )
        manager.push_log("系统", "已接收中止指令", "warning")
        manager.set_conversation_context(old_conv)
        manager.current_request_id = old_req
    return jsonify({'success': True, 'request_id': request_id})

# 获取执行日志
@app.route('/api/get_logs')
def get_logs():
    logs = manager.get_execution_log()
    return jsonify({'logs': logs})

# 获取结构化工作流事件
@app.route('/api/workflow_events')
def get_workflow_events():
    conversation_id = request.args.get('conversation_id', '')
    if conversation_id:
        convo = conversation_manager.get_conversation(conversation_id) or {}
        return jsonify({'workflow_events': convo.get('workflow_events', [])})
    return jsonify({'workflow_events': manager.get_workflow_events()})


@app.route('/api/workflow_stream')
def workflow_stream():
    conversation_id = request.args.get('conversation_id', '')
    if not conversation_id:
        return jsonify({'success': False, 'message': 'missing conversation_id'}), 400

    q = queue.Queue(maxsize=200)
    with sse_lock:
        sse_subscribers.setdefault(conversation_id, []).append(q)

    def stream():
        try:
            # 连接建立后先发一条握手事件
            hello = {"type": "connected", "conversation_id": conversation_id, "timestamp": time.time()}
            yield f"data: {json.dumps(hello, ensure_ascii=False)}\n\n"
            while True:
                try:
                    evt = q.get(timeout=15)
                    yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    keepalive = {"type": "keepalive", "timestamp": time.time()}
                    yield f"data: {json.dumps(keepalive, ensure_ascii=False)}\n\n"
        finally:
            with sse_lock:
                subscribers = sse_subscribers.get(conversation_id, [])
                if q in subscribers:
                    subscribers.remove(q)
                if not subscribers and conversation_id in sse_subscribers:
                    sse_subscribers.pop(conversation_id, None)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return Response(stream(), mimetype='text/event-stream', headers=headers)

# 新建会话
@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    data = request.json or {}
    title = data.get('title', '新会话')
    conversation = conversation_manager.create_conversation(title)
    return jsonify({'conversation': conversation})

# 会话列表（archived可选）
@app.route('/api/conversations')
def list_conversations():
    archived = request.args.get('archived')
    archived_bool = None
    if archived in ('true', 'false'):
        archived_bool = archived == 'true'
    conversations = conversation_manager.list_conversations(archived_bool)
    return jsonify({'conversations': conversations})

# 会话详情
@app.route('/api/conversations/<conversation_id>')
def get_conversation(conversation_id):
    conversation = conversation_manager.get_conversation(conversation_id)
    if not conversation:
        return jsonify({'conversation': None, 'success': False}), 404
    return jsonify({'conversation': conversation, 'success': True})

# 归档会话（用于历史任务视图）
@app.route('/api/conversations/<conversation_id>/archive', methods=['POST'])
def archive_conversation(conversation_id):
    data = request.json or {}
    archived = bool(data.get('archived', True))
    success = conversation_manager.set_archived(conversation_id, archived)
    return jsonify({'success': success})

# 搜索方法论
@app.route('/api/search_methodology', methods=['POST'])
def search_methodology():
    data = request.json
    keyword = data.get('keyword', '')
    results = methodology_manager.search_methodologies(keyword)
    return jsonify({'results': results})

# 获取方法论列表
@app.route('/api/get_methodologies')
def get_methodologies():
    methodologies = methodology_manager.get_all_methodologies()
    return jsonify({'methodologies': methodologies})

# 删除方法论
@app.route('/api/delete_methodology', methods=['POST'])
def delete_methodology():
    data = request.json
    methodology_id = data.get('methodology_id')
    success = methodology_manager.delete_methodology(methodology_id)
    return jsonify({'success': success})

@app.route('/api/delete_methodologies_batch', methods=['POST'])
def delete_methodologies_batch():
    data = request.json or {}
    methodology_ids = data.get('methodology_ids', [])
    result = methodology_manager.delete_methodologies_batch(methodology_ids if isinstance(methodology_ids, list) else [])
    return jsonify(result)

# 更新方法论分类（同时记录人工分类反馈）
@app.route('/api/update_methodology_category', methods=['POST'])
def update_methodology_category():
    data = request.json or {}
    methodology_id = data.get('methodology_id', '')
    category = data.get('category', '')
    if not methodology_id:
        return jsonify({'success': False, 'message': '缺少methodology_id'}), 400
    updated = methodology_manager.update_methodology_category(methodology_id, category)
    return jsonify({'success': bool(updated), 'methodology': updated})

# 创建方法论
@app.route('/api/create_methodology', methods=['POST'])
def create_methodology():
    data = request.json
    scene = data.get('scene')
    keywords = data.get('keywords', [])
    solve_steps = data.get('solve_steps', [])
    methodology = methodology_manager.add_methodology(scene, keywords, solve_steps)
    return jsonify({'methodology_id': methodology['method_id']})

# 获取方法论详情
@app.route('/api/get_methodology', methods=['POST'])
def get_methodology():
    data = request.json
    methodology_id = data.get('methodology_id')
    methodology = methodology_manager.get_methodology_by_id(methodology_id)
    return jsonify({'methodology': methodology})

# 获取记忆状态
@app.route('/api/get_memory_status')
def get_memory_status():
    memory_status = {
        'short_term': {
            'task_id': manager.stm.task_id,
            'user_input': manager.stm.user_input,
            'current_step': manager.stm.current_step,
            'sub_tasks_count': len(manager.stm.sub_tasks),
            'agents_count': len(manager.stm.agent_status),
            'results_count': len(manager.stm.results),
            'logs_count': len(manager.stm.logs)
        },
        'mid_term': {
            'task_templates_count': len(manager.mtm.task_templates),
            'agent_combinations_count': len(manager.mtm.agent_combinations),
            'last_task_flow_count': len(manager.mtm.last_task_flow),
            'common_prompts_count': len(manager.mtm.common_prompts)
        },
        'long_term': {
            'methodologies_count': len(manager.ltm.methodologies),
            'best_cases_count': len(manager.ltm.best_cases),
            'knowledge_base_count': len(manager.ltm.knowledge_base)
        }
    }
    return jsonify({'memory_status': memory_status})

if __name__ == '__main__':
    # 创建templates目录
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # 启动应用
    app.run(debug=True, host='0.0.0.0', port=5000)