import gspread
import ujson as json
import machineid

def checkKey(user_key:str) -> int:
    """
    user_key: int Ключ, который пользователь передал для проверки
    return: int код проверки ключа (0 - ключ прошел проверки, 1 - ключа не существует, 2 - кол-во сессий превышено)
    """
    machine_id = machineid.id()
    gc = gspread.service_account(filename="./server/WebTable/credentials.json")
    SPREADSHEET_ID = "14uH3sv6mTzgh0qRjbP_3FiZnAU8k3k0NOOj4LIHFkF0"
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet("Keys")
    all_records = worksheet.get_all_records()
    for record in all_records:
        if record["key"] == user_key:
            cur_sessions = record["cur_sessions"] + 1
            if cur_sessions > record["max_sessions"]: 
                if machine_id in json.loads(record["cur_users"]): return 0
                else: return 2
            else: 
                incrementSessions(user_key=user_key)
                return 0
    return 1

def updateUserKey(user_key:str, user_id:str) -> None:
    """
    обновляет инфу в файле table_state.json
    user_key: int Ключ, который пользователь передал 
    """
    with open("./server/WebTable/table_state.json", "w") as file:
        file.write(json.dumps({
            "cur_user_key": user_key,
            "machine_id": user_id
        }))
    return

def incrementSessions(user_key:str) -> None:
    """
    увеличивает на 1 кол-во активных сессий
    user_key: int Ключ, который пользователь передал для проверки
    """
    machine_id = machineid.id()
    gc = gspread.service_account(filename="./server/WebTable/credentials.json")
    SPREADSHEET_ID = "14uH3sv6mTzgh0qRjbP_3FiZnAU8k3k0NOOj4LIHFkF0"
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet("Keys")
    all_records = worksheet.get_all_records()
    for r_index, r_item in enumerate(all_records):
        if r_item["key"] == user_key:
            cur_sessions = r_item["cur_sessions"] + 1
            cur_users = json.loads(r_item["cur_users"])
            cur_users.append(machine_id)
            cur_users = json.dumps(cur_users)
            worksheet.update_cell(r_index+2, 3, cur_sessions)
            worksheet.update_cell(r_index+2, 4, cur_users)
    updateUserKey(user_key=user_key, user_id=machine_id)
    return 

def decrementSessions(user_key: str) -> None:
    """
    уменьшает на 1 кол-во активных сессий
    user_key: int Ключ, который пользователь передал для проверки
    """
    machine_id = machineid.id()
    gc = gspread.service_account(filename="./server/WebTable/credentials.json")
    SPREADSHEET_ID = "14uH3sv6mTzgh0qRjbP_3FiZnAU8k3k0NOOj4LIHFkF0"
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet("Keys")
    all_records = worksheet.get_all_records()
    for r_index, r_item in enumerate(all_records):
        if r_item["key"] == user_key:
            cur_sessions = r_item["cur_sessions"] - 1
            worksheet.update_cell(r_index+2, 3, cur_sessions)
            cur_users = json.loads(r_item["cur_users"])
            cur_users.remove(machine_id)
            worksheet.update_cell(r_index+2, 4, json.dumps(cur_users))
    updateUserKey(user_key="", user_id="")
    return 

def getActualAppVersion() -> str:
    gc = gspread.service_account(filename="./server/WebTable/credentials.json")
    SPREADSHEET_ID = "14uH3sv6mTzgh0qRjbP_3FiZnAU8k3k0NOOj4LIHFkF0"
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet("Keys")
    all_records = worksheet.get_all_records()
    version = all_records[0]["actual_version"]
    return version