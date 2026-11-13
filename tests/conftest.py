"""pytest 的公共配置。

这个文件会被 pytest 自动加载，里面的 fixture 所有测试文件都能用。
"""
import logging

# 测试里会故意制造"模型报错""工具报错"，日志会把整屏刷满，
# 这里统一掐掉；真出问题时把这一行注释掉就能看到完整堆栈。
logging.disable(logging.CRITICAL)
