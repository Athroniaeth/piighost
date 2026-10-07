# Decision-guard benchmark, results

## Held out by template

The threshold is chosen on 27 templates, the most leaks caught with at most 5% false alarms there, and applied to the template left out. It sits halfway in the gap the training scores leave open, the last column gives the counts at the low and the high end of that gap. The counts are summed over the 28 templates. Intervals come from a cluster bootstrap over the templates (2,000 resamples, the held-out flags fixed).

| Guard | AUROC (cluster 95 % CI) | Caught, held out | 95 % CI | False alarms, held out | 95 % CI | Thresholds chosen (min, median, max) | Threshold low / high in the gap, caught and false alarms |
|---|---|---|---|---|---|---|---|
| Laya (English) | 0.50 (0.44 to 0.56) | 4/100 (4 %) | 0.00 to 0.11 | 7/100 (7 %) | 0.00 to 0.18 | 0.929, 0.936, 0.936 | 4/7 and 4/7 |
| Laya, placeholder hint | 0.52 (0.44 to 0.60) | 3/100 (3 %) | 0.00 to 0.09 | 3/100 (3 %) | 0.00 to 0.09 | 0.899, 0.901, 0.903 | 4/7 and 3/3 |
| laya-multilingual | 0.50 (0.44 to 0.56) | 0/100 (0 %) | 0.00 to 0.00 | 0/100 (0 %) | 0.00 to 0.00 | 1.000, 1.000, 1.000 | 0/0 and 0/0 |
| Laya (English), two-option choice | 0.51 (0.45 to 0.58) | 5/100 (5 %) | 0.00 to 0.14 | 7/100 (7 %) | 0.00 to 0.18 | 0.934, 0.959, 0.959 | 5/7 and 5/7 |
| Gliner2GuardRail | 0.61 (0.56 to 0.66) | 14/100 (14 %) | 0.03 to 0.26 | 6/100 (6 %) | 0.00 to 0.15 | 0.376, 0.473, 0.507 | 15/6 and 14/6 |
| GLiNER2 spans, raw | 0.84 (0.78 to 0.90) | 60/100 (60 %) | 0.49 to 0.71 | 7/100 (7 %) | 0.00 to 0.18 | 0.972, 0.974, 0.975 | 60/7 and 59/5 |
| GLiNER2 spans, placeholders ignored | 0.94 (0.90 to 0.98) | 83/100 (83 %) | 0.73 to 0.92 | 7/100 (7 %) | 0.00 to 0.18 | 0.865, 0.895, 0.897 | 83/7 and 82/7 |

Fixed thresholds, with cluster bootstrap intervals (in sample, the thresholds were not chosen on other data):

| Guard | Caught at 0.5 | False alarms at 0.5 | Caught at 0.9 | False alarms at 0.9 |
|---|---|---|---|---|
| Laya (English) | 69/100 (0.52 to 0.84) | 60/100 (0.42 to 0.76) | 6/100 (0.00 to 0.15) | 11/100 (0.00 to 0.23) |
| Laya, placeholder hint | 81/100 (0.68 to 0.93) | 81/100 (0.65 to 0.94) | 4/100 (0.00 to 0.10) | 7/100 (0.00 to 0.18) |
| laya-multilingual | 81/100 (0.66 to 0.93) | 81/100 (0.67 to 0.94) | 68/100 (0.50 to 0.84) | 73/100 (0.56 to 0.88) |
| Laya (English), two-option choice | 86/100 (0.74 to 0.96) | 82/100 (0.67 to 0.94) | 24/100 (0.11 to 0.39) | 25/100 (0.10 to 0.42) |
| Gliner2GuardRail | 11/100 (0.03 to 0.20) | 3/100 (0.00 to 0.09) | 1/100 (0.00 to 0.03) | 0/100 (0.00 to 0.00) |
| GLiNER2 spans, raw | 100/100 (1.00 to 1.00) | 100/100 (1.00 to 1.00) | 89/100 (0.79 to 0.96) | 50/100 (0.32 to 0.67) |
| GLiNER2 spans, placeholders ignored | 97/100 (0.93 to 1.00) | 49/100 (0.32 to 0.67) | 83/100 (0.73 to 0.92) | 3/100 (0.00 to 0.09) |

The same rule across languages, the threshold chosen on one language and applied to the other:

