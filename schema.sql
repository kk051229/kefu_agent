-- 建库建表 + 演示数据
-- 用法（本机 MySQL）：mysql -u root -p < schema.sql
-- 用法（Docker）：docker-compose 启动时自动执行（挂到 /docker-entrypoint-initdb.d）
--
-- 注意：这个脚本是"重置演示数据"用的，会先删后插。
-- 已经跑起来的老库不要直接执行，改用 python migrate_auth.py（幂等，不动数据）。

CREATE DATABASE IF NOT EXISTS shop
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE shop;

-- 用户表：登录用
-- password_hash 存的是"加盐哈希"（见 auth.py），绝不存明文密码
CREATE TABLE IF NOT EXISTS users (
  user_id       varchar(20) NOT NULL,
  password_hash varchar(200) NOT NULL,
  created_at    datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 订单表：user_id = 这单是谁的。所有改订单的 SQL 都必须带上它
CREATE TABLE IF NOT EXISTS orders (
  order_id varchar(20) NOT NULL,
  user_id  varchar(20) DEFAULT NULL,
  status   varchar(20) DEFAULT NULL,
  address  varchar(50) DEFAULT NULL,
  PRIMARY KEY (order_id),
  KEY idx_orders_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 优惠券表
CREATE TABLE IF NOT EXISTS coupons (
  id          int NOT NULL AUTO_INCREMENT,
  user_id     varchar(20) NOT NULL,
  coupon_name varchar(20) DEFAULT NULL,
  amount      decimal(10,2) DEFAULT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 人工工单表：user_id = 谁提的，人工客服好回访
CREATE TABLE IF NOT EXISTS tickets (
  id         int NOT NULL AUTO_INCREMENT,
  user_id    varchar(20) DEFAULT NULL,
  status     varchar(20) DEFAULT '未处理',
  content    varchar(100) NOT NULL,
  created_at datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 演示数据（重复执行不会报错：先删后插）
-- 演示账号 u001 / u002，密码都是 123456（哈希是 auth.py 生成的，不是明文）
DELETE FROM users;
INSERT INTO users (user_id, password_hash) VALUES
  ('u001', 'pbkdf2_sha256$200000$ee8e67d84632b2396f2302d953c5da0f$5fc9aa9a5fe37a1a3680ccfaec0b5eaaa9d942d2e47e6076ed4e7257bb1c54be'),
  ('u002', 'pbkdf2_sha256$200000$1b4f6de63284fb8dba5122a1eef0dbce$d110d51df503696cf1c2364f5abd0649c3d13422f00b26769c88f432539b9835');

DELETE FROM orders;
INSERT INTO orders (order_id, user_id, status, address) VALUES
  ('kx666', 'u001', '派送中', '北京朝阳区'),
  ('kx888', 'u002', '已签收', '广州天河区'),
  ('kx999', 'u002', '已签收', '火星第一大道');

DELETE FROM coupons;
INSERT INTO coupons (user_id, coupon_name, amount) VALUES
  ('u001', '满100-10', 10.00),
  ('u001', '满50-5',   5.00),
  ('u002', '满200-30', 30.00);
