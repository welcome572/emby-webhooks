from flask import Flask, request, jsonify
import json
import logging
import sys
import threading
import requests
import os
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

_executor = ThreadPoolExecutor(max_workers=3)

def get_config():
    """直接从环境变量获取配置"""
    return {
        'telegram_token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
        'telegram_chat_id': os.getenv('TELEGRAM_CHAT_ID', ''),
        'proxy_url': os.getenv('PROXY_URL', 'http://admin:wang105220@192.168.1.102:7890')
    }

def send_telegram_direct(message):
    """使用直接 HTTP API 发送 Telegram 消息"""
    try:
        config = get_config()
        
        if not config['telegram_token'] or not config['telegram_chat_id']:
            logger.warning("Telegram 配置不完整")
            return False
        
        # 简化消息内容
        if len(message) > 1000:
            message = message[:1000] + "..."
        
        # 准备代理配置
        proxies = {
            'http': config['proxy_url'],
            'https': config['proxy_url']
        }
        
        # Telegram Bot API URL
        url = f"https://api.telegram.org/bot{config['telegram_token']}/sendMessage"
        
        # 请求数据
        data = {
            'chat_id': config['telegram_chat_id'],
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        logger.info(f"发送 Telegram 消息，长度: {len(message)}")
        
        # 发送请求
        response = requests.post(
            url,
            data=data,
            proxies=proxies,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                logger.info(f"✅ Telegram 消息发送成功！消息ID: {result['result']['message_id']}")
                return True
            else:
                logger.error(f"Telegram API 错误: {result.get('description')}")
                return False
        else:
            logger.error(f"HTTP 错误: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.warning("⚠️ Telegram 发送超时")
        return False
    except Exception as e:
        logger.error(f"❌ Telegram 发送失败: {e}")
        return False

def send_telegram_async(message):
    """异步发送 Telegram 消息"""
    if not message:
        return
    
    def _send():
        try:
            success = send_telegram_direct(message)
            logger.info(f"异步发送结果: {success}")
        except Exception as e:
            logger.error(f"异步发送异常: {e}")
    
    _executor.submit(_send)

def generate_simple_message(data):
    """生成友好的消息格式 - 支持所有 Emby 事件类型"""
    event_type = data.get("Event", "Unknown")
    item = data.get("Item", {})
    user = data.get("User", {})
    server = data.get("Server", {})
    
    item_name = item.get("Name", "Unknown")
    item_type = item.get("Type", "Unknown")
    user_name = user.get("Name", "Unknown")
    server_name = server.get("Name", "Emby Server")
    
    # 根据事件类型生成不同的消息
    if event_type == "library.new":
        if item_type == "Movie":
            year = item.get("ProductionYear", "")
            year_str = f" ({year})" if year else ""
            return f"🎬 <b>新电影添加</b>\n\n{item_name}{year_str}\n🏠 {server_name}"
        elif item_type == "Episode":
            series_name = item.get("SeriesName", "Unknown")
            season = item.get("ParentIndexNumber", "")
            episode = item.get("IndexNumber", "")
            return f"📺 <b>新剧集更新</b>\n\n{series_name}\nS{season}E{episode} - {item_name}\n🏠 {server_name}"
        else:
            return f"📦 <b>新内容添加</b>\n\n{item_name} ({item_type})\n🏠 {server_name}"
    
    # 播放相关事件
    elif event_type == "playback.start":
        if item_type == "Movie":
            return f"▶️ <b>开始播放电影</b>\n\n{item_name}\n👤 {user_name}\n🏠 {server_name}"
        elif item_type == "Episode":
            series_name = item.get("SeriesName", "Unknown")
            return f"▶️ <b>开始播放剧集</b>\n\n{series_name} - {item_name}\n👤 {user_name}\n🏠 {server_name}"
        else:
            return f"▶️ <b>开始播放</b>\n\n{item_name}\n👤 {user_name}\n🏠 {server_name}"
    
    elif event_type == "playback.unpause":
        if item_type == "Movie":
            return f"⏯️ <b>恢复播放电影</b>\n\n{item_name}\n👤 {user_name}\n🏠 {server_name}"
        elif item_type == "Episode":
            series_name = item.get("SeriesName", "Unknown")
            return f"⏯️ <b>恢复播放剧集</b>\n\n{series_name} - {item_name}\n👤 {user_name}\n🏠 {server_name}"
        else:
            return f"⏯️ <b>恢复播放</b>\n\n{item_name}\n👤 {user_name}\n🏠 {server_name}"
    
    elif event_type == "playback.pause":
        if item_type == "Movie":
            return f"⏸️ <b>暂停播放电影</b>\n\n{item_name}\n👤 {user_name}\n🏠 {server_name}"
        elif item_type == "Episode":
            series_name = item.get("SeriesName", "Unknown")
            return f"⏸️ <b>暂停播放剧集</b>\n\n{series_name} - {item_name}\n👤 {user_name}\n🏠 {server_name}"
        else:
            return f"⏸️ <b>暂停播放</b>\n\n{item_name}\n👤 {user_name}\n🏠 {server_name}"
    
    elif event_type == "playback.stop":
        if item_type == "Movie":
            return f"⏹️ <b>停止播放电影</b>\n\n{item_name}\n👤 {user_name}\n🏠 {server_name}"
        elif item_type == "Episode":
            series_name = item.get("SeriesName", "Unknown")
            return f"⏹️ <b>停止播放剧集</b>\n\n{series_name} - {item_name}\n👤 {user_name}\n🏠 {server_name}"
        else:
            return f"⏹️ <b>停止播放</b>\n\n{item_name}\n👤 {user_name}\n🏠 {server_name}"
    
    # 用户相关事件
    elif event_type == "user.authenticated":
        return f"🔐 <b>用户登录</b>\n\n👤 {user_name}\n🏠 {server_name}"
    
    elif event_type == "user.lockedout":
        return f"🚫 <b>用户锁定</b>\n\n👤 {user_name}\n🏠 {server_name}"
    
    elif event_type == "user.deleted":
        return f"🗑️ <b>用户删除</b>\n\n👤 {user_name}\n🏠 {server_name}"
    
    elif event_type == "user.passwordchanged":
        return f"🔑 <b>密码更改</b>\n\n👤 {user_name}\n🏠 {server_name}"
    
    elif event_type == "user.updated":
        return f"👤 <b>用户信息更新</b>\n\n{user_name}\n🏠 {server_name}"
    
    # 系统事件
    elif event_type == "system.webhooktest":
        return "🔔 <b>Webhook 测试</b>\n\nEmby Webhook 服务正常运行！"
    
    elif event_type == "system.notificationtest":
        return "🔔 <b>通知测试</b>\n\nEmby 通知系统测试成功！"
    
    elif event_type == "system.taskcompleted":
        task_name = data.get("Name", "Unknown Task")
        return f"⚙️ <b>任务完成</b>\n\n{task_name}\n🏠 {server_name}"
    
    elif event_type == "system.plugininstalled":
        plugin_name = data.get("Name", "Unknown Plugin")
        return f"🔌 <b>插件安装</b>\n\n{plugin_name}\n🏠 {server_name}"
    
    elif event_type == "system.pluginuninstalled":
        plugin_name = data.get("Name", "Unknown Plugin")
        return f"🔌 <b>插件卸载</b>\n\n{plugin_name}\n🏠 {server_name}"
    
    elif event_type == "system.pluginupdated":
        plugin_name = data.get("Name", "Unknown Plugin")
        return f"🔌 <b>插件更新</b>\n\n{plugin_name}\n🏠 {server_name}"
    
    elif event_type == "system.updated":
        return f"🔄 <b>系统更新</b>\n\nEmby 服务器已更新\n🏠 {server_name}"
    
    elif event_type == "system.restarting":
        return f"🔄 <b>系统重启</b>\n\nEmby 服务器正在重启\n🏠 {server_name}"
    
    elif event_type == "system.shuttingdown":
        return f"🔌 <b>系统关机</b>\n\nEmby 服务器正在关机\n🏠 {server_name}"
    
    # 媒体库事件
    elif event_type == "library.changed":
        return f"📚 <b>媒体库变更</b>\n\n媒体库内容已更新\n🏠 {server_name}"
    
    elif event_type == "library.refreshed":
        return f"🔄 <b>媒体库刷新</b>\n\n媒体库刷新完成\n🏠 {server_name}"
    
    elif event_type == "library.updated":
        return f"📚 <b>媒体库更新</b>\n\n媒体库信息已更新\n🏠 {server_name}"
    
    # 认证事件
    elif event_type == "authentication.succeeded":
        return f"✅ <b>认证成功</b>\n\n👤 {user_name}\n🏠 {server_name}"
    
    elif event_type == "authentication.failed":
        username = data.get("Username", "Unknown")
        return f"❌ <b>认证失败</b>\n\n用户: {username}\n🏠 {server_name}"
    
    elif event_type == "authentication.credentialsinvalid":
        username = data.get("Username", "Unknown")
        return f"❌ <b>凭据无效</b>\n\n用户: {username}\n🏠 {server_name}"
    
    # 会话事件
    elif event_type == "session.start":
        device = data.get("DeviceName", "Unknown Device")
        return f"📱 <b>会话开始</b>\n\n👤 {user_name}\n📱 {device}\n🏠 {server_name}"
    
    elif event_type == "session.end":
        device = data.get("DeviceName", "Unknown Device")
        return f"📱 <b>会话结束</b>\n\n👤 {user_name}\n📱 {device}\n🏠 {server_name}"
    
    # 转码事件
    elif event_type == "transcode.start":
        return f"🎥 <b>开始转码</b>\n\n{item_name}\n👤 {user_name}\n🏠 {server_name}"
    
    elif event_type == "transcode.end":
        return f"🎥 <b>转码完成</b>\n\n{item_name}\n👤 {user_name}\n🏠 {server_name}"
    
    elif event_type == "transcode.failed":
        return f"❌ <b>转码失败</b>\n\n{item_name}\n👤 {user_name}\n🏠 {server_name}"
    
    # 定时任务事件
    elif event_type == "scheduledtask.start":
        task_name = data.get("Name", "Unknown Task")
        return f"⏰ <b>定时任务开始</b>\n\n{task_name}\n🏠 {server_name}"
    
    elif event_type == "scheduledtask.ended":
        task_name = data.get("Name", "Unknown Task")
        return f"⏰ <b>定时任务完成</b>\n\n{task_name}\n🏠 {server_name}"
    
    # 网络事件
    elif event_type == "network.connectionlost":
        return f"📡 <b>网络连接丢失</b>\n\n🏠 {server_name}"
    
    elif event_type == "network.connectionrestored":
        return f"📡 <b>网络连接恢复</b>\n\n🏠 {server_name}"
    
    # 默认情况
    else:
        # 对于未知事件，提供更详细的信息
        return f"📢 <b>{event_type}</b>\n\n内容: {item_name}\n类型: {item_type}\n用户: {user_name}\n服务器: {server_name}"

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        # 快速解析
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = request.get_json() or {}
        else:
            raw_data = request.get_data(as_text=True)
            data = json.loads(raw_data) if raw_data else {}
        
        event_type = data.get("Event", "Unknown")
        logger.info(f"处理事件: {event_type}")
        
        # 异步记录到文件
        def _log_to_file():
            try:
                with open('/app/data/webhook.log', 'a') as f:
                    f.write(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
            except:
                pass
        
        threading.Thread(target=_log_to_file).start()
        
        # 生成消息并异步发送
        message = generate_simple_message(data)
        send_telegram_async(message)
        
        # 立即返回响应
        return jsonify({
            "status": "success", 
            "event": event_type,
            "response_time": "fast"
        }), 200
        
    except Exception as e:
        logger.error(f"Webhook 处理错误: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    config = get_config()
    return jsonify({
        "status": "healthy",
        "telegram_configured": bool(config['telegram_token'] and config['telegram_chat_id']),
        "telegram_token_set": bool(config['telegram_token']),
        "telegram_chat_id_set": bool(config['telegram_chat_id'])
    }), 200

@app.route('/test-telegram', methods=['GET'])
def test_telegram():
    """测试 Telegram 发送"""
    message = "🧪 <b>完整事件测试</b>\n\nEmby Webhook 服务支持所有事件类型！"
    success = send_telegram_direct(message)
    return jsonify({
        "success": success, 
        "method": "direct_http",
        "config": {
            "token_set": bool(get_config()['telegram_token']),
            "chat_id_set": bool(get_config()['telegram_chat_id'])
        }
    })

if __name__ == '__main__':
    logger.info("启动完整事件支持的 Emby Webhooks...")
    app.run(host='0.0.0.0', port=3000, debug=False, threaded=True)