| Guard | Chosen on | Applied to | Threshold (mid) | Caught | False alarms | Low end: threshold, caught, false alarms | High end: threshold, caught, false alarms |
|---|---|---|---|---|---|---|---|
| Laya (English) | FR | EN | 0.929 | 4/50 | 7/50 | 0.928, 4, 7 | 0.931, 4, 7 |
| Laya (English) | EN | FR | 0.955 | 0/50 | 0/50 | 0.955, 0, 0 | inf, 0, 0 |
| Laya, placeholder hint | FR | EN | 0.914 | 0/50 | 0/50 | 0.911, 0, 0 | 0.918, 0, 0 |
| Laya, placeholder hint | EN | FR | 0.901 | 3/50 | 3/50 | 0.901, 3, 3 | 0.901, 3, 3 |
| laya-multilingual | FR | EN | 1.000 | 0/50 | 0/50 | 1.000, 0, 0 | inf, 0, 0 |
| laya-multilingual | EN | FR | 1.000 | 0/50 | 0/50 | 1.000, 0, 0 | inf, 0, 0 |
| Laya (English), two-option choice | FR | EN | 0.937 | 8/50 | 7/50 | 0.934, 8, 8 | 0.941, 6, 7 |
| Laya (English), two-option choice | EN | FR | 0.982 | 0/50 | 0/50 | 0.982, 0, 0 | 0.983, 0, 0 |
| Gliner2GuardRail | FR | EN | 0.473 | 7/50 | 3/50 | 0.473, 7, 3 | 0.474, 7, 3 |
| Gliner2GuardRail | EN | FR | 0.740 | 4/50 | 0/50 | 0.719, 4, 0 | 0.761, 4, 0 |
| GLiNER2 spans, raw | FR | EN | 0.972 | 30/50 | 3/50 | 0.972, 30, 3 | 0.973, 30, 3 |
| GLiNER2 spans, raw | EN | FR | 0.978 | 29/50 | 1/50 | 0.978, 29, 1 | 0.978, 29, 1 |
| GLiNER2 spans, placeholders ignored | FR | EN | 0.862 | 43/50 | 9/50 | 0.813, 44, 11 | 0.910, 39, 3 |
| GLiNER2 spans, placeholders ignored | EN | FR | 0.978 | 27/50 | 0/50 | 0.978, 27, 0 | 0.978, 27, 0 |

## Paired tests

Exact two-sided sign test, ties dropped. Wilcoxon signed-rank (normal approximation) as a check. The template-level sign test compares the mean gap of each of the 28 templates, so it does not assume that texts of one template are independent.

| Guard | Pair | Pairs | First higher / tie / second higher | Sign test p | Wilcoxon p | Templates, first higher / second higher | Template sign test p |
|---|---|---|---|---|---|---|---|
| Laya (English) | leak vs clean twin | 100 | 54 / 0 / 46 | 0.48 | 0.3 | 17 / 11 | 0.34 |
| Laya (English) | de-identified clean vs original | 100 | 85 / 0 / 15 | 4.8e-13 | 1.6e-13 | 24 / 4 | 0.00018 |
| Laya, placeholder hint | leak vs clean twin | 100 | 40 / 0 / 60 | 0.057 | 0.085 | 10 / 18 | 0.18 |
| Laya, placeholder hint | de-identified clean vs original | 100 | 100 / 0 / 0 | 1.6e-30 | 3.9e-18 | 28 / 0 | 7.5e-09 |
| laya-multilingual | leak vs clean twin | 100 | 39 / 19 / 42 | 0.82 | 0.4 | 7 / 17 | 0.064 |
| laya-multilingual | de-identified clean vs original | 100 | 94 / 1 / 5 | 2.4e-22 | 1.5e-17 | 28 / 0 | 7.5e-09 |
| Laya (English), two-option choice | leak vs clean twin | 100 | 50 / 1 / 49 | 1 | 0.86 | 16 / 12 | 0.57 |
| Laya (English), two-option choice | de-identified clean vs original | 100 | 87 / 0 / 13 | 1.3e-14 | 1.5e-14 | 25 / 3 | 2.7e-05 |
| Gliner2GuardRail | leak vs clean twin | 100 | 72 / 0 / 28 | 1.3e-05 | 0.00095 | 23 / 5 | 0.00091 |
| Gliner2GuardRail | de-identified clean vs original | 100 | 22 / 0 / 78 | 1.6e-08 | 1.5e-08 | 5 / 23 | 0.00091 |
| GLiNER2 spans, raw | leak vs clean twin | 100 | 87 / 0 / 13 | 1.3e-14 | 9.7e-15 | 28 / 0 | 7.5e-09 |
| GLiNER2 spans, raw | de-identified clean vs original | 100 | 0 / 0 / 100 | 1.6e-30 | 3.9e-18 | 0 / 28 | 7.5e-09 |
| GLiNER2 spans, placeholders ignored | leak vs clean twin | 100 | 97 / 1 / 2 | 1.6e-26 | 7.3e-18 | 28 / 0 | 7.5e-09 |
| GLiNER2 spans, placeholders ignored | de-identified clean vs original | 100 | 0 / 0 / 100 | 1.6e-30 | 3.9e-18 | 0 / 28 | 7.5e-09 |

## Adding Laya to the span detector, or lowering its threshold

Each rule, then the span detector alone at the threshold that catches at least as many leaks with the fewest false alarms (in sample).

