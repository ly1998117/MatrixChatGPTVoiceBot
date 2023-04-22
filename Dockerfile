FROM python:3.10
COPY matrix_chatgpt_voice_bot /MatrixBot/matrix_chatgpt_voice_bot
COPY config/config.toml /MatrixBot/config/config.toml
COPY setup.py /MatrixBot/setup.py
COPY pyproject.toml /MatrixBot/pyproject.toml
VOLUME ["/MatrixBot/config"]
WORKDIR /MatrixBot
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential gcc libolm-dev  && \
    apt-get install -y ffmpeg && \
    pip install .
CMD ["python", "-m", "matrix_chatgpt_voice_bot.main"]