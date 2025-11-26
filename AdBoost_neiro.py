import os
from telethon.errors import SessionPasswordNeededError
from colorama import Fore, init
import requests
import json
import asyncio
import random
from telethon import TelegramClient, events
from datetime import datetime

CONFIG_FILE = "accs_data.json"
MAIN_PROMT_FILE = "main_promt.txt"
PAIDED_PROMT_FILE = "paided_promt.txt"
PAY_NUM_FILE = "pay_num_file.txt"
SEEN_IDS_FILE = "ang_ids.json"
PAIDED_USERS_FILE = "paided_users.json"
HOUR_MESSAGES_LIMIT = 10


def load_promt(filename):
    with open(filename, 'r', encoding="utf-8-sig") as f:
        promt = f.read()
    return promt


def read_ids(filename):
    with open(filename, 'r', encoding="utf-8-sig") as f:
        ids = [int(row.strip()) for row in f]
    f.close()
    return ids


def save_id(user_id, filename):
    with open(filename, 'a', encoding="utf-8") as f:
        f.write(f'{user_id}\n')
    f.close()


async def connect_client(number):
    json_file = f"{number}.json"
    session_name = number
    if os.path.exists(json_file):
        with open(json_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        client = TelegramClient(
            session=session_name,
            api_id=cfg["app_id"],
            api_hash=cfg["app_hash"],
            device_model=cfg["device"],
            app_version=cfg["app_version"],
            system_version=cfg["sdk"]
        )

        await client.connect()

        if await client.is_user_authorized():
            print(f"Аккаунт {number} успешно подключён по session/json.")
            return client
        else:
            print(f"⚠️ Session существует, но аккаунт не авторизован — потребуется вход.")

    print(f"Запускаю первичную авторизацию для номера {number}...")

    api_id = 24474790
    api_hash = "26b2f72269d6259330788d0daeb07413"
    device = "Windows Server"
    app_version = "10.0"
    sdk = "4.16.30-vxCUSTOM"

    client = TelegramClient(
        session=session_name,
        api_id=api_id,
        api_hash=api_hash,
        device_model=device,
        app_version=app_version,
        system_version=sdk
    )

    await client.connect()
    await client.send_code_request(number)
    code = input(f"Введите код, пришедший на {number}: ")
    try:
        await client.sign_in(number, code)
    except SessionPasswordNeededError:
        pwd = input("Аккаунт защищён паролем 2FA. Введите пароль: ")
        await client.sign_in(password=pwd)
    cfg = {
        "phone": number,
        "app_id": api_id,
        "app_hash": api_hash,
        "device": device,
        "app_version": app_version,
        "sdk": sdk
    }
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)
    print(f"Первичная авторизация {number} выполнена. JSON и session сохранены.")
    return client


async def answer(client, name, answer_text, user, limits):
    answers_delay = limits["answers_delay"]
    typing_min, typing_max = limits["typing_delay"]

    await asyncio.sleep(answers_delay)

    async with client.action(user, "typing"):
        typing_time = random.randint(typing_min, typing_max) / 1000
        await asyncio.sleep(typing_time)
    try:
        await client.send_message(user, answer_text)
        print(f"{datetime.now().strftime('%H:%M:%S')} {Fore.LIGHTRED_EX}[SUCCESS]{Fore.RESET} Аккаунт {Fore.LIGHTBLUE_EX}{name}{Fore.RESET}Успешно ответил пользователю {Fore.LIGHTBLUE_EX}{user}")
    except Exception as e:
        print(f"{datetime.now().strftime('%H:%M:%S')} {Fore.LIGHTRED_EX}[ERROR]{Fore.RESET} Аккаунт {Fore.LIGHTRED_EX}{name}{Fore.RESET} Ошибка при ответе пользователю {user}: {e}")


def generate_answer(final_promt, llm_cfg):
    url = llm_cfg["api_base"].rstrip("/") + "/chat/completions"

    headers = {
        "Authorization": f"Bearer {llm_cfg['api_token']}",
        "Content-Type": "application/json",
    }

    if llm_cfg.get("http_referer"):
        headers["HTTP-Referer"] = llm_cfg["http_referer"]

    payload = {
        "model": llm_cfg["model"],
        "messages": [
            {"role": "user", "content": final_promt}
        ],
        "max_tokens": llm_cfg["max_tokens"],
        "temperature": llm_cfg["temperature"],
        "top_p": llm_cfg["top_p"],
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)

        if r.status_code != 200:
            print(f"OpenRouter HTTP {r.status_code}: {r.text[:300]}")
            return "Извини зайка, я сейчас занята, отвечу чуть позже\nP.S. это автоматический ответ от Telegram"

        data = r.json()
        content = (
            data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
        )

        return content.strip() if content else "..."

    except Exception as e:
        print(f"LLM error: {e}")
        return "Извини зайка, я сейчас занята, отвечу чуть позже\nP.S. это автоматический ответ от Telegram"


async def answer_controller(client, name, llm_cfg, limits, user):
    main_promt = load_promt(MAIN_PROMT_FILE)
    paided_promt = load_promt(PAIDED_PROMT_FILE)
    paided_users = read_ids(PAIDED_USERS_FILE)
    pay_number = load_promt(PAY_NUM_FILE)
    seen_users = read_ids(SEEN_IDS_FILE)
    msg_limit = limits['hour_msg_limit']


    chat_id = user.chat_id
    if chat_id not in seen_users:
        save_id(chat_id, SEEN_IDS_FILE)

    msgs_list = []

    async for msg in client.iter_messages(chat_id, limit=msg_limit):
        if not msg.text:
            continue

        if msg.out:
            msgs_list.append(("assistant", msg.text))
        else:
            msgs_list.append(("user", msg.text))

    msgs_list.reverse()
    msgs_text = ""

    for role, text in msgs_list:
        if role == "user":
            msgs_text += f"Пользователь: {text}\n"
        else:
            msgs_text += f"Бот: {text}\n"

    msgs_text = msgs_text.strip()

    if chat_id in paided_users:
        pass
    else:
        final_promt = f"{main_promt}\nПереписка с пользователем:\n{msgs_text}\nНомер для оплаты:\n{pay_number}"
        answ = generate_answer(final_promt, llm_cfg)


async def event_checker(client, name, llm_cfg, limits):
    @client.on(events.NewMessage())
    async def handler(event):
        sender = await event.get_sender()

        if event.is_private and not sender.bot:
            await answer_controller(client, name, llm_cfg, limits, event)

        try:
            await client.run_until_disconnected()
        except Exception as e:
            warning = f"cyka blyat {name} ot'ebnul"
            print(warning)
            await asyncio.sleep(1000)


async def main():
    tasks = []

    with open(CONFIG_FILE, 'r', encoding="utf-8-sig") as f:
        data = json.load(f)

    for number in data['numbers']:
        client = await connect_client(number)
        if not client:
            continue

        me = await client.get_me()
        name = me.first_name
        print(f"{datetime.now().strftime('%H:%M:%S')}{Fore.GREEN} [SUCCESS] {Fore.RESET} Аккаунт {Fore.LIGHTBLUE_EX}{name}{Fore.RESET} подключен и готов к работе")

        tasks.append(event_checker(client, name, data['llm'], data['limits']))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    init(autoreset=True)
    asyncio.run(main())
    input("Нажмите Enter для выхода...")