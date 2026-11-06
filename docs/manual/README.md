# PySig 0.4.5 manual source

The manual's authoritative source is `pysig_manual.tex` plus the files under `chapters/`.

## Local build

Install a TeX Live distribution containing `latexmk`, `newtx`, `titlesec`, `listings`, `hyperref`, and the standard LaTeX packages used by the root file, then run:

```bash
cd docs/manual
latexmk -pdf -halt-on-error -interaction=nonstopmode pysig_manual.tex
```

Clean temporary files with:

```bash
latexmk -c
```

GitHub Actions builds the same root file automatically on changes under `docs/manual/`.
