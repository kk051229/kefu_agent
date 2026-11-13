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
            # 注意：没有 user_id 参数了。查谁的券由"登录的是谁"决定，
            # 不能让模型（或用户）自己报一个编号 —— 那就等于谁都能查别人的券。
            "name": "get_coupon",
            "description": "查询当前登录用户的优惠券列表，不需要用户提供编号",
            "parameters": {
                "type": "object",
                "properties": {},
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
# 每个"跟订单有关"的工具都多收一个 当前用户 参数：
# 这个值只能来自登录态（令牌里解出来的），绝不能来自模型的参数。
#
# 查不到和"不是你的"故意回同一句话：如果别人的单说"不属于你"，
# 坏人就能拿订单号一个个试，摸出"哪些订单真实存在"。统一说"没找到"，什么都不透露。
def check_order(order_id, 当前用户=None):
    if not 当前用户:
        return "请先登录后再查询订单"
    row = db.get_order(order_id)
    if row is None or row.get("user_id") != 当前用户:
        return f"数据库中没有找到订单 {order_id}"
    return f"订单 {row['order_id']}，状态：{row['status']}，配送到：{row['address']}"


def tuikuan(order_id, 当前用户=None):
    if not 当前用户:
        return "请先登录后再申请退款"
    row = db.get_order(order_id)
    if row is None or row.get("user_id") != 当前用户:
        return f"数据库中没有找到订单 {order_id}，无法提交退款"
    return f"已为订单 {order_id} 提交退款申请，退款将在 3 个工作日内原路退回"


def study(question, 当前用户=None):
    db.create_ticket(question, 当前用户)   # 工单记下是谁提的
    return "已登记您的问题，请耐心等待客服处理"


def change_address(order_id, new_address, 当前用户=None):
    if not 当前用户:
        return "请先登录后再修改地址"
    # UPDATE 自带 user_id 条件：不是你的单，影响行数就是 0，根本改不动
    count = db.update_order(order_id, new_address, 当前用户)
    if count == 0:
        result = f"数据库中没有找到订单{order_id}，无法修改地址"
    else:
        result = f"订单{order_id}的地址已经修改为{new_address}"
    return result


def get_coupon(当前用户=None):
    if not 当前用户:
        return "请先登录后再查询优惠券"
    rows = db.get_coupons(当前用户)
    if len(rows) == 0:
        return f"数据库中没有找到用户{当前用户}的优惠劵"
    else:
        result = f"用户{当前用户}的优惠劵有："
        for row in rows:
            result += f"\n优惠劵编号:{row['id']}，优惠内容：{row['coupon_name']}，优惠金额：{row['amount']}"
        return result


def update_order_status(order_id, new_status, 当前用户=None):
    if not 当前用户:
        return "请先登录后再修改订单状态"
    row = db.get_order(order_id)          # 先查：在不在？是不是你的？
    if row is None or row.get("user_id") != 当前用户:   # 不在/不是你的 → 压根不改
        return f"数据库中没有找到订单{order_id}，无法修改状态"
    db.update_order_status(order_id, new_status, 当前用户)   # 在且是你的 → 放心改
    return f"您的订单{order_id}的状态已经修改成{new_status}"   # 报事实

def search_policy(question):
    """取 top3：一条政策可能只回答半个问题（比如"预售退款"要 p15+p7 两条）。"""
    q_vec = knowledge.embedder.embed(question)
    result = knowledge.collection.query(query_embeddings=[q_vec], n_results=3)
    docs = result["documents"][0]
    dists = result["distances"][0]

    # 放行与否只看第 1 名：第 1 名都不够像，说明这个问题知识库里根本没有
    if not dists or dists[0] >= 0.95:   # rag_eval.py 标定：域内最差 0.919，域外最近 1.053
        return "知识库中没有找到相关资料"

    # 第 1 名放行后，后面的只挑同样够像的，避免把八竿子打不着的段落也塞给模型
    命中 = [doc for doc, d in zip(docs, dists) if d < 0.95]
    if len(命中) == 1:
        return 命中[0]
    return "\n\n".join(f"[资料{i + 1}] {doc}" for i, doc in enumerate(命中))

            


# 模型只会给出"工具名 + 参数"，由这个函数负责真正调用 Python 函数
#
# 当前用户 由调用方从登录态取来传进来（graph.py / main.py 传的是 memory.user_id），
# 模型给的参数里就算混进了 user_id，也直接丢掉 —— 身份不能由"被服务的人"自己宣布。
收当前用户的工具 = {
    "check_order", "tuikuan", "study",
    "change_address", "get_coupon", "update_order_status",
}


def execute(name, args, 当前用户=None):
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

    参数 = dict(args)              # 拷一份，别改模型给的原始字典
    参数.pop("user_id", None)      # 身份只认登录态，模型说的一律不信
    if name in 收当前用户的工具:
        return func(当前用户=当前用户, **参数)
    return func(**参数)