| Rule | Caught | False alarms | Spans alone, threshold | Caught | False alarms |
|---|---|---|---|---|---|
| spans >= 0.9 OR Laya >= 0.5 | 95/100 | 60/100 | 0.645 | 95/100 | 32/100 |
| spans >= 0.9 OR Laya >= 0.6 | 94/100 | 57/100 | 0.697 | 94/100 | 28/100 |
| spans >= 0.9 OR Laya >= 0.7 | 92/100 | 45/100 | 0.762 | 92/100 | 20/100 |
| spans >= 0.9 OR Laya >= 0.8 | 89/100 | 32/100 | 0.807 | 89/100 | 14/100 |
| spans >= 0.9 OR Laya >= 0.9 | 83/100 | 14/100 | 0.902 | 83/100 | 3/100 |
| spans >= 0.5 AND Laya >= 0.5 | 66/100 | 29/100 | 0.948 | 66/100 | 3/100 |
| spans >= 0.6 AND Laya >= 0.6 | 58/100 | 20/100 | 0.962 | 58/100 | 3/100 |
| spans >= 0.7 AND Laya >= 0.7 | 43/100 | 11/100 | 0.987 | 43/100 | 0/100 |
| spans >= 0.8 AND Laya >= 0.8 | 19/100 | 0/100 | 0.998 | 19/100 | 0/100 |
| spans >= 0.9 AND Laya >= 0.9 | 6/100 | 0/100 | 1.000 | 6/100 | 0/100 |

## At a glance

| Guard | AUROC | AUROC FR | AUROC EN | Caught at 0.5 | False alarms at 0.5 | Median latency |
|---|---|---|---|---|---|---|
| Laya (English) | 0.50 | 0.52 | 0.47 | 69/100 (69 %) | 60/100 (60 %) | 708 ms |
| Laya, placeholder hint | 0.52 | 0.52 | 0.51 | 81/100 (81 %) | 81/100 (81 %) | 744 ms |
| laya-multilingual | 0.50 | 0.50 | 0.49 | 81/100 (81 %) | 81/100 (81 %) | 390 ms |
| Laya (English), two-option choice | 0.51 | 0.52 | 0.51 | 86/100 (86 %) | 82/100 (82 %) | 678 ms |
| Gliner2GuardRail | 0.61 | 0.62 | 0.60 | 11/100 (11 %) | 3/100 (3 %) | 330 ms |
| GLiNER2 spans, raw | 0.84 | 0.87 | 0.82 | 100/100 (100 %) | 100/100 (100 %) | 402 ms |
| GLiNER2 spans, placeholders ignored | 0.94 | 0.97 | 0.92 | 97/100 (97 %) | 49/100 (49 %) | 430 ms |

## Laya (English)

| Threshold | Caught | 95 % CI | False alarms | 95 % CI | Caught FR | Alarms FR | Caught EN | Alarms EN |
|---|---|---|---|---|---|---|---|---|
| 0.1 | 96/100 (96 %) | 0.90 to 0.98 | 97/100 (97 %) | 0.92 to 0.99 | 50/50 | 50/50 | 46/50 | 47/50 |
| 0.2 | 89/100 (89 %) | 0.81 to 0.94 | 87/100 (87 %) | 0.79 to 0.92 | 48/50 | 47/50 | 41/50 | 40/50 |
| 0.3 | 83/100 (83 %) | 0.74 to 0.89 | 77/100 (77 %) | 0.68 to 0.84 | 45/50 | 41/50 | 38/50 | 36/50 |
| 0.4 | 77/100 (77 %) | 0.68 to 0.84 | 71/100 (71 %) | 0.61 to 0.79 | 41/50 | 35/50 | 36/50 | 36/50 |
| 0.5 | 69/100 (69 %) | 0.59 to 0.77 | 60/100 (60 %) | 0.50 to 0.69 | 34/50 | 25/50 | 35/50 | 35/50 |
| 0.6 | 61/100 (61 %) | 0.51 to 0.70 | 57/100 (57 %) | 0.47 to 0.66 | 29/50 | 25/50 | 32/50 | 32/50 |
| 0.7 | 48/100 (48 %) | 0.38 to 0.58 | 45/100 (45 %) | 0.36 to 0.55 | 20/50 | 18/50 | 28/50 | 27/50 |
| 0.8 | 24/100 (24 %) | 0.17 to 0.33 | 29/100 (29 %) | 0.21 to 0.39 | 14/50 | 14/50 | 10/50 | 15/50 |
| 0.9 | 6/100 (6 %) | 0.03 to 0.12 | 11/100 (11 %) | 0.06 to 0.19 | 1/50 | 4/50 | 5/50 | 7/50 |

Caught at 0.5 by leak type: name 8/12, variant 3/10, partial 6/10, email 7/12, phone 8/12, iban 10/12, address 12/12, id 7/10, split 8/10.
False alarms at 0.5 by placeholder count: 4 to 6 7/22, 7 to 8 47/66, 11 to 15 6/12.
Latency per text: median 708 ms, p90 1127 ms, max 3733 ms.
Calibration: ECE 0.233, Brier 0.319. Bins (score range, n, mean score, share leaking): 0.0-0.1 n=7 0.06/0.57; 0.1-0.2 n=17 0.16/0.41; 0.2-0.3 n=16 0.24/0.38; 0.3-0.4 n=12 0.35/0.50; 0.4-0.5 n=19 0.45/0.42; 0.5-0.6 n=11 0.55/0.73; 0.6-0.7 n=25 0.67/0.52; 0.7-0.8 n=40 0.77/0.60; 0.8-0.9 n=36 0.83/0.50; 0.9-1.0 n=17 0.94/0.35.
Texts truncated by Laya's window: 0.

