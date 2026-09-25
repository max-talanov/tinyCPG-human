#!/bin/bash -l
#SBATCH --job-name=Neuron_calc
#SBATCH --output=Neuron_comp.slurmout
#SBATCH --error=Neuron_comp.slurmerr
#SBATCH --nodes=1
#SBATCH --ntasks=50
#SBATCH --ntasks-per-node=50
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --partition=gp_bsccs

srun -n 2 python3 -u nest_mpi_test.py