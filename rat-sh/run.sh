#!/bin/bash -l
#SBATCH --job-name=CPG_NEST
#SBATCH --output=Nest_processing_%A_%a.slurmout
#SBATCH --error=Nest_processing_%A_%a.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --array=0-9
#SBATCH --cpus-per-task=64
#SBATCH --time=12:00:00
#SBATCH --partition=acc

export LANG=${LANG:-C.UTF-8}
export LC_ALL=${LC_ALL:-C.UTF-8}
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "[Slurm] ntasks=$SLURM_NTASKS cpus-per-task=$SLURM_CPUS_PER_TASK array_task=${SLURM_ARRAY_TASK_ID:-NA}"

python3 - <<'PY'
import nest
ks = nest.GetKernelStatus()
mpi = ks.get("mpi_num_processes", ks.get("num_processes", ks.get("total_num_processes", 1)))
thr = ks.get("local_num_threads", ks.get("num_threads", ks.get("threads", 1)))
print("nest", nest.__version__, "mpi_procs", mpi, "local_threads", thr)
PY

# 10 diagnostic (mu,CV) pairs (Option C)
SWEEP_PAIRS="0:0,0.5:0.8,1.0:0.6,2.0:0.45,3.5:0.30,5.0:0.20,7.0:0.15,9.0:0.10,12.0:0.08,16.0:0.05"
OUTDIR="results/"
TAG="bursting_paced_120s"
BASE_SEED=12345

srun --cpu-bind=cores --distribution=block:block \
  python3 -u cpg_2legs_fast.py \
    --out cpg_run.h5 \
    --outdir "$OUTDIR" \
    --tag "$TAG" \
    --seed $BASE_SEED \
    --sweep-pairs "$SWEEP_PAIRS" \
    --sweep-run-idx ${SLURM_ARRAY_TASK_ID} \
    --sweep-dist lognormal_cv \
    --sim-ms 120000 \
    --dt-ms 10 \
    --threads $SLURM_CPUS_PER_TASK \
    --nest-verbosity M_ERROR \
    --max-weight-conns 2000 \
    --save-weights snapshots \
    --delay-model length_velocity \
    --species rat \
    --delay-jitter-ms 0.2 \
    --weight-sample-ms 1000 \
    --rate-update-ms 100 \
    --simulate-chunk-ms 100 \
    --bs-base-hz 6 \
    --bs-noise-std-hz 0.25 \
    --enforce-tonic-bs \
    --paced-gait \
    --step-period-ms 520 \
    --stance-fraction 0.5 \
    --n-ia-groups 3 \
    --ia-ext-hz 60 80 100 \
    --ia-ext-f-hz 80 \
    --long-run
