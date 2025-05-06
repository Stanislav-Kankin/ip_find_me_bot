import os
import requests
import folium
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import (
    Message,
    FSInputFile,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем токен бота из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("Не удалось загрузить BOT_TOKEN из .env файла")

# Инициализация бота с HTML-разметкой по умолчанию
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML))

dp = Dispatcher()


def get_ip_info(ip: str = '127.0.0.1') -> tuple[dict | None, str | None]:
    """Получает информацию об IP-адресе и создает карту."""
    try:
        response = requests.get(f'http://ip-api.com/json/{ip}', timeout=10).json()

        if response.get('status') == 'fail':
            return None, response.get('message', 'Unknown error')

        data = {
            'IP': response.get('query'),
            'Интернет провайдер': response.get('isp'),
            'Страна': response.get('country'),
            'Регион': response.get('regionName'),
            'Город': response.get('city'),
            'Индекс': response.get('zip'),
            'Широта': response.get('lat'),
            'Долгота': response.get('lon')
        }

        # Создаем карту, если есть координаты
        if response.get('lat') and response.get('lon'):
            area = folium.Map(
                location=[response['lat'], response['lon']],
                zoom_start=12
            )
            # Добавляем маркер
            folium.Marker(
                [response['lat'], response['lon']],
                popup=response.get('city', 'Unknown location')
            ).add_to(area)

            map_filename = f"ip_map_{response['query']}.html"
            area.save(map_filename)
            return data, map_filename

        return data, None

    except requests.exceptions.RequestException as e:
        return None, f'Ошибка сети: {str(e)}'
    except Exception as e:
        return None, f'Произошла ошибка: {str(e)}'


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Обработчик команды /start."""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Мой IP"))
    builder.add(KeyboardButton(text="Помощь"))

    await message.answer(
        "<b>Привет!</b> Я бот для получения информации об IP-адресах.\n"
        "Просто отправь мне любой IP-адрес или нажми кнопку ниже.",
        reply_markup=builder.as_markup(
            resize_keyboard=True,
            input_field_placeholder="Выберите действие..."
        )
    )


@dp.message(lambda message: message.text and message.text.lower() == "помощь")
async def cmd_help(message: Message) -> None:
    """Обработчик кнопки 'Помощь'."""
    help_text = (
        "<b>📌 Как пользоваться ботом:</b>\n\n"
        "1. Отправьте мне <i>IPv4-адрес</i> (например, 8.8.8.8)\n"
        "2. Или нажмите кнопку <b>'Мой IP'</b>\n\n"
        "Я покажу информацию о местоположении и пришлю карту.\n"
        "Карту можешь открыть с телефона или ПК в любом браузере"
    )
    await message.answer(help_text, reply_markup=ReplyKeyboardRemove())


@dp.message(lambda message: message.text and message.text.lower() == "мой ip")
async def cmd_my_ip(message: Message) -> None:
    """Обработчик кнопки 'Мой IP'."""
    try:
        # Получаем реальный IP пользователя через внешний сервис
        ip_response = requests.get('https://api.ipify.org?format=json', timeout=5).json()
        user_ip = ip_response.get('ip')

        if user_ip:
            await process_ip_request(message, user_ip)
        else:
            await message.answer("Не удалось определить ваш IP-адрес.")
    except requests.exceptions.RequestException:
        await message.answer(
            "Не удалось определить ваш IP автоматически. "
            "Пожалуйста, введите IP-адрес вручную."
        )


@dp.message(lambda message: message.text and is_valid_ip(message.text))
async def process_ip(message: Message) -> None:
    """Обработчик ввода IP-адреса."""
    await process_ip_request(message, message.text.strip())


def is_valid_ip(ip: str) -> bool:
    """Проверяет, является ли строка валидным IPv4 адресом."""
    parts = ip.split('.')
    if len(parts) != 4:
        return False

    try:
        return all(0 <= int(part) <= 255 for part in parts)
    except ValueError:
        return False


async def process_ip_request(message: Message, ip: str) -> None:
    """Обрабатывает запрос информации об IP."""
    # Показываем статус "печатает..."
    await bot.send_chat_action(message.chat.id, "typing")

    data, map_filename = get_ip_info(ip)

    if data is None:
        await message.answer(f"❌ {map_filename}")
        return

    # Форматируем информацию в HTML
    info_text = "<b>🔍 Информация об IP:</b>\n\n" + \
                "\n".join(f"<b>{k}:</b> <code>{v}</code>" for k, v in data.items())

    if map_filename:
        try:
            # Отправляем информацию и карту
            await message.answer(info_text)
            await message.answer_document(
                FSInputFile(map_filename),
                caption="📍 Карта местоположения"
            )
        finally:
            # Удаляем временный файл в любом случае
            if os.path.exists(map_filename):
                os.remove(map_filename)
    else:
        await message.answer(info_text + "\n\n⚠ <i>Не удалось создать карту для этого IP</i>")


async def main() -> None:
    """Запуск бота."""
    await dp.start_polling(bot)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
