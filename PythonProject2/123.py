import os
import requests
from telegram import Update, InputFile, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8554206583:AAHEFxTe1O1svGNrJHR-9rffvzgjc_IXVkA"
WEATHER_API_KEY = "6f361e789c23484a80873013252011"


class WeatherBot:
    def __init__(self):
        self.weather_api_url = "http://api.weatherapi.com/v1/current.json"
        self.image_folder = "city_images"
        self.last_cities = []

        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder)

    def get_keyboard(self):
        if not self.last_cities:
            return None
        buttons = [[city] for city in self.last_cities[-3:]]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "Привет! Я бот погоды🌤️\n\n"
            "Напиши любой город и я покажу погоду\n"
            "Например: Москва, Питер, Воронеж"
        )
        await update.message.reply_text(text, reply_markup=self.get_keyboard())

    async def handle_city(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        city = update.message.text.strip()

        if not city:
            await update.message.reply_text("Где живешь?")
            return

        try:
            weather = await self.get_weather(city)

            if weather:
                if city not in self.last_cities:
                    self.last_cities.append(city)
                if len(self.last_cities) > 3:
                    self.last_cities.pop(0)

                text = self.make_weather_text(weather)

                sent_pic = await self.send_pic(update, city)

                await update.message.reply_text(text, parse_mode='HTML', reply_markup=self.get_keyboard())

                if not sent_pic:
                    await update.message.reply_text("Картинки нет(", reply_markup=self.get_keyboard())
            else:
                await update.message.reply_text("Не нашел город...", reply_markup=self.get_keyboard())

        except Exception as e:
            await update.message.reply_text("Что-то сломалось...", reply_markup=self.get_keyboard())

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

    async def send_pic(self, update: Update, city: str) -> bool:
        try:
            name = city.lower().replace(' ', '_').replace('-', '_')

            exts = ['.jpg', '.jpeg', '.png', '.webp']
            path = None

            for ext in exts:
                test = os.path.join(self.image_folder, f"{name}{ext}")
                if os.path.exists(test):
                    path = test
                    break

            if path:
                with open(path, 'rb') as f:
                    await update.message.reply_photo(
                        photo=InputFile(f),
                        caption=f"🏙️ {city}",
                        reply_markup=self.get_keyboard()
                    )
                return True
            return False

        except:
            return False


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    bot = WeatherBot()

    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_city))

    print("Бот работает!")
    app.run_polling()


if __name__ == '__main__':
    main()