## Laya, placeholder hint

| Threshold | Caught | 95 % CI | False alarms | 95 % CI | Caught FR | Alarms FR | Caught EN | Alarms EN |
|---|---|---|---|---|---|---|---|---|
| 0.1 | 100/100 (100 %) | 0.96 to 1.00 | 100/100 (100 %) | 0.96 to 1.00 | 50/50 | 50/50 | 50/50 | 50/50 |
| 0.2 | 96/100 (96 %) | 0.90 to 0.98 | 93/100 (93 %) | 0.86 to 0.97 | 50/50 | 50/50 | 46/50 | 43/50 |
| 0.3 | 88/100 (88 %) | 0.80 to 0.93 | 86/100 (86 %) | 0.78 to 0.91 | 49/50 | 50/50 | 39/50 | 36/50 |
| 0.4 | 86/100 (86 %) | 0.78 to 0.91 | 83/100 (83 %) | 0.74 to 0.89 | 48/50 | 47/50 | 38/50 | 36/50 |
| 0.5 | 81/100 (81 %) | 0.72 to 0.87 | 81/100 (81 %) | 0.72 to 0.87 | 44/50 | 45/50 | 37/50 | 36/50 |
| 0.6 | 72/100 (72 %) | 0.63 to 0.80 | 72/100 (72 %) | 0.63 to 0.80 | 38/50 | 39/50 | 34/50 | 33/50 |
| 0.7 | 48/100 (48 %) | 0.38 to 0.58 | 38/100 (38 %) | 0.29 to 0.48 | 23/50 | 19/50 | 25/50 | 19/50 |
| 0.8 | 16/100 (16 %) | 0.10 to 0.24 | 18/100 (18 %) | 0.12 to 0.27 | 13/50 | 14/50 | 3/50 | 4/50 |
| 0.9 | 4/100 (4 %) | 0.02 to 0.10 | 7/100 (7 %) | 0.03 to 0.14 | 3/50 | 3/50 | 1/50 | 4/50 |

Caught at 0.5 by leak type: name 10/12, variant 6/10, partial 6/10, email 11/12, phone 11/12, iban 9/12, address 12/12, id 9/10, split 7/10.
False alarms at 0.5 by placeholder count: 4 to 6 18/22, 7 to 8 55/66, 11 to 15 8/12.
Latency per text: median 744 ms, p90 976 ms, max 1751 ms.
Calibration: ECE 0.219, Brier 0.304. Bins (score range, n, mean score, share leaking): 0.1-0.2 n=11 0.15/0.36; 0.2-0.3 n=15 0.23/0.53; 0.3-0.4 n=5 0.36/0.40; 0.4-0.5 n=7 0.46/0.71; 0.5-0.6 n=18 0.57/0.50; 0.6-0.7 n=58 0.66/0.41; 0.7-0.8 n=52 0.73/0.62; 0.8-0.9 n=23 0.84/0.52; 0.9-1.0 n=11 0.91/0.36.
Texts truncated by Laya's window: 0.

## laya-multilingual

| Threshold | Caught | 95 % CI | False alarms | 95 % CI | Caught FR | Alarms FR | Caught EN | Alarms EN |
|---|---|---|---|---|---|---|---|---|
| 0.1 | 88/100 (88 %) | 0.80 to 0.93 | 95/100 (95 %) | 0.89 to 0.98 | 45/50 | 50/50 | 43/50 | 45/50 |
| 0.2 | 88/100 (88 %) | 0.80 to 0.93 | 93/100 (93 %) | 0.86 to 0.97 | 45/50 | 49/50 | 43/50 | 44/50 |
| 0.3 | 85/100 (85 %) | 0.77 to 0.91 | 91/100 (91 %) | 0.84 to 0.95 | 43/50 | 47/50 | 42/50 | 44/50 |
| 0.4 | 83/100 (83 %) | 0.74 to 0.89 | 88/100 (88 %) | 0.80 to 0.93 | 41/50 | 44/50 | 42/50 | 44/50 |
| 0.5 | 81/100 (81 %) | 0.72 to 0.87 | 81/100 (81 %) | 0.72 to 0.87 | 39/50 | 40/50 | 42/50 | 41/50 |
| 0.6 | 77/100 (77 %) | 0.68 to 0.84 | 81/100 (81 %) | 0.72 to 0.87 | 36/50 | 40/50 | 41/50 | 41/50 |
| 0.7 | 75/100 (75 %) | 0.66 to 0.82 | 77/100 (77 %) | 0.68 to 0.84 | 35/50 | 36/50 | 40/50 | 41/50 |
| 0.8 | 74/100 (74 %) | 0.65 to 0.82 | 76/100 (76 %) | 0.67 to 0.83 | 35/50 | 35/50 | 39/50 | 41/50 |
| 0.9 | 68/100 (68 %) | 0.58 to 0.76 | 73/100 (73 %) | 0.64 to 0.81 | 29/50 | 32/50 | 39/50 | 41/50 |

