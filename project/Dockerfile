# syntax=docker/dockerfile:1
FROM python:3.10-alpine as builder
WORKDIR /code

RUN apk add --no-cache gcc musl-dev linux-headers

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt

FROM python:3.10-alpine
WORKDIR /code

COPY --from=builder /wheels /wheels
COPY --from=builder /code/requirements.txt .
RUN pip install --no-cache /wheels/*

COPY src/ .
RUN addgroup --gid 1001 --system app && \
    adduser --no-create-home --shell /bin/false --disabled-password --uid 1001 --system app

RUN mkdir /code/data
RUN chown -R app:app /code/data
USER app:app
CMD ["python", "app.py"]
