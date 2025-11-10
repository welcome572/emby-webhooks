FROM python:3.9

WORKDIR /app

# 使用国内镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip config set install.trusted-host pypi.tuna.tsinghua.edu.cn

# 复制现有文件
COPY app.py .
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 3000

# 使用 Python 直接运行（而不是 gunicorn）
CMD ["python", "app.py"]
