import os

import pymysql
from dotenv import load_dotenv

load_dotenv()  # 读取 .env（LLM.py 里也调用了一次，重复加载没有副作用）

# 数据库配置统一从 .env 读取，不要写死在代码里
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "shop"),
    "charset": "utf8mb4",
    "connect_timeout": 5,  # 5 秒连不上就报错，避免程序无限卡住
}


def get_order(order_id):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        # DictCursor：结果按列名取值（row["status"]），表结构调顺序也不受影响
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
            return cursor.fetchone()
    finally:
        # 不管查询成功还是报错，都保证关闭连接，否则连接会越攒越多
        conn.close()
def update_order(order_id,new_address):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            count=cursor.execute("UPDATE orders SET address = %s WHERE order_id = %s", (new_address, order_id))
            conn.commit()
            return count
    finally:
        conn.close()

def update_order_status(order_id,new_status):
    conn=pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor(pymysql.cursors.DictCursor)as cursor:
            count=cursor.execute("UPDATE orders SET status =%s WHERE order_id = %s", (new_status,order_id))
            conn.commit()
            return count
    finally:
        conn.close()

def create_ticket(question):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO tickets (content) VALUES (%s)",(question,))
            conn.commit()
            return True
    finally:
        conn.close()

def get_coupons(user_id):
    conn=pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor(pymysql.cursors.DictCursor)as cursor:
            cursor.execute("SELECT * FROM coupons WHERE user_id=%s",(user_id,))
            return cursor.fetchall()
    finally:
        conn.close()

# 测试代码放在 __main__ 里：只有直接运行 python db.py 才会执行；
# 其他模块 import db 时不会触发数据库连接
if __name__ == "__main__":
    result = get_order("kx666")
    print(result)
