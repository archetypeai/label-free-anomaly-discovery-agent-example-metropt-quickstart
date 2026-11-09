# Prepared input files: data attribution

`metropt_A.csv`, `metropt_B.csv` and `metropt_C.csv` are derived from the **MetroPT-3
Dataset**:

> Davari, N., Veloso, B., Ribeiro, R., & Gama, J. (2021). *MetroPT-3 Dataset* [Dataset].
> UCI Machine Learning Repository. https://doi.org/10.24432/C5VW3R

Source: https://archive.ics.uci.edu/dataset/791/metropt+3+dataset

These files are licensed under the
[Creative Commons Attribution 4.0 International License (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/),
like the dataset they come from. They are **not** covered by this repository's Apache
License 2.0, which applies to its code.

**Changes made** (November 2026, by `prep/prepare.py` in this repository):

- the raw samples were snapped to a 10 s grid: holes of up to 50 s filled with the last
  value, longer gaps left as gaps;
- stretches where every channel was unchanged for 30 minutes or more (the logger froze)
  were removed;
- three date ranges were cut out: A, 2020-04-04 to 2020-04-25; B, 2020-07-01 to
  2020-07-22; C, 2020-03-01 to 2020-03-22;
- only the 7 analog channels were kept (`TP2`, `TP3`, `H1`, `DV_pressure`, `Reservoirs`,
  `Oil_temperature`, `Motor_current`);
- timestamps were written as seconds since 1970, on the dataset's own clock with no time
  zone shift.

The dataset's creators and their institutions are not involved in this example and do not
endorse it.