Caught at 0.5 by leak type: name 10/12, variant 5/10, partial 8/10, email 8/12, phone 10/12, iban 12/12, address 12/12, id 10/10, split 6/10.
False alarms at 0.5 by placeholder count: 4 to 6 18/22, 7 to 8 63/66, 11 to 15 0/12.
Latency per text: median 390 ms, p90 633 ms, max 2519 ms.
Calibration: ECE 0.466, Brier 0.468. Bins (score range, n, mean score, share leaking): 0.0-0.1 n=17 0.03/0.71; 0.1-0.2 n=2 0.12/0.00; 0.2-0.3 n=5 0.25/0.60; 0.3-0.4 n=5 0.34/0.40; 0.4-0.5 n=9 0.46/0.22; 0.5-0.6 n=4 0.54/1.00; 0.6-0.7 n=6 0.66/0.33; 0.7-0.8 n=2 0.75/0.50; 0.8-0.9 n=9 0.87/0.67; 0.9-1.0 n=141 0.99/0.48.
Texts truncated by Laya's window: 0.

## Laya (English), two-option choice

| Threshold | Caught | 95 % CI | False alarms | 95 % CI | Caught FR | Alarms FR | Caught EN | Alarms EN |
|---|---|---|---|---|---|---|---|---|
| 0.1 | 96/100 (96 %) | 0.90 to 0.98 | 99/100 (99 %) | 0.95 to 1.00 | 50/50 | 50/50 | 46/50 | 49/50 |
| 0.2 | 96/100 (96 %) | 0.90 to 0.98 | 97/100 (97 %) | 0.92 to 0.99 | 50/50 | 50/50 | 46/50 | 47/50 |
| 0.3 | 96/100 (96 %) | 0.90 to 0.98 | 97/100 (97 %) | 0.92 to 0.99 | 50/50 | 50/50 | 46/50 | 47/50 |
| 0.4 | 95/100 (95 %) | 0.89 to 0.98 | 95/100 (95 %) | 0.89 to 0.98 | 50/50 | 48/50 | 45/50 | 47/50 |
| 0.5 | 86/100 (86 %) | 0.78 to 0.91 | 82/100 (82 %) | 0.73 to 0.88 | 44/50 | 40/50 | 42/50 | 42/50 |
| 0.6 | 81/100 (81 %) | 0.72 to 0.87 | 75/100 (75 %) | 0.66 to 0.82 | 40/50 | 35/50 | 41/50 | 40/50 |
| 0.7 | 70/100 (70 %) | 0.60 to 0.78 | 67/100 (67 %) | 0.57 to 0.75 | 33/50 | 31/50 | 37/50 | 36/50 |
| 0.8 | 52/100 (52 %) | 0.42 to 0.62 | 49/100 (49 %) | 0.39 to 0.59 | 21/50 | 18/50 | 31/50 | 31/50 |
| 0.9 | 24/100 (24 %) | 0.17 to 0.33 | 25/100 (25 %) | 0.18 to 0.34 | 10/50 | 10/50 | 14/50 | 15/50 |

Caught at 0.5 by leak type: name 10/12, variant 6/10, partial 9/10, email 11/12, phone 11/12, iban 11/12, address 12/12, id 7/10, split 9/10.
False alarms at 0.5 by placeholder count: 4 to 6 12/22, 7 to 8 63/66, 11 to 15 7/12.
Latency per text: median 678 ms, p90 864 ms, max 1870 ms.
Calibration: ECE 0.278, Brier 0.346. Bins (score range, n, mean score, share leaking): 0.0-0.1 n=5 0.08/0.80; 0.1-0.2 n=2 0.10/0.00; 0.3-0.4 n=3 0.37/0.33; 0.4-0.5 n=22 0.46/0.41; 0.5-0.6 n=12 0.55/0.42; 0.6-0.7 n=19 0.65/0.58; 0.7-0.8 n=36 0.76/0.50; 0.8-0.9 n=52 0.85/0.54; 0.9-1.0 n=49 0.93/0.49.
Texts truncated by Laya's window: 0.

## Gliner2GuardRail

