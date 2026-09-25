FROM python:3.11-slim

WORKDIR /tinyCPG

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./*.py ./
COPY ./*.sh ./
# Species configs (PLAN.md P1) -- the model cannot start without them.
COPY config/ ./config/
# Rat reference scripts (rat-sh/README.md), for comparison runs.
COPY rat-sh/ ./rat-sh/
RUN chmod +x ./*.sh ./rat-sh/*.sh

ENTRYPOINT ["./entrypoint.sh"]
# Default job: the human model, five locomotion modes (debug-small, 120 s, lambda 1e-4),
# written to results/modes/human/. Pass other arguments to override, e.g.
#   docker run IMAGE ./run_modes_local.sh human 30000 1e-3 medium
# The rat container job is still available: docker run IMAGE --script=rat-sh/run_sim_mt.sh
CMD ["./run_modes_local.sh", "human"]
