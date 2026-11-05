## 0.4.4

### Traffic-engineering definitions and transparency

- Distinguished signal green from effective green.
- Added configurable start and end displacement, defaulting to 3 seconds each.
- Defined effective green as signal green minus start displacement plus end displacement.
- Added nominal lane capacity using `s(g/C)`.
- Added nominal degree of saturation using `q/c`.
- Renamed time-sliced capacity as simulated service capacity.
- Added simulated degree of saturation as a separate result.
- Retained the shared physical lane queue and FIFO-composition approximation.
- Rounded operational JSON and CSV values to two decimal places at serialisation only.
- Retained six decimal places for conservation and convergence diagnostics.
- Added signal-timing, capacity, DoS and output-rounding regression tests.
- Added a comprehensive traffic-engineering methodology chapter to the LaTeX manual.