| Threshold | Caught | 95 % CI | False alarms | 95 % CI | Caught FR | Alarms FR | Caught EN | Alarms EN |
|---|---|---|---|---|---|---|---|---|
| 0.1 | 35/100 (35 %) | 0.26 to 0.45 | 13/100 (13 %) | 0.08 to 0.21 | 17/50 | 6/50 | 18/50 | 7/50 |
| 0.2 | 22/100 (22 %) | 0.15 to 0.31 | 10/100 (10 %) | 0.06 to 0.17 | 9/50 | 3/50 | 13/50 | 7/50 |
| 0.3 | 17/100 (17 %) | 0.11 to 0.26 | 10/100 (10 %) | 0.06 to 0.17 | 8/50 | 3/50 | 9/50 | 7/50 |
| 0.4 | 14/100 (14 %) | 0.09 to 0.22 | 6/100 (6 %) | 0.03 to 0.12 | 6/50 | 3/50 | 8/50 | 3/50 |
| 0.5 | 11/100 (11 %) | 0.06 to 0.19 | 3/100 (3 %) | 0.01 to 0.08 | 4/50 | 0/50 | 7/50 | 3/50 |
| 0.6 | 10/100 (10 %) | 0.06 to 0.17 | 3/100 (3 %) | 0.01 to 0.08 | 4/50 | 0/50 | 6/50 | 3/50 |
| 0.7 | 7/100 (7 %) | 0.03 to 0.14 | 3/100 (3 %) | 0.01 to 0.08 | 4/50 | 0/50 | 3/50 | 3/50 |
| 0.8 | 7/100 (7 %) | 0.03 to 0.14 | 1/100 (1 %) | 0.00 to 0.05 | 4/50 | 0/50 | 3/50 | 1/50 |
| 0.9 | 1/100 (1 %) | 0.00 to 0.05 | 0/100 (0 %) | 0.00 to 0.04 | 0/50 | 0/50 | 1/50 | 0/50 |

Caught at 0.5 by leak type: name 4/12, variant 0/10, partial 0/10, email 2/12, phone 0/12, iban 1/12, address 2/12, id 0/10, split 2/10.
False alarms at 0.5 by placeholder count: 4 to 6 0/22, 7 to 8 3/66, 11 to 15 0/12.
Latency per text: median 330 ms, p90 416 ms, max 660 ms.
Calibration: ECE 0.403, Brier 0.408. Bins (score range, n, mean score, share leaking): 0.0-0.1 n=152 0.02/0.43; 0.1-0.2 n=16 0.13/0.81; 0.2-0.3 n=5 0.24/1.00; 0.3-0.4 n=7 0.36/0.43; 0.4-0.5 n=6 0.47/0.50; 0.5-0.6 n=1 0.54/1.00; 0.6-0.7 n=3 0.65/1.00; 0.7-0.8 n=2 0.74/0.00; 0.8-0.9 n=7 0.86/0.86; 0.9-1.0 n=1 0.91/1.00.

## GLiNER2 spans, raw

| Threshold | Caught | 95 % CI | False alarms | 95 % CI | Caught FR | Alarms FR | Caught EN | Alarms EN |
|---|---|---|---|---|---|---|---|---|
| 0.1 | 100/100 (100 %) | 0.96 to 1.00 | 100/100 (100 %) | 0.96 to 1.00 | 50/50 | 50/50 | 50/50 | 50/50 |
| 0.2 | 100/100 (100 %) | 0.96 to 1.00 | 100/100 (100 %) | 0.96 to 1.00 | 50/50 | 50/50 | 50/50 | 50/50 |
| 0.3 | 100/100 (100 %) | 0.96 to 1.00 | 100/100 (100 %) | 0.96 to 1.00 | 50/50 | 50/50 | 50/50 | 50/50 |
| 0.4 | 100/100 (100 %) | 0.96 to 1.00 | 100/100 (100 %) | 0.96 to 1.00 | 50/50 | 50/50 | 50/50 | 50/50 |
| 0.5 | 100/100 (100 %) | 0.96 to 1.00 | 100/100 (100 %) | 0.96 to 1.00 | 50/50 | 50/50 | 50/50 | 50/50 |
| 0.6 | 100/100 (100 %) | 0.96 to 1.00 | 100/100 (100 %) | 0.96 to 1.00 | 50/50 | 50/50 | 50/50 | 50/50 |
| 0.7 | 99/100 (99 %) | 0.95 to 1.00 | 100/100 (100 %) | 0.96 to 1.00 | 50/50 | 50/50 | 49/50 | 50/50 |
| 0.8 | 99/100 (99 %) | 0.95 to 1.00 | 91/100 (91 %) | 0.84 to 0.95 | 50/50 | 49/50 | 49/50 | 42/50 |
| 0.9 | 89/100 (89 %) | 0.81 to 0.94 | 50/100 (50 %) | 0.40 to 0.60 | 46/50 | 24/50 | 43/50 | 26/50 |

Caught at 0.5 by leak type: name 12/12, variant 10/10, partial 10/10, email 12/12, phone 12/12, iban 12/12, address 12/12, id 10/10, split 10/10.
False alarms at 0.5 by placeholder count: 4 to 6 22/22, 7 to 8 66/66, 11 to 15 12/12.
Latency per text: median 402 ms, p90 528 ms, max 1082 ms.
Calibration: ECE 0.431, Brier 0.404. Bins (score range, n, mean score, share leaking): 0.6-0.7 n=1 0.64/1.00; 0.7-0.8 n=9 0.77/0.00; 0.8-0.9 n=51 0.86/0.20; 0.9-1.0 n=139 0.97/0.64.
At 0.5, 96 of the 100 leaks caught had a detection on the leaked value itself. Clean texts flagged: 100 with a detection touching a placeholder, 0 on other text.

## GLiNER2 spans, placeholders ignored

