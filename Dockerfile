FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn
RUN python -c "from zoneinfo import ZoneInfo; ZoneInfo('America/Lima'); ZoneInfo('Europe/Oslo')"

COPY app.py muhurta.py .
COPY prepare_ephemeris.py .
RUN python prepare_ephemeris.py
COPY test_ephemeris.py .
RUN python -m unittest test_ephemeris
COPY test_muhurta.py .
RUN python -m unittest test_muhurta

ENV PORT=8000
EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]

