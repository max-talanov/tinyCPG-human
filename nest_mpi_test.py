import nest

rank = getattr(nest, "Rank", lambda: 0)()
nproc = getattr(nest, "NumProcesses", lambda: 1)()

print(f"Hello from rank {rank}/{nproc} | NEST {nest.__version__}")

# Minimal simulate to force initialization fully
nest.ResetKernel()
nest.Simulate(0.1)
print(f"After init rank {rank}/{nproc}")