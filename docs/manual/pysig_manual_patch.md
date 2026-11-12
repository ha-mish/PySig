# Manual integration order

Replace the corresponding existing chapters with the files in this package and add the
new dedicated short-lane and reference chapters.

Recommended `pysig_manual.tex` ordering:

```latex
\input{chapters/02_model_concepts}
\input{chapters/05_signal_control}
\input{chapters/06_demand_assignment}
\input{chapters/07_saturation_flow}
\input{chapters/08_optimisation}
\input{chapters/09_networks}
\input{chapters/10_results_testing}
\input{chapters/12_traffic_engineering_methodology}
\input{chapters/13_analytical_engine}
\input{chapters/14_short_lanes}

\appendix
\input{chapters/a_yaml_reference}
\input{chapters/b_equations}
\input{chapters/c_references}
```

Keep the existing Getting Started, intersection-building, lane/movement, troubleshooting
and acceptance chapters where they remain useful; update their cross-references to the
technical chapters above.
