# Paper build Makefile.
# Targets:
#   make pdf      → compile main.tex with bibtex (full bibliography pass)
#   make quick    → single pdflatex pass (no bibtex, useful when iterating prose)
#   make clean    → remove all latex aux files
#   make figures  → regenerate figures/*.png from the latest results/<date>/ (see INDIR)
#   make params   → regenerate params.tex from the model source

LATEXMK    = latexmk -pdf -interaction=nonstopmode
PDFLATEX   = pdflatex -interaction=nonstopmode
BIBTEX     = bibtex
MAIN       = main

.PHONY: pdf quick clean figures params all

all: pdf

pdf:
	$(LATEXMK) $(MAIN).tex

quick:
	$(PDFLATEX) $(MAIN).tex

clean:
	latexmk -C
	rm -f *.aux *.log *.bbl *.blg *.out *.toc *.synctex.gz sections/*.aux

# Regenerate figures from a dated results/ folder pulled back from MN5.
# Usage: make figures INDIR=../results/2026-07-14
PY    ?= /opt/homebrew/bin/python3
INDIR ?= ../results/2026-07-14

figures:
	$(PY) ../scripts/cpg_architecture_diagram.py
	$(PY) ../scripts/cpg_connectivity_figure.py \
		--in ../results/connectivity/conn_dump_sensory.h5 --out figures/fig_connectivity.png
	$(PY) ../scripts/cpg_stdp_weight_matrix.py --indir $(INDIR) --out figures/fig_stdp_weight_matrix.png
	$(PY) ../scripts/cpg_stdp_weights_grid.py  --indir $(INDIR) --out figures/fig_stdp_weights_grid.png
	for lam in lam1em2 lam1em3 lam1em4 lam1em5 lam1em6; do \
		$(PY) ../scripts/cpg_force_stages.py --indir $(INDIR) --lambda-tag $$lam \
			--out figures/fig_force_stages_$$lam.png; \
		$(PY) ../scripts/cpg_network_matrix.py --indir $(INDIR) --lambda-tag $$lam \
			--out figures/fig_network_matrix_$$lam.png; \
	done
	$(PY) ../scripts/cpg_mode_lambda_summary.py --indir $(INDIR) --out figures/fig_mode_lambda
	cp figures/fig_mode_lambda_table.tex mode_lambda_table.tex
	$(PY) ../scripts/cpg_epidural_contrast.py --stim-dir $(INDIR) --natural-dir $(INDIR) \
		--out figures/fig9_epidural_contrast.png

params:
	$(PY) ../scripts/cpg_param_table.py \
		--src ../cpg_2legs_fast.py --format latex --out params.tex
