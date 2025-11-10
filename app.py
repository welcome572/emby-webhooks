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
        
        logger.info(f"Telegram 配置检查 - Token: {'*' * 10 if config['telegram_token'] else '未设置'}, Chat ID: {config['telegram_chat_id']}")
        
        if not config['telegram_token']:
            logger.error("Telegram Token 未设置")
            return False
        
        if not config['telegram_chat_id']:
            logger.error("Telegram Chat ID 未设置")
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
        
        logger.info("开始发送 Telegram 消息...")
        
        # 发送请求
        response = requests.post(
            url,
            data=data,
            proxies=proxies,
            timeout=15
        )
        
        logger.info(f"Telegram API 响应状态: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                logger.info(f"✅ Telegram 消息发送成功！消息ID: {result['result']['message_id']}")
                return True
            else:
                error_desc = result.get('description', 'Unknown error')
                logger.error(f"Telegram API 错误: {error_desc}")
                return False
        else:
            logger.error(f"HTTP 错误 {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.warning("⚠️ Telegram 发送超时")
        return False
    except requests.exceptions.ProxyError as e:
        logger.error(f"❌ 代理错误: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Telegram 发送失败: {str(e)}")
        return False

def send_telegram_async(message):
    """异步发送 Telegram 消息"""
    if not message:
        return
    
    def _send():
        try:
            success = send_telegram_direct(message)
            if success:
                logger.info("✅ 异步 Telegram 发送成功")
            else:
                logger.warning("❌ 异步 Telegram 发送失败")
        except Exception as e:
            logger.error(f"异步发送异常: {e}")
    
    _executor.submit(_send)

def generate_simple_message(data):
    """生成简化消息"""
    event_type = data.get("Event", "Unknown")
    
    if event_type == "library.new":
        item = data.get("Item", {})
        item_type = item.get("Type", "Unknown")
        item_name = item.get("Name", "Unknown")
        
        if item_type == "Movie":
            year = item.get("ProductionYear", "")
            year_str = f" ({year})" if year else ""
            return f"🎬 <b>新电影添加</b>\n\n{item_name}{year_str}"
            
        elif item_type == "Episode":
            series_name = item.get("SeriesName", "Unknown")
            season = item.get("ParentIndexNumber", "")
            episode = item.get("IndexNumber", "")
            return f"📺 <b>新剧集更新</b>\n\n{series_name}\nS{season}E{episode} - {item_name}"
        else:
            return f"📦 <b>新内容</b>\n\n{item_name} ({item_type})"
    
    elif event_type in ["system.webhooktest", "system.notificationtest"]:
        return "🔔 <b>测试通知</b>\n\nEmby Webhook 服务正常运行！"
    
    elif event_type == "playback.start":
        item = data.get("Item", {})
        user = data.get("User", {})
        return f"▶️ <b>开始播放</b>\n\n{item.get('Name', 'Unknown')}\n👤 {user.get('Name', 'Unknown')}"
    
    else:
        return f"📢 <b>{event_type}</b>\n\n事件已记录"

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
        logger.info(f"处理 Webhook 事件: {event_type}")
        
        # 异步记录到文件
        def _log_to_file():
            try:
                with open('/app/data/webhook.log', 'a') as f:
                    f.write(json.dumps(data, ensure_ascii=False) + '\n')
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
    message = "🧪 <b>直接 API 测试</b>\n\n如果收到此消息，说明直接 HTTP API 工作正常！"
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
    logger.info("启动直接环境变量版本的 Emby Webhooks...")
    app.run(host='0.0.0.0', port=3000, debug=False, threaded=True)
