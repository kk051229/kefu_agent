# 客服 Agent 的镜像：把整个项目装进一个干净容器里跑
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先拷依赖清单再装：只是改了代码时，这一层能用缓存，不会重新装包
COPY requirements.txt .
RUN pip install -r requirements.txt

# 再拷代码
COPY . .

EXPOSE 8000

# 容器自己探活：健康检查返回 503 就会被标记为不健康
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
