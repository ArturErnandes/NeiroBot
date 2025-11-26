import os

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv


PAY_NUM_FILE = "pay_num_file.txt"
load_dotenv()

admins = [5354134749, 6524917951]

token = os.getenv("TOKEN")
bot = telebot.TeleBot(token)

waiting_for_new_number = {}


def read_pay_number():
    try:
        with open(PAY_NUM_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(e)
        return "Файл пуст или отсутствует."


def write_pay_number(text):
    with open(PAY_NUM_FILE, "w", encoding="utf-8") as f:
        f.write(text.strip())


def main_menu():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Посмотреть текущий номер", callback_data="view"),
              InlineKeyboardButton("Изменить номер", callback_data="edit"))
    return markup


def is_admin(user_id):
    return user_id in admins


@bot.message_handler(commands=["start"])
def start(msg):
    if is_admin(msg.from_user.id):
        bot.send_message(msg.chat.id, "Выберите действие:", reply_markup=main_menu())
    else:
        bot.send_message(msg.chat.id, "У вас нет доступа к этому боту.")



@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    chat_id = call.message.chat.id

    if call.data == "view":
        number = read_pay_number()
        bot.send_message(chat_id, f"Текущий номер для оплаты:\n\n{number}")

    elif call.data == "edit":
        bot.send_message(chat_id, "Введите новый номер для оплаты:")
        waiting_for_new_number[chat_id] = True


@bot.message_handler(func=lambda msg: True)
def text_handler(msg):
    chat_id = msg.chat.id
    user_id = msg.from_user.id

    if not is_admin(user_id):
        return

    if waiting_for_new_number.get(chat_id):
        new_number = msg.text.strip()
        write_pay_number(new_number)

        bot.send_message(chat_id, f"Номер обновлён:\n\n{new_number}")
        waiting_for_new_number.pop(chat_id, None)

        for admin_id in admins:
            if admin_id != user_id:
                try:
                    bot.send_message(admin_id,f"Номер для оплаты был изменён.\nТекущий номер: {new_number}")
                except Exception as e:
                    print(f"Ошибка при отправке сообщения админу: {e}")

        bot.send_message(chat_id, "Меню:", reply_markup=main_menu())

    else:
        bot.send_message(chat_id, "Выберите действие:", reply_markup=main_menu())


bot.infinity_polling()