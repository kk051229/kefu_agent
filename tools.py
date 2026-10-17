import db
import knowledge
import embedding

# ============ 工具的 JSON Schema（给模型看的"说明书"） ============
# 模型就是根据这些描述来决定：调用哪个工具、传什么参数。
# 描述写得越具体，模型越不容易搞错。
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_order",
            "description": "根据订单号查询订单的物流状态和配送地址",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "订单号，例如 kx666、kx888",
                    },
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tuikuan",
            "description": "为用户提交退款申请，需要用户提供要退款的订单号",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "用户要退款的订单号",
                    },
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "study",
            "description": "遇到当前解决不了、还没学过的问题，或者用户明确要求人工服务时，转接人工客服",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "用户的问题",
                    },
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "change_address",
            "description": "用于修改用户的订单配送地址，需要用户提供新的配送地址",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "用户要修改地址的配送号",
                    },
                    "new_address": {
                        "type": "string",
                        "description": "用户要修改的新的配送地址",
                    },
                },
                "required": ["order_id", "new_address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_coupon",
            "description": "用于查询用户的优惠券列表，需要用户提供用户编号；如果用户没有提供编号，需要先向用户询问编号",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "用户id",
                    },
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_order_status",
            "description": "用于修改用户的订单状态，需要用户提供新的订单状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "用户要修改的订单状态的订单号",
                    },
                    "new_status": {
                        "type": "string",
                        "description": "用户要修改的新订单状态",
                    },
                },
                "required": ["order_id", "new_status"],
            },
        },
    },
    {
        "type":"function",
        "function":{
            "name":"search_policy",
            "description":"查询公司政策知识库（退货、发货、运费、发票等），遇到政策类问题时调用",
            "parameters":{
                "type":"object",
                "properties":{
                    "question":{
                        "type":"string",
                        "description":"用户问题原文",
                    },
                },
                "required":["question"],
            },
        },
    },
]


# ============ 工具的实际实现（给 Python 用的函数） ============
def check_order(order_id):
    row = db.get_order(order_id)
    if row is None:
        return f"数据库中没有找到订单 {order_id}"
    return f"订单 {row['order_id']}，状态：{row['status']}，配送到：{row['address']}"


def tuikuan(order_id):
    return f"已为订单 {order_id} 提交退款申请，退款将在 3 个工作日内原路退回"


def study(question):
    db.create_ticket(question)
    return "已登记您的问题，请耐心等待客服处理"


def change_address(order_id, new_address):
    count = db.update_order(order_id, new_address)
    if count == 0:
        result = f"数据库中没有找到订单{order_id}，无法修改地址"
    else:
        result = f"订单{order_id}的地址已经修改为{new_address}"
    return result


def get_coupon(user_id):
    rows = db.get_coupons(user_id)
    if len(rows) == 0:
        return f"数据库中没有找到用户{user_id}的优惠劵"
    else:
        result = f"用户{user_id}的优惠劵有："
        for row in rows:
            result += f"\n优惠劵编号:{row['id']}，优惠内容：{row['coupon_name']}，优惠金额：{row['amount']}"
        return result


def update_order_status(order_id, new_status):
    row = db.get_order(order_id)          # 先查：在不在？
    if row is None:                       # 不在 → 直接报错，压根不改
        return f"数据库中没有找到订单{order_id}，无法修改状态"
    db.update_order_status(order_id, new_status)   # 在 → 放心改
    return f"您的订单{order_id}的状态已经修改成{new_status}"   # 报事实

def search_policy(question):
    q_vec = knowledge.embedder.embed(question)
    result = knowledge.collection.query(query_embeddings=[q_vec], n_results=1)
    doc = result["documents"][0][0]
    distance = result["distances"][0][0]
    if distance < 0.9:
        return doc
    return "知识库中没有找到相关资料"

            


# 模型只会给出"工具名 + 参数"，由这个函数负责真正调用 Python 函数
def execute(name, args):
    funcs = {
        "check_order": check_order,
        "tuikuan": tuikuan,
        "study": study,
        "change_address": change_address,
        "get_coupon": get_coupon,
        "update_order_status": update_order_status,
        "search_policy":search_policy
    }
    func = funcs.get(name)
    if func is None:
        return f"未知工具：{name}"
    return func(**args)



