FROM python:3.11-slim

WORKDIR /tinyCPG

COPY requirements.txt ./
RUN pip install decorator attrs psutil absl-py "tensorflow>=1.10.0"
RUN pip install --no-cache-dir -r requirements.txt

COPY ./*.py ./
COPY ./*.sh ./
# Species configs (PLAN.md P1) -- the model cannot start without them.
COPY config/ ./config/
# Rat reference scripts (rat-sh/README.md), incl. the default job below.
COPY rat-sh/ ./rat-sh/
RUN chmod +x ./*.sh ./rat-sh/*.sh

ENTRYPOINT ["./entrypoint.sh"]
CMD ["./rat-sh/run_sim_mt.sh"]