| Threshold | Caught | 95 % CI | False alarms | 95 % CI | Caught FR | Alarms FR | Caught EN | Alarms EN |
|---|---|---|---|---|---|---|---|---|
| 0.1 | 99/100 (99 %) | 0.95 to 1.00 | 79/100 (79 %) | 0.70 to 0.86 | 49/50 | 39/50 | 50/50 | 40/50 |
| 0.2 | 99/100 (99 %) | 0.95 to 1.00 | 76/100 (76 %) | 0.67 to 0.83 | 49/50 | 38/50 | 50/50 | 38/50 |
| 0.3 | 99/100 (99 %) | 0.95 to 1.00 | 63/100 (63 %) | 0.53 to 0.72 | 49/50 | 25/50 | 50/50 | 38/50 |
| 0.4 | 98/100 (98 %) | 0.93 to 0.99 | 54/100 (54 %) | 0.44 to 0.63 | 49/50 | 16/50 | 49/50 | 38/50 |
| 0.5 | 97/100 (97 %) | 0.92 to 0.99 | 49/100 (49 %) | 0.39 to 0.59 | 48/50 | 11/50 | 49/50 | 38/50 |
| 0.6 | 96/100 (96 %) | 0.90 to 0.98 | 35/100 (35 %) | 0.26 to 0.45 | 48/50 | 5/50 | 48/50 | 30/50 |
| 0.7 | 93/100 (93 %) | 0.86 to 0.97 | 27/100 (27 %) | 0.19 to 0.36 | 46/50 | 4/50 | 47/50 | 23/50 |
| 0.8 | 89/100 (89 %) | 0.81 to 0.94 | 15/100 (15 %) | 0.09 to 0.23 | 43/50 | 3/50 | 46/50 | 12/50 |
| 0.9 | 83/100 (83 %) | 0.74 to 0.89 | 3/100 (3 %) | 0.01 to 0.08 | 42/50 | 0/50 | 41/50 | 3/50 |

Caught at 0.5 by leak type: name 12/12, variant 10/10, partial 9/10, email 12/12, phone 12/12, iban 12/12, address 12/12, id 9/10, split 9/10.
False alarms at 0.5 by placeholder count: 4 to 6 14/22, 7 to 8 32/66, 11 to 15 3/12.
Latency per text: median 430 ms, p90 588 ms, max 751 ms.
Calibration: ECE 0.192, Brier 0.158. Bins (score range, n, mean score, share leaking): 0.0-0.1 n=22 0.00/0.05; 0.1-0.2 n=3 0.15/0.00; 0.2-0.3 n=13 0.26/0.00; 0.3-0.4 n=10 0.35/0.10; 0.4-0.5 n=6 0.42/0.17; 0.5-0.6 n=15 0.55/0.07; 0.6-0.7 n=11 0.66/0.27; 0.7-0.8 n=16 0.75/0.25; 0.8-0.9 n=18 0.84/0.33; 0.9-1.0 n=86 0.98/0.97.
At 0.5, 96 of the 97 leaks caught had a detection on the leaked value itself. Clean texts flagged: 22 with a detection touching a placeholder, 27 on other text.

## Combinations

| Rule | Caught | False alarms |
|---|---|---|
| GLiNER2 spans, placeholders ignored >= 0.9 OR Laya (English) >= 0.9 | 83/100 (83 %) | 14/100 (14 %) |
| GLiNER2 spans, placeholders ignored >= 0.9 OR Gliner2GuardRail >= 0.5 | 84/100 (84 %) | 6/100 (6 %) |
| GLiNER2 spans, placeholders ignored >= 0.5 AND Laya (English) >= 0.5 | 66/100 (66 %) | 29/100 (29 %) |
| GLiNER2 spans, placeholders ignored >= 0.7 AND Laya (English) >= 0.7 | 43/100 (43 %) | 11/100 (11 %) |
| Gliner2GuardRail >= 0.5 OR Laya (English) >= 0.9 | 17/100 (17 %) | 14/100 (14 %) |

## Paired test, each leak against its clean twin

| Guard | Pairs | Leak scored higher | Mean score gap | Twin flagged at 0.5 | Only the leak flagged at 0.5 |
|---|---|---|---|---|---|
| Laya (English) | 100 | 54.0 | +0.007 | 65 | 7 |
| Laya, placeholder hint | 100 | 40.0 | -0.005 | 85 | 2 |
| laya-multilingual | 100 | 48.5 | -0.028 | 81 | 5 |
| Laya (English), two-option choice | 100 | 50.5 | +0.001 | 86 | 3 |
| Gliner2GuardRail | 100 | 72.0 | +0.041 | 4 | 9 |
| GLiNER2 spans, raw | 100 | 87.0 | +0.068 | 100 | 0 |
| GLiNER2 spans, placeholders ignored | 100 | 97.5 | +0.460 | 51 | 46 |

Laya (English), leak scored higher than its twin, by type: name 8.0/12 (gap +0.03), variant 7.0/10 (gap +0.00), partial 5.0/10 (gap +0.00), email 6.0/12 (gap +0.01), phone 7.0/12 (gap -0.01), iban 7.0/12 (gap +0.01), address 6.0/12 (gap +0.00), id 5.0/10 (gap +0.00), split 3.0/10 (gap -0.00).

