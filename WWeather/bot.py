import os
import json
import requests
from datetime import datetime, time as datetime_time
from telegram import Update, InputFile, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext

BOT_TOKEN = "8554206583:AAHEFxTe1O1svGNrJHR-9rffvzgjc_IXVkA"
WEATHER_API_KEY = "6f361e789c23484a80873013252011"
UNSPLASH_ACCESS_KEY = "QAyQ7hC6D4KCcPCABDccc7j2qGwpBw98kGAJwxxLBDs"


class WeatherBot:
    def __init__(self):
        self.weather_api_url = "http://api.weatherapi.com/v1/current.json"
        self.city_images_folder = "saved_city_images"
        self.data_file = "user_data.json"

        self.user_data = self.load_data()

        if not os.path.exists(self.city_images_folder):
            os.makedirs(self.city_images_folder)

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_data(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.user_data, f, ensure_ascii=False, indent=2)

    def get_user_data(self, user_id):
        if str(user_id) not in self.user_data:
            self.user_data[str(user_id)] = {
                'last_cities': [],
                'notification': None,
                'job_name': None
            }
        return self.user_data[str(user_id)]

    def get_main_menu(self, user_id):
        user = self.get_user_data(user_id)
        if user['notification']:
            return [["Последние города", "Уведомление создано"]]
        return [["Последние города", "Включить уведомление"]]

    def get_cities_keyboard(self, user_id):
        user = self.get_user_data(user_id)
        keyboard = []
        for city in user['last_cities'][-3:]:
            keyboard.append([city])
        keyboard.append(["Назад"])
        return keyboard

    def get_notification_info_keyboard(self):
        return [["Изменить уведомление", "Назад"]]

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.chat_id
        text = "Главное меню"
        await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(self.get_main_menu(user_id),
                                                                               resize_keyboard=True))

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.chat_id
        text = update.message.text.strip()

        if text == "Последние города":
            user = self.get_user_data(user_id)
            if user['last_cities']:
                await update.message.reply_text("Выбери город:",
                                                reply_markup=ReplyKeyboardMarkup(self.get_cities_keyboard(user_id),
                                                                                 resize_keyboard=True))
            else:
                await update.message.reply_text("Ты еще не искал города",
                                                reply_markup=ReplyKeyboardMarkup(self.get_main_menu(user_id),
                                                                                 resize_keyboard=True))

        elif text == "Включить уведомление":
            await update.message.reply_text("Введи время в формате ЧЧ:ММ (например 10:00 или 23:30)")
            context.user_data['waiting_for_time'] = True

        elif text == "Уведомление создано":
            user = self.get_user_data(user_id)
            if user['notification']:
                city, time_str = user['notification']
                info = f"Уведомление установлено:\nГород: {city}\nВремя: {time_str}"
                await update.message.reply_text(info,
                                                reply_markup=ReplyKeyboardMarkup(self.get_notification_info_keyboard(),
                                                                                 resize_keyboard=True))
            else:
                await update.message.reply_text("Нет активных уведомлений",
                                                reply_markup=ReplyKeyboardMarkup(self.get_main_menu(user_id),
                                                                                 resize_keyboard=True))

        elif text == "Назад":
            await update.message.reply_text("Главное меню",
                                            reply_markup=ReplyKeyboardMarkup(self.get_main_menu(user_id),
                                                                             resize_keyboard=True))

        elif text == "Изменить уведомление":
            user = self.get_user_data(user_id)
            await self.remove_notification_job(context, user_id, user)
            user['notification'] = None
            user['job_name'] = None
            self.save_data()
            await update.message.reply_text("Уведомление сброшено",
                                            reply_markup=ReplyKeyboardMarkup(self.get_main_menu(user_id),
                                                                             resize_keyboard=True))

        elif 'waiting_for_time' in context.user_data and context.user_data['waiting_for_time']:
            try:
                time_obj = datetime.strptime(text, "%H:%M").time()
                context.user_data['notification_time'] = text
                context.user_data['waiting_for_time'] = False
                context.user_data['waiting_for_city'] = True

                user = self.get_user_data(user_id)
                if user['last_cities']:
                    await update.message.reply_text(f"Время {text} установлено. Теперь выбери город:",
                                                    reply_markup=ReplyKeyboardMarkup(self.get_cities_keyboard(user_id),
                                                                                     resize_keyboard=True))
                else:
                    await update.message.reply_text(f"Время {text} установлено. Теперь напиши название города:")
            except ValueError:
                await update.message.reply_text("Неверный формат времени. Введи в формате ЧЧ:ММ (например 09:30)")

        elif 'waiting_for_city' in context.user_data and context.user_data['waiting_for_city']:
            city = text
            time_str = context.user_data['notification_time']

            user = self.get_user_data(user_id)
            user['notification'] = (city, time_str)

            await self.schedule_notification(context, user_id, city, time_str)

            context.user_data['waiting_for_city'] = False
            if 'notification_time' in context.user_data:
                del context.user_data['notification_time']

            self.save_data()

            await update.message.reply_text(f"Уведомление создано!\nГород: {city}\nВремя: {time_str}",
                                            reply_markup=ReplyKeyboardMarkup(self.get_main_menu(user_id),
                                                                             resize_keyboard=True))

        else:
            user = self.get_user_data(user_id)
            if text in user['last_cities']:
                await self.handle_city(update, context, text, user_id)
            else:
                await self.handle_city(update, context, text, user_id)

    async def handle_city(self, update: Update, context: ContextTypes.DEFAULT_TYPE, city=None, user_id=None):
        if not user_id:
            user_id = update.message.chat_id

        if not city:
            city = update.message.text.strip()

        try:
            weather = await self.get_weather(city)

            if weather:
                user = self.get_user_data(user_id)
                if city not in user['last_cities']:
                    user['last_cities'].append(city)
                if len(user['last_cities']) > 3:
                    user['last_cities'].pop(0)

                self.save_data()

                text = self.make_weather_text(weather)

                english_name = weather['location']['region']
                await self.send_city_pic(update, city, english_name)

                await update.message.reply_text(text, parse_mode='HTML')

            else:
                await update.message.reply_text("Не нашел город...")

        except Exception as e:
            print(f"Ошибка: {e}")
            await update.message.reply_text("Что-то сломалось...")

    async def get_weather(self, city: str) -> dict:
        try:
            params = {
                'key': WEATHER_API_KEY,
                'q': city,
                'lang': 'ru'
            }

            r = requests.get(self.weather_api_url, params=params, timeout=10)
            return r.json()

        except:
            return None

    def make_weather_text(self, data: dict) -> str:
        loc = data['location']
        cur = data['current']

        sun = "☀️" if cur['is_day'] else "🌙"

        text = (
            f"{sun} <b>Погода в {loc['name']}</b>\n"
            f"📍 {loc['region']}\n"
            f"🇷🇺 {loc['country']}\n\n"

            f"🌡️ {cur['temp_c']}°C\n"
            f"🤔 Ощущается {cur['feelslike_c']}°C\n"
            f"☁️ {cur['condition']['text']}\n\n"

            f"💨 Ветер {cur['wind_kph']} км/ч\n"
            f"💧 Влажность {cur['humidity']}%\n"
            f"📊 Давление {cur['pressure_mb']} мбар\n\n"

            f"🕒 {cur['last_updated']}"
        )

        return text

    def get_city_filename(self, city: str) -> str:
        city_normalized = city.lower().replace(' ', '_').replace('-', '_')
        return os.path.join(self.city_images_folder, f"{city_normalized}.jpg")

    async def send_city_pic(self, update: Update, city: str, english_name: str) -> bool:
        try:
            filename = self.get_city_filename(city)

            if os.path.exists(filename):
                with open(filename, 'rb') as f:
                    await update.message.reply_photo(
                        photo=InputFile(f),
                        caption=f"🏙️ {city}"
                    )
                return True

            search_url = f"https://api.unsplash.com/search/photos"
            params = {
                'query': f"{english_name} city",
                'client_id': UNSPLASH_ACCESS_KEY,
                'per_page': 1
            }

            response = requests.get(search_url, params=params, timeout=10)
            data = response.json()

            if data['results']:
                image_url = data['results'][0]['urls']['regular']

                image_response = requests.get(image_url, timeout=10)

                with open(filename, 'wb') as f:
                    f.write(image_response.content)

                with open(filename, 'rb') as f:
                    await update.message.reply_photo(
                        photo=InputFile(f),
                        caption=f"🏙️ {city}"
                    )
                return True
            return False

        except Exception as e:
            print(f"Ошибка: {e}")
            return False

    async def remove_notification_job(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, user: dict):
        if user['job_name']:
            job_name = user['job_name']
            current_jobs = context.application.job_queue.jobs()
            for job in current_jobs:
                if job.name == job_name:
                    job.schedule_removal()
                    break

    async def schedule_notification(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, city: str, time_str: str):
        try:
            hour, minute = map(int, time_str.split(':'))

            user = self.get_user_data(user_id)

            await self.remove_notification_job(context, user_id, user)

            job_name = f"notify_{user_id}"
            user['job_name'] = job_name

            context.application.job_queue.run_daily(
                self.send_notification,
                time=datetime_time(hour, minute),
                name=job_name,
                data={'user_id': user_id, 'city': city}
            )

            print(f"Уведомление создано для user_id={user_id} на {time_str}")

        except Exception as e:
            print(f"Ошибка планирования: {e}")

    async def send_notification(self, context: CallbackContext):
        job_data = context.job.data
        user_id = job_data['user_id']
        city = job_data['city']

        try:
            weather = await self.get_weather(city)

            if weather:
                text = f"⏰ <b>Ежедневное уведомление</b>\n\n" + self.make_weather_text(weather)

                filename = self.get_city_filename(city)
                if os.path.exists(filename):
                    with open(filename, 'rb') as f:
                        await context.bot.send_photo(
                            chat_id=user_id,
                            photo=InputFile(f),
                            caption=f"🏙️ {city}"
                        )

                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode='HTML'
                )

        except Exception as e:
            print(f"Ошибка отправки уведомления: {e}")


async def restore_notifications(application: Application):
    bot = None
    for handler in application.handlers[0]:
        if hasattr(handler.callback, '__self__'):
            bot = handler.callback.__self__
            break

    if bot and hasattr(bot, 'user_data'):
        for user_id_str, user_data in bot.user_data.items():
            if user_data.get('notification'):
                city, time_str = user_data['notification']
                user_id = int(user_id_str)
                await bot.schedule_notification(application, user_id, city, time_str)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    bot = WeatherBot()

    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))

    app.post_init = restore_notifications

    print("Бот работает!")
    app.run_polling()


if __name__ == '__main__':
    main()