#!/usr/bin/env python3
"""
Упрощенный Telegram бот для мониторинга системы
"""

import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = '8157382379:AAGf0bxhk3vSgKAEvQY_hu6xPtjm-1jKhtI'
ADMIN_CHAT_ID = '632306300'

# Адреса сервисов
PROMETHEUS_URL = 'http://localhost:9090'
ALERTMANAGER_URL = 'http://localhost:9093'
GRAFANA_URL = 'http://localhost:3000'

# Блейды для мониторинга
BLADES = {
    'blade1': 'localhost:9100',
    'blade2': 'localhost:9100', 
    'blade3': 'localhost:9100'
}

# Запросы для Prometheus
METRICS_QUERIES = {
    'cpu_usage': '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
    'memory_usage': '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
    'disk_usage': '(1 - (node_filesystem_avail_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes{fstype!="tmpfs"})) * 100',
    'load_average': 'node_load5'
}

# ==================== РАБОТА С PROMETHEUS ====================
def get_blade_metrics(blade_address):
    """Получить все метрики для блейда"""
    metrics = {}
    
    for metric_name, query in METRICS_QUERIES.items():
        try:
            formatted_query = query.replace('instance', f'instance="{blade_address}"')
            
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={'query': formatted_query},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    value = float(data['data']['result'][0]['value'][1])
                    metrics[metric_name] = value
                else:
                    metrics[metric_name] = None
            else:
                metrics[metric_name] = None
                
        except Exception as e:
            logging.error(f"Error getting {metric_name} for {blade_address}: {e}")
            metrics[metric_name] = None
    
    return metrics

# ==================== КОМАНДЫ БОТА ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - главное меню"""
    keyboard = [
        [InlineKeyboardButton("🖥 Blade 1", callback_data="blade1")],
        [InlineKeyboardButton("🖥 Blade 2", callback_data="blade2")],
        [InlineKeyboardButton("🖥 Blade 3", callback_data="blade3")],
        [InlineKeyboardButton("📊 System Info", callback_data="system")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 System Monitoring Bot\n\n"
        "Select a blade to check its status:\n\n"
        "Available commands:\n"
        "/status <blade> - Check blade status\n"
        "/grafana - Get Grafana dashboard info\n"
        "/start - Show this menu",
        reply_markup=reply_markup
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status <blade>"""
    if not context.args:
        await update.message.reply_text("Usage: /status <blade1|blade2|blade3>")
        return
    
    blade_name = context.args[0].lower()
    await show_blade_status(update, context, blade_name)

async def grafana_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /grafana - информация о Grafana"""
    await update.message.reply_text(
        f"📊 **Grafana Dashboard**\n\n"
        f"Access your monitoring dashboard:\n"
        f"🔗 {GRAFANA_URL}\n"
        f"👤 Username: `admin`\n"
        f"🔑 Password: `admin`\n\n"
        f"Copy and paste the URL in your browser",
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('blade'):
        await show_blade_status(update, context, query.data)
    elif query.data == 'system':
        await show_system_info(update, context)

async def show_blade_status(update: Update, context: ContextTypes.DEFAULT_TYPE, blade_name: str):
    """Показать статус блейда"""
    if blade_name not in BLADES:
        await send_reply(update, "❌ Invalid blade name")
        return
    
    blade_address = BLADES[blade_name]
    
    try:
        metrics = get_blade_metrics(blade_address)
        
        message = f"📊 **{blade_name.upper()} Status**\n"
        message += f"📍 `{blade_address}`\n\n"
        
        if metrics.get('cpu_usage') is not None:
            message += f"🖥 CPU: `{metrics['cpu_usage']:.1f}%`\n"
        else:
            message += f"🖥 CPU: `No data`\n"
            
        if metrics.get('memory_usage') is not None:
            message += f"💾 Memory: `{metrics['memory_usage']:.1f}%`\n"
        else:
            message += f"💾 Memory: `No data`\n"
            
        if metrics.get('disk_usage') is not None:
            message += f"💽 Disk: `{metrics['disk_usage']:.1f}%`\n"
        else:
            message += f"💽 Disk: `No data`\n"
            
        if metrics.get('load_average') is not None:
            message += f"📈 Load: `{metrics['load_average']:.2f}`\n"
        else:
            message += f"📈 Load: `No data`\n"
        
        # Проверяем критичные значения
        warning = False
        if metrics.get('cpu_usage') and metrics['cpu_usage'] > 80:
            message += "⚠️ High CPU usage!\n"
            warning = True
        if metrics.get('memory_usage') and metrics['memory_usage'] > 85:
            message += "⚠️ High memory usage!\n" 
            warning = True
            
        if not warning and any(metrics.values()):
            message += "\n✅ All systems normal"
        elif not any(metrics.values()):
            message += "\n❌ No metrics data available"
            
        await send_reply(update, message)
        
    except Exception as e:
        logging.error(f"Error: {e}")
        await send_reply(update, f"❌ Error getting status for {blade_name}")

async def show_system_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о системе"""
    try:
        services_status = ""
        
        # Проверяем Prometheus
        try:
            response = requests.get(f"{PROMETHEUS_URL}/api/v1/query?query=up", timeout=5)
            if response.status_code == 200:
                services_status += "✅ Prometheus: Online\n"
            else:
                services_status += "❌ Prometheus: Offline\n"
        except:
            services_status += "❌ Prometheus: Offline\n"
        
        # Проверяем Alertmanager
        try:
            response = requests.get(f"{ALERTMANAGER_URL}/api/v1/status", timeout=5)
            if response.status_code == 200:
                services_status += "✅ Alertmanager: Online\n"
            else:
                services_status += "❌ Alertmanager: Offline\n"
        except:
            services_status += "❌ Alertmanager: Offline\n"
        
        # Проверяем Grafana
        try:
            response = requests.get(f"{GRAFANA_URL}/api/health", timeout=5)
            if response.status_code == 200:
                services_status += "✅ Grafana: Online\n"
            else:
                services_status += "❌ Grafana: Offline\n"
        except:
            services_status += "❌ Grafana: Offline\n"
        
        message = f"🔧 **System Information**\n\n{services_status}"
        await send_reply(update, message)
        
    except Exception as e:
        logging.error(f"Error getting system info: {e}")
        await send_reply(update, "❌ Error getting system information")

async def send_reply(update: Update, text: str):
    """Отправить ответ в нужный контекст"""
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

# ==================== ЗАПУСК БОТА ====================
def main():
    """Запуск бота"""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("grafana", grafana_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Starting Telegram bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