Laya, placeholder hint, leak scored higher than its twin, by type: name 4.0/12 (gap +0.02), variant 6.0/10 (gap +0.01), partial 3.0/10 (gap -0.00), email 5.0/12 (gap +0.01), phone 7.0/12 (gap +0.00), iban 4.0/12 (gap -0.04), address 5.0/12 (gap +0.00), id 3.0/10 (gap -0.02), split 3.0/10 (gap -0.02).

laya-multilingual, leak scored higher than its twin, by type: name 2.5/12 (gap -0.03), variant 3.5/10 (gap -0.01), partial 4.5/10 (gap +0.02), email 6.5/12 (gap -0.13), phone 6.0/12 (gap +0.01), iban 7.5/12 (gap +0.01), address 5.5/12 (gap -0.01), id 8.5/10 (gap +0.04), split 4.0/10 (gap -0.15).

Laya (English), two-option choice, leak scored higher than its twin, by type: name 6.0/12 (gap +0.02), variant 6.0/10 (gap +0.02), partial 7.0/10 (gap +0.02), email 4.0/12 (gap -0.03), phone 6.0/12 (gap -0.01), iban 6.0/12 (gap -0.01), address 6.5/12 (gap +0.02), id 3.0/10 (gap -0.00), split 6.0/10 (gap -0.02).

Gliner2GuardRail, leak scored higher than its twin, by type: name 11.0/12 (gap +0.23), variant 10.0/10 (gap +0.02), partial 9.0/10 (gap +0.01), email 10.0/12 (gap +0.07), phone 4.0/12 (gap -0.00), iban 2.0/12 (gap -0.08), address 12.0/12 (gap +0.12), id 7.0/10 (gap -0.03), split 7.0/10 (gap +0.00).

GLiNER2 spans, raw, leak scored higher than its twin, by type: name 12.0/12 (gap +0.06), variant 7.0/10 (gap +0.04), partial 6.0/10 (gap +0.02), email 12.0/12 (gap +0.12), phone 12.0/12 (gap +0.12), iban 12.0/12 (gap +0.08), address 8.0/12 (gap +0.05), id 10.0/10 (gap +0.03), split 8.0/10 (gap +0.07).

GLiNER2 spans, placeholders ignored, leak scored higher than its twin, by type: name 12.0/12 (gap +0.46), variant 10.0/10 (gap +0.60), partial 10.0/10 (gap +0.37), email 12.0/12 (gap +0.60), phone 12.0/12 (gap +0.41), iban 12.0/12 (gap +0.49), address 12.0/12 (gap +0.46), id 10.0/10 (gap +0.37), split 7.5/10 (gap +0.36).

## The documents before de-identification, every value in clear

| Guard | Documents | Flagged at 0.5 | Mean score |
|---|---|---|---|
| Laya (English) | 100 | 33 | 0.40 |
| Gliner2GuardRail | 100 | 23 | 0.23 |
| GLiNER2 spans, raw | 100 | 100 | 1.00 |
| laya-multilingual | 100 | 47 | 0.42 |
| Laya, placeholder hint | 100 | 27 | 0.35 |
| Laya (English), two-option choice | 100 | 50 | 0.53 |
| GLiNER2 spans, placeholders ignored | 100 | 100 | 1.00 |

## Run

```json
{
  "laya-en": {
    "load_and_warmup_s": 5.081877302378416,
    "warnings": [
      "laya: this checkpoint ships invalid temperatures or values outside [0.5, 5]; using choice:11+=0.10058280825614929 -> 0.5. Treat confidence from the affected entries as uncalibrated."
    ]
  },
  "machine": {
    "python": "3.13.15",
    "platform": "Linux-6.14.0-37-generic-x86_64-with-glibc2.41",
    "processor": "x86_64"
  },
  "gliner2-guard": {
    "load_and_warmup_s": 9.260362468659878,
    "warnings": []
  },
  "gliner2-spans": {
    "load_and_warmup_s": 10.029534913599491,
    "warnings": []
  },
  "laya-multi": {
    "load_and_warmup_s": 9.2636534338817,
    "warnings": []
  },
  "gliner2-spans-ph": {
    "load_and_warmup_s": 10.335399337112904,
    "warnings": []
  },
  "laya-en-hint": {
    "load_and_warmup_s": 1.8806332033127546,
    "warnings": [
      "laya: this checkpoint ships invalid temperatures or values outside [0.5, 5]; using choice:11+=0.10058280825614929 -> 0.5. Treat confidence from the affected entries as uncalibrated."
    ]
  },
  "laya-en-choice": {
    "load_and_warmup_s": 1.9597455961629748,
    "warnings": [
      "laya: this checkpoint ships invalid temperatures or values outside [0.5, 5]; using choice:11+=0.10058280825614929 -> 0.5. Treat confidence from the affected entries as uncalibrated."
    ]
  }
}
```
