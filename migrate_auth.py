"""给已经建好的老数据库补上"登录"需要的东西。

为什么不用 schema.sql：那是"重置演示数据"脚本，会先删后插；
老库里可能已经有你自己的数据，不能那么干。

这个脚本是**幂等**的：跑一遍、跑十遍，结果都一样，不删任何数据。

做了什么：
1. 建 users 表（已经存在就跳过）
2. orders 加 user_id 列（没有才加）
3. tickets 加 user_id 列（没有才加）
4. 补两个演示账号 u001 / u002，密码 123456（已经存在就跳过）
5. 把演示订单挂到演示账号名下（已经有主人的不动）

用法：python migrate_auth.py
"""
import pymysql

import auth
import db

库名 = db.DB_CONFIG["database"]


def 建表(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
          user_id       varchar(20) NOT NULL,
          password_hash varchar(200) NOT NULL,
          created_at    datetime DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("① users 表：就绪")


def 有列(cursor, 表名, 列名):
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        (库名, 表名, 列名),
    )
    return cursor.fetchone()[0] > 0


def 加列(cursor):
    # MySQL 8 不支持 "ADD COLUMN IF NOT EXISTS"，只能自己先查一下
    if 有列(cursor, "orders", "user_id"):
        print("② orders.user_id：已经有了")
    else:
        cursor.execute("ALTER TABLE orders ADD COLUMN user_id varchar(20) DEFAULT NULL, ADD KEY idx_orders_user (user_id)")
        print("② orders.user_id：已添加")

    if 有列(cursor, "tickets", "user_id"):
        print("③ tickets.user_id：已经有了")
    else:
        cursor.execute("ALTER TABLE tickets ADD COLUMN user_id varchar(20) DEFAULT NULL")
        print("③ tickets.user_id：已添加")


def 补演示账号(cursor):
    for 账号 in ("u001", "u002"):
        cursor.execute("SELECT COUNT(*) FROM users WHERE user_id = %s", (账号,))
        if cursor.fetchone()[0] > 0:
            print(f"④ 演示账号 {账号}：已经存在")
            continue
        cursor.execute(
            "INSERT INTO users (user_id, password_hash) VALUES (%s, %s)",
            (账号, auth.生成密码哈希("123456")),   # 密码 123456，存的是哈希
        )
        print(f"④ 演示账号 {账号}：已创建（密码 123456）")


def 挂订单(cursor):
    """演示订单默认挂给演示账号；已经有主人的订单不碰。"""
    归属 = {"kx666": "u001", "kx888": "u002", "kx999": "u002"}
    for 订单号, 用户 in 归属.items():
        cursor.execute(
            "UPDATE orders SET user_id = %s WHERE order_id = %s AND user_id IS NULL",
            (用户, 订单号),
        )
        if cursor.rowcount:
            print(f"⑤ 订单 {订单号} → {用户}：已挂好")


def main():
    conn = pymysql.connect(**db.DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            建表(cursor)
            加列(cursor)
            conn.commit()          # 表结构改完先提交
            补演示账号(cursor)
            挂订单(cursor)
            conn.commit()
    finally:
        conn.close()
    print("\n完成。演示账号：u001 / u002，密码 123456")
    print("没挂主人的老订单 user_id 是 NULL：谁都查不到，需要手动 UPDATE 指派。")


if __name__ == "__main__":
    main()
