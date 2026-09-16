FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 
PYTHONDONTWRITEBYTECODE=1 
PORT=5000 
NCS_TRUST_PROXY=1

WORKDIR /app

COPY requirements.txt ./

RUN pip install 
--no-cache-dir 
--disable-pip-version-check 
-r requirements.txt 
&& useradd 
--create-home 
--uid 10001 
ncsuser

COPY . .

RUN chown -R ncsuser:ncsuser /app

USER ncsuser

EXPOSE 5000

HEALTHCHECK 
--interval=30s 
--timeout=5s 
--start-period=15s 
--retries=3 
CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=3).read()"

CMD ["python", "app.py"]
