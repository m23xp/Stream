import subprocess
import yt_dlp
import telebot
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = '7877058951:AAElNyt9k2yZi4GKr5SoxJvT16Bnx9X4gPg'
OWNER_ID = 7792227700

bot = telebot.TeleBot(BOT_TOKEN)

STREAM_KEY = "2292984892:wwT9tkiSHHb9BO399gO2xQ"
RTMP_URL = f"rtmps://dc4-1.rtmp.t.me/s/{STREAM_KEY}"

last_url = None
ffmpeg_process = None
playlist_videos = []
current_index = 0

def get_youtube_stream_url(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4]/best',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info['url'], info.get("title", "Unknown Title")

def stream_to_telegram(stream_url):
    global ffmpeg_process
    command = [
        "ffmpeg",
        "-re",
        "-i", stream_url,
        "-c", "copy",
        "-f", "flv",
        RTMP_URL
    ]
    ffmpeg_process = subprocess.Popen(command)

def stop_stream():
    global ffmpeg_process
    if ffmpeg_process and ffmpeg_process.poll() is None:
        ffmpeg_process.terminate()
        ffmpeg_process.wait()
        ffmpeg_process = None
        return True
    return False

def stream_playlist(chat_id):
    global ffmpeg_process, current_index, playlist_videos
    while current_index < len(playlist_videos):
        entry = playlist_videos[current_index]
        stream_url = entry['url']
        title = entry.get('title', f'Video {current_index + 1}')
        bot.send_message(chat_id, f"🎬 بث: {title}", reply_markup=get_control_buttons())
        ffmpeg_process = subprocess.Popen([
            "ffmpeg",
            "-re",
            "-i", stream_url,
            "-c", "copy",
            "-f", "flv",
            RTMP_URL
        ])
        ffmpeg_process.wait()
        ffmpeg_process = None
        current_index += 1
    bot.send_message(chat_id, "✅ تم الانتهاء من بث كل المقاطع.")

def get_control_buttons():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🛑 إيقاف البث", callback_data="stop"),
        InlineKeyboardButton("🔁 إعادة البث", callback_data="restart"),
        InlineKeyboardButton("⏭️ التالي", callback_data="next")
    )
    return markup

@bot.message_handler(commands=['start'])
def start_handler(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "❌ غير مصرح لك باستخدام هذا البوت.")
    bot.reply_to(message, "أرسل رابط يوتيوب أو قائمة تشغيل لبثها مباشرة للقناة.")

@bot.message_handler(func=lambda m: any(x in m.text for x in ['youtube.com', 'youtu.be']))
def youtube_handler(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "❌ هذا البوت خاص.")
    global last_url, playlist_videos, current_index
    url = message.text.strip()
    bot.reply_to(message, "📡 جاري معالجة الرابط...")
    def process():
        try:
            if "list=" in url:
                last_url = url
                with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if 'entries' not in info:
                        bot.send_message(message.chat.id, "❌ لم أتمكن من قراءة قائمة التشغيل.")
                        return
                    playlist_videos = info['entries']
                    current_index = 0
                    bot.send_message(message.chat.id, f"📀 سيتم بث {len(playlist_videos)} فيديو...")
                    stream_playlist(message.chat.id)
            else:
                stream_url, title = get_youtube_stream_url(url)
                last_url = url
                bot.send_message(message.chat.id, f"🎬 بدء البث: {title}", reply_markup=get_control_buttons())
                stream_to_telegram(stream_url)
                if ffmpeg_process:
                    ffmpeg_process.wait()
                bot.send_message(message.chat.id, "✅ انتهى البث.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطأ: {e}")
    threading.Thread(target=process).start()

@bot.callback_query_handler(func=lambda call: call.data in ["stop", "restart", "next"])
def callback_handler(call):
    global last_url, playlist_videos, current_index, ffmpeg_process
    if call.from_user.id != OWNER_ID:
        return bot.answer_callback_query(call.id, "❌ غير مسموح.")
    if call.data == "stop":
        if stop_stream():
            bot.answer_callback_query(call.id, "✅ تم إيقاف البث.")
            bot.send_message(call.message.chat.id, "🛑 تم إيقاف البث.")
        else:
            bot.answer_callback_query(call.id, "⚠️ لا يوجد بث شغال.")
    elif call.data == "restart":
        if last_url:
            bot.answer_callback_query(call.id, "🔁 إعادة البث...")
            def restart():
                try:
                    stream_url, title = get_youtube_stream_url(last_url)
                    bot.send_message(call.message.chat.id, f"🎬 إعادة البث: {title}", reply_markup=get_control_buttons())
                    stream_to_telegram(stream_url)
                    if ffmpeg_process:
                        ffmpeg_process.wait()
                    bot.send_message(call.message.chat.id, "✅ انتهى البث.")
                except Exception as e:
                    bot.send_message(call.message.chat.id, f"❌ خطأ أثناء الإعادة: {e}")
            threading.Thread(target=restart).start()
        else:
            bot.answer_callback_query(call.id, "⚠️ لم يتم إرسال رابط بعد.")
    elif call.data == "next":
        if ffmpeg_process:
            ffmpeg_process.terminate()
            ffmpeg_process.wait()
            ffmpeg_process = None
            bot.answer_callback_query(call.id, "⏭️ يتم الانتقال إلى التالي...")
        else:
            bot.answer_callback_query(call.id, "⚠️ لا يوجد بث نشط.")

print("🤖 البوت يعمل...")
bot.polling()
