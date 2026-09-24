FROM python:3.11-slim

WORKDIR /tinyCPG

COPY requirements.txt ./
RUN pip install decorator attrs psutil absl-py "tensorflow>=1.10.0"
RUN pip install --no-cache-dir -r requirements.txt

COPY ./*.py ./
COPY ./*.sh ./
RUN chmod +x ./*.sh

ENTRYPOINT ["./entrypoint.sh"]
CMD ["./run_sim_mt.sh"]